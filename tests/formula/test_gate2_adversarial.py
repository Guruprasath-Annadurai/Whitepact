# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import pytest
from tests.formula.helpers import make_grant

from responsibleai.formula.authority.algebra import EffectiveAuthorityEvaluator
from responsibleai.formula.authority.models import ExplicitDeny
from responsibleai.formula.errors import VersionMismatch
from responsibleai.formula.fence import CommitFence, EvaluationPin
from responsibleai.formula.invariants import FormulaInvariantChecker
from responsibleai.formula.transitions import ProbabilityMass


def test_shell_capability_zero_authority() -> None:
    checker = FormulaInvariantChecker()
    v = checker.check_capability_not_authority(True, True, False)
    assert v and v[0].invariant.value == "INV_CAPABILITY_NOT_AUTHORITY"


def test_stale_snapshot_version_fence() -> None:
    pin = EvaluationPin("e1", "0.1.0", 1, 1, "p1")
    fence = CommitFence(1, 1)
    with pytest.raises(VersionMismatch):
        fence.validate(pin, 2, 1)


def test_cross_tenant_deny_ignored() -> None:
    g = make_grant("g", "s1", tenant="t1")
    deny = ExplicitDeny("d", "t2", "s1", frozenset({"read"}), frozenset({"x"}))
    eff = EffectiveAuthorityEvaluator().effective((g,), (deny,), "s1", "t1", g.not_before)
    assert len(eff) == 1


def test_cross_tenant_grant_ignored() -> None:
    g = make_grant("g", "s1", tenant="t2")
    eff = EffectiveAuthorityEvaluator().effective((g,), (), "s1", "t1", g.not_before)
    assert eff == frozenset()


def test_probability_mass_rejects_invalid() -> None:
    with pytest.raises(ValueError):
        ProbabilityMass((("w", float("nan")),))
    with pytest.raises(ValueError):
        ProbabilityMass((("w", 1.5),))


def test_delegator_without_grant_to_child() -> None:
    parent = make_grant("p", "parent", allow_delegation=True)
    eff = EffectiveAuthorityEvaluator().effective((parent,), (), "child", "t1", parent.not_before)
    assert not any(t.action == "read" for t in eff)
