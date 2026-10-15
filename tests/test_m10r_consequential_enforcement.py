# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M10-R Consequential Execution Path Enforcement Suite.

Proves that WhitePact security protections are enforced on real consequential
execution paths (InternalToolExecutor, apply_governance, and MCP tool dispatch),
rather than merely being evaluated as disconnected standalone functions.

Verifies:
1. End-to-end tool execution through apply_governance() -> InternalToolExecutor -> tool result.
2. Immediate denial blocks execution: dispatch_tool() is never reached when gateway denies.
3. Single-use replay protection: reusing an ExecutionAuthorization raises AuthorizationAlreadyConsumedError.
4. Action digest tampering protection: mutating arguments after authorization raises AuthorizationActionMismatchError.
5. Revocation epoch invalidation: bumping epoch between authorization and execution blocks dispatch.
6. Target drift protection: target fingerprint change raises AuthorizationTargetDriftError.
7. Expiry protection: expired authorization raises AuthorizationExpiredError.
8. Durable admission in PostgreSQL: nonces are transactionally committed and consumed.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import insert

from responsibleai.db import (
    ApprovalRepository,
    DelegationRepository,
    EvidenceRepository,
    OrgAuthorityCeilingRepository,
    OrgRepository,
    PolicyRepository,
    WorkflowRuleRepository,
    create_engine,
)
from responsibleai.db.consent_proof_repository import ConsentProofRepository
from responsibleai.db.engine import organizations
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
)
from responsibleai.db.migrate import run_migrations_or_raise
from responsibleai.db.revocation_epoch_repository import (
    RevocationEpochRepository,
)
from responsibleai.db.root_authority_repository import RootAuthorityRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
    InternalToolExecutor,
    WhitePactRuntimeGateway,
    authorize_execution,
)
from responsibleai.governance.authority_resolver import AuthorityResolver
from responsibleai.governance.execution import (
    AuthorizationActionMismatchError,
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationTargetDriftError,
    check_target_fingerprint,
)
from responsibleai.integrations.client import TrustClient
from responsibleai.mcp.governance_integration import GovernanceServices, apply_governance
from responsibleai.rbac.models import OrgContext, Role
from tests.pg_test_url import create_isolated_database, database_url, drop_isolated_database

pytestmark = pytest.mark.asyncio


@pytest.fixture
async def pg_engine():
    """Provision a clean, disposable PostgreSQL database with full schema applied."""
    admin_url, db_name = await create_isolated_database("m10r_consequential")
    raw_pg_url = database_url(admin_url, db_name)
    async_pg_url = raw_pg_url.replace("postgresql://", "postgresql+asyncpg://")

    await run_migrations_or_raise(raw_pg_url)

    engine = create_engine(async_pg_url)
    await engine.init(auto_create_tables=False)

    try:
        yield engine
    finally:
        await engine.close()
        await drop_isolated_database(admin_url, db_name)


async def _setup_test_org(engine: Any, org_id: str, key_id: str) -> None:
    now = datetime.now(UTC).isoformat()
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name=f"Org {org_id}",
                slug=f"slug-{org_id}",
                monthly_budget_usd=10000.0,
                created_at=now,
                plan="ENTERPRISE",
            )
        )


async def test_end_to_end_consequential_tool_dispatch(
    pg_engine: Any, seed_runtime_authority: Any
) -> None:
    """Proves end-to-end consequential tool dispatch:
    1. Caller requests 'rai_health' tool.
    2. Authority is resolved, policy allows.
    3. apply_governance() authorizes execution and calls InternalToolExecutor.
    4. InternalToolExecutor verifies authorization, commits nonce to PostgreSQL, and invokes tool.
    5. Outcome records successful execution with real tool output.
    """
    org_id = "org-m10r-e2e"
    key_id = "key-m10r-e2e"
    await _setup_test_org(pg_engine, org_id, key_id)

    await seed_runtime_authority(
        pg_engine,
        organization_id=org_id,
        principal_id=key_id,
        action_types=("rai_health",),
        targets=("rai_health",),
    )

    services = GovernanceServices(
        gateway=WhitePactRuntimeGateway(),
        evidence_repo=EvidenceRepository(pg_engine),
        approval_repo=ApprovalRepository(pg_engine),
        policy_repo=PolicyRepository(pg_engine),
        trust_client=TrustClient(cache_ttl_minutes=0),
        ceiling_repo=OrgAuthorityCeilingRepository(pg_engine),
        workflow_rule_repo=WorkflowRuleRepository(pg_engine),
        delegation_repo=DelegationRepository(pg_engine),
        nonce_repo=ExecutionNonceRepository(pg_engine),
        epoch_repo=RevocationEpochRepository(pg_engine),
        org_repo=OrgRepository(pg_engine),
        authority_resolver=AuthorityResolver(
            RootAuthorityRepository(pg_engine),
            ConsentProofRepository(pg_engine),
            DelegationRepository(pg_engine),
        ),
    )

    ctx = OrgContext(org_id=org_id, key_id=key_id, role=Role.ANALYST, org_name="Test")

    # Apply governance to real tool 'rai_health'
    outcome = await apply_governance(
        name="rai_health",
        arguments={},
        ctx=ctx,
        services=services,
        purpose="automated-test",
    )

    assert outcome.proceed is True, f"Expected proceed=True, got: {outcome.blocked_response}"
    assert outcome.result is not None
    assert isinstance(outcome.result, dict)
    assert outcome.result.get("status") == "ok"

    # Verify that an evidence record was persisted in PostgreSQL
    evidence_rows = await services.evidence_repo.list_for_org(org_id)
    assert len(evidence_rows) >= 1
    assert evidence_rows[0].action_type == "rai_health"
    assert evidence_rows[0].decision == GovernanceDecision.ALLOW.value


async def test_denied_governance_never_invokes_executor(
    pg_engine: Any, seed_runtime_authority: Any
) -> None:
    """Proves that when governance evaluates to DENY, InternalToolExecutor is NEVER reached
    and the tool is structurally blocked from execution.
    """
    org_id = "org-m10r-deny"
    key_id = "key-m10r-deny"
    await _setup_test_org(pg_engine, org_id, key_id)

    # Seed authority only for 'rai_health', NOT for 'unauthorized_action'
    await seed_runtime_authority(
        pg_engine,
        organization_id=org_id,
        principal_id=key_id,
        action_types=("rai_health",),
        targets=("rai_health",),
    )

    services = GovernanceServices(
        gateway=WhitePactRuntimeGateway(),
        evidence_repo=EvidenceRepository(pg_engine),
        approval_repo=ApprovalRepository(pg_engine),
        policy_repo=PolicyRepository(pg_engine),
        trust_client=TrustClient(cache_ttl_minutes=0),
        ceiling_repo=OrgAuthorityCeilingRepository(pg_engine),
        workflow_rule_repo=WorkflowRuleRepository(pg_engine),
        delegation_repo=DelegationRepository(pg_engine),
        nonce_repo=ExecutionNonceRepository(pg_engine),
        epoch_repo=RevocationEpochRepository(pg_engine),
        org_repo=OrgRepository(pg_engine),
        authority_resolver=AuthorityResolver(
            RootAuthorityRepository(pg_engine),
            ConsentProofRepository(pg_engine),
            DelegationRepository(pg_engine),
        ),
    )

    ctx = OrgContext(org_id=org_id, key_id=key_id, role=Role.ANALYST, org_name="Test")

    with patch.object(InternalToolExecutor, "execute", AsyncMock()) as mock_execute:
        outcome = await apply_governance(
            name="rai_scan",  # ungranted action
            arguments={"target": "http://example.com"},
            ctx=ctx,
            services=services,
            purpose="automated-test",
        )

        assert outcome.proceed is False
        assert outcome.blocked_response is not None
        assert outcome.blocked_response["error"] == "governance_denied"
        # Tool execution was NEVER dispatched
        mock_execute.assert_not_called()


async def test_replay_attack_on_internal_tool_executor_rejected(pg_engine: Any) -> None:
    """Proves that replay attacks on InternalToolExecutor are rejected:
    An attacker who captures a valid ExecutionAuthorization and tries to execute it
    a second time is stopped by AuthorizationAlreadyConsumedError.
    """
    nonce_repo = ExecutionNonceRepository(pg_engine)
    epoch_repo = RevocationEpochRepository(pg_engine)
    org_id = "org-m10r-replay"
    await _setup_test_org(pg_engine, org_id, "key-1")

    current_epoch = (await epoch_repo.current(org_id)).epoch

    agent = AgentContext(
        identity=IdentityContext(identity_id="key-1", kind="api_key", org_id=org_id),
        organization_id=org_id,
        agent_id="agent-1",
    )
    action = ActionRequest(agent=agent, action_type="rai_health", target="rai_health", arguments={})
    decision = DecisionResult(decision=GovernanceDecision.ALLOW, action_id=action.action_id)

    auth = authorize_execution(decision, action, revocation_epoch=current_epoch)

    executor = InternalToolExecutor(nonce_repo=nonce_repo)

    # First execution succeeds
    res1 = await executor.execute(auth, action)
    assert res1.get("status") == "ok"
    assert auth.consumed is True

    # Second execution with exact same authorization MUST raise AuthorizationAlreadyConsumedError
    with pytest.raises(AuthorizationAlreadyConsumedError):
        await executor.execute(auth, action)


async def test_argument_tampering_rejected_by_action_digest(pg_engine: Any) -> None:
    """Proves that tampering with action arguments between authorization and execution
    is detected and rejected by action digest verification in InternalToolExecutor.
    """
    org_id = "org-m10r-tamper"
    await _setup_test_org(pg_engine, org_id, "key-1")

    agent = AgentContext(
        identity=IdentityContext(identity_id="key-1", kind="api_key", org_id=org_id),
        organization_id=org_id,
        agent_id="agent-1",
    )
    # Authorized with benign argument
    authorized_action = ActionRequest(
        agent=agent,
        action_type="rai_health",
        target="rai_health",
        arguments={"mode": "readonly"},
    )
    decision = DecisionResult(
        decision=GovernanceDecision.ALLOW, action_id=authorized_action.action_id
    )

    auth = authorize_execution(decision, authorized_action)

    executor = InternalToolExecutor()

    # Attacker mutates the action to dangerous arguments
    tampered_action = ActionRequest(
        agent=agent,
        action_type="rai_health",
        target="rai_health",
        arguments={"mode": "admin_escalate"},
    )

    with pytest.raises(AuthorizationActionMismatchError):
        await executor.execute(auth, tampered_action)


async def test_revocation_epoch_invalidation_blocks_execution(pg_engine: Any) -> None:
    """Proves that bumping the organization revocation epoch between decision and execution
    immediately invalidates the permit and prevents execution dispatch.
    """
    nonce_repo = ExecutionNonceRepository(pg_engine)
    epoch_repo = RevocationEpochRepository(pg_engine)
    org_id = "org-m10r-revoked-epoch"
    await _setup_test_org(pg_engine, org_id, "key-1")

    initial_epoch = (await epoch_repo.current(org_id)).epoch

    agent = AgentContext(
        identity=IdentityContext(identity_id="key-1", kind="api_key", org_id=org_id),
        organization_id=org_id,
        agent_id="agent-1",
    )
    action = ActionRequest(agent=agent, action_type="rai_health", target="rai_health", arguments={})
    decision = DecisionResult(decision=GovernanceDecision.ALLOW, action_id=action.action_id)

    # Permit issued at initial_epoch
    auth = authorize_execution(decision, action, revocation_epoch=initial_epoch)

    # Admin revokes session/epoch before executor runs
    bump_res = await epoch_repo.bump(org_id)
    assert bump_res.epoch > initial_epoch

    executor = InternalToolExecutor(nonce_repo=nonce_repo)

    # Execution MUST be refused because epoch moved
    from responsibleai.db.execution_nonce_repository import StaleRevocationEpochError

    with pytest.raises(StaleRevocationEpochError):
        await executor.execute(auth, action)


async def test_target_drift_and_expiry_protection() -> None:
    """Proves target drift and expiration protection in ExecutionAuthorization."""
    agent = AgentContext(
        identity=IdentityContext(identity_id="key-1", kind="api_key", org_id="org-drift"),
        organization_id="org-drift",
        agent_id="agent-1",
    )
    action = ActionRequest(
        agent=agent, action_type="remote_tool", target="srv-1::tool", arguments={}
    )
    decision = DecisionResult(decision=GovernanceDecision.ALLOW, action_id=action.action_id)

    # Target fingerprint drift check
    auth_drift = authorize_execution(decision, action, target_fingerprint="sha256-original-config")
    with pytest.raises(AuthorizationTargetDriftError):
        check_target_fingerprint(auth_drift, current_target_fingerprint="sha256-tampered-config")

    # Expiry check
    auth_expired = authorize_execution(decision, action, ttl_seconds=-1)
    executor = InternalToolExecutor()
    with pytest.raises(AuthorizationExpiredError):
        await executor.execute(auth_expired, action)
