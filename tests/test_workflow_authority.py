"""Tests for the Workflow Authority Engine (governance/workflow.py):
`check_composition_violation()`, its wiring into
`WhitePactRuntimeGateway.evaluate()`, `EvidenceRepository.list_recent_actions()`,
and `WorkflowRuleRepository`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from responsibleai.db import EvidenceRepository, WorkflowRuleRepository, create_engine
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
    TimestampedAction,
    WhitePactRuntimeGateway,
    WorkflowSequenceRule,
    check_composition_violation,
)
from responsibleai.governance.evidence import build_evidence_record

_NOW = datetime(2026, 1, 1, 12, 0, tzinfo=UTC)


def _rule(
    *action_types: str, window_minutes: int = 60, rule_id: str = "r1"
) -> WorkflowSequenceRule:
    return WorkflowSequenceRule(
        rule_id=rule_id, action_types=action_types, window_minutes=window_minutes
    )


def _at(minutes_ago: int, action_type: str) -> TimestampedAction:
    return TimestampedAction(action_type=action_type, at=_NOW - timedelta(minutes=minutes_ago))


class TestFlagshipScenario:
    def test_full_sequence_denied_on_completing_action(self) -> None:
        """beneficiary.create -> payment.limit.raise -> payment.execute,
        each individually permitted, sequence denied on the third."""
        rule = _rule("beneficiary.create", "payment.limit.raise", "payment.execute")
        history = [_at(10, "beneficiary.create"), _at(5, "payment.limit.raise")]
        reason = check_composition_violation(history, "payment.execute", _NOW, [rule])
        assert reason is not None
        assert reason.startswith("AUTHORITY_COMPOSITION_VIOLATION")
        assert "rule_id=r1" in reason

    def test_first_two_steps_alone_not_denied(self) -> None:
        rule = _rule("beneficiary.create", "payment.limit.raise", "payment.execute")
        history = [_at(10, "beneficiary.create")]
        reason = check_composition_violation(history, "payment.limit.raise", _NOW, [rule])
        assert reason is None

    def test_unrelated_action_in_between_does_not_reset_match(self) -> None:
        rule = _rule("beneficiary.create", "payment.execute")
        history = [_at(10, "beneficiary.create"), _at(5, "rai_health")]
        reason = check_composition_violation(history, "payment.execute", _NOW, [rule])
        assert reason is not None

    def test_wrong_order_not_denied(self) -> None:
        rule = _rule("beneficiary.create", "payment.execute")
        history = [_at(10, "payment.execute")]
        reason = check_composition_violation(history, "beneficiary.create", _NOW, [rule])
        assert reason is None


class TestFiresOnlyOnce:
    def test_action_after_completed_sequence_not_re_flagged(self) -> None:
        """Once a sequence has already been completed by prior history,
        an unrelated subsequent action must not also be flagged --
        otherwise every future call would be denied forever."""
        rule = _rule("a", "b", "c")
        history = [_at(30, "a"), _at(20, "b"), _at(10, "c")]
        reason = check_composition_violation(history, "d", _NOW, [rule])
        assert reason is None


class TestWindow:
    def test_step_outside_window_does_not_count(self) -> None:
        rule = _rule("a", "b", window_minutes=10)
        history = [_at(60, "a")]  # far outside the 10-minute window
        reason = check_composition_violation(history, "b", _NOW, [rule])
        assert reason is None

    def test_step_inside_window_counts(self) -> None:
        rule = _rule("a", "b", window_minutes=10)
        history = [_at(5, "a")]
        reason = check_composition_violation(history, "b", _NOW, [rule])
        assert reason is not None

    def test_different_rules_apply_their_own_window_independently(self) -> None:
        narrow = _rule("a", "b", window_minutes=5, rule_id="narrow")
        wide = _rule("a", "c", window_minutes=60, rule_id="wide")
        history = [_at(30, "a")]  # outside narrow's window, inside wide's
        assert check_composition_violation(history, "b", _NOW, [narrow]) is None
        assert check_composition_violation(history, "c", _NOW, [wide]) is not None


class TestNoRulesOrNoMatch:
    def test_empty_rules_never_denies(self) -> None:
        assert check_composition_violation([], "payment.execute", _NOW, []) is None

    def test_unrelated_action_never_denies(self) -> None:
        rule = _rule("a", "b")
        assert check_composition_violation([_at(5, "x")], "y", _NOW, [rule]) is None


def _identity(org_id: str = "org-1") -> IdentityContext:
    return IdentityContext(identity_id="k1", kind="api_key", org_id=org_id)


def _agent(org_id: str = "org-1") -> AgentContext:
    return AgentContext(identity=_identity(org_id), agent_id="agent-1", framework="mcp-client")


def _authority(**kwargs) -> AuthorityContext:
    kwargs.setdefault("delegated_by", "org-1")
    kwargs.setdefault("granted_action_types", frozenset({"payment.execute"}))
    return AuthorityContext(**kwargs)


class TestGatewayWiring:
    def test_no_workflow_rules_unaffected(self) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(agent=_agent(), action_type="payment.execute", target="x")
        result = gw.evaluate(action, _authority())
        assert result.decision == GovernanceDecision.ALLOW

    def test_composition_violation_denies_before_authority_check(self) -> None:
        """Denied for the composition even though authority itself would
        have permitted the action -- the composition check runs first."""
        gw = WhitePactRuntimeGateway()
        rule = _rule("beneficiary.create", "payment.limit.raise", "payment.execute")
        history = [_at(10, "beneficiary.create"), _at(5, "payment.limit.raise")]
        action = ActionRequest(
            agent=_agent(),
            action_type="payment.execute",
            target="vendor_xyz",
            proposed_at=_NOW,
        )
        result = gw.evaluate(
            action,
            _authority(granted_action_types=frozenset({"payment.execute"})),
            recent_actions=history,
            workflow_rules=[rule],
        )
        assert result.decision == GovernanceDecision.DENY
        assert result.reason_codes[0].startswith("AUTHORITY_COMPOSITION_VIOLATION")

    def test_composition_check_wins_over_quarantine(self) -> None:
        """Quarantine (step -2, checked first) still wins over a
        composition violation when both apply."""
        from responsibleai.governance import QUARANTINE_VIOLATION_THRESHOLD

        gw = WhitePactRuntimeGateway()
        rule = _rule("a", "b")
        action = ActionRequest(agent=_agent(), action_type="b", target="x", proposed_at=_NOW)
        result = gw.evaluate(
            action,
            _authority(granted_action_types=frozenset({"b"})),
            recent_actions=[_at(1, "a")],
            workflow_rules=[rule],
            recent_violation_count=QUARANTINE_VIOLATION_THRESHOLD,
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
def workflow_rule_repo(engine):
    return WorkflowRuleRepository(engine)


class TestEvidenceRepositoryListRecentActions:
    async def test_empty_history_returns_empty(self, evidence_repo) -> None:
        actions = await evidence_repo.list_recent_actions(
            "org-1", "agent-1", since="2020-01-01T00:00:00+00:00"
        )
        assert actions == []

    async def test_records_come_back_chronological(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        for action_type in ["beneficiary.create", "payment.limit.raise", "payment.execute"]:
            action = ActionRequest(agent=_agent(), action_type=action_type, target="x")
            authority = _authority(granted_action_types=frozenset({action_type}))
            decision = gw.evaluate(action, authority)
            evidence = build_evidence_record(action, _agent(), authority, decision)
            await evidence_repo.record(evidence)

        actions = await evidence_repo.list_recent_actions(
            "org-1",
            "agent-1",
            since="2020-01-01T00:00:00+00:00",
        )
        assert [a.action_type for a in actions] == [
            "beneficiary.create",
            "payment.limit.raise",
            "payment.execute",
        ]

    async def test_since_filters_out_old_entries(self, evidence_repo) -> None:
        action = ActionRequest(agent=_agent(), action_type="x", target="x")
        authority = _authority(granted_action_types=frozenset({"x"}))
        gw = WhitePactRuntimeGateway()
        decision = gw.evaluate(action, authority)
        evidence = build_evidence_record(action, _agent(), authority, decision)
        await evidence_repo.record(evidence)

        future = (datetime.now(UTC) + timedelta(days=1)).isoformat()
        actions = await evidence_repo.list_recent_actions("org-1", "agent-1", since=future)
        assert actions == []

    async def test_scoped_to_agent_and_org(self, evidence_repo) -> None:
        gw = WhitePactRuntimeGateway()
        action = ActionRequest(agent=_agent(org_id="org-1"), action_type="x", target="x")
        authority = _authority(granted_action_types=frozenset({"x"}))
        decision = gw.evaluate(action, authority)
        evidence = build_evidence_record(action, _agent(org_id="org-1"), authority, decision)
        await evidence_repo.record(evidence)

        other_org = await evidence_repo.list_recent_actions(
            "org-2", "agent-1", since="2020-01-01T00:00:00+00:00"
        )
        assert other_org == []


class TestWorkflowRuleRepository:
    async def test_get_rules_empty_for_new_org(self, workflow_rule_repo) -> None:
        assert await workflow_rule_repo.get_rules("org-1") == []

    async def test_add_and_get_round_trip(self, workflow_rule_repo) -> None:
        rule = _rule(
            "beneficiary.create", "payment.limit.raise", "payment.execute", window_minutes=30
        )
        await workflow_rule_repo.add_rule("org-1", rule)
        rules = await workflow_rule_repo.get_rules("org-1")
        assert len(rules) == 1
        assert rules[0].rule_id == "r1"
        assert rules[0].action_types == (
            "beneficiary.create",
            "payment.limit.raise",
            "payment.execute",
        )
        assert rules[0].window_minutes == 30

    async def test_duplicate_rule_id_rejected(self, workflow_rule_repo) -> None:
        from responsibleai.db import WorkflowRuleAlreadyExistsError

        rule = _rule("a", "b")
        await workflow_rule_repo.add_rule("org-1", rule)
        with pytest.raises(WorkflowRuleAlreadyExistsError):
            await workflow_rule_repo.add_rule("org-1", rule)

    async def test_remove_rule(self, workflow_rule_repo) -> None:
        rule = _rule("a", "b")
        await workflow_rule_repo.add_rule("org-1", rule)
        await workflow_rule_repo.remove_rule("org-1", "r1")
        assert await workflow_rule_repo.get_rules("org-1") == []

    async def test_remove_unknown_rule_raises(self, workflow_rule_repo) -> None:
        from responsibleai.db import WorkflowRuleNotFoundError

        with pytest.raises(WorkflowRuleNotFoundError):
            await workflow_rule_repo.remove_rule("org-1", "does-not-exist")

    async def test_orgs_isolated(self, workflow_rule_repo) -> None:
        await workflow_rule_repo.add_rule("org-1", _rule("a", "b"))
        assert await workflow_rule_repo.get_rules("org-2") == []
