# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial security qualification of customer root authority bootstrap on real PostgreSQL."""

from __future__ import annotations

import base64
import hashlib
import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from sqlalchemy import insert, update

from responsibleai.db.engine import (
    authority_recovery_requests,
    authority_step_up_challenges,
    create_engine,
    trust_fabric_principals,
    web_users,
)
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.enterprise.authority.errors import (
    BOOTSTRAP_TOKEN_REPLAY,
    PASSKEY_STEP_UP_REQUIRED,
    ROOT_ALREADY_EXISTS,
    UNAUTHORIZED_BOOTSTRAP_CALLER,
    WEBAUTHN_ASSERTION_INVALID,
    WEBAUTHN_CHALLENGE_EXPIRED,
)
from responsibleai.enterprise.authority.service import (
    CustomerAuthorityService,
    compute_canonical_operation_digest,
)
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role
from tests.pg_test_url import isolated_pg_url


def _gen_ed25519():
    priv = Ed25519PrivateKey.generate()
    pub_bytes = priv.public_key().public_bytes_raw()
    return priv, pub_bytes.hex(), pub_bytes


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


@pytest.mark.asyncio
async def test_root_bootstrap_disabled_and_suspended_accounts_rejected():
    """Verify disabled or suspended user accounts are strictly rejected from root bootstrap."""
    async for url in isolated_pg_url("wp_titan_disabled_user"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]

        # 1. Registered user who is disabled (disabled=1)
        uid, token = await web_repo.register(
            "Disabled Owner", f"disabled.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Disabled Org {suffix}",
            slug=f"disabled-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_iso = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Disabled Owner",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )
            # Disable the account
            await conn.execute(update(web_users).where(web_users.c.id == uid).values(disabled=1))

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # Initiate fails closed
        with pytest.raises(EnterpriseError) as exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER

        # Re-enable but mark verification_status as SUSPENDED
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(web_users)
                .where(web_users.c.id == uid)
                .values(disabled=0, verification_status="SUSPENDED")
            )

        with pytest.raises(EnterpriseError) as susp_exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert susp_exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER

        # Mark verification_status as REJECTED
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(web_users)
                .where(web_users.c.id == uid)
                .values(verification_status="REJECTED")
            )

        with pytest.raises(EnterpriseError) as rej_exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert rej_exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER


@pytest.mark.asyncio
async def test_root_bootstrap_revoked_principal_rejected():
    """Verify an owner whose principal in trust_fabric_principals is REVOKED or SUSPENDED fails closed."""
    async for url in isolated_pg_url("wp_titan_revoked_principal"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "Revoked Principal", f"revoked.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Revoked Org {suffix}",
            slug=f"revoked-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_iso = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Revoked Principal",
                    lifecycle_state="REVOKED",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # Initiate fails closed because principal is REVOKED
        with pytest.raises(EnterpriseError) as exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER

        # Switch to SUSPENDED
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_principals)
                .where(trust_fabric_principals.c.id == uid)
                .values(lifecycle_state="SUSPENDED")
            )

        with pytest.raises(EnterpriseError) as susp_exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert susp_exc.value.code == UNAUTHORIZED_BOOTSTRAP_CALLER


@pytest.mark.asyncio
async def test_root_bootstrap_pending_quorum_recovery_blocks_out_of_band_bootstrap():
    """Verify an active quorum recovery request prevents unilateral out-of-band root bootstrap."""
    async for url in isolated_pg_url("wp_titan_pending_recovery"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "Recovery Owner", f"recovery.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Recovery Org {suffix}",
            slug=f"recovery-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_dt = datetime.now(UTC)
        now_iso = now_dt.isoformat()
        expires_at = (now_dt + timedelta(hours=24)).isoformat()

        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Recovery Owner",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )
            # Active quorum recovery request in progress
            await conn.execute(
                authority_recovery_requests.insert().values(
                    id=f"wp_rec_{uuid.uuid4().hex}",
                    org_id=org_id,
                    request_type="ROOT_RECOVERY",
                    target_root_id="old_root_id",
                    requester_user_id=uid,
                    proposed_parameters_json=json.dumps({"reason": "Key rotation"}),
                    action_digest="test_digest",
                    required_quorum_m=2,
                    eligible_quorum_n=3,
                    status="PENDING",
                    expires_at=expires_at,
                    executed_at=None,
                    executed_by_user_id=None,
                    created_at=now_iso,
                )
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # Unilateral initiate bootstrap is rejected because quorum recovery is pending
        with pytest.raises(EnterpriseError) as exc:
            await svc.initiate_root_bootstrap(actor, org_id=org_id)
        assert exc.value.code == ROOT_ALREADY_EXISTS


@pytest.mark.asyncio
async def test_root_bootstrap_webauthn_adversarial_paths():
    """Verify expired step-up, challenge replay, and operation digest mismatches are rejected."""
    async for url in isolated_pg_url("wp_titan_webauthn_adv"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "WebAuthn Owner", f"webauthn.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"WebAuthn Org {suffix}",
            slug=f"webauthn-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_dt = datetime.now(UTC)
        now_iso = now_dt.isoformat()

        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="WebAuthn Owner",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # 1. Initiate with passkey step-up required
        init_res = await svc.initiate_root_bootstrap(
            actor, org_id=org_id, require_identity_assurance=True, require_passkey_stepup=True
        )
        boot_token = init_res["token"]
        boot_nonce = init_res["nonce"]
        token_hash = hashlib.sha256(boot_token.encode()).hexdigest()

        priv, pub_hex, _ = _gen_ed25519()

        # Omitting webauthn_assertion fails with PASSKEY_STEP_UP_REQUIRED
        with pytest.raises(EnterpriseError) as no_wa_exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=boot_token,
                nonce=boot_nonce,
                root_public_key=pub_hex,
                scope_description="Scope",
                purpose="Testing",
                allowed_action_types=["test.read"],
                allowed_targets=["test:target"],
            )
        assert no_wa_exc.value.code == PASSKEY_STEP_UP_REQUIRED

        # 2. Expired challenge rejection
        correct_digest = compute_canonical_operation_digest(
            "COMPLETE_ROOT_BOOTSTRAP",
            {
                "org_id": org_id,
                "nonce": boot_nonce,
                "token_hash": token_hash,
                "root_public_key": pub_hex,
            },
        )

        ch_exp = await svc.create_authority_stepup_challenge(
            actor,
            org_id=org_id,
            action="COMPLETE_ROOT_BOOTSTRAP",
            operation_digest=correct_digest,
            ttl_seconds=300,
        )
        past_iso = (datetime.now(UTC) - timedelta(seconds=60)).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(authority_step_up_challenges)
                .where(authority_step_up_challenges.c.challenge_hash == ch_exp["challenge_hash"])
                .values(expires_at=past_iso)
            )

        fake_assertion = {
            "credential_id": "fake_cred_id",
            "client_data_json": _b64url(
                json.dumps(
                    {
                        "type": "webauthn.get",
                        "challenge": ch_exp["challenge"],
                        "origin": ch_exp["origin"],
                    }
                ).encode()
            ),
            "authenticator_data": _b64url(b"fake_auth_data"),
            "signature": _b64url(b"fake_sig"),
        }

        with pytest.raises(EnterpriseError) as exp_exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=boot_token,
                nonce=boot_nonce,
                root_public_key=pub_hex,
                scope_description="Scope",
                purpose="Testing",
                allowed_action_types=["test.read"],
                allowed_targets=["test:target"],
                webauthn_assertion=fake_assertion,
            )
        assert exp_exc.value.code == WEBAUTHN_CHALLENGE_EXPIRED

        # 3. Digest mismatch rejection
        ch_mm = await svc.create_authority_stepup_challenge(
            actor,
            org_id=org_id,
            action="COMPLETE_ROOT_BOOTSTRAP",
            operation_digest="wrong_digest_for_another_operation",
            ttl_seconds=300,
        )

        mismatched_assertion = {
            "credential_id": "fake_cred_id",
            "client_data_json": _b64url(
                json.dumps(
                    {
                        "type": "webauthn.get",
                        "challenge": ch_mm["challenge"],
                        "origin": ch_mm["origin"],
                    }
                ).encode()
            ),
            "authenticator_data": _b64url(b"fake_auth_data"),
            "signature": _b64url(b"fake_sig"),
        }

        with pytest.raises(EnterpriseError) as mm_exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=boot_token,
                nonce=boot_nonce,
                root_public_key=pub_hex,
                scope_description="Scope",
                purpose="Testing",
                allowed_action_types=["test.read"],
                allowed_targets=["test:target"],
                webauthn_assertion=mismatched_assertion,
            )
        assert mm_exc.value.code == WEBAUTHN_ASSERTION_INVALID


@pytest.mark.asyncio
async def test_root_bootstrap_concurrent_race_serializes_cleanly():
    """Verify concurrent complete_root_bootstrap attempts serialize safely with only one winner."""
    async for url in isolated_pg_url("wp_titan_concurrent_boot"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        engine = create_engine(url)

        web_repo = WebIdentityRepository(engine)
        iam = EnterpriseIAM(engine)
        svc = CustomerAuthorityService(engine)

        suffix = uuid.uuid4().hex[:8]
        uid, token = await web_repo.register(
            "Race Owner", f"race.{suffix}@example.com", "Password123!@#"
        )
        await web_repo.verify_email(token)
        org = await iam.create_workspace(
            actor_user_id=uid,
            name=f"Race Org {suffix}",
            slug=f"race-org-{suffix}",
            kind="ORGANIZATION",
        )
        org_id = org["id"] if isinstance(org, dict) else org.id

        now_iso = datetime.now(UTC).isoformat()
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(trust_fabric_principals).values(
                    id=uid,
                    org_id=org_id,
                    principal_type="HUMAN",
                    display_name="Race Owner",
                    lifecycle_state="ACTIVE",
                    created_at=now_iso,
                    updated_at=now_iso,
                )
            )

        actor = Actor(
            actor_type="USER",
            actor_id=uid,
            user_id=uid,
            org_id=org_id,
            role=Role.OWNER,
            membership_status="ACTIVE",
        )

        # Two distinct initiation ceremonies for Org
        init1 = await svc.initiate_root_bootstrap(
            actor, org_id=org_id, require_identity_assurance=True
        )
        priv1, pub1, _ = _gen_ed25519()
        pop1 = _b64url(
            priv1.sign(
                f"WP_ROOT_POP:{org_id}:{init1['nonce']}:{hashlib.sha256(init1['token'].encode()).hexdigest()}".encode()
            )
        )

        # Complete first bootstrap
        res1 = await svc.complete_root_bootstrap(
            actor,
            org_id=org_id,
            token=init1["token"],
            nonce=init1["nonce"],
            root_public_key=pub1,
            root_signature=pop1,
            scope_description="Root 1",
            purpose="Race testing",
            allowed_action_types=["test.action"],
            allowed_targets=["test:target"],
        )
        assert res1["status"] == "BOOTSTRAPPED"

        # Subsequent complete attempt fails closed with ROOT_ALREADY_EXISTS
        priv2, pub2, _ = _gen_ed25519()
        pop2 = _b64url(
            priv2.sign(
                f"WP_ROOT_POP:{org_id}:{init1['nonce']}:{hashlib.sha256(init1['token'].encode()).hexdigest()}".encode()
            )
        )

        with pytest.raises(EnterpriseError) as race_exc:
            await svc.complete_root_bootstrap(
                actor,
                org_id=org_id,
                token=init1["token"],
                nonce=init1["nonce"],
                root_public_key=pub2,
                root_signature=pop2,
                scope_description="Root 2",
                purpose="Race testing 2",
                allowed_action_types=["test.action"],
                allowed_targets=["test:target"],
            )
        assert race_exc.value.code in {ROOT_ALREADY_EXISTS, BOOTSTRAP_TOKEN_REPLAY}
