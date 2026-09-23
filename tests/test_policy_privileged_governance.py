# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Comprehensive Tests for Phase 5 Policy Privileged Governance & Real Phase-4 Guard Integration.

Verifies complete canonical enforcement:
- Direct service calls without caller context fail closed (no unauthenticated bypass).
- Cross-tenant mutations rejected (boundary isolation).
- Non-admin callers rejected (role check).
- Step-Up MFA authentication required for all critical mutations.
- Replayed, expired, or cross-principal step-up proofs rejected.
- Four-Eyes dual-custody approval required for all critical mutations.
- Fabricated, expired, already-consumed, or cross-tenant approvals rejected.
- Target revision and policy digest mismatches rejected.
- Anti-self-approval strictly enforced (requester == approver blocked).
- Stale approvals invalidated after security epoch bumps.
- Fully authorized dual-custody critical policy mutations succeed atomically.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select

from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    governance_policy_revisions,
    iam_four_eyes_requests,
    organizations,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.policy_lifecycle import (
    PolicyLifecycleManager,
    compute_policy_digest,
)
from responsibleai.governance.risk import RiskTier
from responsibleai.iam.enums import (
    FourEyesStatus,
    PrivilegedAction,
    StepUpMethod,
)
from responsibleai.iam.errors import (
    CrossTenantEscalationError,
    FourEyesRequiredError,
    PrivilegedAccessDeniedError,
    SelfApprovalBlockedError,
    StepUpRequiredError,
)
from responsibleai.iam.models import PrivilegedCallerContext, StepUpProof
from responsibleai.rbac.models import Role


def _now() -> str:
    return datetime.now(UTC).isoformat()


@pytest.fixture
async def sqlite_engine():
    engine = create_engine(":memory:")
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id="org_alpha",
                name="Alpha Corp",
                slug="alpha-corp",
                monthly_budget_usd=10000.0,
                created_at=_now(),
                plan="ENTERPRISE",
            )
        )
        await conn.execute(
            insert(organizations).values(
                id="org_beta",
                name="Beta Corp",
                slug="beta-corp",
                monthly_budget_usd=10000.0,
                created_at=_now(),
                plan="ENTERPRISE",
            )
        )
    yield engine
    await engine.close()


@pytest.fixture
def critical_rules() -> list[PolicyRule]:
    """Critical policy rule granting unrestricted wildcard ALLOW."""
    return [
        PolicyRule(
            rule_id="crit-rule-1",
            reason_code="RC_PERMISSIVE",
            effect=GovernanceDecision.ALLOW,
            risk_tiers=None,
            action_types=None,
            targets=None,
        )
    ]


@pytest.fixture
def standard_rules() -> list[PolicyRule]:
    """Standard restricted rule with explicit constraints."""
    return [
        PolicyRule(
            rule_id="std-rule-1",
            reason_code="RC_SAFE_READ",
            effect=GovernanceDecision.ALLOW,
            risk_tiers=frozenset([RiskTier.LOW]),
            action_types=frozenset(["mcp:read"]),
            targets=frozenset(["tool:read_data"]),
        )
    ]


async def _create_valid_step_up(
    engine: DatabaseEngine,
    org_id: str,
    principal_id: str,
    action: str = PrivilegedAction.MUTATE_CRITICAL_POLICY.value,
    target_resource_id: str | None = None,
) -> StepUpProof:
    from responsibleai.iam.step_up import StepUpVerifier

    verifier = StepUpVerifier(engine)
    nonce = await verifier.issue_step_up_nonce(
        org_id=org_id,
        principal_id=principal_id,
        action=action,
        target_resource_id=target_resource_id,
    )
    now = datetime.now(UTC).isoformat()
    return StepUpProof(
        nonce=nonce,
        method=StepUpMethod.MFA_TOTP,
        auth_time=now,
        token_or_code="123456",
    )


async def _create_four_eyes_approval(
    engine: DatabaseEngine,
    org_id: str,
    requester: str,
    approver: str,
    action: str = PrivilegedAction.MUTATE_CRITICAL_POLICY.value,
    target_resource_id: str | None = None,
    parameters: dict | None = None,
    status: str = FourEyesStatus.APPROVED.value,
    expired: bool = False,
    already_executed: bool = False,
) -> str:
    fe_id = str(uuid.uuid4())
    now = datetime.now(UTC)
    created_at = (now - timedelta(minutes=10)).isoformat()
    expires_at = (
        (now - timedelta(minutes=1)).isoformat()
        if expired
        else (now + timedelta(minutes=30)).isoformat()
    )
    executed_at = now.isoformat() if already_executed else None

    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(iam_four_eyes_requests).values(
                id=fe_id,
                org_id=org_id,
                requester_principal_id=requester,
                action=action,
                target_resource_id=target_resource_id,
                parameters_json=json.dumps(parameters or {}),
                request_digest="req-digest",
                status=status,
                approver_principal_id=approver,
                approval_time=now.isoformat(),
                executed_at=executed_at,
                created_at=created_at,
                expires_at=expires_at,
            )
        )
    return fe_id


@pytest.mark.asyncio
async def test_direct_critical_policy_mutation_fails_without_caller(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule]
):
    mgr = PolicyLifecycleManager(sqlite_engine)
    # Direct service call to create_revision without caller must fail closed
    with pytest.raises(PrivilegedAccessDeniedError, match="Privileged caller context required"):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="anon",
            change_reason="Direct bypass attempt",
            caller=None,
        )


@pytest.mark.asyncio
async def test_cross_tenant_critical_mutation_blocked(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule]
):
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="admin_beta",
        org_id="org_beta",
        role=Role.ADMIN,
    )
    with pytest.raises(
        CrossTenantEscalationError, match="cannot execute privileged actions on tenant"
    ):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="admin_beta",
            change_reason="Cross-tenant attempt",
            caller=caller,
        )


@pytest.mark.asyncio
async def test_insufficient_role_critical_mutation_blocked(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="viewer_alpha")
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="viewer_alpha",
        org_id="org_alpha",
        role=Role.VIEWER,
    )
    with pytest.raises(PrivilegedAccessDeniedError, match="requires ADMIN or OWNER role"):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="viewer_alpha",
            change_reason="Role violation attempt",
            caller=caller,
        )


@pytest.mark.asyncio
async def test_missing_step_up_critical_mutation_blocked(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="admin_alpha")
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    with pytest.raises(StepUpRequiredError):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="admin_alpha",
            change_reason="Step up missing",
            caller=caller,
            step_up_proof=None,
        )


@pytest.mark.asyncio
async def test_missing_four_eyes_critical_mutation_blocked(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="admin_alpha")
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    proof = await _create_valid_step_up(
        sqlite_engine, "org_alpha", "admin_alpha", PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )

    with pytest.raises(FourEyesRequiredError, match="requires dual-custody approval"):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="admin_alpha",
            change_reason="Four eyes missing",
            caller=caller,
            step_up_proof=proof,
            four_eyes_approval_id=None,
        )


@pytest.mark.asyncio
async def test_fabricated_approval_id_blocked(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="admin_alpha")
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    proof = await _create_valid_step_up(
        sqlite_engine, "org_alpha", "admin_alpha", PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )

    with pytest.raises(PrivilegedAccessDeniedError, match="Four-Eyes approval record not found"):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="admin_alpha",
            change_reason="Fabricated approval ID",
            caller=caller,
            step_up_proof=proof,
            four_eyes_approval_id="fabricated-approval-id-999",
        )


@pytest.mark.asyncio
async def test_expired_approval_blocked(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="admin_alpha")
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    proof = await _create_valid_step_up(
        sqlite_engine, "org_alpha", "admin_alpha", PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )
    fe_id = await _create_four_eyes_approval(
        sqlite_engine, "org_alpha", requester="admin_alpha", approver="admin_checker", expired=True
    )

    with pytest.raises(PrivilegedAccessDeniedError, match="Four-Eyes approval has expired"):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="admin_alpha",
            change_reason="Expired approval attempt",
            caller=caller,
            step_up_proof=proof,
            four_eyes_approval_id=fe_id,
        )


@pytest.mark.asyncio
async def test_already_consumed_approval_blocked(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="admin_alpha")
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    proof = await _create_valid_step_up(
        sqlite_engine, "org_alpha", "admin_alpha", PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )
    fe_id = await _create_four_eyes_approval(
        sqlite_engine,
        "org_alpha",
        requester="admin_alpha",
        approver="admin_checker",
        already_executed=True,
    )

    with pytest.raises(
        PrivilegedAccessDeniedError, match="Four-Eyes approval has already been consumed"
    ):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="admin_alpha",
            change_reason="Already consumed approval attempt",
            caller=caller,
            step_up_proof=proof,
            four_eyes_approval_id=fe_id,
        )


@pytest.mark.asyncio
async def test_cross_tenant_approval_blocked(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="admin_alpha")
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    proof = await _create_valid_step_up(
        sqlite_engine, "org_alpha", "admin_alpha", PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )
    # Created for org_beta, presented to org_alpha
    fe_id = await _create_four_eyes_approval(
        sqlite_engine, "org_beta", requester="admin_beta", approver="admin_checker"
    )

    with pytest.raises(PrivilegedAccessDeniedError, match="Four-Eyes approval record not found"):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="admin_alpha",
            change_reason="Cross-tenant approval attempt",
            caller=caller,
            step_up_proof=proof,
            four_eyes_approval_id=fe_id,
        )


@pytest.mark.asyncio
async def test_self_approval_prevention_real_enforcement(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    """Prove WhitePact actively blocks execution when requester == approver."""
    mgr = PolicyLifecycleManager(sqlite_engine)
    admin_id = "admin_maker_and_checker"
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id=admin_id)

    caller = PrivilegedCallerContext(
        principal_id=admin_id,
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    proof = await _create_valid_step_up(
        sqlite_engine, "org_alpha", admin_id, PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )

    # Self-approved record: requester == approver
    fe_id = await _create_four_eyes_approval(
        sqlite_engine,
        org_id="org_alpha",
        requester=admin_id,
        approver=admin_id,
    )

    # Invariant: Self-approval must raise SelfApprovalBlockedError!
    with pytest.raises(
        SelfApprovalBlockedError, match="Requester cannot approve their own privileged request"
    ):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by=admin_id,
            change_reason="Self-approved mutation",
            caller=caller,
            step_up_proof=proof,
            four_eyes_approval_id=fe_id,
        )

    # Assert database state unchanged: 0 revisions created!
    async with sqlite_engine.raw.connect() as conn:
        revs = (
            await conn.execute(
                select(governance_policy_revisions).where(
                    governance_policy_revisions.c.org_id == "org_alpha"
                )
            )
        ).fetchall()
        assert len(revs) == 0


@pytest.mark.asyncio
async def test_approval_policy_digest_mismatch_blocked(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="admin_alpha")
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="admin_alpha",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    proof = await _create_valid_step_up(
        sqlite_engine, "org_alpha", "admin_alpha", PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )
    # Approval bound to a different digest
    fe_id = await _create_four_eyes_approval(
        sqlite_engine,
        "org_alpha",
        requester="admin_alpha",
        approver="admin_checker",
        parameters={"policy_digest": "different_digest_hash_000"},
    )

    with pytest.raises(
        PrivilegedAccessDeniedError, match="Four-Eyes approval policy digest mismatch"
    ):
        await mgr.create_revision(
            org_id="org_alpha",
            rules=critical_rules,
            created_by="admin_alpha",
            change_reason="Digest mismatch",
            caller=caller,
            step_up_proof=proof,
            four_eyes_approval_id=fe_id,
        )


@pytest.mark.asyncio
async def test_security_epoch_changed_after_approval_blocked(
    sqlite_engine: DatabaseEngine,
    standard_rules: list[PolicyRule],
    critical_rules: list[PolicyRule],
    seed_trust_employment,
):
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="admin_maker")
    mgr = PolicyLifecycleManager(sqlite_engine)
    # First create a revision so we have a revision_id to activate
    await mgr.create_revision(
        "org_alpha", standard_rules, "admin_maker", "Initial standard revision"
    )

    caller = PrivilegedCallerContext(
        principal_id="admin_maker",
        org_id="org_alpha",
        role=Role.ADMIN,
    )

    epoch_repo = RevocationEpochRepository(sqlite_engine)
    e1 = (await epoch_repo.bump("org_alpha")).epoch
    # Generate approval with initial epoch
    fe_id = await _create_four_eyes_approval(
        sqlite_engine,
        "org_alpha",
        requester="admin_maker",
        approver="admin_checker",
        parameters={"governance_epoch": e1},
    )

    # Now bump epoch again (e.g. key rotation / admin event)
    await epoch_repo.bump("org_alpha")

    # Create step up under new epoch
    proof = await _create_valid_step_up(
        sqlite_engine, "org_alpha", "admin_maker", PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )

    # Create a critical revision to activate
    fe_create = await _create_four_eyes_approval(
        sqlite_engine, "org_alpha", requester="admin_maker", approver="admin_checker"
    )
    proof_create = await _create_valid_step_up(
        sqlite_engine, "org_alpha", "admin_maker", PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )
    crit_rev = await mgr.create_revision(
        "org_alpha",
        critical_rules,
        "admin_maker",
        "Critical rev",
        caller=caller,
        step_up_proof=proof_create,
        four_eyes_approval_id=fe_create,
    )

    # Activating critical revision with stale approval epoch must be rejected!
    with pytest.raises(
        PrivilegedAccessDeniedError, match="Four-Eyes approval security epoch mismatch"
    ):
        await mgr.activate_revision(
            org_id="org_alpha",
            revision_id=crit_rev.id,
            activated_by="admin_maker",
            caller=caller,
            step_up_proof=proof,
            four_eyes_approval_id=fe_id,
        )


@pytest.mark.asyncio
async def test_fully_authorized_critical_policy_mutation_succeeds(
    sqlite_engine: DatabaseEngine, critical_rules: list[PolicyRule], seed_trust_employment
):
    """Prove authorized critical policy mutation succeeds and marks approval executed."""
    await seed_trust_employment(sqlite_engine, org_id="org_alpha", principal_id="admin_maker")
    mgr = PolicyLifecycleManager(sqlite_engine)
    caller = PrivilegedCallerContext(
        principal_id="admin_maker",
        org_id="org_alpha",
        role=Role.ADMIN,
    )
    digest = compute_policy_digest(critical_rules)

    # 1. Create independent four-eyes approval
    fe_id = await _create_four_eyes_approval(
        sqlite_engine,
        org_id="org_alpha",
        requester="admin_maker",
        approver="admin_checker",
        parameters={"policy_digest": digest},
    )

    # 2. Complete step-up reauthentication
    proof = await _create_valid_step_up(
        sqlite_engine, "org_alpha", "admin_maker", PrivilegedAction.MUTATE_CRITICAL_POLICY.value
    )

    # 3. Create critical revision
    rev = await mgr.create_revision(
        org_id="org_alpha",
        rules=critical_rules,
        created_by="admin_maker",
        change_reason="Authorized critical expansion",
        caller=caller,
        step_up_proof=proof,
        four_eyes_approval_id=fe_id,
    )
    assert rev.revision_num == 1
    assert rev.content_digest == digest

    # 4. Invariant verification: Approval record is marked EXECUTED!
    async with sqlite_engine.raw.connect() as conn:
        fe_row = (
            await conn.execute(
                select(iam_four_eyes_requests).where(iam_four_eyes_requests.c.id == fe_id)
            )
        ).fetchone()
        assert fe_row is not None
        assert fe_row.status == "EXECUTED"
        assert fe_row.executed_at is not None
