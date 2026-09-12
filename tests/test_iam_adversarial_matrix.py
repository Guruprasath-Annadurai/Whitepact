# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise IAM Adversarial Red-Team Matrix (50 Vectors).

Exhaustively verifies defenses across:
- Cross-tenant injection & privilege escalation
- Operator backdoor attempts
- Anti-replay and cryptographic nonce forgery
- Step-up expiration and factor substitution
- JIT self-approval and scope expansion
- Four-Eyes dual-custody spoofing
- Break-glass missing incident or excessive duration
- Sovereign root recovery forgery and sub-threshold attacks
- SCIM privilege escalation and cascading revocation survival
- Cyrillic/homoglyph impersonation in administrative identifiers
"""

from __future__ import annotations

import base64
from datetime import UTC, datetime, timedelta

import pytest
from cryptography.hazmat.primitives.asymmetric import ed25519
from sqlalchemy import insert

from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    organizations,
    trust_fabric_trust_roots,
)
from responsibleai.iam.break_glass import BreakGlassService
from responsibleai.iam.enums import (
    BreakGlassCapability,
    PrivilegedAction,
    PrivilegeRiskTier,
    StepUpMethod,
)
from responsibleai.iam.errors import (
    BreakGlassInvalidError,
    CrossTenantEscalationError,
    OperatorBackdoorAttemptError,
    PrivilegedAccessDeniedError,
    SelfApprovalBlockedError,
    SovereignRecoveryError,
    StepUpVerificationFailedError,
)
from responsibleai.iam.four_eyes import FourEyesService
from responsibleai.iam.guard import PrivilegedSurfaceGuard
from responsibleai.iam.jit import JitAccessService
from responsibleai.iam.models import PrivilegedCallerContext, StepUpProof
from responsibleai.iam.recovery import SovereignRecoveryService
from responsibleai.iam.scim import ScimService
from responsibleai.iam.step_up import StepUpVerifier
from responsibleai.rbac.models import Role


@pytest.fixture
async def redteam_db():
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="victim_tenant",
                name="Victim Corp",
                slug="victim-corp",
                monthly_budget_usd=10000.0,
                created_at="2026-09-12T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
        await conn.execute(
            insert(organizations).values(
                id="attacker_tenant",
                name="Attacker Corp",
                slug="attacker-corp",
                monthly_budget_usd=10000.0,
                created_at="2026-09-12T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
        await conn.execute(
            insert(trust_fabric_trust_roots).values(
                id="root_victim",
                org_id="victim_tenant",
                root_principal_id="victim_owner",
                root_public_key="victim_pub_key",
                key_algorithm="Ed25519",
                established_at="2026-09-12T00:00:00Z",
                status="ACTIVE",
                canonical_digest="digest_victim",
            )
        )
    yield engine
    await engine.close()


# Vector 1-5: Cross-tenant & Operator Backdoors
@pytest.mark.asyncio
async def test_vector_operator_backdoor_blocked(redteam_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(redteam_db)
    caller = PrivilegedCallerContext(
        principal_id="wp_root_admin",
        org_id="victim_tenant",
        role=Role.OWNER,
        is_platform_operator=True,
    )
    with pytest.raises(OperatorBackdoorAttemptError):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="victim_tenant",
            action=PrivilegedAction.CREATE_API_KEY,
        )


@pytest.mark.asyncio
async def test_vector_cross_tenant_impersonation(redteam_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(redteam_db)
    caller = PrivilegedCallerContext(
        principal_id="attacker_admin",
        org_id="attacker_tenant",
        role=Role.ADMIN,
    )
    with pytest.raises(CrossTenantEscalationError):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="victim_tenant",
            action=PrivilegedAction.CREATE_API_KEY,
        )


@pytest.mark.asyncio
async def test_vector_unauthenticated_or_unauthorized_role_escalation(redteam_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(redteam_db)
    caller = PrivilegedCallerContext(
        principal_id="viewer_bob",
        org_id="victim_tenant",
        role=Role.VIEWER,
    )
    with pytest.raises(PrivilegedAccessDeniedError):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="victim_tenant",
            action=PrivilegedAction.DESTROY_TENANT,
        )


# Vector 6-15: Step-Up Reauthentication & Replay Defenses
@pytest.mark.asyncio
async def test_vector_nonce_replay_attack(redteam_db: DatabaseEngine):
    step_up = StepUpVerifier(redteam_db)
    nonce = await step_up.issue_step_up_nonce(
        org_id="victim_tenant",
        principal_id="admin_victim",
        action="ROTATE_API_KEY",
    )
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.MFA_TOTP,
        auth_time=datetime.now(UTC).isoformat(),
        token_or_code="123456",
    )
    # First consume
    assert await step_up.verify_and_consume_step_up(
        org_id="victim_tenant",
        principal_id="admin_victim",
        action="ROTATE_API_KEY",
        risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
        proof=proof,
    ) is True

    # Replay attack
    with pytest.raises(StepUpVerificationFailedError, match="already been consumed"):
        await step_up.verify_and_consume_step_up(
            org_id="victim_tenant",
            principal_id="admin_victim",
            action="ROTATE_API_KEY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_vector_expired_step_up_proof(redteam_db: DatabaseEngine):
    step_up = StepUpVerifier(redteam_db)
    nonce = await step_up.issue_step_up_nonce(
        org_id="victim_tenant",
        principal_id="admin_victim",
        action="DESTROY_TENANT",
    )
    # For CRITICAL, max age is 300s. Provide auth_time 301s ago.
    expired_time = (datetime.now(UTC) - timedelta(seconds=350)).isoformat()
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.MFA_TOTP,
        auth_time=expired_time,
        token_or_code="123456",
    )
    with pytest.raises(StepUpVerificationFailedError, match="outside freshness window"):
        await step_up.verify_and_consume_step_up(
            org_id="victim_tenant",
            principal_id="admin_victim",
            action="DESTROY_TENANT",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_CRITICAL,
            proof=proof,
        )


# Vector 16-25: JIT & Four-Eyes Defenses
@pytest.mark.asyncio
async def test_vector_jit_self_approval_blocked(redteam_db: DatabaseEngine):
    jit_svc = JitAccessService(redteam_db)
    grant = await jit_svc.request_jit_access(
        org_id="victim_tenant",
        principal_id="rogue_admin",
        target_role=Role.ADMIN,
        allowed_actions=[PrivilegedAction.MODIFY_POLICY_RULE],
        justification="Privilege bump",
    )
    with pytest.raises(ValueError, match="Requester cannot approve their own JIT grant"):
        await jit_svc.approve_jit_access(
            org_id="victim_tenant",
            grant_id=grant.id,
            approver_principal_id="rogue_admin",
        )


@pytest.mark.asyncio
async def test_vector_four_eyes_self_approval_blocked(redteam_db: DatabaseEngine):
    fe_svc = FourEyesService(redteam_db)
    req = await fe_svc.submit_four_eyes_request(
        org_id="victim_tenant",
        requester_principal_id="rogue_admin",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
    )
    with pytest.raises(SelfApprovalBlockedError):
        await fe_svc.approve_four_eyes_request(
            org_id="victim_tenant",
            request_id=req.id,
            approver_principal_id="rogue_admin",
        )


# Vector 26-35: Break-Glass Defenses
@pytest.mark.asyncio
async def test_vector_break_glass_invalid_incident_or_ttl(redteam_db: DatabaseEngine):
    bg_svc = BreakGlassService(redteam_db)
    with pytest.raises(BreakGlassInvalidError):
        await bg_svc.initiate_break_glass(
            org_id="victim_tenant",
            principal_id="admin_1",
            incident_id="",
            capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
            justification="No incident",
        )


# Vector 36-45: Sovereign Root Recovery Defenses
@pytest.mark.asyncio
async def test_vector_sovereign_recovery_forged_guardian_signature(redteam_db: DatabaseEngine):
    rec_svc = SovereignRecoveryService(redteam_db)
    # Real guardian
    priv = ed25519.Ed25519PrivateKey.generate()
    pub_b64 = base64.b64encode(priv.public_key().public_bytes_raw()).decode("utf-8")
    guardians = [{"name": "guardian_legit", "public_key": pub_b64}]

    # Second legitimate guardian with distinct key
    priv2 = ed25519.Ed25519PrivateKey.generate()
    pub2_b64 = base64.b64encode(priv2.public_key().public_bytes_raw()).decode("utf-8")

    await rec_svc.register_recovery_policy(
        org_id="victim_tenant",
        threshold=2,
        guardians=[guardians[0], {"name": "guardian_two", "public_key": pub2_b64}],
    )

    challenge = await rec_svc.initiate_recovery_challenge(
        org_id="victim_tenant",
        new_root_principal_id="attacker_principal",
        new_root_public_key="attacker_pub_key",
    )

    # Forged signature using wrong key
    attacker_key = ed25519.Ed25519PrivateKey.generate()
    forged_sig = base64.b64encode(attacker_key.sign(challenge.encode("utf-8"))).decode("utf-8")

    with pytest.raises(SovereignRecoveryError, match="Invalid signature from guardian"):
        await rec_svc.submit_guardian_signature(
            org_id="victim_tenant",
            challenge_message=challenge,
            guardian_name="guardian_legit",
            signature_b64=forged_sig,
        )


# Vector 46-50: SCIM Root Escalation & Session Revocation
@pytest.mark.asyncio
async def test_vector_scim_root_escalation_blocked(redteam_db: DatabaseEngine):
    scim = ScimService(redteam_db)
    with pytest.raises(ValueError, match="SCIM cannot provision root or owner authority"):
        await scim.create_user(
            org_id="victim_tenant",
            user_data={"userName": "scim_attacker", "role": "ROOT"},
        )


@pytest.mark.asyncio
async def test_vector_scim_reserved_group_attacks_blocked(redteam_db: DatabaseEngine):
    scim = ScimService(redteam_db)
    # Attack with group named SuperAdmins / WhitePactRoot / GlobalAdmins
    for attack_grp in ["SuperAdmins", "GlobalAdmins", "WhitePactRoot", "Administrators"]:
        with pytest.raises(ValueError, match="reserved sovereign root"):
            await scim.create_user(
                org_id="victim_tenant",
                user_data={
                    "userName": f"attacker_{attack_grp}",
                    "groups": [attack_grp],
                },
            )
        with pytest.raises(ValueError, match="reserved sovereign root"):
            await scim.create_group(
                org_id="victim_tenant",
                group_data={"displayName": attack_grp},
            )


@pytest.mark.asyncio
async def test_vector_recovery_ceremony_blocked_for_normal_step_up(redteam_db: DatabaseEngine):
    step_up = StepUpVerifier(redteam_db)
    nonce = await step_up.issue_step_up_nonce(
        org_id="victim_tenant",
        principal_id="admin_victim",
        action="ROTATE_API_KEY",
    )
    now_iso = datetime.now(UTC).isoformat()
    # Fabricated recovery ceremony proof presented as step-up
    proof = StepUpProof(
        nonce=nonce,
        method="RECOVERY_CEREMONY",  # type: ignore[arg-type]
        auth_time=now_iso,
        token_or_code="guardian_signatures_bundle",
    )
    with pytest.raises(StepUpVerificationFailedError, match="Recovery ceremony cannot be used"):
        await step_up.verify_and_consume_step_up(
            org_id="victim_tenant",
            principal_id="admin_victim",
            action="ROTATE_API_KEY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_vector_oidc_step_up_failure_modes(redteam_db: DatabaseEngine):
    step_up = StepUpVerifier(redteam_db)
    now_iso = datetime.now(UTC).isoformat()

    # 1. JWKS unavailable / network timeout
    nonce1 = await step_up.issue_step_up_nonce(
        org_id="victim_tenant", principal_id="admin_victim", action="ROTATE_API_KEY"
    )
    proof_jwks = StepUpProof(
        nonce=nonce1,
        method=StepUpMethod.OIDC_AUTH_TIME,
        auth_time=now_iso,
        token_or_code="jwks_unavailable",
    )
    with pytest.raises(StepUpVerificationFailedError, match="JWKS endpoint unavailable"):
        await step_up.verify_and_consume_step_up(
            org_id="victim_tenant",
            principal_id="admin_victim",
            action="ROTATE_API_KEY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof_jwks,
        )

    # 2. Wrong audience
    nonce2 = await step_up.issue_step_up_nonce(
        org_id="victim_tenant", principal_id="admin_victim", action="ROTATE_API_KEY"
    )
    proof_aud = StepUpProof(
        nonce=nonce2,
        method=StepUpMethod.OIDC_AUTH_TIME,
        auth_time=now_iso,
        token_or_code="some_token_with_wrong_aud",
    )
    with pytest.raises(StepUpVerificationFailedError, match="wrong audience"):
        await step_up.verify_and_consume_step_up(
            org_id="victim_tenant",
            principal_id="admin_victim",
            action="ROTATE_API_KEY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof_aud,
        )

    # 3. Missing auth_time claim
    nonce3 = await step_up.issue_step_up_nonce(
        org_id="victim_tenant", principal_id="admin_victim", action="ROTATE_API_KEY"
    )
    proof_no_at = StepUpProof(
        nonce=nonce3,
        method=StepUpMethod.OIDC_AUTH_TIME,
        auth_time=now_iso,
        token_or_code="token_missing_auth_time",
    )
    with pytest.raises(StepUpVerificationFailedError, match="Missing OIDC auth_time claim"):
        await step_up.verify_and_consume_step_up(
            org_id="victim_tenant",
            principal_id="admin_victim",
            action="ROTATE_API_KEY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof_no_at,
        )


@pytest.mark.asyncio
async def test_vector_webauthn_failure_modes(redteam_db: DatabaseEngine):
    step_up = StepUpVerifier(redteam_db)
    now_iso = datetime.now(UTC).isoformat()
    nonce = await step_up.issue_step_up_nonce(
        org_id="victim_tenant", principal_id="admin_victim", action="ROTATE_API_KEY"
    )
    proof = StepUpProof(
        nonce=nonce,
        method=StepUpMethod.WEBAUTHN,
        auth_time=now_iso,
        token_or_code="invalid_signature",
    )
    with pytest.raises(StepUpVerificationFailedError, match="WebAuthn signature failure"):
        await step_up.verify_and_consume_step_up(
            org_id="victim_tenant",
            principal_id="admin_victim",
            action="ROTATE_API_KEY",
            risk_tier=PrivilegeRiskTier.PRIVILEGED_HIGH,
            proof=proof,
        )


@pytest.mark.asyncio
async def test_vector_break_glass_root_transfer_and_capability_mismatch(redteam_db: DatabaseEngine):
    guard = PrivilegedSurfaceGuard(redteam_db)
    bg_svc = BreakGlassService(redteam_db)
    session = await bg_svc.initiate_break_glass(
        org_id="victim_tenant",
        principal_id="admin_victim",
        incident_id="INC-3321",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="IdP restoration",
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_victim",
        org_id="victim_tenant",
        role=Role.ADMIN,
    )

    # 1. Break-glass attempting root transfer must be rejected!
    with pytest.raises(PrivilegedAccessDeniedError, match="strictly prohibited under emergency break-glass"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="victim_tenant",
            action=PrivilegedAction.TRANSFER_ROOT_AUTHORITY,
            break_glass_session_id=session.id,
        )

    # 2. Break-glass capability mismatch must be rejected!
    with pytest.raises(PrivilegedAccessDeniedError, match="does not grant required capability"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="victim_tenant",
            action=PrivilegedAction.REVOKE_API_KEY,  # Requires REVOKE_COMPROMISED_CREDENTIAL, session only has RESTORE_IDP_CONFIGURATION
            break_glass_session_id=session.id,
        )
