# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact M12-FS Root Hardening & Founder Policy Adversarial Test Suite.

Verifies:
1. Phishing-Resistant WebAuthn Level 3 Step-Up (Founder Decision A).
2. Root Key Provenance & Ed25519 Proof-of-Possession (PoP).
3. Read-Only Deterministic Status Reconciliation.
4. Single-Owner Emergency Containment & Kill-Switch (Founder Decision B).
5. M-of-N High-Assurance Quorum Recovery (Founder Decision B).
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ec, ed25519
from cryptography.hazmat.primitives.serialization import (
    Encoding,
    PublicFormat,
)
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, update

from responsibleai.dashboard.app import app, limiter, settings
from responsibleai.db.engine import (
    authority_containment_records,
    authority_step_up_challenges,
    passkey_credentials,
    trust_fabric_principals,
    web_memberships,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.errors import (
    ALREADY_VOTED,
    PASSKEY_STEP_UP_REQUIRED,
    PROOF_OF_POSSESSION_INVALID,
    QUORUM_NOT_MET,
    RECOVERY_ALREADY_EXECUTED,
    RECOVERY_DIGEST_MISMATCH,
    SELF_APPROVAL_BLOCKED,
    UNAUTHORIZED_BOOTSTRAP_CALLER,
    WEBAUTHN_ASSERTION_INVALID,
    WEBAUTHN_CHALLENGE_EXPIRED,
    WEBAUTHN_CHALLENGE_REPLAY,
)
from responsibleai.enterprise.authority.service import (
    CustomerAuthorityService,
    compute_canonical_operation_digest,
    verify_root_proof_of_possession,
)
from responsibleai.enterprise.runtime import configure_enterprise, get_enterprise_engine
from responsibleai.enterprise.security.webauthn import b64url_decode, b64url_encode
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role
from tests.webauthn_fakes import assertion_blob


@pytest.fixture(autouse=True)
async def _configure_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    from responsibleai.db.engine import create_engine

    db_file = tmp_path / "m12fs_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["m12fs-admin-key"])
    monkeypatch.setattr(settings, "db_path", str(db_file))
    monkeypatch.setattr(settings, "database_url", db_url)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()

    engine = create_engine(db_url)
    await engine.init(auto_create_tables=True)
    configure_enterprise(engine)
    yield engine
    await engine.raw.dispose()


@pytest.fixture
async def api_client():
    from asgi_lifespan import LifespanManager

    async with LifespanManager(app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app),
            base_url="http://test",
            cookies={},
        ) as client:
            yield client


async def _create_test_owner(email: str = "founder@m12fs.com", org_slug: str = "m12fs-org"):
    engine = get_enterprise_engine()
    web_repo = WebIdentityRepository(engine)
    iam = EnterpriseIAM(engine)

    user_id, token = await web_repo.register("Founder M12FS", email, "FounderPassword123!@#")
    await web_repo.verify_email(token)
    org = await iam.create_workspace(
        actor_user_id=user_id,
        name="M12FS Test Org",
        slug=org_slug,
        kind="ORGANIZATION",
    )
    org_id = org["id"] if isinstance(org, dict) else org.id
    session_token, csrf_token = await web_repo.create_session(user_id, org_id=org_id)
    actor = Actor(
        actor_type="USER",
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=Role.OWNER,
        membership_status="ACTIVE",
    )
    return actor, user_id, org_id, session_token, csrf_token


async def _create_additional_admin(org_id: str, email: str, role: Role = Role.ADMIN):
    engine = get_enterprise_engine()
    web_repo = WebIdentityRepository(engine)
    user_id, token = await web_repo.register("Admin User", email, "AdminPassword123!@#")
    await web_repo.verify_email(token)

    async with engine.raw.begin() as conn:
        await conn.execute(
            web_memberships.insert().values(
                id=f"mem_{uuid.uuid4().hex[:12]}",
                user_id=user_id,
                org_id=org_id,
                role=role.value,
                status="ACTIVE",
                created_at=datetime.now(UTC).isoformat(),
            )
        )
    session_token, csrf_token = await web_repo.create_session(user_id, org_id=org_id)
    actor = Actor(
        actor_type="USER",
        actor_id=user_id,
        user_id=user_id,
        org_id=org_id,
        role=role,
        membership_status="ACTIVE",
    )
    return actor, user_id, session_token, csrf_token


def _register_fake_passkey(user_id: str, rp_id: str = "localhost"):
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    numbers = public_key.public_numbers()
    uncompressed = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
    cred_id = hashlib.sha256(
        numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
    ).digest()[:16]
    cred_id_b64 = b64url_encode(cred_id)
    pub_b64 = b64url_encode(uncompressed)
    return private_key, cred_id_b64, pub_b64


async def _create_containment_assertion(
    svc: CustomerAuthorityService,
    actor: Actor,
    org_id: str,
    target_type: str,
    target_id: str,
    containment_action: str,
    engine: Any | None = None,
) -> dict[str, Any]:
    if engine is None:
        engine = get_enterprise_engine()
    priv_key, cred_id_b64, pub_b64 = _register_fake_passkey(actor.user_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            passkey_credentials.insert().values(
                id=f"pk_{uuid.uuid4().hex[:12]}",
                user_id=actor.user_id,
                credential_id=cred_id_b64,
                public_key=pub_b64,
                sign_count=0,
                rp_id="localhost",
                transports_json="[]",
                aaguid="00000000-0000-0000-0000-000000000000",
                backup_eligible=1,
                backup_state=1,
                display_name="Test Passkey",
                status="ACTIVE",
                created_at=datetime.now(UTC).isoformat(),
            )
        )
    op_digest = compute_canonical_operation_digest(
        "EMERGENCY_CONTAINMENT",
        {
            "org_id": org_id,
            "target_type": target_type.upper(),
            "target_id": target_id,
            "containment_action": containment_action.upper(),
        },
    )
    ch_res = await svc.create_authority_stepup_challenge(
        actor, org_id=org_id, action="EMERGENCY_CONTAINMENT", operation_digest=op_digest
    )
    raw_challenge = b64url_decode(ch_res["challenge"])
    cdata, auth_data, sig = assertion_blob(
        rp_id="localhost",
        origin=ch_res["origin"],
        challenge=raw_challenge,
        private_key=priv_key,
        sign_count=1,
    )
    return {
        "credential_id": cred_id_b64,
        "client_data_json": cdata,
        "authenticator_data": auth_data,
        "signature": sig,
    }


# ==============================================================================
# 1. WebAuthn Step-Up Assurance Tests (Founder Decision A)
# ==============================================================================


@pytest.mark.asyncio
async def test_bootstrap_requires_stepup_when_configured():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    init_res = await svc.initiate_root_bootstrap(actor, org_id=org_id, require_passkey_stepup=True)
    assert init_res["require_passkey_stepup"] is True

    # Attempting complete_root_bootstrap without passkey assertion must fail closed
    with pytest.raises(Exception) as exc_info:
        await svc.complete_root_bootstrap(
            actor,
            org_id=org_id,
            token=init_res["token"],
            nonce=init_res["nonce"],
            root_public_key="ed25519_test_pubkey",
            scope_description="Test scope",
            purpose="Test purpose",
            allowed_action_types=["read", "write"],
            allowed_targets=["test/*"],
        )
    assert exc_info.value.code == PASSKEY_STEP_UP_REQUIRED


@pytest.mark.asyncio
async def test_bootstrap_with_valid_passkey_stepup_succeeds():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    # 1. Register active passkey credential
    priv_key, cred_id_b64, pub_b64 = _register_fake_passkey(user_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            passkey_credentials.insert().values(
                id=f"pk_{uuid.uuid4().hex[:12]}",
                user_id=user_id,
                credential_id=cred_id_b64,
                public_key=pub_b64,
                sign_count=0,
                rp_id="localhost",
                transports_json="[]",
                backup_eligible=1,
                backup_state=1,
                display_name="Test Passkey",
                status="ACTIVE",
                created_at=datetime.now(UTC).isoformat(),
            )
        )

    # 2. Initiate bootstrap with step-up required
    init_res = await svc.initiate_root_bootstrap(actor, org_id=org_id, require_passkey_stepup=True)

    root_key = "test_ed25519_root_public_key"
    token_hash = hashlib.sha256(init_res["token"].encode("utf-8")).hexdigest()
    op_digest = compute_canonical_operation_digest(
        "COMPLETE_ROOT_BOOTSTRAP",
        {
            "org_id": org_id,
            "nonce": init_res["nonce"],
            "token_hash": token_hash,
            "root_public_key": root_key,
        },
    )

    # 3. Create challenge
    ch_res = await svc.create_authority_stepup_challenge(
        actor, org_id=org_id, action="COMPLETE_ROOT_BOOTSTRAP", operation_digest=op_digest
    )
    raw_challenge = b64url_decode(ch_res["challenge"])

    # 4. Generate valid assertion
    cdata, auth_data, sig = assertion_blob(
        rp_id="localhost",
        origin=ch_res["origin"],
        challenge=raw_challenge,
        private_key=priv_key,
        sign_count=1,
    )
    assertion = {
        "credential_id": cred_id_b64,
        "client_data_json": cdata,
        "authenticator_data": auth_data,
        "signature": sig,
    }

    # 5. Complete bootstrap
    complete_res = await svc.complete_root_bootstrap(
        actor,
        org_id=org_id,
        token=init_res["token"],
        nonce=init_res["nonce"],
        root_public_key=root_key,
        scope_description="Step-up protected scope",
        purpose="Step-up root creation",
        allowed_action_types=["admin:*"],
        allowed_targets=["*"],
        webauthn_assertion=assertion,
    )

    assert complete_res["status"] == "BOOTSTRAPPED"
    assert complete_res["passkey_verified"] is True

    # 6. Check sign counter advanced
    async with engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(passkey_credentials.c.sign_count).where(
                    passkey_credentials.c.credential_id == cred_id_b64
                )
            )
        ).first()
        assert row[0] == 1


@pytest.mark.asyncio
async def test_stepup_rejects_replayed_challenge():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    priv_key, cred_id_b64, pub_b64 = _register_fake_passkey(user_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            passkey_credentials.insert().values(
                id=f"pk_{uuid.uuid4().hex[:12]}",
                user_id=user_id,
                credential_id=cred_id_b64,
                public_key=pub_b64,
                sign_count=0,
                rp_id="localhost",
                transports_json="[]",
                status="ACTIVE",
                created_at=datetime.now(UTC).isoformat(),
            )
        )

    init_res = await svc.initiate_root_bootstrap(actor, org_id=org_id, require_passkey_stepup=True)
    token_hash = hashlib.sha256(init_res["token"].encode("utf-8")).hexdigest()
    op_digest = compute_canonical_operation_digest(
        "COMPLETE_ROOT_BOOTSTRAP",
        {
            "org_id": org_id,
            "nonce": init_res["nonce"],
            "token_hash": token_hash,
            "root_public_key": "pubkey",
        },
    )

    ch_res = await svc.create_authority_stepup_challenge(
        actor, org_id=org_id, action="COMPLETE_ROOT_BOOTSTRAP", operation_digest=op_digest
    )
    raw_challenge = b64url_decode(ch_res["challenge"])

    cdata, auth_data, sig = assertion_blob(
        rp_id="localhost",
        origin=ch_res["origin"],
        challenge=raw_challenge,
        private_key=priv_key,
        sign_count=1,
    )
    assertion = {
        "credential_id": cred_id_b64,
        "client_data_json": cdata,
        "authenticator_data": auth_data,
        "signature": sig,
    }

    # Consume once
    await svc.complete_root_bootstrap(
        actor,
        org_id=org_id,
        token=init_res["token"],
        nonce=init_res["nonce"],
        root_public_key="pubkey",
        scope_description="First",
        purpose="First",
        allowed_action_types=["*"],
        allowed_targets=["*"],
        webauthn_assertion=assertion,
    )

    # Replay on another action or attempt -> challenge replay error
    async with engine.raw.connect() as conn:
        with pytest.raises(Exception) as exc_info:
            await svc._verify_webauthn_stepup_on_conn(
                conn,
                actor=actor,
                org_id=org_id,
                action="COMPLETE_ROOT_BOOTSTRAP",
                operation_digest=op_digest,
                assertion=assertion,
            )
        assert exc_info.value.code == WEBAUTHN_CHALLENGE_REPLAY


@pytest.mark.asyncio
async def test_stepup_rejects_expired_challenge():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    priv_key, cred_id_b64, pub_b64 = _register_fake_passkey(user_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            passkey_credentials.insert().values(
                id=f"pk_{uuid.uuid4().hex[:12]}",
                user_id=user_id,
                credential_id=cred_id_b64,
                public_key=pub_b64,
                sign_count=0,
                rp_id="localhost",
                transports_json="[]",
                status="ACTIVE",
                created_at=datetime.now(UTC).isoformat(),
            )
        )

    op_digest = "test_digest_123"
    ch_res = await svc.create_authority_stepup_challenge(
        actor,
        org_id=org_id,
        action="EMERGENCY_CONTAINMENT",
        operation_digest=op_digest,
        ttl_seconds=300,
    )

    # Fast forward challenge expiration in DB
    past_iso = (datetime.now(UTC) - timedelta(seconds=10)).isoformat()
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(authority_step_up_challenges)
            .where(authority_step_up_challenges.c.challenge_hash == ch_res["challenge_hash"])
            .values(expires_at=past_iso)
        )

    raw_challenge = b64url_decode(ch_res["challenge"])
    cdata, auth_data, sig = assertion_blob(
        rp_id="localhost",
        origin=ch_res["origin"],
        challenge=raw_challenge,
        private_key=priv_key,
        sign_count=1,
    )
    assertion = {
        "credential_id": cred_id_b64,
        "client_data_json": cdata,
        "authenticator_data": auth_data,
        "signature": sig,
    }

    async with engine.raw.connect() as conn:
        with pytest.raises(Exception) as exc_info:
            await svc._verify_webauthn_stepup_on_conn(
                conn,
                actor=actor,
                org_id=org_id,
                action="EMERGENCY_CONTAINMENT",
                operation_digest=op_digest,
                assertion=assertion,
            )
        assert exc_info.value.code == WEBAUTHN_CHALLENGE_EXPIRED


@pytest.mark.asyncio
async def test_stepup_rejects_digest_mismatch():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    priv_key, cred_id_b64, pub_b64 = _register_fake_passkey(user_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            passkey_credentials.insert().values(
                id=f"pk_{uuid.uuid4().hex[:12]}",
                user_id=user_id,
                credential_id=cred_id_b64,
                public_key=pub_b64,
                sign_count=0,
                rp_id="localhost",
                transports_json="[]",
                status="ACTIVE",
                created_at=datetime.now(UTC).isoformat(),
            )
        )

    ch_res = await svc.create_authority_stepup_challenge(
        actor, org_id=org_id, action="EMERGENCY_CONTAINMENT", operation_digest="digest_A"
    )
    raw_challenge = b64url_decode(ch_res["challenge"])
    cdata, auth_data, sig = assertion_blob(
        rp_id="localhost",
        origin=ch_res["origin"],
        challenge=raw_challenge,
        private_key=priv_key,
        sign_count=1,
    )
    assertion = {
        "credential_id": cred_id_b64,
        "client_data_json": cdata,
        "authenticator_data": auth_data,
        "signature": sig,
    }

    # Attempt to present assertion for digest_B
    async with engine.raw.connect() as conn:
        with pytest.raises(Exception) as exc_info:
            await svc._verify_webauthn_stepup_on_conn(
                conn,
                actor=actor,
                org_id=org_id,
                action="EMERGENCY_CONTAINMENT",
                operation_digest="digest_B",
                assertion=assertion,
            )
        assert exc_info.value.code == WEBAUTHN_ASSERTION_INVALID


# ==============================================================================
# 2. Root Key Provenance & Proof-of-Possession (PoP) Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_root_proof_of_possession_valid_and_forged():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    # 1. Generate Ed25519 root authority key pair
    ed_priv = ed25519.Ed25519PrivateKey.generate()
    ed_pub = ed_priv.public_key()
    pub_bytes = ed_pub.public_bytes(Encoding.Raw, PublicFormat.Raw)
    pub_hex = pub_bytes.hex()

    init_res = await svc.initiate_root_bootstrap(actor, org_id=org_id)
    token_hash = hashlib.sha256(init_res["token"].encode("utf-8")).hexdigest()
    nonce = init_res["nonce"]

    # Valid PoP message signature
    message = f"WP_ROOT_POP:{org_id}:{nonce}:{token_hash}".encode()
    valid_sig = b64url_encode(ed_priv.sign(message))

    # Test verify_root_proof_of_possession directly
    verify_root_proof_of_possession(org_id, nonce, token_hash, pub_hex, valid_sig)

    # Adversarial: Corrupted / forged signature
    forged_sig = b64url_encode(b"\x00" * 64)
    with pytest.raises(Exception) as exc_info:
        verify_root_proof_of_possession(org_id, nonce, token_hash, pub_hex, forged_sig)
    assert exc_info.value.code == PROOF_OF_POSSESSION_INVALID

    # Adversarial: Signature over tampered nonce
    tampered_msg = f"WP_ROOT_POP:{org_id}:tampered_nonce:{token_hash}".encode()
    tampered_sig = b64url_encode(ed_priv.sign(tampered_msg))
    with pytest.raises(Exception) as exc_info2:
        verify_root_proof_of_possession(org_id, nonce, token_hash, pub_hex, tampered_sig)
    assert exc_info2.value.code == PROOF_OF_POSSESSION_INVALID

    # Test complete_root_bootstrap with valid root_signature
    complete_res = await svc.complete_root_bootstrap(
        actor,
        org_id=org_id,
        token=init_res["token"],
        nonce=nonce,
        root_public_key=pub_hex,
        scope_description="PoP test scope",
        purpose="PoP root establishment",
        allowed_action_types=["*"],
        allowed_targets=["*"],
        root_signature=valid_sig,
    )
    assert complete_res["status"] == "BOOTSTRAPPED"
    assert complete_res["proof_of_possession_verified"] is True


# ==============================================================================
# 3. Read-Only Deterministic Status Reconciliation Tests
# ==============================================================================


@pytest.mark.asyncio
async def test_reconcile_bootstrap_status_deterministic():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    # Non-existent nonce
    res_nf = await svc.reconcile_bootstrap_status(
        actor, org_id=org_id, token="fake_token", nonce="fake_nonce"
    )
    assert res_nf["status"] == "NOT_FOUND"

    # Pending ceremony
    init_res = await svc.initiate_root_bootstrap(actor, org_id=org_id)
    res_pending = await svc.reconcile_bootstrap_status(
        actor, org_id=org_id, token=init_res["token"], nonce=init_res["nonce"]
    )
    assert res_pending["status"] == "PENDING_COMPLETION"

    # Token mismatch
    res_mismatch = await svc.reconcile_bootstrap_status(
        actor, org_id=org_id, token="wrong_token", nonce=init_res["nonce"]
    )
    assert res_mismatch["status"] == "TOKEN_MISMATCH"

    # Complete ceremony -> verify COMMITTED status
    comp = await svc.complete_root_bootstrap(
        actor,
        org_id=org_id,
        token=init_res["token"],
        nonce=init_res["nonce"],
        root_public_key="some_key",
        scope_description="Scope",
        purpose="Purpose",
        allowed_action_types=["read"],
        allowed_targets=["*"],
    )
    res_committed = await svc.reconcile_bootstrap_status(
        actor, org_id=org_id, token=init_res["token"], nonce=init_res["nonce"]
    )
    assert res_committed["status"] == "COMMITTED"
    assert res_committed["root_id"] == comp["root_id"]
    assert res_committed["revocation_epoch"] == comp["epoch"]


# ==============================================================================
# 4. Emergency Containment & Kill-Switch Tests (Founder Decision B)
# ==============================================================================


@pytest.mark.asyncio
async def test_emergency_agent_containment_quarantines_and_bumps_epoch():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    # Bootstrap root and register agent
    init_res = await svc.initiate_root_bootstrap(actor, org_id=org_id)
    await svc.complete_root_bootstrap(
        actor,
        org_id=org_id,
        token=init_res["token"],
        nonce=init_res["nonce"],
        root_public_key="key",
        scope_description="Scope",
        purpose="Purpose",
        allowed_action_types=["read", "write"],
        allowed_targets=["*"],
    )
    agent_res = await svc.register_agent(actor, org_id=org_id, name="Malfunctioning Agent")
    agent_id = agent_res["agent_id"]

    # Delegate authority to agent
    await svc.delegate_to_agent(
        actor,
        org_id=org_id,
        agent_id=agent_id,
        granted_action_types=["read"],
        allowed_targets=["*"],
        purpose="Read tasks",
    )

    epochs = RevocationEpochRepository(engine)
    epoch_before = (await epochs.current(org_id)).epoch

    # Single-owner emergency containment with required passkey step-up
    assertion = await _create_containment_assertion(
        svc, actor, org_id, "AGENT", agent_id, "QUARANTINE", engine
    )
    cnt_res = await svc.execute_emergency_containment(
        actor,
        org_id=org_id,
        target_type="AGENT",
        target_id=agent_id,
        containment_action="QUARANTINE",
        reason="Agent behaving maliciously",
        webauthn_assertion=assertion,
    )

    assert cnt_res["status"] == "CONTAINED"
    assert cnt_res["revocation_epoch"] > epoch_before

    # Verify agent principal is QUARANTINED
    async with engine.raw.connect() as conn:
        agent_row = (
            await conn.execute(
                select(trust_fabric_principals.c.lifecycle_state).where(
                    trust_fabric_principals.c.id == agent_id
                )
            )
        ).first()
        assert agent_row[0] == "QUARANTINED"

        # Verify containment record created
        cnt_row = (
            await conn.execute(
                select(authority_containment_records).where(
                    authority_containment_records.c.id == cnt_res["containment_id"]
                )
            )
        ).first()
        assert cnt_row is not None
        assert cnt_row.target_id == agent_id


@pytest.mark.asyncio
async def test_emergency_organization_lockdown():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    init_res = await svc.initiate_root_bootstrap(actor, org_id=org_id)
    await svc.complete_root_bootstrap(
        actor,
        org_id=org_id,
        token=init_res["token"],
        nonce=init_res["nonce"],
        root_public_key="key",
        scope_description="Scope",
        purpose="Purpose",
        allowed_action_types=["*"],
        allowed_targets=["*"],
    )

    # Trigger lockdown with required passkey step-up
    assertion = await _create_containment_assertion(
        svc, actor, org_id, "ORGANIZATION", org_id, "LOCKDOWN", engine
    )
    lock_res = await svc.execute_emergency_containment(
        actor,
        org_id=org_id,
        target_type="ORGANIZATION",
        target_id=org_id,
        containment_action="LOCKDOWN",
        reason="Suspected intrusion",
        webauthn_assertion=assertion,
    )
    assert lock_res["status"] == "CONTAINED"

    # Status check must report no active authority
    status = await svc.get_authority_status(actor, org_id=org_id)
    assert status["has_active_authority"] is False


@pytest.mark.asyncio
async def test_containment_rejects_unauthorized_caller():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    # Caller with VIEWER role
    viewer = Actor(
        actor_type="USER",
        actor_id="viewer_1",
        user_id="viewer_1",
        org_id=org_id,
        role=Role.VIEWER,
        membership_status="ACTIVE",
    )

    with pytest.raises(Exception) as exc_info:
        await svc.execute_emergency_containment(
            viewer,
            org_id=org_id,
            target_type="ORGANIZATION",
            target_id=org_id,
            containment_action="LOCKDOWN",
            reason="Unauthorized attempt",
        )
    assert exc_info.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER


# ==============================================================================
# 5. M-of-N Quorum Recovery Tests (Founder Decision B)
# ==============================================================================


@pytest.mark.asyncio
async def test_quorum_recovery_full_lifecycle_2_of_3():
    owner, owner_id, org_id, _, _ = await _create_test_owner()
    admin_2, admin_2_id, _, _ = await _create_additional_admin(org_id, "admin2@m12fs.com")
    admin_3, admin_3_id, _, _ = await _create_additional_admin(org_id, "admin3@m12fs.com")

    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    # Establish initial root
    init_res = await svc.initiate_root_bootstrap(owner, org_id=org_id)
    comp = await svc.complete_root_bootstrap(
        owner,
        org_id=org_id,
        token=init_res["token"],
        nonce=init_res["nonce"],
        root_public_key="initial_key",
        scope_description="Scope",
        purpose="Purpose",
        allowed_action_types=["*"],
        allowed_targets=["*"],
    )
    initial_root_id = comp["root_id"]

    # 1. Admin 2 creates a 2-of-3 recovery request
    proposed = {
        "new_owner_user_id": admin_2_id,
        "new_root_public_key": "recovered_root_public_key",
        "scope_description": "Recovered Scope",
        "purpose": "Disaster Recovery",
        "allowed_action_types": ["*"],
        "allowed_targets": ["*"],
    }
    req_res = await svc.create_recovery_request(
        admin_2,
        org_id=org_id,
        request_type="ROOT_RECOVERY",
        target_root_id=initial_root_id,
        proposed_parameters=proposed,
        required_quorum_m=2,
        eligible_quorum_n=3,
    )
    request_id = req_res["request_id"]
    action_digest = req_res["action_digest"]

    # 2. Anti-Self-Approval: Admin 2 (requester) cannot approve their own request
    with pytest.raises(Exception) as exc_self:
        await svc.vote_recovery_request(
            admin_2,
            org_id=org_id,
            request_id=request_id,
            decision="APPROVE",
            action_digest=action_digest,
        )
    assert exc_self.value.code == SELF_APPROVAL_BLOCKED

    # 3. Execution before quorum fails
    with pytest.raises(Exception) as exc_q:
        await svc.execute_recovery_request(
            owner, org_id=org_id, request_id=request_id, action_digest=action_digest
        )
    assert exc_q.value.code == QUORUM_NOT_MET

    # 4. Owner approves (Approval #1)
    v1 = await svc.vote_recovery_request(
        owner,
        org_id=org_id,
        request_id=request_id,
        decision="APPROVE",
        action_digest=action_digest,
    )
    assert v1["current_approvals"] == 1

    # 5. Duplicate vote rejected
    with pytest.raises(Exception) as exc_dup:
        await svc.vote_recovery_request(
            owner,
            org_id=org_id,
            request_id=request_id,
            decision="APPROVE",
            action_digest=action_digest,
        )
    assert exc_dup.value.code == ALREADY_VOTED

    # 6. Admin 3 approves (Approval #2 -> Quorum satisfied)
    v2 = await svc.vote_recovery_request(
        admin_3,
        org_id=org_id,
        request_id=request_id,
        decision="APPROVE",
        action_digest=action_digest,
    )
    assert v2["current_approvals"] == 2

    # 7. Execute recovery
    exec_res = await svc.execute_recovery_request(
        admin_2,
        org_id=org_id,
        request_id=request_id,
        action_digest=action_digest,
    )
    assert exec_res["status"] == "EXECUTED"
    assert exec_res["approving_voters_count"] == 2

    # 8. Re-execution rejected
    with pytest.raises(Exception) as exc_reexec:
        await svc.execute_recovery_request(
            admin_2,
            org_id=org_id,
            request_id=request_id,
            action_digest=action_digest,
        )
    assert exc_reexec.value.code == RECOVERY_ALREADY_EXECUTED

    # 9. Status check confirms new recovered root is active
    status = await svc.get_authority_status(admin_2, org_id=org_id)
    assert status["has_active_authority"] is True
    assert status["root_authority"]["root_id"] != initial_root_id
    assert status["root_authority"]["subject_id"] == admin_2_id


@pytest.mark.asyncio
async def test_quorum_pre_execution_deactivation_check():
    """Verify that if an approving voter is deactivated before execution, quorum fails."""
    owner, owner_id, org_id, _, _ = await _create_test_owner()
    admin_2, admin_2_id, _, _ = await _create_additional_admin(org_id, "adm2@m12fs.com")
    admin_3, admin_3_id, _, _ = await _create_additional_admin(org_id, "adm3@m12fs.com")

    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    init_res = await svc.initiate_root_bootstrap(owner, org_id=org_id)
    comp = await svc.complete_root_bootstrap(
        owner,
        org_id=org_id,
        token=init_res["token"],
        nonce=init_res["nonce"],
        root_public_key="k",
        scope_description="S",
        purpose="P",
        allowed_action_types=["*"],
        allowed_targets=["*"],
    )

    req_res = await svc.create_recovery_request(
        admin_2,
        org_id=org_id,
        request_type="KEY_ROTATION",
        target_root_id=comp["root_id"],
        proposed_parameters={"new_root_public_key": "rotated_key"},
        required_quorum_m=2,
        eligible_quorum_n=3,
    )
    req_id = req_res["request_id"]
    action_digest = req_res["action_digest"]

    # Vote 1: Owner
    await svc.vote_recovery_request(
        owner, org_id=org_id, request_id=req_id, decision="APPROVE", action_digest=action_digest
    )
    # Vote 2: Admin 3
    await svc.vote_recovery_request(
        admin_3, org_id=org_id, request_id=req_id, decision="APPROVE", action_digest=action_digest
    )

    # Malicious/compromised admin 3 membership is revoked before execution
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(web_memberships.c.user_id == admin_3_id)
            .values(status="REVOKED")
        )

    # Pre-execution check must catch revoked admin and reject execution
    with pytest.raises(Exception) as exc_info:
        await svc.execute_recovery_request(
            admin_2, org_id=org_id, request_id=req_id, action_digest=action_digest
        )
    assert exc_info.value.code == QUORUM_NOT_MET


@pytest.mark.asyncio
async def test_recovery_request_digest_mismatch_rejected():
    owner, owner_id, org_id, _, _ = await _create_test_owner()
    admin_2, admin_2_id, _, _ = await _create_additional_admin(org_id, "ad2@m12fs.com")

    engine = get_enterprise_engine()
    svc = CustomerAuthorityService(engine)

    req_res = await svc.create_recovery_request(
        admin_2,
        org_id=org_id,
        request_type="KEY_ROTATION",
        target_root_id="root_1",
        proposed_parameters={"new_root_public_key": "rotated_key"},
    )
    req_id = req_res["request_id"]

    # Tampered action digest on vote
    with pytest.raises(Exception) as exc_vote:
        await svc.vote_recovery_request(
            owner,
            org_id=org_id,
            request_id=req_id,
            decision="APPROVE",
            action_digest="tampered_digest",
        )
    assert exc_vote.value.code == RECOVERY_DIGEST_MISMATCH
