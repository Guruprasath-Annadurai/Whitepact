# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Unit and Adversarial Tests for JIT Grants, Four-Eyes, Break-Glass, and Sovereign Recovery."""

from __future__ import annotations

import base64

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from sqlalchemy import insert, select

from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    organizations,
    trust_fabric_trust_roots,
)
from responsibleai.iam.break_glass import BreakGlassService
from responsibleai.iam.enums import (
    BreakGlassCapability,
    FourEyesStatus,
    JitGrantStatus,
    PrivilegedAction,
)
from responsibleai.iam.errors import (
    BreakGlassInvalidError,
    PrivilegedAccessDeniedError,
    SelfApprovalBlockedError,
    SovereignRecoveryError,
)
from responsibleai.iam.four_eyes import FourEyesService
from responsibleai.iam.jit import JitAccessService
from responsibleai.iam.recovery import SovereignRecoveryService
from responsibleai.iam.transfer import SovereignTransferService
from responsibleai.rbac.models import Role


@pytest.fixture
async def test_db():
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="org_gov",
                name="Governance Corp",
                slug="gov-corp",
                monthly_budget_usd=10000.0,
                created_at="2026-09-12T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
        # Add initial trust root
        await conn.execute(
            insert(trust_fabric_trust_roots).values(
                id="root_initial",
                org_id="org_gov",
                root_principal_id="prin_root_old",
                root_public_key="initial_pub_key",
                key_algorithm="Ed25519",
                established_at="2026-09-12T00:00:00Z",
                status="ACTIVE",
                canonical_digest="digest_initial",
            )
        )
    yield engine
    await engine.close()


@pytest.mark.asyncio
async def test_jit_grant_and_anti_self_approval(test_db: DatabaseEngine):
    jit_svc = JitAccessService(test_db)

    # 1. Request grant
    grant = await jit_svc.request_jit_access(
        org_id="org_gov",
        principal_id="user_charlie",
        target_role=Role.ADMIN,
        allowed_actions=[PrivilegedAction.MODIFY_POLICY_RULE],
        justification="Incident remediation #402",
        ttl_minutes=60,
    )
    assert grant.status == JitGrantStatus.REQUESTED

    # 2. Self-approval must fail!
    with pytest.raises(ValueError, match="Requester cannot approve their own JIT grant"):
        await jit_svc.approve_jit_access(
            org_id="org_gov",
            grant_id=grant.id,
            approver_principal_id="user_charlie",
        )

    # 3. Independent approver succeeds
    approved = await jit_svc.approve_jit_access(
        org_id="org_gov",
        grant_id=grant.id,
        approver_principal_id="user_david",
    )
    assert approved.status == JitGrantStatus.ACTIVE
    assert approved.approver_principal_id == "user_david"


@pytest.mark.asyncio
async def test_four_eyes_dual_custody_self_approval_blocked(test_db: DatabaseEngine):
    fe_svc = FourEyesService(test_db)

    req = await fe_svc.submit_four_eyes_request(
        org_id="org_gov",
        requester_principal_id="admin_1",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
    )
    assert req.status == FourEyesStatus.PENDING

    # Self-approval prohibited
    with pytest.raises(SelfApprovalBlockedError):
        await fe_svc.approve_four_eyes_request(
            org_id="org_gov",
            request_id=req.id,
            approver_principal_id="admin_1",
        )

    # Independent approval succeeds
    approved = await fe_svc.approve_four_eyes_request(
        org_id="org_gov",
        request_id=req.id,
        approver_principal_id="admin_2",
    )
    assert approved.status == FourEyesStatus.APPROVED


@pytest.mark.asyncio
async def test_break_glass_requires_incident_and_capped_ttl(test_db: DatabaseEngine):
    bg_svc = BreakGlassService(test_db)

    # Missing incident ID fails
    with pytest.raises(BreakGlassInvalidError, match="valid, documented incident identifier"):
        await bg_svc.initiate_break_glass(
            org_id="org_gov",
            principal_id="sre_oncall",
            incident_id="",
            capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
            justification="Emergency IdP repair",
        )

    # Excessive TTL (>60m) fails
    with pytest.raises(BreakGlassInvalidError, match="cannot exceed 60 minutes"):
        await bg_svc.initiate_break_glass(
            org_id="org_gov",
            principal_id="sre_oncall",
            incident_id="INC-9912",
            capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
            justification="Emergency IdP repair",
            ttl_minutes=120,
        )

    # Valid session succeeds
    session = await bg_svc.initiate_break_glass(
        org_id="org_gov",
        principal_id="sre_oncall",
        incident_id="INC-9912",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Emergency IdP repair",
        ttl_minutes=30,
    )
    assert session.status == "ACTIVE"


@pytest.mark.asyncio
async def test_sovereign_root_recovery_n_of_m_ceremony(test_db: DatabaseEngine):
    rec_svc = SovereignRecoveryService(test_db)

    # 1. Generate 3 guardian keypairs (Threshold 2-of-3)
    guardian_privs = [ed25519.Ed25519PrivateKey.generate() for _ in range(3)]
    guardians = [
        {
            "name": f"guardian_{i}",
            "public_key": base64.b64encode(p.public_key().public_bytes_raw()).decode("utf-8"),
        }
        for i, p in enumerate(guardian_privs)
    ]

    policy = await rec_svc.register_recovery_policy(
        org_id="org_gov",
        threshold=2,
        guardians=guardians,
    )
    assert policy.threshold == 2

    # 2. Initiate challenge
    new_root_pub = "new_ed25519_root_public_key_base64"
    challenge_msg = await rec_svc.initiate_recovery_challenge(
        org_id="org_gov",
        new_root_principal_id="prin_root_new",
        new_root_public_key=new_root_pub,
    )

    # 3. Submit signature from Guardian 0
    sig0 = guardian_privs[0].sign(challenge_msg.encode("utf-8"))
    sig0_b64 = base64.b64encode(sig0).decode("utf-8")
    count = await rec_svc.submit_guardian_signature(
        org_id="org_gov",
        challenge_message=challenge_msg,
        guardian_name="guardian_0",
        signature_b64=sig0_b64,
    )
    assert count == 1

    # Attempting to finalize with only 1 signature must fail (threshold is 2)
    with pytest.raises(SovereignRecoveryError, match="Threshold not met"):
        await rec_svc.finalize_sovereign_recovery(
            org_id="org_gov",
            challenge_message=challenge_msg,
        )

    # 4. Submit signature from Guardian 1
    sig1 = guardian_privs[1].sign(challenge_msg.encode("utf-8"))
    sig1_b64 = base64.b64encode(sig1).decode("utf-8")
    count2 = await rec_svc.submit_guardian_signature(
        org_id="org_gov",
        challenge_message=challenge_msg,
        guardian_name="guardian_1",
        signature_b64=sig1_b64,
    )
    assert count2 == 2

    # 5. Finalize recovery
    finalized = await rec_svc.finalize_sovereign_recovery(
        org_id="org_gov",
        challenge_message=challenge_msg,
    )
    assert finalized is True

    # 6. Verify trust root atomically updated and old root revoked
    async with test_db.raw.connect() as conn:
        roots = (
            await conn.execute(
                select(trust_fabric_trust_roots).where(
                    trust_fabric_trust_roots.c.org_id == "org_gov"
                )
            )
        ).fetchall()
        assert len(roots) == 1
        root = roots[0]
        assert root.status == "ACTIVE"
        assert root.root_principal_id == "prin_root_new"
        assert root.root_public_key == new_root_pub


@pytest.mark.asyncio
async def test_jit_ttl_bounds_rejection(test_db: DatabaseEngine):
    jit_svc = JitAccessService(test_db)
    # Zero TTL
    with pytest.raises(ValueError, match="TTL must be between 1 and 480 minutes"):
        await jit_svc.request_jit_access(
            org_id="org_gov",
            principal_id="user_charlie",
            target_role=Role.ADMIN,
            allowed_actions=[PrivilegedAction.MODIFY_POLICY_RULE],
            justification="Zero TTL test",
            ttl_minutes=0,
        )
    # Negative TTL
    with pytest.raises(ValueError, match="TTL must be between 1 and 480 minutes"):
        await jit_svc.request_jit_access(
            org_id="org_gov",
            principal_id="user_charlie",
            target_role=Role.ADMIN,
            allowed_actions=[PrivilegedAction.MODIFY_POLICY_RULE],
            justification="Negative TTL test",
            ttl_minutes=-10,
        )


@pytest.mark.asyncio
async def test_break_glass_ttl_bounds_rejection(test_db: DatabaseEngine):
    bg_svc = BreakGlassService(test_db)
    # Zero TTL
    with pytest.raises(BreakGlassInvalidError, match="TTL must be between 1 and 60 minutes"):
        await bg_svc.initiate_break_glass(
            org_id="org_gov",
            principal_id="sre_oncall",
            incident_id="INC-1234",
            capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
            justification="Zero TTL test",
            ttl_minutes=0,
        )
    # Negative TTL
    with pytest.raises(BreakGlassInvalidError, match="TTL must be between 1 and 60 minutes"):
        await bg_svc.initiate_break_glass(
            org_id="org_gov",
            principal_id="sre_oncall",
            incident_id="INC-1234",
            capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
            justification="Negative TTL test",
            ttl_minutes=-5,
        )


@pytest.mark.asyncio
async def test_guardian_key_uniqueness_and_operator_rejection(test_db: DatabaseEngine):
    rec_svc = SovereignRecoveryService(test_db)
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode("utf-8")

    # Duplicate public keys must be rejected
    with pytest.raises(ValueError, match="Guardian public keys must be unique"):
        await rec_svc.register_recovery_policy(
            org_id="org_gov",
            threshold=2,
            guardians=[
                {"name": "guardian_1", "public_key": pub_b64},
                {"name": "guardian_2", "public_key": pub_b64},
            ],
        )

    # Platform operator identity rejected
    priv2 = ed25519.Ed25519PrivateKey.generate()
    pub2_b64 = base64.b64encode(priv2.public_key().public_bytes_raw()).decode("utf-8")
    with pytest.raises(SovereignRecoveryError, match="Platform operators cannot be registered"):
        await rec_svc.register_recovery_policy(
            org_id="org_gov",
            threshold=2,
            guardians=[
                {"name": "platform_operator_alice", "public_key": pub_b64},
                {"name": "guardian_customer", "public_key": pub2_b64},
            ],
        )


@pytest.mark.asyncio
async def test_voluntary_root_transfer_lifecycle(test_db: DatabaseEngine):
    xfer_svc = SovereignTransferService(test_db)
    token = xfer_svc.generate_transfer_token()

    # 1. Self-transfer prohibited
    with pytest.raises(SelfApprovalBlockedError):
        await xfer_svc.transfer_root_authority(
            org_id="org_gov",
            current_root_principal_id="prin_root_old",
            new_root_principal_id="prin_root_old",
            new_root_public_key="new_key",
            transfer_token=token,
        )

    # 2. Non-root caller prohibited
    with pytest.raises(PrivilegedAccessDeniedError, match="is not the active sovereign root"):
        await xfer_svc.transfer_root_authority(
            org_id="org_gov",
            current_root_principal_id="impostor",
            new_root_principal_id="prin_root_successor",
            new_root_public_key="successor_pub_key",
            transfer_token=token,
        )

    # 3. Legitimate transfer succeeds
    success = await xfer_svc.transfer_root_authority(
        org_id="org_gov",
        current_root_principal_id="prin_root_old",
        new_root_principal_id="prin_root_successor",
        new_root_public_key="successor_pub_key",
        transfer_token=token,
    )
    assert success is True

    # 4. Token cannot be replayed
    with pytest.raises(PrivilegedAccessDeniedError, match="already been consumed"):
        await xfer_svc.transfer_root_authority(
            org_id="org_gov",
            current_root_principal_id="prin_root_successor",
            new_root_principal_id="another_successor",
            new_root_public_key="another_key",
            transfer_token=token,
        )

    # 5. Old root authority is 0 (no longer root)
    async with test_db.raw.connect() as conn:
        root_row = (
            await conn.execute(
                select(trust_fabric_trust_roots).where(
                    trust_fabric_trust_roots.c.org_id == "org_gov"
                )
            )
        ).one()
        assert root_row.root_principal_id == "prin_root_successor"
        assert root_row.root_principal_id != "prin_root_old"
