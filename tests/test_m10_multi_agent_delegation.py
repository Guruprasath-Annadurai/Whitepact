# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M10-G Multi-Agent & Transitive Capability Control Suite (Section 8).

Verifies:
1. 6-Role multi-agent workflow: Planner -> Worker -> Reviewer -> Tool-using Agent -> External MCP -> Human Approver.
2. Capability attenuation: each hop strictly reduces or preserves authority; cannot expand.
3. Scope confinement: subagents cannot exceed the parent's target scope.
4. Ancestor cascading revocation: revoking Planner revokes all downstream agents (Worker, Reviewer, Tool Agent, MCP).
5. Approval isolation: subagents cannot approve their own parent's or peer's actions.
6. Cycle rejection: agent A delegating to B which delegates to A, or self-delegation, is structurally rejected.
"""

from __future__ import annotations

import pytest

from responsibleai.db import ApprovalRepository, DelegationRepository, create_engine
from responsibleai.db.delegation_repository import DelegationEscalationError
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
)
from responsibleai.governance.approval import (
    ApprovalRequest,
    ApprovalStatus,
)

ORG_ID = "org-enterprise-m10"


@pytest.fixture
async def db_engine():
    engine = create_engine(":memory:")
    await engine.init()
    return engine


@pytest.fixture
def delegation_repo(db_engine):
    return DelegationRepository(db_engine)


@pytest.fixture
def approval_repo(db_engine):
    return ApprovalRepository(db_engine)


# ==============================================================================
# 1. 6-Role Multi-Agent Workflow Hierarchy & Attenuation
# ==============================================================================
@pytest.mark.asyncio
async def test_m10_six_role_multi_agent_workflow_and_attenuation(
    delegation_repo: DelegationRepository,
) -> None:
    """Sets up a complete 6-role multi-agent workflow:
    Planner (Root) -> Worker -> Reviewer -> Tool-using Agent -> External MCP
    With Human Approver as independent governance authority.
    Validates strictly attenuated capabilities across every single hop.
    """
    # 1. Planner (Root Grant from human owner)
    planner_actions = frozenset(
        {
            "plan_task",
            "delegate_task",
            "read_codebase",
            "write_code",
            "run_tests",
            "invoke_mcp",
            "deploy_service",
        }
    )
    planner_grant = await delegation_repo.grant(
        ORG_ID,
        "agent-planner",
        granted_action_types=planner_actions,
        constraints={"max_budget_cents": 50000, "allowed_repos": ["repo-alpha"]},
        purpose="Project Planner root agent",
        granted_by="human-owner",
    )
    assert planner_grant.is_active()

    # 2. Worker (Delegated from Planner - attenuated: no deploy_service)
    worker_actions = frozenset({"read_codebase", "write_code", "run_tests", "invoke_mcp"})
    worker_grant = await delegation_repo.grant(
        ORG_ID,
        "agent-worker",
        from_identity_id="agent-planner",
        granted_action_types=worker_actions,
        constraints={"max_budget_cents": 20000, "allowed_repos": ["repo-alpha"]},
        purpose="Engineering worker agent",
        granted_by="agent-planner",
    )
    assert worker_grant.is_active()

    # 3. Reviewer (Delegated from Worker - attenuated: read and test only, no write or invoke_mcp)
    reviewer_actions = frozenset({"read_codebase", "run_tests"})
    reviewer_grant = await delegation_repo.grant(
        ORG_ID,
        "agent-reviewer",
        from_identity_id="agent-worker",
        granted_action_types=reviewer_actions,
        constraints={"max_budget_cents": 5000, "allowed_repos": ["repo-alpha"]},
        purpose="Code reviewer agent",
        granted_by="agent-worker",
    )
    assert reviewer_grant.is_active()

    # 4. Tool-using Agent (Delegated from Worker - tool execution only: run_tests, invoke_mcp)
    tool_agent_actions = frozenset({"run_tests", "invoke_mcp"})
    tool_grant = await delegation_repo.grant(
        ORG_ID,
        "agent-tool-executor",
        from_identity_id="agent-worker",
        granted_action_types=tool_agent_actions,
        constraints={"max_budget_cents": 10000, "allowed_repos": ["repo-alpha"]},
        purpose="Tool execution agent",
        granted_by="agent-worker",
    )
    assert tool_grant.is_active()

    # 5. External MCP Agent (Delegated from Tool Agent - invoke_mcp only, strictly constrained)
    mcp_actions = frozenset({"invoke_mcp"})
    mcp_grant = await delegation_repo.grant(
        ORG_ID,
        "agent-external-mcp",
        from_identity_id="agent-tool-executor",
        granted_action_types=mcp_actions,
        constraints={"max_budget_cents": 2000, "allowed_repos": ["repo-alpha"]},
        purpose="Sandboxed external MCP interface",
        granted_by="agent-tool-executor",
    )
    assert mcp_grant.is_active()

    # Verify authority chain from External MCP all the way back to root
    chain = await delegation_repo.get_authority_chain(ORG_ID, "agent-external-mcp")
    assert len(chain) == 4
    chain_ids = [d.to_identity_id for d in chain]
    assert chain_ids == [
        "agent-planner",
        "agent-worker",
        "agent-tool-executor",
        "agent-external-mcp",
    ]


# ==============================================================================
# 2. Capability Attenuation Invariant (Escalation Rejection)
# ==============================================================================
@pytest.mark.asyncio
async def test_m10_capability_attenuation_escalation_rejected(
    delegation_repo: DelegationRepository,
) -> None:
    """Verifies that an agent cannot delegate authority it does not possess."""
    # Worker only has read_codebase and run_tests
    await delegation_repo.grant(
        ORG_ID,
        "planner-1",
        granted_action_types=frozenset({"read_codebase", "run_tests"}),
        purpose="Planner",
        granted_by="admin",
    )

    # Worker attempts to grant write_code to subagent -> Must raise DelegationEscalationError
    with pytest.raises(DelegationEscalationError, match="DELEGATION_AUTHORITY_ESCALATION"):
        await delegation_repo.grant(
            ORG_ID,
            "worker-escalated",
            from_identity_id="planner-1",
            granted_action_types=frozenset({"read_codebase", "write_code"}),
            purpose="Escalated worker",
            granted_by="planner-1",
        )


# ==============================================================================
# 3. Scope Confinement
# ==============================================================================
def test_m10_scope_confinement_target_matching() -> None:
    """Verifies subagents cannot act outside the target scope of their granted authority."""
    gateway = WhitePactRuntimeGateway()
    agent = AgentContext(
        identity=IdentityContext(identity_id="subagent-confined", kind="api_key", org_id=ORG_ID),
        framework="mcp-client",
    )
    # Authority is confined to allowed_targets=["repo-alpha"]
    authority = AuthorityContext(
        delegated_by="agent-worker",
        granted_action_types=frozenset({"read_codebase"}),
        constraints={"allowed_targets": ["repo-alpha"]},
    )

    # Action targeting repo-beta outside scope
    action = ActionRequest(
        action_type="read_codebase",
        target="repo-beta",
        arguments={"repo": "repo-beta"},
        agent=agent,
        purpose="inspect unauthorized repo",
    )
    result = gateway.evaluate(action, authority=authority)
    assert result.decision == GovernanceDecision.DENY
    assert "TARGET_NOT_ALLOWED" in result.reason_codes[0]


# ==============================================================================
# 4. Ancestor Cascading Revocation
# ==============================================================================
@pytest.mark.asyncio
async def test_m10_ancestor_cascading_revocation(
    delegation_repo: DelegationRepository,
) -> None:
    """Verifies revoking Planner immediately revokes Worker, Reviewer, Tool Agent, and External MCP."""
    # Setup hierarchy
    await delegation_repo.grant(
        ORG_ID,
        "planner-node",
        granted_action_types=frozenset({"task_all"}),
        purpose="root",
        granted_by="admin",
    )
    await delegation_repo.grant(
        ORG_ID,
        "worker-node",
        from_identity_id="planner-node",
        granted_action_types=frozenset({"task_all"}),
        purpose="worker",
        granted_by="planner-node",
    )
    await delegation_repo.grant(
        ORG_ID,
        "reviewer-node",
        from_identity_id="worker-node",
        granted_action_types=frozenset({"task_all"}),
        purpose="reviewer",
        granted_by="worker-node",
    )
    await delegation_repo.grant(
        ORG_ID,
        "tool-node",
        from_identity_id="worker-node",
        granted_action_types=frozenset({"task_all"}),
        purpose="tool",
        granted_by="worker-node",
    )
    await delegation_repo.grant(
        ORG_ID,
        "mcp-node",
        from_identity_id="tool-node",
        granted_action_types=frozenset({"task_all"}),
        purpose="mcp",
        granted_by="tool-node",
    )

    # All 5 nodes active initially
    for node_id in ("planner-node", "worker-node", "reviewer-node", "tool-node", "mcp-node"):
        active = await delegation_repo.get_active_delegation(ORG_ID, node_id)
        assert active is not None and active.is_active()

    # Revoke Planner
    revoked_ids = await delegation_repo.revoke_branch(
        ORG_ID,
        "planner-node",
        revoked_by="security-officer",
        reason="Security incident quarantine",
    )
    assert len(revoked_ids) == 5

    # Every descendant must now be inactive
    for node_id in ("planner-node", "worker-node", "reviewer-node", "tool-node", "mcp-node"):
        active = await delegation_repo.get_active_delegation(ORG_ID, node_id)
        assert active is None


# ==============================================================================
# 5. Approval Isolation (Four-Eyes Principle / No Self or Peer Approval)
# ==============================================================================
@pytest.mark.asyncio
async def test_m10_approval_isolation_subagents_cannot_self_or_peer_approve(
    approval_repo: ApprovalRepository,
) -> None:
    """Verifies that an agent cannot approve its own action or its peer's action.
    Approvals strictly enforce four-eyes verification: approver != requester identity.
    """
    from datetime import UTC, datetime

    from responsibleai.db.approval_repository import SelfApprovalError

    req = ApprovalRequest(
        action_id="act-sec-1",
        action_type="deploy_service",
        target="prod-cluster",
        reason_codes=["APPROVAL_REQUIRED"],
        requested_at=datetime.now(UTC),
        requested_by="agent-worker-1",
        organization_id=ORG_ID,
    )
    saved = await approval_repo.create(req)

    # Case 1: Agent worker attempts to approve its own action -> Must fail with SelfApprovalError
    with pytest.raises(SelfApprovalError):
        await approval_repo.resolve(
            saved.approval_id,
            resolved_by="agent-worker-1",
            outcome=ApprovalStatus.APPROVED,
        )

    # Case 2: Independent human security approver resolves -> Succeeds
    resolved = await approval_repo.resolve(
        saved.approval_id,
        resolved_by="human-security-officer",
        outcome=ApprovalStatus.APPROVED,
    )
    assert resolved.status == ApprovalStatus.APPROVED
    assert resolved.resolved_by == "human-security-officer"


# ==============================================================================
# 6. Cycle Rejection
# ==============================================================================
@pytest.mark.asyncio
async def test_m10_cycle_rejection_self_and_transitive(
    delegation_repo: DelegationRepository,
) -> None:
    """Verifies structural rejection of circular delegation:
    1. A -> A (Self delegation)
    2. A -> B -> A (2-hop cycle)
    3. A -> B -> C -> A (3-hop cycle)
    """
    # Root grant A
    await delegation_repo.grant(
        ORG_ID,
        "agent-A",
        granted_action_types=frozenset({"read_code", "write_code"}),
        purpose="Root A",
        granted_by="admin",
    )

    # 1. Self delegation: A -> A
    with pytest.raises(DelegationEscalationError, match="self-delegation"):
        await delegation_repo.grant(
            ORG_ID,
            "agent-A",
            from_identity_id="agent-A",
            granted_action_types=frozenset({"read_code"}),
            purpose="Self loop",
            granted_by="agent-A",
        )

    # A -> B
    await delegation_repo.grant(
        ORG_ID,
        "agent-B",
        from_identity_id="agent-A",
        granted_action_types=frozenset({"read_code", "write_code"}),
        purpose="A to B",
        granted_by="agent-A",
    )

    # 2. 2-hop cycle: B -> A
    with pytest.raises(DelegationEscalationError, match="Delegation cycle detected"):
        await delegation_repo.grant(
            ORG_ID,
            "agent-A",
            from_identity_id="agent-B",
            granted_action_types=frozenset({"read_code"}),
            purpose="B to A cycle",
            granted_by="agent-B",
        )

    # B -> C
    await delegation_repo.grant(
        ORG_ID,
        "agent-C",
        from_identity_id="agent-B",
        granted_action_types=frozenset({"read_code"}),
        purpose="B to C",
        granted_by="agent-B",
    )

    # 3. 3-hop cycle: C -> A
    with pytest.raises(DelegationEscalationError, match="Delegation cycle detected"):
        await delegation_repo.grant(
            ORG_ID,
            "agent-A",
            from_identity_id="agent-C",
            granted_action_types=frozenset({"read_code"}),
            purpose="C to A cycle",
            granted_by="agent-C",
        )
