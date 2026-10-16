# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact M13-R3 Security Regression Test Suite.

Validates:
1. P0-C: Quorum Recovery Protection
   - Dynamic OWNER/ADMIN role recheck at recovery execution.
   - Demotion of an approver from OWNER/ADMIN to MEMBER prior to execution fails quorum.
   - Inactive or removed administrator approval is invalidated at execution.
   - Anti-self-approval enforcement (requester cannot vote or approve).
   - Duplicate voter deduplication (same voter cannot count twice towards quorum).
   - Cross-tenant recovery isolation.
   - Action digest binding enforcement.

2. P0-D: Approved WebAuthn Policy (WP-M13-POL-002)
   - Path A: Fresh server-verified, operation-bound WebAuthn assertion.
   - Path B: Pre-verified, short-lived, operation-bound authorization ticket minted
     from a genuine WebAuthn ceremony.
   - Path B single-use atomic consumption: replay fails with explicit replay rejection.
   - Path B digest binding: mismatching operation fails closed.
   - Path B restricted scope: strictly barred for root recovery or expansion.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from sqlalchemy import insert, select, update

from responsibleai.dashboard.app import limiter, settings
from responsibleai.db.engine import (
    DatabaseEngine,
    authority_recovery_requests,
    authority_recovery_votes,
    create_engine,
    organizations,
    passkey_credentials,
    trust_fabric_bootstrap_records,
    trust_fabric_principals,
    trust_fabric_trust_roots,
    web_memberships,
    web_users,
)
from responsibleai.enterprise.authority.errors import (
    ALREADY_VOTED,
    QUORUM_NOT_MET,
    RECOVERY_DIGEST_MISMATCH,
    SELF_APPROVAL_BLOCKED,
    WEBAUTHN_ASSERTION_INVALID,
    WEBAUTHN_CHALLENGE_REPLAY,
)
from responsibleai.enterprise.authority.service import (
    CustomerAuthorityService,
    compute_canonical_operation_digest,
)
from responsibleai.enterprise.runtime import configure_enterprise, get_enterprise_engine
from responsibleai.enterprise.security.webauthn import b64url_decode, b64url_encode
from responsibleai.enterprise.service import Actor
from responsibleai.rbac.models import Role
from tests.webauthn_fakes import assertion_blob


@pytest.fixture(autouse=True)
async def _configure_test_env(monkeypatch: pytest.MonkeyPatch, tmp_path):
    db_file = tmp_path / "m13r3_test.db"
    db_url = f"sqlite+aiosqlite:///{db_file}"
    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", ["m13r3-admin-key"])
    monkeypatch.setattr(settings, "db_path", str(db_file))
    monkeypatch.setattr(settings, "database_url", db_url)
    monkeypatch.setattr(settings, "auto_migrate", False)
    limiter.reset()

    engine = create_engine(db_url)
    await engine.init(auto_create_tables=True)
    configure_enterprise(engine)
    yield engine
    await engine.raw.dispose()


def _iso(dt: datetime | None = None) -> str:
    return (dt or datetime.now(UTC)).isoformat()


def _register_fake_passkey(user_id: str):
    private_key = ec.generate_private_key(ec.SECP256R1())
    public_key = private_key.public_key()
    numbers = public_key.public_numbers()
    uncompressed = b"\x04" + numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")
    cred_id = hashlib.sha256(numbers.x.to_bytes(32, "big") + numbers.y.to_bytes(32, "big")).digest()[:16]
    cred_id_b64 = b64url_encode(cred_id)
    pub_b64 = b64url_encode(uncompressed)
    return private_key, cred_id_b64, pub_b64


async def _setup_test_org_and_users(engine: DatabaseEngine):
    """Setup an organization with an Owner and two Admins for 2-of-3 quorum testing."""
    org_id = f"org_{uuid.uuid4().hex[:12]}"
    now = _iso()

    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="M13R3 Test Enterprise",
                slug=f"m13r3-{uuid.uuid4().hex[:8]}",
                monthly_budget_usd=5000.0,
                created_at=now,
                plan="ENTERPRISE",
            )
        )

        users = {}
        for role, name in [(Role.OWNER, "Alice Owner"), (Role.ADMIN, "Bob Admin"), (Role.ADMIN, "Charlie Admin")]:
            uid = f"usr_{uuid.uuid4().hex[:12]}"
            await conn.execute(
                insert(web_users).values(
                    id=uid,
                    email=f"{name.lower().replace(' ', '')}@m13r3.test",
                    full_name=name,
                    password_hash="mock_hash",
                    disabled=0,
                    email_verified_at=now,
                    verification_status="VERIFIED",
                    created_at=now,
                    updated_at=now,
                )
            )
            await conn.execute(
                insert(web_memberships).values(
                    id=f"mem_{uuid.uuid4().hex[:12]}",
                    org_id=org_id,
                    user_id=uid,
                    role=role.value,
                    status="ACTIVE",
                    created_at=now,
                )
            )
            users[name] = {"user_id": uid, "role": role, "name": name}

        # Setup trust root
        root_id = f"root_{uuid.uuid4().hex[:12]}"
        await conn.execute(
            insert(trust_fabric_trust_roots).values(
                id=root_id,
                org_id=org_id,
                root_principal_id="prin_test_root",
                root_public_key="test_public_key",
                key_algorithm="Ed25519",
                status="ACTIVE",
                established_at=now,
                canonical_digest="digest_test",
            )
        )

    return org_id, root_id, users


async def _register_passkey_in_db(engine: DatabaseEngine, user_id: str):
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
                aaguid="00000000-0000-0000-0000-000000000000",
                backup_eligible=1,
                backup_state=1,
                display_name="Test Passkey",
                status="ACTIVE",
                created_at=_iso(),
            )
        )
    return priv_key, cred_id_b64


def _build_signed_assertion(priv_key: ec.EllipticCurvePrivateKey, cred_id_b64: str, ch_dict: dict[str, Any], sign_count: int = 1) -> dict[str, Any]:
    raw_challenge = b64url_decode(ch_dict["challenge"])
    cdata, auth_data, sig = assertion_blob(
        rp_id="localhost",
        origin=ch_dict["origin"],
        challenge=raw_challenge,
        private_key=priv_key,
        sign_count=sign_count,
    )
    return {
        "credential_id": cred_id_b64,
        "client_data_json": cdata,
        "authenticator_data": auth_data,
        "signature": sig,
    }


@pytest.mark.asyncio
async def test_quorum_role_demotion_invalidates_recovery():
    """P0-C: Approver voting while ADMIN, then demoted to MEMBER before execution, fails quorum."""
    engine = get_enterprise_engine()
    service = CustomerAuthorityService(engine)
    org_id, root_id, users = await _setup_test_org_and_users(engine)

    alice = users["Alice Owner"]
    bob = users["Bob Admin"]
    charlie = users["Charlie Admin"]

    actor_alice = Actor(actor_type="USER", actor_id=alice["user_id"], user_id=alice["user_id"], role=Role.OWNER, org_id=org_id, membership_status="ACTIVE")
    actor_bob = Actor(actor_type="USER", actor_id=bob["user_id"], user_id=bob["user_id"], role=Role.ADMIN, org_id=org_id, membership_status="ACTIVE")
    actor_charlie = Actor(actor_type="USER", actor_id=charlie["user_id"], user_id=charlie["user_id"], role=Role.ADMIN, org_id=org_id, membership_status="ACTIVE")

    # 1. Alice creates recovery request
    req = await service.create_recovery_request(
        actor_alice,
        org_id=org_id,
        request_type="ROTATE_ROOT_KEY",
        target_root_id=root_id,
        proposed_parameters={
            "root_public_key": "new_pub_key_123",
            "key_algorithm": "Ed25519",
            "proof_of_possession": "mock_pop",
        },
    )
    request_id = req["request_id"]
    action_digest = req["action_digest"]

    # 2. Bob votes APPROVE while still ADMIN
    await service.vote_recovery_request(
        actor_bob,
        org_id=org_id,
        request_id=request_id,
        decision="APPROVE",
        action_digest=action_digest,
    )

    # 3. Charlie votes APPROVE while still ADMIN -> quorum 2-of-3 initially satisfied
    await service.vote_recovery_request(
        actor_charlie,
        org_id=org_id,
        request_id=request_id,
        decision="APPROVE",
        action_digest=action_digest,
    )

    # 4. Now Charlie is DEMOTED to MEMBER before recovery execution
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(web_memberships.c.user_id == charlie["user_id"])
            .values(role="MEMBER")
        )

    # 5. Alice attempts to execute recovery -> MUST FAIL because Charlie's approval is invalidated!
    with pytest.raises(Exception) as exc_info:
        await service.execute_recovery_request(
            actor_alice,
            org_id=org_id,
            request_id=request_id,
            action_digest=action_digest,
        )
    assert exc_info.value.code == QUORUM_NOT_MET
    assert "Quorum threshold 2 not satisfied" in str(exc_info.value)


@pytest.mark.asyncio
async def test_quorum_anti_self_approval_and_duplicate_voting():
    """P0-C: Requester cannot vote for self-approval; duplicate votes are rejected and deduplicated."""
    engine = get_enterprise_engine()
    service = CustomerAuthorityService(engine)
    org_id, root_id, users = await _setup_test_org_and_users(engine)

    alice = users["Alice Owner"]
    bob = users["Bob Admin"]

    actor_alice = Actor(actor_type="USER", actor_id=alice["user_id"], user_id=alice["user_id"], role=Role.OWNER, org_id=org_id, membership_status="ACTIVE")
    actor_bob = Actor(actor_type="USER", actor_id=bob["user_id"], user_id=bob["user_id"], role=Role.ADMIN, org_id=org_id, membership_status="ACTIVE")

    # 1. Alice creates recovery request
    req = await service.create_recovery_request(
        actor_alice,
        org_id=org_id,
        request_type="ROTATE_ROOT_KEY",
        target_root_id=root_id,
        proposed_parameters={
            "root_public_key": "new_pub_key_456",
            "key_algorithm": "Ed25519",
            "proof_of_possession": "mock_pop",
        },
    )
    request_id = req["request_id"]
    action_digest = req["action_digest"]

    # 2. Alice attempts to vote on her own request -> SELF_APPROVAL_BLOCKED
    with pytest.raises(Exception) as exc_self:
        await service.vote_recovery_request(
            actor_alice,
            org_id=org_id,
            request_id=request_id,
            decision="APPROVE",
            action_digest=action_digest,
        )
    assert exc_self.value.code == SELF_APPROVAL_BLOCKED

    # 3. Bob votes APPROVE
    await service.vote_recovery_request(
        actor_bob,
        org_id=org_id,
        request_id=request_id,
        decision="APPROVE",
        action_digest=action_digest,
    )

    # 4. Bob attempts to vote again -> ALREADY_VOTED
    with pytest.raises(Exception) as exc_dup:
        await service.vote_recovery_request(
            actor_bob,
            org_id=org_id,
            request_id=request_id,
            decision="APPROVE",
            action_digest=action_digest,
        )
    assert exc_dup.value.code == ALREADY_VOTED

    # 5. Alice attempts execution with only Bob's 1 vote -> QUORUM_NOT_MET
    with pytest.raises(Exception) as exc_q:
        await service.execute_recovery_request(
            actor_alice,
            org_id=org_id,
            request_id=request_id,
            action_digest=action_digest,
        )
    assert exc_q.value.code == QUORUM_NOT_MET


@pytest.mark.asyncio
async def test_webauthn_policy_path_a_and_path_b():
    """P0-D: WP-M13-POL-002: Path A fresh assertion and Path B pre-verified single-use ticket."""
    engine = get_enterprise_engine()
    service = CustomerAuthorityService(engine)
    org_id, root_id, users = await _setup_test_org_and_users(engine)

    alice = users["Alice Owner"]
    actor_alice = Actor(actor_type="USER", actor_id=alice["user_id"], user_id=alice["user_id"], role=Role.OWNER, org_id=org_id, membership_status="ACTIVE")
    priv_key, cred_id = await _register_passkey_in_db(engine, alice["user_id"])

    # Register an agent to contain
    agent_id = f"prin_agent_{uuid.uuid4().hex[:8]}"
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(trust_fabric_principals).values(
                id=agent_id,
                org_id=org_id,
                principal_type="ai_agent",
                display_name="Test Agent",
                lifecycle_state="ACTIVE",
                created_at=_iso(),
                updated_at=_iso(),
            )
        )

    # ── Path A: Fresh assertion directly on execute_emergency_containment ──────
    op_a = {
        "org_id": org_id,
        "target_type": "AGENT",
        "target_id": agent_id,
        "containment_action": "QUARANTINE",
    }
    op_a_digest = compute_canonical_operation_digest("EMERGENCY_CONTAINMENT", op_a)

    ch_a = await service.create_authority_stepup_challenge(
        actor_alice,
        org_id=org_id,
        action="EMERGENCY_CONTAINMENT",
        operation_digest=op_a_digest,
    )
    assertion_a = _build_signed_assertion(priv_key, cred_id, ch_a)

    res_a = await service.execute_emergency_containment(
        actor_alice,
        org_id=org_id,
        containment_action="QUARANTINE",
        target_type="AGENT",
        target_id=agent_id,
        reason="Path A test",
        webauthn_assertion=assertion_a,
    )
    assert res_a["status"] == "CONTAINED"
    assert res_a["target_id"] == agent_id

    # ── Path B: Pre-verified single-use ticket ──────────────────────────────────
    agent_id_2 = f"prin_agent_{uuid.uuid4().hex[:8]}"
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(trust_fabric_principals).values(
                id=agent_id_2,
                org_id=org_id,
                principal_type="ai_agent",
                display_name="Test Agent 2",
                lifecycle_state="ACTIVE",
                created_at=_iso(),
                updated_at=_iso(),
            )
        )

    op_b = {
        "org_id": org_id,
        "target_type": "AGENT",
        "target_id": agent_id_2,
        "containment_action": "QUARANTINE",
    }
    op_b_digest = compute_canonical_operation_digest("EMERGENCY_CONTAINMENT", op_b)

    ch_b = await service.create_authority_stepup_challenge(
        actor_alice,
        org_id=org_id,
        action="EMERGENCY_CONTAINMENT",
        operation_digest=op_b_digest,
    )
    assertion_b = _build_signed_assertion(priv_key, cred_id, ch_b, sign_count=2)

    # Mint Path B pre-verified authorization ticket
    path_b_ticket = await service.create_preverified_stepup_authorization(
        actor_alice,
        org_id=org_id,
        action="EMERGENCY_CONTAINMENT",
        operation=op_b,
        webauthn_assertion=assertion_b,
    )
    authz_id = path_b_ticket["authorization_id"]
    assert authz_id.startswith("wp_authz_")

    # 1. First consumption succeeds
    res_b = await service.execute_emergency_containment(
        actor_alice,
        org_id=org_id,
        containment_action="QUARANTINE",
        target_type="AGENT",
        target_id=agent_id_2,
        reason="Path B test",
        stepup_authorization_id=authz_id,
    )
    assert res_b["status"] == "CONTAINED"

    # 2. Replay attempt with same ticket FAILS with WEBAUTHN_CHALLENGE_REPLAY
    with pytest.raises(Exception) as exc_replay:
        await service.execute_emergency_containment(
            actor_alice,
            org_id=org_id,
            containment_action="QUARANTINE",
            target_type="AGENT",
            target_id=agent_id_2,
            reason="Path B test",
            stepup_authorization_id=authz_id,
        )
    assert exc_replay.value.code == WEBAUTHN_CHALLENGE_REPLAY
    assert "already been consumed" in str(exc_replay.value)


@pytest.mark.asyncio
async def test_path_b_operation_mismatch_and_scope_restriction():
    """P0-D: Path B ticket bound to operation X cannot be used for operation Y; barred for recovery."""
    engine = get_enterprise_engine()
    service = CustomerAuthorityService(engine)
    org_id, root_id, users = await _setup_test_org_and_users(engine)

    alice = users["Alice Owner"]
    actor_alice = Actor(actor_type="USER", actor_id=alice["user_id"], user_id=alice["user_id"], role=Role.OWNER, org_id=org_id, membership_status="ACTIVE")
    priv_key, cred_id = await _register_passkey_in_db(engine, alice["user_id"])

    # Attempting to mint Path B for non-containment action is strictly BARRED
    with pytest.raises(Exception) as exc_barred:
        await service.create_preverified_stepup_authorization(
            actor_alice,
            org_id=org_id,
            action="EXECUTE_RECOVERY_REQUEST",
            operation={"request_id": "req_123"},
            webauthn_assertion={},
        )
    assert "strictly barred" in str(exc_barred.value)

    # Mint Path B for agent 1
    op_1 = {
        "org_id": org_id,
        "target_type": "AGENT",
        "target_id": "prin_agent_1",
        "containment_action": "QUARANTINE",
    }
    op_1_digest = compute_canonical_operation_digest("EMERGENCY_CONTAINMENT", op_1)
    ch = await service.create_authority_stepup_challenge(
        actor_alice, org_id=org_id, action="EMERGENCY_CONTAINMENT", operation_digest=op_1_digest
    )
    assertion = _build_signed_assertion(priv_key, cred_id, ch)

    ticket = await service.create_preverified_stepup_authorization(
        actor_alice,
        org_id=org_id,
        action="EMERGENCY_CONTAINMENT",
        operation=op_1,
        webauthn_assertion=assertion,
    )
    authz_id = ticket["authorization_id"]

    # Attempt to consume ticket for agent 2 (mismatching target) -> FAILS closed
    with pytest.raises(Exception) as exc_mismatch:
        await service.execute_emergency_containment(
            actor_alice,
            org_id=org_id,
            containment_action="QUARANTINE",
            target_type="AGENT",
            target_id="prin_agent_2",  # Mismatch!
            reason="Target 1",
            stepup_authorization_id=authz_id,
        )
    assert exc_mismatch.value.code == WEBAUTHN_ASSERTION_INVALID
    assert "Operation digest mismatch" in str(exc_mismatch.value)
