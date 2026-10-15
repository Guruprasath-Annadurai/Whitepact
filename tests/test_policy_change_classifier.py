# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The tightening/loosening classifier must never call a loosening edit a tightening one."""

from __future__ import annotations

import itertools

import pytest

from responsibleai.governance.models import GovernanceDecision as D
from responsibleai.governance.policy import PolicyRule
from responsibleai.governance.policy_change import ChangeKind, classify_change, rules_digest


def r(rule_id: str, effect: D, action: str | None = None) -> PolicyRule:
    return PolicyRule(
        rule_id, rule_id.upper(), effect, action_types=frozenset({action}) if action else None
    )


DENY, REVIEW, ALLOW = D.DENY, D.REQUIRE_APPROVAL, D.ALLOW


@pytest.mark.parametrize(
    ("before", "after", "expected"),
    [
        ([], [], ChangeKind.NEUTRAL),
        ([r("a", DENY, "x")], [r("a", DENY, "x")], ChangeKind.NEUTRAL),
        ([], [r("a", DENY, "x")], ChangeKind.TIGHTENING),
        ([], [r("a", REVIEW, "x")], ChangeKind.TIGHTENING),
        ([], [r("a", ALLOW, "x")], ChangeKind.LOOSENING),
        ([r("a", DENY, "x")], [], ChangeKind.LOOSENING),
        ([r("a", REVIEW, "x")], [], ChangeKind.LOOSENING),
        ([r("a", ALLOW, "x")], [], ChangeKind.TIGHTENING),
        # same id, softened or broadened content is never trusted
        ([r("a", DENY, "x")], [r("a", REVIEW, "x")], ChangeKind.LOOSENING),
        ([r("a", DENY, "x")], [r("a", DENY, "y")], ChangeKind.LOOSENING),
        ([r("a", DENY, "x")], [r("a", DENY)], ChangeKind.LOOSENING),
        # reorders
        (
            [r("a", ALLOW, "x"), r("b", DENY, "x")],
            [r("b", DENY, "x"), r("a", ALLOW, "x")],
            ChangeKind.TIGHTENING,
        ),
        (
            [r("b", DENY, "x"), r("a", ALLOW, "x")],
            [r("a", ALLOW, "x"), r("b", DENY, "x")],
            ChangeKind.LOOSENING,
        ),
        (
            [r("b", DENY, "x"), r("c", REVIEW, "x")],
            [r("c", REVIEW, "x"), r("b", DENY, "x")],
            ChangeKind.LOOSENING,
        ),
        (
            [r("c", REVIEW, "x"), r("b", DENY, "x")],
            [r("b", DENY, "x"), r("c", REVIEW, "x")],
            ChangeKind.TIGHTENING,
        ),
        # adding a restriction while moving an ALLOW above another restriction is a loosening overall
        (
            [r("d", DENY, "x"), r("a", ALLOW, "y")],
            [r("a", ALLOW, "y"), r("d", DENY, "x"), r("n", DENY, "z")],
            ChangeKind.LOOSENING,
        ),
    ],
)
def test_classification(before, after, expected) -> None:
    assert classify_change(before, after) is expected


def test_removing_a_restriction_and_adding_one_in_the_same_edit_is_a_loosening() -> None:
    assert classify_change([r("a", DENY, "x")], [r("b", DENY, "y")]) is ChangeKind.LOOSENING


def test_the_digest_covers_order_and_content() -> None:
    one = rules_digest([r("a", DENY, "x"), r("b", DENY, "y")])
    assert one == rules_digest([r("a", DENY, "x"), r("b", DENY, "y")])
    assert one != rules_digest([r("b", DENY, "y"), r("a", DENY, "x")])
    assert one != rules_digest([r("a", DENY, "x"), r("b", DENY, "z")])


def test_exhaustive_small_universe_never_calls_a_permitting_edit_a_tightening() -> None:
    """Brute force: for every ordered rule list over a small universe and every pair of lists,
    a TIGHTENING result must not remove a restriction, add an ALLOW, change a rule or move a less
    severe rule ahead of a more severe one."""
    universe = [r("a", ALLOW, "x"), r("b", REVIEW, "x"), r("c", DENY, "x")]
    sev = {ALLOW: 0, REVIEW: 1, DENY: 2}
    lists = [
        list(p)
        for size in range(0, 4)
        for combo in itertools.combinations(universe, size)
        for p in itertools.permutations(combo)
    ]
    for before, after in itertools.product(lists, lists):
        kind = classify_change(before, after)
        if kind is not ChangeKind.TIGHTENING:
            continue
        ids_b, ids_a = {x.rule_id: x for x in before}, {x.rule_id: x for x in after}
        assert not any(sev[x.effect] > 0 for rid, x in ids_b.items() if rid not in ids_a), (
            before,
            after,
        )
        assert not any(sev[x.effect] == 0 for rid, x in ids_a.items() if rid not in ids_b), (
            before,
            after,
        )
        common = [x.rule_id for x in after if x.rule_id in ids_b]
        for i, first in enumerate(common):
            for second in common[i + 1 :]:
                order_before = [x.rule_id for x in before if x.rule_id in ids_a]
                if order_before.index(first) > order_before.index(second):
                    assert sev[ids_a[first].effect] >= sev[ids_a[second].effect], (before, after)
