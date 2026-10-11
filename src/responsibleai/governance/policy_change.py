# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Is a proposed policy edit a tightening, a loosening, or neither?

Used by the tiered policy-governance model (decision paper REC-25, option C): an edit that can only make
the policy stricter may be made by one administrator, while an edit that could permit something it
previously did not needs step-up authentication and a second approver.

The classifier is deliberately conservative. Policy is first-match-wins over an ordered list, so the effect
of an edit depends on which actions each rule matches; this module does not try to prove semantic
equivalence. Anything it cannot show to be a tightening is a loosening:

* removing a restrictive rule (REQUIRE_APPROVAL, DENY) loosens;
* adding an ALLOW rule loosens;
* a rule whose content changed under the same id loosens;
* reordering loosens if any pair of surviving rules is flipped so the less severe one now comes first,
  or if the reorder both tightens and loosens;
* only adding a restrictive rule, removing an ALLOW rule, or flipping a pair toward the more severe rule
  first is a tightening;
* an identical rule list is neutral.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Sequence
from enum import StrEnum
from typing import Any

from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.policy import PolicyRule

_SEVERITY: dict[GovernanceDecision, int] = {
    GovernanceDecision.ALLOW: 0,
    GovernanceDecision.REQUIRE_APPROVAL: 1,
    GovernanceDecision.DENY: 2,
}


class ChangeKind(StrEnum):
    NEUTRAL = "NEUTRAL"
    TIGHTENING = "TIGHTENING"
    LOOSENING = "LOOSENING"


def _severity(rule: PolicyRule) -> int:
    # An effect this module does not know is treated as the least severe, so any edit touching it
    # classifies as a loosening.
    return _SEVERITY.get(rule.effect, 0)


def rule_snapshot(rule: PolicyRule) -> dict[str, Any]:
    return {
        "rule_id": rule.rule_id,
        "reason_code": rule.reason_code,
        "effect": rule.effect.value,
        "risk_tiers": sorted(t.value for t in rule.risk_tiers) if rule.risk_tiers else None,
        "action_types": sorted(rule.action_types) if rule.action_types else None,
        "targets": sorted(rule.targets) if rule.targets else None,
    }


def rules_digest(rules: Sequence[PolicyRule]) -> str:
    """Digest of an ordered rule list (order is part of the policy)."""
    material = json.dumps([rule_snapshot(r) for r in rules], sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def classify_change(before: Sequence[PolicyRule], after: Sequence[PolicyRule]) -> ChangeKind:
    before_by_id = {r.rule_id: r for r in before}
    after_by_id = {r.rule_id: r for r in after}
    loosening = False
    tightening = False

    for rule_id, rule in before_by_id.items():
        if rule_id not in after_by_id:
            if _severity(rule) > 0:
                loosening = True  # a restriction was removed
            else:
                tightening = True  # an ALLOW was removed
    for rule_id, rule in after_by_id.items():
        if rule_id not in before_by_id:
            if _severity(rule) > 0:
                tightening = True
            else:
                loosening = True  # a new ALLOW
        elif rule_snapshot(rule) != rule_snapshot(before_by_id[rule_id]):
            loosening = True  # same id, different content: not analysed, so not trusted

    common = [r.rule_id for r in before if r.rule_id in after_by_id]
    before_pos = {rid: i for i, rid in enumerate(common)}
    after_order = [r.rule_id for r in after if r.rule_id in before_by_id]
    after_pos = {rid: i for i, rid in enumerate(after_order)}
    for i, first in enumerate(common):
        for second in common[i + 1 :]:
            if (before_pos[first] < before_pos[second]) == (after_pos[first] < after_pos[second]):
                continue
            # The pair flipped. Whichever rule is now first decides ties between them.
            now_first, now_second = (
                (first, second) if after_pos[first] < after_pos[second] else (second, first)
            )
            a, b = _severity(before_by_id[now_first]), _severity(before_by_id[now_second])
            if a < b:
                loosening = True
            elif a > b:
                tightening = True

    if loosening:
        return ChangeKind.LOOSENING
    if tightening:
        return ChangeKind.TIGHTENING
    return ChangeKind.NEUTRAL
