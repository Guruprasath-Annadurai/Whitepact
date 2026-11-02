"""The policy engine — SPEC.md Section 3.5: "a small, strongly typed
internal model first — not an LLM, not necessarily OPA/Rego on day
one." This is that first version: an ordered list of deterministic
rules, evaluated first-match-wins, each one a plain equality/membership
check against risk tier, action type, and/or target — no expression
language, no regex DSL, nothing that needs its own parser or its own
security review. Escalating to OPA/Rego or a richer rule language is
explicitly left for a later iteration, not implied by this one.

Distinct from `GuardrailsEngine` (`guardrails/engine.py`), which this
package's gateway also uses: guardrails inspects *content* (does this
string contain PII/toxicity/a blocked pattern); a `Policy` here governs
*actions* (is this organization willing to let this action type, at
this risk tier, targeting this tool, happen at all) — SPEC.md Section
2's "Action -> evaluated against Policy" step, upstream of and
independent from content scanning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from responsibleai.governance.models import ActionRequest, GovernanceDecision
from responsibleai.governance.risk import RiskTier

# Effects a policy rule may produce. Deliberately excludes
# ALLOW_WITH_REDACTION -- redaction is GuardrailsEngine's job (it needs
# the actual matched span to redact, which a policy rule never sees) and
# QUARANTINE (needs cross-request pattern state no rule here has access
# to; see governance/models.py's module docstring).
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
    risk_tiers: frozenset[RiskTier] | None = None  # None = matches any tier
    action_types: frozenset[str] | None = None  # None = matches any action_type
    targets: frozenset[str] | None = None  # None = matches any target

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
    """An organization's ordered rule set. First matching rule wins —
    order is the whole conflict-resolution model, deliberately, so a
    policy's behavior is always "read the rules top to bottom," not a
    priority/specificity scoring system that needs its own explanation.

    ``version`` is a monotonically increasing integer bumped by
    ``PolicyRepository`` on every mutation (add/remove/reorder a rule)
    — not a version of any one rule, but of the *ordered set as a
    whole*, since a reorder with no rule content change still changes
    which rule wins for an overlapping action. ``0`` for an in-memory
    ``Policy`` built directly (e.g. in a test) rather than fetched via
    ``PolicyRepository.get_policy()`` — never persisted, never
    evaluated as if it were a real version.
    """

    org_id: str
    rules: list[PolicyRule] = field(default_factory=list)
    version: int = 0

    def evaluate(self, action: ActionRequest, risk_tier: RiskTier) -> PolicyMatch | None:
        for rule in self.rules:
            if rule.matches(action, risk_tier):
                return PolicyMatch(rule=rule)
        return None
