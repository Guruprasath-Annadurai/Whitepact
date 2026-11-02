"""Tests for the Autonomy Budget (governance/autonomy_budget.py):
`recent_autonomous_action_count()`, its wiring into
`WhitePactRuntimeGateway.evaluate()`, and `OrgAutonomyBudgetRepository`.
"""

from __future__ import annotations

import pytest

from responsibleai.db import EvidenceRepository, OrgAutonomyBudgetRepository, create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    AutonomyBudgetPolicy,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
    recent_autonomous_action_count,
)
from responsibleai.governance.evidence import build_evidence_record


def _agent(org_id: str = "org-1") -> AgentContext:
    identity = IdentityContext(identity_id="agent-1", kind="api_key", org_id=org_id)
    return AgentContext(identity=identity, agent_id="agent-1", framework="mcp-client")


def _authority(**kwargs) -> AuthorityContext:
    kwargs.setdefault("delegated_by", "org-1")
    kwargs.setdefault("granted_action_types", frozenset({"mcp_tool_call"}))
    return AuthorityContext(**kwargs)


class TestGatewayAutonomyBudget:
    def _gateway_authority(self) -> tuple[WhitePactRuntimeGateway, AuthorityContext]:
        return WhitePactRuntimeGateway(), _authority()

    def test_no_budget_configured_allows_normally(self) -> None:
        gw, authority = self._gateway_authority()
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="x")
        result = gw.evaluate(action, authority)
        assert result.decision == GovernanceDecision.ALLOW

    def test_under_budget_allows_normally(self) -> None:
        gw, authority = self._gateway_authority()
        policy = AutonomyBudgetPolicy(max_autonomous_actions=5, window_minutes=60)
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="x")
        result = gw.evaluate(
            action, authority, autonomy_budget=policy, recent_autonomous_action_count=4
        )
        assert result.decision == GovernanceDecision.ALLOW

    def test_at_budget_requires_approval(self) -> None:
        gw, authority = self._gateway_authority()
        policy = AutonomyBudgetPolicy(max_autonomous_actions=5, window_minutes=60)
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="x")
        result = gw.evaluate(
            action, authority, autonomy_budget=policy, recent_autonomous_action_count=5
        )
        assert result.decision == GovernanceDecision.REQUIRE_APPROVAL
        assert any(code.startswith("AUTONOMY_BUDGET_EXCEEDED:") for code in result.reason_codes)

    def test_over_budget_requires_approval(self) -> None:
        gw, authority = self._gateway_authority()
        policy = AutonomyBudgetPolicy(max_autonomous_actions=5, window_minutes=60)
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="x")
        result = gw.evaluate(
            action, authority, autonomy_budget=policy, recent_autonomous_action_count=9
        )
        assert result.decision == GovernanceDecision.REQUIRE_APPROVAL

    def test_budget_overridden_by_hard_block(self) -> None:
        """A toxicity/injection DENY still wins even at budget -- the
        budget check only fires for what would otherwise be an
        autonomous ALLOW/ALLOW_WITH_REDACTION."""
        gw, authority = self._gateway_authority()
        policy = AutonomyBudgetPolicy(max_autonomous_actions=5, window_minutes=60)
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="x",
            arguments={"note": "I will kill you"},
        )
        result = gw.evaluate(
            action, authority, autonomy_budget=policy, recent_autonomous_action_count=99
        )
        assert result.decision == GovernanceDecision.DENY

    def test_budget_overrides_would_be_pii_redaction(self) -> None:
        """A call that would otherwise be ALLOW_WITH_REDACTION is
        forced to REQUIRE_APPROVAL once the budget is exhausted --
        redaction still counts as unsupervised execution."""
        gw, authority = self._gateway_authority()
        policy = AutonomyBudgetPolicy(max_autonomous_actions=5, window_minutes=60)
        action = ActionRequest(
            agent=_agent(),
            action_type="mcp_tool_call",
            target="x",
            arguments={"note": "contact me at a@b.com"},
        )
        result = gw.evaluate(
            action, authority, autonomy_budget=policy, recent_autonomous_action_count=5
        )
        assert result.decision == GovernanceDecision.REQUIRE_APPROVAL
        assert any(code.startswith("AUTONOMY_BUDGET_EXCEEDED:") for code in result.reason_codes)
        assert result.redacted_arguments is None

    def test_quarantine_still_wins_over_budget(self) -> None:
        gw, authority = self._gateway_authority()
        policy = AutonomyBudgetPolicy(max_autonomous_actions=5, window_minutes=60)
        action = ActionRequest(agent=_agent(), action_type="mcp_tool_call", target="x")
        result = gw.evaluate(
            action,
            authority,
            autonomy_budget=policy,
            recent_autonomous_action_count=99,
            recent_violation_count=5,
        )
        assert result.decision == GovernanceDecision.QUARANTINE


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def evidence_repo(engine):
    return EvidenceRepository(engine)


@pytest.fixture()
def autonomy_budget_repo(engine):
    return OrgAutonomyBudgetRepository(engine)


async def _seed_decision(
    evidence_repo: EvidenceRepository, decision: GovernanceDecision, *, org_id: str = "org-1"
) -> None:
    gw = WhitePactRuntimeGateway()
    agent = _agent(org_id=org_id)
    if decision == GovernanceDecision.DENY:
        action = ActionRequest(
            agent=agent,
            action_type="mcp_tool_call",
            target="x",
            arguments={"note": "I will kill you"},
        )
        authority = _authority()
    elif decision == GovernanceDecision.ALLOW_WITH_REDACTION:
        action = ActionRequest(
            agent=agent,
            action_type="mcp_tool_call",
            target="x",
            arguments={"note": "contact me at a@b.com"},
        )
        authority = _authority()
    else:
        action = ActionRequest(agent=agent, action_type="mcp_tool_call", target="x")
        authority = _authority()
    result = gw.evaluate(action, authority)
    assert result.decision == decision
    evidence = build_evidence_record(action, agent, authority, result)
    await evidence_repo.record(evidence)


class TestRecentAutonomousActionCount:
    async def test_zero_when_no_history(self, evidence_repo) -> None:
        count = await recent_autonomous_action_count(
            evidence_repo, "org-1", "agent-1", window_minutes=60
        )
        assert count == 0

    async def test_counts_allow_decisions(self, evidence_repo) -> None:
        for _ in range(3):
            await _seed_decision(evidence_repo, GovernanceDecision.ALLOW)
        count = await recent_autonomous_action_count(
            evidence_repo, "org-1", "agent-1", window_minutes=60
        )
        assert count == 3

    async def test_counts_allow_with_redaction_decisions(self, evidence_repo) -> None:
        for _ in range(2):
            await _seed_decision(evidence_repo, GovernanceDecision.ALLOW_WITH_REDACTION)
        count = await recent_autonomous_action_count(
            evidence_repo, "org-1", "agent-1", window_minutes=60
        )
        assert count == 2

    async def test_sums_both_allow_kinds(self, evidence_repo) -> None:
        await _seed_decision(evidence_repo, GovernanceDecision.ALLOW)
        await _seed_decision(evidence_repo, GovernanceDecision.ALLOW)
        await _seed_decision(evidence_repo, GovernanceDecision.ALLOW_WITH_REDACTION)
        count = await recent_autonomous_action_count(
            evidence_repo, "org-1", "agent-1", window_minutes=60
        )
        assert count == 3

    async def test_deny_decisions_not_counted(self, evidence_repo) -> None:
        await _seed_decision(evidence_repo, GovernanceDecision.DENY)
        count = await recent_autonomous_action_count(
            evidence_repo, "org-1", "agent-1", window_minutes=60
        )
        assert count == 0

    async def test_scoped_to_org(self, evidence_repo) -> None:
        await _seed_decision(evidence_repo, GovernanceDecision.ALLOW, org_id="org-1")
        count = await recent_autonomous_action_count(
            evidence_repo, "org-2", "agent-1", window_minutes=60
        )
        assert count == 0


class TestOrgAutonomyBudgetRepository:
    async def test_get_returns_none_when_unset(self, autonomy_budget_repo) -> None:
        assert await autonomy_budget_repo.get("org-1") is None

    async def test_set_and_get_round_trip(self, autonomy_budget_repo) -> None:
        policy = AutonomyBudgetPolicy(max_autonomous_actions=10, window_minutes=30)
        await autonomy_budget_repo.set("org-1", policy)
        fetched = await autonomy_budget_repo.get("org-1")
        assert fetched == policy

    async def test_set_upserts_not_duplicates(self, autonomy_budget_repo) -> None:
        await autonomy_budget_repo.set(
            "org-1", AutonomyBudgetPolicy(max_autonomous_actions=10, window_minutes=30)
        )
        await autonomy_budget_repo.set(
            "org-1", AutonomyBudgetPolicy(max_autonomous_actions=20, window_minutes=45)
        )
        fetched = await autonomy_budget_repo.get("org-1")
        assert fetched == AutonomyBudgetPolicy(max_autonomous_actions=20, window_minutes=45)

    async def test_orgs_isolated(self, autonomy_budget_repo) -> None:
        await autonomy_budget_repo.set(
            "org-1", AutonomyBudgetPolicy(max_autonomous_actions=10, window_minutes=30)
        )
        assert await autonomy_budget_repo.get("org-2") is None

    async def test_delete_removes_row(self, autonomy_budget_repo) -> None:
        await autonomy_budget_repo.set(
            "org-1", AutonomyBudgetPolicy(max_autonomous_actions=10, window_minutes=30)
        )
        await autonomy_budget_repo.delete("org-1")
        assert await autonomy_budget_repo.get("org-1") is None
