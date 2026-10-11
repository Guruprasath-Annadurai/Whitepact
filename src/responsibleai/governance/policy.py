# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
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
from typing import Any

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


class PolicyShadowError(ValueError):
    """A stricter rule can never fire because an earlier rule already matches
    every action it would match. First-match would let the earlier, weaker
    effect win, including a broad ALLOW hiding a later DENY."""

    def __init__(self, shadowed_rule_id: str, covering_rule_id: str) -> None:
        self.shadowed_rule_id = shadowed_rule_id
        self.covering_rule_id = covering_rule_id
        super().__init__(
            f"Policy rule {shadowed_rule_id!r} is shadowed by earlier rule "
            f"{covering_rule_id!r}. Place the stricter rule first or narrow "
            "the earlier rule. A DENY or approval requirement hidden behind "
            "a broader ALLOW does not take effect."
        )


_EFFECT_STRENGTH = {
    GovernanceDecision.ALLOW: 0,
    GovernanceDecision.REQUIRE_APPROVAL: 1,
    GovernanceDecision.DENY: 2,
}


def _dimension_covers(earlier: frozenset[Any] | None, later: frozenset[Any] | None) -> bool:
    if earlier is None:
        return True
    if later is None:
        return False
    return later <= earlier


def rule_match_covers(earlier: PolicyRule, later: PolicyRule) -> bool:
    """True when every action *later* matches is already matched by *earlier*."""
    return (
        _dimension_covers(earlier.risk_tiers, later.risk_tiers)
        and _dimension_covers(earlier.action_types, later.action_types)
        and _dimension_covers(earlier.targets, later.targets)
    )


def shadowed_restrictive_rules(rules: list[PolicyRule]) -> list[tuple[PolicyRule, PolicyRule]]:
    """Later rules that are strictly stronger than an earlier covering rule.

    Duplicate DENY rules are not reported: a second DENY does not enlarge
    authority. An ALLOW or REQUIRE_APPROVAL that covers a later DENY does.
    """
    found: list[tuple[PolicyRule, PolicyRule]] = []
    for index, rule in enumerate(rules):
        rule_strength = _EFFECT_STRENGTH[rule.effect]
        for earlier in rules[:index]:
            if _EFFECT_STRENGTH[earlier.effect] >= rule_strength:
                continue
            if rule_match_covers(earlier, rule):
                found.append((rule, earlier))
                break
    return found


def reject_shadowed_restrictive_rules(rules: list[PolicyRule]) -> None:
    shadowed = shadowed_restrictive_rules(rules)
    if not shadowed:
        return
    rule, cover = shadowed[0]
    raise PolicyShadowError(rule.rule_id, cover.rule_id)
