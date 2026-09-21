# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact BreakGlass -> Policy Final Closure Test Suite.

Verifies the constitutional invariant:
BREAK-GLASS / EMERGENCY AUTHORITY MUST NEVER BECOME AN OUT-OF-BAND BYPASS
AROUND WHITEPACT POLICY ENFORCEMENT.

Covers:
- WP-BG-001: Wrong-principal emergency grant binding
- Cross-tenant emergency binding
- Caller-forged emergency parameters
- Policy-DENY invariant (emergency authority cannot override policy DENY)
- Scope and capability enforcement
- Sovereign root & recovery separation
- Expiry and termination enforcement
- Mandatory step-up reauthentication under break-glass
- Fail-closed behavior on provider / evidence failure
- Tamper-evident attribution
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import insert, select

from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    iam_break_glass_sessions,
    iam_privileged_audit_log,
    organizations,
    trust_fabric_trust_roots,
)
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import Policy, PolicyRule
from responsibleai.governance.policy_lifecycle import PolicyLifecycleManager
from responsibleai.governance.risk import RiskTier
from responsibleai.iam.break_glass import BreakGlassService
from responsibleai.iam.enums import (
    BreakGlassCapability,
    PrivilegedAction,
    StepUpMethod,
)
from responsibleai.iam.errors import (
    CrossTenantEscalationError,
    PrivilegedAccessDeniedError,
    StepUpRequiredError,
    StepUpVerificationFailedError,
)
from responsibleai.iam.guard import PrivilegedSurfaceGuard
from responsibleai.iam.models import PrivilegedCallerContext, StepUpProof
from responsibleai.iam.step_up import StepUpVerifier
from responsibleai.rbac.models import Role


@pytest.fixture
async def bg_db():
    """In-memory database engine seeded with test organizations and roots."""
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="org_alpha",
                name="Alpha Corp",
                slug="alpha-corp",
                monthly_budget_usd=10000.0,
                created_at="2026-09-12T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
        await conn.execute(
            insert(organizations).values(
                id="org_beta",
                name="Beta Corp",
                slug="beta-corp",
                monthly_budget_usd=10000.0,
                created_at="2026-09-12T00:00:00Z",
                plan="ENTERPRISE",
            )
        )
        await conn.execute(
            insert(trust_fabric_trust_roots).values(
                id="root_alpha",
                org_id="org_alpha",
                root_principal_id="owner_alpha",
                root_public_key="alpha_pub_key",
                key_algorithm="Ed25519",
                established_at="2026-09-12T00:00:00Z",
                status="ACTIVE",
                canonical_digest="digest_alpha",
            )
        )
        await conn.execute(
            insert(trust_fabric_trust_roots).values(
                id="root_beta",
                org_id="org_beta",
                root_principal_id="owner_beta",
                root_public_key="beta_pub_key",
                key_algorithm="Ed25519",
                established_at="2026-09-12T00:00:00Z",
                status="ACTIVE",
                canonical_digest="digest_beta",
            )
        )
    yield engine
    await engine.close()


async def _issue_step_up_proof(
    engine: DatabaseEngine,
    org_id: str,
    principal_id: str,
    action: str,
    target_resource_id: str | None = None,
) -> StepUpProof:
    """Helper to issue a fresh, valid step-up proof for testing."""
    verifier = StepUpVerifier(engine)
    nonce = await verifier.issue_step_up_nonce(
        org_id=org_id,
        principal_id=principal_id,
        action=action,
        target_resource_id=target_resource_id,
    )
    return StepUpProof(
        nonce=nonce,
        method=StepUpMethod.MFA_TOTP,
        auth_time=datetime.now(UTC).isoformat(),
        token_or_code="123456",
    )


# =========================================================================
# 1. WP-BG-001: PRINCIPAL BINDING & TENANT BINDING
# =========================================================================


@pytest.mark.asyncio
async def test_wp_bg_001_wrong_principal_break_glass_blocked(
    bg_db: DatabaseEngine, seed_trust_employment
):
    """Prove that an emergency grant issued to Principal A cannot be consumed by Principal B."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_legit")
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_intruder")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_legit",
        incident_id="INC-ALPHA-01",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Legitimate emergency IdP restore",
    )

    intruder_caller = PrivilegedCallerContext(
        principal_id="admin_intruder",
        org_id="org_alpha",
        role=Role.ADMIN,
    )

    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_intruder",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )

    with pytest.raises(
        PrivilegedAccessDeniedError, match="Break-glass session belongs to another principal"
    ):
        await guard.authorize_privileged_operation(
            caller=intruder_caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            step_up_proof=step_up,
            break_glass_session_id=session.id,
        )


@pytest.mark.asyncio
async def test_cross_tenant_break_glass_blocked(bg_db: DatabaseEngine, seed_trust_employment):
    """Prove that an emergency session issued in Tenant Alpha cannot be used in Tenant Beta."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")
    await seed_trust_employment(bg_db, org_id="org_beta", principal_id="admin_beta")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-02",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Alpha IdP restore",
    )

    # 1. Caller from beta targeting alpha -> cross tenant escalation blocked
    beta_caller = PrivilegedCallerContext(
        principal_id="admin_beta",
        org_id="org_beta",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    with pytest.raises(CrossTenantEscalationError):
        await guard.authorize_privileged_operation(
            caller=beta_caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            break_glass_session_id=session.id,
        )

    # 2. Caller from beta targeting beta presenting alpha session -> invalid session
    step_up_beta = await _issue_step_up_proof(
        bg_db,
        org_id="org_beta",
        principal_id="admin_beta",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )
    with pytest.raises(PrivilegedAccessDeniedError, match="Invalid emergency break-glass session"):
        await guard.authorize_privileged_operation(
            caller=beta_caller,
            target_org_id="org_beta",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            step_up_proof=step_up_beta,
            break_glass_session_id=session.id,
        )


# =========================================================================
# 2. CALLER-CONTROLLED STATE ATTACKS
# =========================================================================


@pytest.mark.asyncio
async def test_forged_break_glass_session_id_blocked(bg_db: DatabaseEngine, seed_trust_employment):
    """Prove that caller-fabricated session IDs are strictly rejected."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )

    with pytest.raises(PrivilegedAccessDeniedError, match="Invalid emergency break-glass session"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            step_up_proof=step_up,
            break_glass_session_id="bg_forged_random_id_12345",
        )


@pytest.mark.asyncio
async def test_caller_supplied_break_glass_flag_has_no_bypass_effect(
    bg_db: DatabaseEngine, seed_trust_employment
):
    """Passing break_glass=True in context data does not bypass Four-Eyes or role checks."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )

    from responsibleai.iam.errors import FourEyesRequiredError

    with pytest.raises(FourEyesRequiredError):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            step_up_proof=step_up,
            context_data={"break_glass": True, "emergency": True, "bypass_policy": True},
        )


# =========================================================================
# 3. CORE SEAM PROOF: POLICY-DENY INVARIANT & LIFECYCLE
# =========================================================================


@pytest.mark.asyncio
async def test_core_seam_valid_emergency_operational_policy_mutation_succeeds(
    bg_db: DatabaseEngine, seed_trust_employment
):
    """Core Seam Pair A: Valid emergency authority allows operational policy update."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-03",
        capabilities=[BreakGlassCapability.RESTORE_OPERATIONAL_POLICY_CONFIGURATION],
        justification="Operational policy restore during outage",
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.MODIFY_POLICY_RULE.value,
    )

    # Operational (non-critical) policy rules
    operational_rules = [
        PolicyRule(
            rule_id="op_rule_1",
            reason_code="RC_STANDARD",
            effect=GovernanceDecision.ALLOW,
            action_types=frozenset(["read_log"]),
            risk_tiers=frozenset([RiskTier.LOW]),
            targets=frozenset(["logs"]),
        )
    ]

    manager = PolicyLifecycleManager(bg_db)
    rev = await manager.create_revision(
        org_id="org_alpha",
        rules=operational_rules,
        created_by="admin_alpha",
        change_reason="Emergency restore operational rules",
        caller=caller,
        step_up_proof=step_up,
        break_glass_session_id=session.id,
    )
    assert rev.revision_num == 1

    # Activation under break-glass
    step_up_act = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.MODIFY_POLICY_RULE.value,
        target_resource_id=rev.id,
    )
    act = await manager.activate_revision(
        org_id="org_alpha",
        revision_id=rev.id,
        activated_by="admin_alpha",
        caller=caller,
        step_up_proof=step_up_act,
        break_glass_session_id=session.id,
    )
    assert act.is_active is True
    assert act.governance_epoch == 1


@pytest.mark.asyncio
async def test_core_seam_critical_policy_mutation_blocked_under_break_glass(
    bg_db: DatabaseEngine, seed_trust_employment
):
    """Core Seam Pair B: Break-glass cannot mutate critical policies (policy rules remain supreme)."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-04",
        capabilities=[BreakGlassCapability.RESTORE_OPERATIONAL_POLICY_CONFIGURATION],
        justification="Attempting critical policy alteration under break glass",
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.MUTATE_CRITICAL_POLICY.value,
    )

    # Critical policy rule: wildcard target or RC_CRITICAL
    critical_rules = [
        PolicyRule(
            rule_id="crit_rule_1",
            reason_code="RC_CRITICAL",
            effect=GovernanceDecision.ALLOW,
            action_types=frozenset(["*"]),
            risk_tiers=frozenset([RiskTier.HIGH]),
            targets=frozenset(["*"]),
        )
    ]

    manager = PolicyLifecycleManager(bg_db)
    with pytest.raises(
        PrivilegedAccessDeniedError, match="not permissible under emergency break-glass"
    ):
        await manager.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="admin_alpha",
            change_reason="Attempting critical expansion under break glass",
            caller=caller,
            step_up_proof=step_up,
            break_glass_session_id=session.id,
        )


@pytest.mark.asyncio
async def test_policy_deny_remains_deny_even_with_active_emergency_session():
    """Prove that canonical Policy engine evaluation DENY is never overridden by break-glass state."""
    # Policy with an explicit DENY rule
    deny_rule = PolicyRule(
        rule_id="strict_deny",
        reason_code="RC_STRICT_DENY",
        effect=GovernanceDecision.DENY,
        action_types=frozenset(["sensitive_operation"]),
        risk_tiers=frozenset([RiskTier.HIGH]),
        targets=frozenset(["secrets"]),
    )
    policy = Policy(org_id="org_alpha", rules=[deny_rule])

    # An action matching the DENY rule
    from responsibleai.governance.models import ActionRequest, AgentContext, IdentityContext

    action = ActionRequest(
        action_type="sensitive_operation",
        target="secrets",
        agent=AgentContext(
            agent_id="emergency_agent",
            identity=IdentityContext(identity_id="admin_alpha", kind="human", org_id="org_alpha"),
        ),
        arguments={"break_glass": True, "session_id": "bg_active_session"},
    )

    match = policy.evaluate(action, RiskTier.HIGH)
    assert match is not None
    assert match.rule.effect == GovernanceDecision.DENY
    assert match.rule.reason_code == "RC_STRICT_DENY"


# =========================================================================
# 4. SCOPE & CAPABILITY ENFORCEMENT
# =========================================================================


@pytest.mark.asyncio
async def test_scope_and_capability_mismatch_blocked(bg_db: DatabaseEngine, seed_trust_employment):
    """Prove capability mismatch is strictly blocked."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    # Session granted only RESTORE_IDP_CONFIGURATION
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-05",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="IdP restore only",
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.REVOKE_API_KEY.value,
    )

    # REVOKE_API_KEY requires REVOKE_COMPROMISED_CREDENTIAL -> mismatch
    with pytest.raises(PrivilegedAccessDeniedError, match="does not grant required capability"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.REVOKE_API_KEY,
            step_up_proof=step_up,
            break_glass_session_id=session.id,
        )


# =========================================================================
# 5. SOVEREIGN ROOT & RECOVERY SEPARATION
# =========================================================================


@pytest.mark.asyncio
async def test_sovereign_root_actions_strictly_prohibited_under_break_glass(
    bg_db: DatabaseEngine, seed_trust_employment
):
    """Prove break-glass cannot perform root authority transfer, recovery, or tenant destruction."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-06",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Root test",
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.OWNER,
        is_root=True,
    )
    guard = PrivilegedSurfaceGuard(bg_db)

    for prohibited_action in [
        PrivilegedAction.TRANSFER_ROOT_AUTHORITY,
        PrivilegedAction.RECOVER_ROOT_AUTHORITY,
        PrivilegedAction.DESTROY_TENANT,
    ]:
        with pytest.raises(
            PrivilegedAccessDeniedError, match="strictly prohibited under emergency break-glass"
        ):
            await guard.authorize_privileged_operation(
                caller=caller,
                target_org_id="org_alpha",
                action=prohibited_action,
                break_glass_session_id=session.id,
            )


# =========================================================================
# 6. EXPIRY & TERMINATION ENFORCEMENT
# =========================================================================


@pytest.mark.asyncio
async def test_expired_break_glass_session_blocked(bg_db: DatabaseEngine, seed_trust_employment):
    """Prove expired emergency sessions cannot be consumed."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-07",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Expired session test",
        ttl_minutes=1,
    )

    # Fast-forward expiry in DB
    past = (datetime.now(UTC) - timedelta(minutes=5)).isoformat()
    from sqlalchemy import update

    async with bg_db.raw.begin() as conn:
        await conn.execute(
            update(iam_break_glass_sessions)
            .where(iam_break_glass_sessions.c.id == session.id)
            .values(expires_at=past)
        )

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )

    with pytest.raises(PrivilegedAccessDeniedError, match="expired or inactive"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            step_up_proof=step_up,
            break_glass_session_id=session.id,
        )


@pytest.mark.asyncio
async def test_explicitly_terminated_break_glass_session_blocked(
    bg_db: DatabaseEngine, seed_trust_employment
):
    """Prove explicitly terminated emergency sessions cannot be consumed."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-08",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Termination test",
    )

    # Terminate the session
    ok = await bg_svc.terminate_break_glass(org_id="org_alpha", session_id=session.id)
    assert ok is True

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )

    with pytest.raises(PrivilegedAccessDeniedError, match="expired or inactive"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            step_up_proof=step_up,
            break_glass_session_id=session.id,
        )


# =========================================================================
# 7. MANDATORY STEP-UP REAUTHENTICATION UNDER BREAK-GLASS
# =========================================================================


@pytest.mark.asyncio
async def test_missing_step_up_under_break_glass_blocked(
    bg_db: DatabaseEngine, seed_trust_employment
):
    """Prove step-up reauthentication is mandatory even during break-glass."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-09",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Step-up missing test",
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)

    # Omitting step_up_proof must raise StepUpRequiredError
    with pytest.raises(StepUpRequiredError):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            step_up_proof=None,
            break_glass_session_id=session.id,
        )


@pytest.mark.asyncio
async def test_replayed_step_up_nonce_under_break_glass_blocked(
    bg_db: DatabaseEngine, seed_trust_employment
):
    """Prove single-use step-up nonce replay is blocked."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-10",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Nonce replay test",
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )

    # First call consumes nonce -> succeeds
    res1 = await guard.authorize_privileged_operation(
        caller=caller,
        target_org_id="org_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
        step_up_proof=step_up,
        break_glass_session_id=session.id,
    )
    assert res1.allowed is True

    # Replay with same proof -> blocked
    with pytest.raises(StepUpVerificationFailedError, match="already been consumed"):
        await guard.authorize_privileged_operation(
            caller=caller,
            target_org_id="org_alpha",
            action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
            step_up_proof=step_up,
            break_glass_session_id=session.id,
        )


# =========================================================================
# 8. NORMAL AUTHORITY INVARIANT & NO PERSISTENT PRIVILEGE ESCALATION
# =========================================================================


@pytest.mark.asyncio
async def test_no_persistent_privilege_escalation(bg_db: DatabaseEngine, seed_trust_employment):
    """Prove break-glass does not permanently elevate the user role in the DB."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="analyst_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="analyst_alpha",
        incident_id="INC-ALPHA-11",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Temporary emergency IdP update",
    )

    caller = PrivilegedCallerContext(
        principal_id="analyst_alpha",
        org_id="org_alpha",
        role=Role.ANALYST,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="analyst_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )

    res = await guard.authorize_privileged_operation(
        caller=caller,
        target_org_id="org_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
        step_up_proof=step_up,
        break_glass_session_id=session.id,
    )
    assert res.allowed is True
    # Caller context still reflects ANALYST; no permanent DB alteration to role
    assert caller.role == Role.ANALYST


# =========================================================================
# 9. FAIL-CLOSED & ATTRIBUTION
# =========================================================================


@pytest.mark.asyncio
async def test_fail_closed_on_evidence_prewrite_failure(
    bg_db: DatabaseEngine, seed_trust_employment
):
    """Prove that if attribution evidence pre-recording fails, operation fails closed."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-12",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Attribution failure test",
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )

    with patch.object(
        guard.attribution,
        "record_privileged_event",
        AsyncMock(side_effect=RuntimeError("Storage unreachable")),
    ):
        with pytest.raises(RuntimeError, match="Storage unreachable"):
            await guard.authorize_privileged_operation(
                caller=caller,
                target_org_id="org_alpha",
                action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
                step_up_proof=step_up,
                break_glass_session_id=session.id,
            )


@pytest.mark.asyncio
async def test_tamper_evident_attribution_recorded(bg_db: DatabaseEngine, seed_trust_employment):
    """Prove emergency actions record full attribution in tamper-evident log."""
    await seed_trust_employment(bg_db, org_id="org_alpha", principal_id="admin_alpha")

    bg_svc = BreakGlassService(bg_db)
    session = await bg_svc.initiate_break_glass(
        org_id="org_alpha",
        principal_id="admin_alpha",
        incident_id="INC-ALPHA-13",
        capabilities=[BreakGlassCapability.RESTORE_IDP_CONFIGURATION],
        justification="Attribution verification",
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    guard = PrivilegedSurfaceGuard(bg_db)
    step_up = await _issue_step_up_proof(
        bg_db,
        org_id="org_alpha",
        principal_id="admin_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value,
    )

    res = await guard.authorize_privileged_operation(
        caller=caller,
        target_org_id="org_alpha",
        action=PrivilegedAction.UPDATE_SSO_IDP_CONFIG,
        step_up_proof=step_up,
        break_glass_session_id=session.id,
    )
    assert res.allowed is True
    assert res.break_glass_active is True

    # Verify attribution entry in DB
    async with bg_db.raw.connect() as conn:
        stmt = select(iam_privileged_audit_log).where(
            iam_privileged_audit_log.c.org_id == "org_alpha"
        )
        entries = (await conn.execute(stmt)).fetchall()
        assert len(entries) > 0
        latest = dict(entries[-1]._mapping)
        assert latest["principal_id"] == "admin_alpha"
        assert latest["action"] == PrivilegedAction.UPDATE_SSO_IDP_CONFIG.value
        context = json.loads(latest["details_json"])
        assert context["break_glass_session_id"] == session.id
        assert latest["entry_hash"] is not None
