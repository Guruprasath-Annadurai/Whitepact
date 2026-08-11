"""Tests for the policy engine (SPEC.md Section 3.5, Phase 10):
`governance/policy.py`'s `PolicyRule` matching and `Policy`'s
first-match-wins evaluation.
"""

from __future__ import annotations

import pytest

from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.policy import Policy, PolicyRule
from responsibleai.governance.risk import RiskTier


def _agent() -> AgentContext:
    return AgentContext(identity=IdentityContext(identity_id="k1", kind="api_key", org_id="org-1"))


def _action(action_type: str = "mcp_tool_call", target: str = "rai_scan") -> ActionRequest:
    return ActionRequest(agent=_agent(), action_type=action_type, target=target)


class TestPolicyRuleValidation:
    def test_allow_with_redaction_is_rejected(self) -> None:
        """Redaction needs a matched span GuardrailsEngine finds, which a
        policy rule never sees -- ALLOW_WITH_REDACTION isn't a valid
        rule effect."""
        with pytest.raises(ValueError, match="effect must be one of"):
            PolicyRule(rule_id="r1", reason_code="x", effect=GovernanceDecision.ALLOW_WITH_REDACTION)

    def test_quarantine_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="effect must be one of"):
            PolicyRule(rule_id="r1", reason_code="x", effect=GovernanceDecision.QUARANTINE)

    def test_allow_deny_require_approval_are_valid(self) -> None:
        for effect in (GovernanceDecision.ALLOW, GovernanceDecision.DENY, GovernanceDecision.REQUIRE_APPROVAL):
            PolicyRule(rule_id="r1", reason_code="x", effect=effect)


class TestPolicyRuleMatching:
    def test_matches_any_by_default(self) -> None:
        rule = PolicyRule(rule_id="r1", reason_code="x", effect=GovernanceDecision.ALLOW)
        assert rule.matches(_action(), RiskTier.LOW) is True
        assert rule.matches(_action(action_type="payment"), RiskTier.HIGH) is True

    def test_filters_by_risk_tier(self) -> None:
        rule = PolicyRule(
            rule_id="r1", reason_code="x", effect=GovernanceDecision.DENY,
            risk_tiers=frozenset({RiskTier.HIGH}),
        )
        assert rule.matches(_action(), RiskTier.HIGH) is True
        assert rule.matches(_action(), RiskTier.LOW) is False

    def test_filters_by_action_type(self) -> None:
        rule = PolicyRule(
            rule_id="r1", reason_code="x", effect=GovernanceDecision.DENY,
            action_types=frozenset({"payment"}),
        )
        assert rule.matches(_action(action_type="payment"), RiskTier.LOW) is True
        assert rule.matches(_action(action_type="mcp_tool_call"), RiskTier.LOW) is False

    def test_filters_by_target(self) -> None:
        rule = PolicyRule(
            rule_id="r1", reason_code="x", effect=GovernanceDecision.DENY,
            targets=frozenset({"rai_incident_log"}),
        )
        assert rule.matches(_action(target="rai_incident_log"), RiskTier.LOW) is True
        assert rule.matches(_action(target="rai_scan"), RiskTier.LOW) is False

    def test_all_filters_must_pass(self) -> None:
        rule = PolicyRule(
            rule_id="r1", reason_code="x", effect=GovernanceDecision.DENY,
            risk_tiers=frozenset({RiskTier.HIGH}),
            action_types=frozenset({"mcp_tool_call"}),
            targets=frozenset({"rai_hallucination"}),
        )
        assert rule.matches(_action(target="rai_hallucination"), RiskTier.HIGH) is True
        assert rule.matches(_action(target="rai_hallucination"), RiskTier.LOW) is False
        assert rule.matches(_action(target="rai_scan"), RiskTier.HIGH) is False


class TestPolicyEvaluation:
    def test_no_rules_no_match(self) -> None:
        policy = Policy(org_id="org-1", rules=[])
        assert policy.evaluate(_action(), RiskTier.LOW) is None

    def test_first_match_wins(self) -> None:
        rule_a = PolicyRule(rule_id="a", reason_code="first", effect=GovernanceDecision.DENY)
        rule_b = PolicyRule(rule_id="b", reason_code="second", effect=GovernanceDecision.ALLOW)
        policy = Policy(org_id="org-1", rules=[rule_a, rule_b])
        match = policy.evaluate(_action(), RiskTier.LOW)
        assert match is not None
        assert match.rule.rule_id == "a"

    def test_falls_through_to_later_matching_rule(self) -> None:
        rule_a = PolicyRule(
            rule_id="a", reason_code="high_only", effect=GovernanceDecision.DENY,
            risk_tiers=frozenset({RiskTier.HIGH}),
        )
        rule_b = PolicyRule(rule_id="b", reason_code="catch_all", effect=GovernanceDecision.ALLOW)
        policy = Policy(org_id="org-1", rules=[rule_a, rule_b])
        match = policy.evaluate(_action(), RiskTier.LOW)
        assert match is not None
        assert match.rule.rule_id == "b"

    def test_no_matching_rule_returns_none(self) -> None:
        rule = PolicyRule(
            rule_id="a", reason_code="x", effect=GovernanceDecision.DENY,
            risk_tiers=frozenset({RiskTier.HIGH}),
        )
        policy = Policy(org_id="org-1", rules=[rule])
        assert policy.evaluate(_action(), RiskTier.LOW) is None
