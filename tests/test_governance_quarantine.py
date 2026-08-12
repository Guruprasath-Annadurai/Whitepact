"""Tests for cross-request violation-pattern tracking — proving
`GovernanceDecision.QUARANTINE` is actually reachable (governance/
quarantine.py + WhitePactRuntimeGateway.evaluate()'s
recent_violation_count parameter), not just a defined enum member.
"""

from __future__ import annotations

import pytest

from responsibleai.db import EvidenceRepository, create_engine
from responsibleai.governance import (
    QUARANTINE_VIOLATION_THRESHOLD,
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    WhitePactRuntimeGateway,
    recent_violation_count,
)
from responsibleai.governance.evidence import build_evidence_record


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def evidence_repo(engine):
    return EvidenceRepository(engine)


def _identity(org_id: str = "org-1") -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)


def _agent(agent_id: str, org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=_identity(org_id), agent_id=agent_id, framework="mcp-client")


def _denied_action(agent: AgentContext) -> ActionRequest:
    return ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan", arguments={})


class TestGatewayQuarantineThreshold:
    def test_below_threshold_not_quarantined(self) -> None:
        gateway = WhitePactRuntimeGateway()
        agent = _agent("agent-1")
        authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"rai_scan"}))
        action = ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan", arguments={})

        result = gateway.evaluate(
            action, authority, recent_violation_count=QUARANTINE_VIOLATION_THRESHOLD - 1,
        )
        assert result.decision == GovernanceDecision.ALLOW

    def test_at_threshold_quarantines(self) -> None:
        gateway = WhitePactRuntimeGateway()
        agent = _agent("agent-1")
        authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"rai_scan"}))
        action = ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan", arguments={})

        result = gateway.evaluate(
            action, authority, recent_violation_count=QUARANTINE_VIOLATION_THRESHOLD,
        )
        assert result.decision == GovernanceDecision.QUARANTINE
        assert any("quarantine:recent_denials" in code for code in result.reason_codes)

    def test_quarantine_overrides_valid_authority_grant(self) -> None:
        """A quarantined agent is blocked even though its AuthorityContext
        explicitly grants the action — the whole point of quarantine is
        that a pattern of violations overrides a standing grant."""
        gateway = WhitePactRuntimeGateway()
        agent = _agent("agent-1")
        authority = AuthorityContext(
            delegated_by="org-1", granted_action_types=frozenset({"rai_scan", "rai_incident_log"}),
        )
        action = ActionRequest(agent=agent, action_type="rai_incident_log", target="rai_incident_log", arguments={})

        result = gateway.evaluate(
            action, authority, recent_violation_count=QUARANTINE_VIOLATION_THRESHOLD + 10,
        )
        assert result.decision == GovernanceDecision.QUARANTINE

    def test_quarantine_result_carries_risk_tier(self) -> None:
        gateway = WhitePactRuntimeGateway()
        agent = _agent("agent-1")
        authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"rai_scan"}))
        action = ActionRequest(agent=agent, action_type="rai_scan", target="rai_scan", arguments={})

        result = gateway.evaluate(
            action, authority, recent_violation_count=QUARANTINE_VIOLATION_THRESHOLD,
        )
        assert result.risk_tier is not None


class TestRecentViolationCountQuery:
    async def test_zero_when_no_evidence(self, evidence_repo: EvidenceRepository) -> None:
        count = await recent_violation_count(evidence_repo, "org-1", "agent-1")
        assert count == 0

    async def test_counts_only_deny_decisions_for_this_agent(self, evidence_repo: EvidenceRepository) -> None:
        gateway = WhitePactRuntimeGateway()
        agent = _agent("agent-1")
        other_agent = _agent("agent-2")
        denying_authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset())
        allowing_authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"rai_scan"}))

        # 3 DENYs for agent-1 (authority not granted).
        for _ in range(3):
            action = _denied_action(agent)
            decision = gateway.evaluate(action, denying_authority)
            assert decision.decision == GovernanceDecision.DENY
            await evidence_repo.record(build_evidence_record(action, agent, denying_authority, decision))

        # 1 ALLOW for agent-1 — should not count.
        allow_action = _denied_action(agent)
        allow_decision = gateway.evaluate(allow_action, allowing_authority)
        assert allow_decision.decision == GovernanceDecision.ALLOW
        await evidence_repo.record(build_evidence_record(allow_action, agent, allowing_authority, allow_decision))

        # 5 DENYs for a different agent — should not count toward agent-1.
        for _ in range(5):
            other_action = _denied_action(other_agent)
            other_decision = gateway.evaluate(other_action, denying_authority)
            await evidence_repo.record(build_evidence_record(other_action, other_agent, denying_authority, other_decision))

        count = await recent_violation_count(evidence_repo, "org-1", "agent-1")
        assert count == 3

    async def test_scoped_to_org(self, evidence_repo: EvidenceRepository) -> None:
        gateway = WhitePactRuntimeGateway()
        agent_org_a = _agent("shared-agent-id", org_id="org-a")
        denying_authority = AuthorityContext(delegated_by="org-x", granted_action_types=frozenset())

        action_a = _denied_action(agent_org_a)
        decision_a = gateway.evaluate(action_a, denying_authority)
        await evidence_repo.record(build_evidence_record(action_a, agent_org_a, denying_authority, decision_a))

        count_a = await recent_violation_count(evidence_repo, "org-a", "shared-agent-id")
        count_b = await recent_violation_count(evidence_repo, "org-b", "shared-agent-id")
        assert count_a == 1
        assert count_b == 0

    async def test_end_to_end_repeated_violations_trigger_quarantine(
        self, evidence_repo: EvidenceRepository,
    ) -> None:
        """The realistic sequence: an agent keeps getting DENYed, each
        decision gets recorded as evidence, and once the threshold is
        crossed the *next* evaluate() call — fed the freshly queried
        count — actually returns QUARANTINE."""
        gateway = WhitePactRuntimeGateway()
        agent = _agent("repeat-offender")
        denying_authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset())

        for _ in range(QUARANTINE_VIOLATION_THRESHOLD):
            count = await recent_violation_count(evidence_repo, "org-1", "repeat-offender")
            action = _denied_action(agent)
            decision = gateway.evaluate(action, denying_authority, recent_violation_count=count)
            assert decision.decision == GovernanceDecision.DENY
            await evidence_repo.record(build_evidence_record(action, agent, denying_authority, decision))

        final_count = await recent_violation_count(evidence_repo, "org-1", "repeat-offender")
        assert final_count == QUARANTINE_VIOLATION_THRESHOLD
        final_action = _denied_action(agent)
        final_decision = gateway.evaluate(final_action, denying_authority, recent_violation_count=final_count)
        assert final_decision.decision == GovernanceDecision.QUARANTINE
