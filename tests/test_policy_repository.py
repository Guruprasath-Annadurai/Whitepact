"""Tests for PolicyRepository — persisted governance policy rules
(previously code-only PolicyRule/Policy objects, now a real DB table).
"""

from __future__ import annotations

import pytest

from responsibleai.db import PolicyRepository, PolicyRuleNotFoundError, create_engine
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.risk import RiskTier


@pytest.fixture()
async def engine():
    e = create_engine(":memory:")
    await e.init()
    yield e
    await e.close()


@pytest.fixture()
def repo(engine):
    return PolicyRepository(engine)


def _rule(rule_id: str, effect: GovernanceDecision = GovernanceDecision.DENY) -> PolicyRule:
    return PolicyRule(
        rule_id=rule_id,
        reason_code="test_reason",
        effect=effect,
        risk_tiers=frozenset({RiskTier.HIGH}),
        action_types=frozenset({"rai_incident_log"}),
        targets=None,
    )


class TestGetPolicy:
    async def test_empty_policy_for_unknown_org(self, repo: PolicyRepository) -> None:
        policy = await repo.get_policy("org-1")
        assert policy.org_id == "org-1"
        assert policy.rules == []

    async def test_returns_added_rule(self, repo: PolicyRepository) -> None:
        await repo.add_rule("org-1", _rule("r1"))
        policy = await repo.get_policy("org-1")
        assert len(policy.rules) == 1
        rule = policy.rules[0]
        assert rule.rule_id == "r1"
        assert rule.effect == GovernanceDecision.DENY
        assert rule.risk_tiers == frozenset({RiskTier.HIGH})
        assert rule.action_types == frozenset({"rai_incident_log"})
        assert rule.targets is None

    async def test_null_fields_round_trip_as_match_any(self, repo: PolicyRepository) -> None:
        rule = PolicyRule(rule_id="r1", reason_code="rc", effect=GovernanceDecision.ALLOW)
        await repo.add_rule("org-1", rule)
        policy = await repo.get_policy("org-1")
        assert policy.rules[0].risk_tiers is None
        assert policy.rules[0].action_types is None
        assert policy.rules[0].targets is None


class TestOrdering:
    async def test_rules_persist_in_insertion_order(self, repo: PolicyRepository) -> None:
        await repo.add_rule("org-1", _rule("r1"))
        await repo.add_rule("org-1", _rule("r2"))
        await repo.add_rule("org-1", _rule("r3"))
        policy = await repo.get_policy("org-1")
        assert [r.rule_id for r in policy.rules] == ["r1", "r2", "r3"]

    async def test_reorder_changes_evaluation_order(self, repo: PolicyRepository) -> None:
        await repo.add_rule("org-1", _rule("r1"))
        await repo.add_rule("org-1", _rule("r2"))
        await repo.add_rule("org-1", _rule("r3"))
        await repo.reorder("org-1", ["r3", "r1", "r2"])
        policy = await repo.get_policy("org-1")
        assert [r.rule_id for r in policy.rules] == ["r3", "r1", "r2"]

    async def test_reorder_rejects_mismatched_rule_set(self, repo: PolicyRepository) -> None:
        await repo.add_rule("org-1", _rule("r1"))
        await repo.add_rule("org-1", _rule("r2"))
        with pytest.raises(ValueError, match="current rule_ids"):
            await repo.reorder("org-1", ["r1", "r-does-not-exist"])


class TestRemoveRule:
    async def test_removes_existing_rule(self, repo: PolicyRepository) -> None:
        await repo.add_rule("org-1", _rule("r1"))
        await repo.add_rule("org-1", _rule("r2"))
        await repo.remove_rule("org-1", "r1")
        policy = await repo.get_policy("org-1")
        assert [r.rule_id for r in policy.rules] == ["r2"]

    async def test_raises_for_unknown_rule(self, repo: PolicyRepository) -> None:
        with pytest.raises(PolicyRuleNotFoundError):
            await repo.remove_rule("org-1", "does-not-exist")


class TestOrgIsolation:
    async def test_rules_scoped_to_org(self, repo: PolicyRepository) -> None:
        await repo.add_rule("org-a", _rule("r1"))
        await repo.add_rule("org-b", _rule("r1"))  # same rule_id, different org — allowed

        policy_a = await repo.get_policy("org-a")
        policy_b = await repo.get_policy("org-b")
        assert len(policy_a.rules) == 1
        assert len(policy_b.rules) == 1

        await repo.remove_rule("org-a", "r1")
        policy_a = await repo.get_policy("org-a")
        policy_b = await repo.get_policy("org-b")
        assert policy_a.rules == []
        assert len(policy_b.rules) == 1


class TestIntegrationWithGatewayEvaluate:
    async def test_persisted_policy_used_directly_by_gateway(self, repo: PolicyRepository) -> None:
        from responsibleai.governance import (
            ActionRequest,
            AgentContext,
            AuthorityContext,
            GovernanceDecision as GD,
            IdentityContext,
            WhitePactRuntimeGateway,
        )

        await repo.add_rule(
            "org-1",
            PolicyRule(
                rule_id="block-incident-log",
                reason_code="no_incident_logging_from_this_org",
                effect=GD.DENY,
                action_types=frozenset({"rai_incident_log"}),
            ),
        )
        policy = await repo.get_policy("org-1")

        gateway = WhitePactRuntimeGateway()
        identity = IdentityContext(identity_id="k1", kind="api_key", org_id="org-1")
        agent = AgentContext(identity=identity)
        authority = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"rai_incident_log"}))
        action = ActionRequest(agent=agent, action_type="rai_incident_log", target="rai_incident_log", arguments={})

        result = gateway.evaluate(action, authority, policy=policy)
        assert result.decision == GD.DENY
        assert any("block-incident-log" in code for code in result.reason_codes)
