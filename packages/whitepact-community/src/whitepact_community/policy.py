"""First-match-wins policy engine for Community Core."""

from __future__ import annotations

from dataclasses import dataclass, field

from whitepact_community.models import ActionRequest, GovernanceDecision
from whitepact_community.risk import RiskTier

_RULE_EFFECTS = frozenset(
    {
        GovernanceDecision.ALLOW,
        GovernanceDecision.REQUIRE_APPROVAL,
        GovernanceDecision.DENY,
    }
)


@dataclass(frozen=True)
class PolicyRule:
    rule_id: str
    reason_code: str
    effect: GovernanceDecision
    risk_tiers: frozenset[RiskTier] | None = None
    action_types: frozenset[str] | None = None
    targets: frozenset[str] | None = None

    def __post_init__(self) -> None:
        if self.effect not in _RULE_EFFECTS:
            raise ValueError(
                f"PolicyRule {self.rule_id!r}: effect must be one of "
                f"{sorted(e.value for e in _RULE_EFFECTS)}, got {self.effect.value!r}"
            )

    def matches(self, action: ActionRequest, risk_tier: RiskTier) -> bool:
        if self.risk_tiers is not None and risk_tier not in self.risk_tiers:
            return False
        if self.action_types is not None and action.action_type not in self.action_types:
            return False
        return not (self.targets is not None and action.target not in self.targets)


@dataclass
class PolicyMatch:
    rule: PolicyRule


@dataclass
class Policy:
    """Ordered rule set. First matching rule wins.

    Community Core is deny-by-default when ``deny_unmatched`` is True
    (the default): if no rule matches, the gateway denies rather than
    silently allowing.
    """

    org_id: str
    rules: list[PolicyRule] = field(default_factory=list)
    version: int = 1
    deny_unmatched: bool = True

    def evaluate(self, action: ActionRequest, risk_tier: RiskTier) -> PolicyMatch | None:
        for rule in self.rules:
            if rule.matches(action, risk_tier):
                return PolicyMatch(rule=rule)
        return None


def default_local_policy(org_id: str = "local") -> Policy:
    """Safe local test policy: allow only known community local tools."""
    return Policy(
        org_id=org_id,
        version=1,
        deny_unmatched=True,
        rules=[
            PolicyRule(
                rule_id="allow-local-echo",
                reason_code="community_local_allow",
                effect=GovernanceDecision.ALLOW,
                action_types=frozenset({"local_echo", "local_health", "policy_evaluate"}),
                targets=frozenset({"local_echo", "local_health", "policy_evaluate"}),
            ),
            PolicyRule(
                rule_id="allow-governed-local",
                reason_code="community_governed_local_allow",
                effect=GovernanceDecision.ALLOW,
                action_types=frozenset({"governed_local_action"}),
                targets=frozenset({"governed_local_action"}),
            ),
            PolicyRule(
                rule_id="deny-enterprise-surface",
                reason_code="enterprise_surface_blocked",
                effect=GovernanceDecision.DENY,
                action_types=frozenset(
                    {
                        "billing_checkout",
                        "tenant_admin",
                        "saas_deploy",
                        "stripe_webhook",
                    }
                ),
            ),
        ],
    )
