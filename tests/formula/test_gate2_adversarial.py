# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from responsibleai.formula.authority.algebra import EffectiveAuthorityEvaluator
from responsibleai.formula.authority.models import (
    AuthorityConstraint,
    AuthorityContext,
    AuthorityGrant,
    AuthorityLifecycle,
    AuthoritySubject,
)
from responsibleai.formula.capability.models import CapabilityKind, CapabilityRef
from responsibleai.formula.errors import VersionMismatch
from responsibleai.formula.fence import CommitFence, EvaluationPin
from responsibleai.formula.invariants import FormulaInvariantChecker


def test_shell_capability_zero_authority() -> None:
    _cap = CapabilityRef("t", "s", "shell", CapabilityKind.DIRECT_TOOL)
    checker = FormulaInvariantChecker()
    assert checker.check_capability_not_authority(True, False, False) == []
    v = checker.check_capability_not_authority(True, True, False)
    assert v and v[0].invariant.value == "INV_CAPABILITY_NOT_AUTHORITY"


def test_stale_snapshot_version_fence() -> None:
    pin = EvaluationPin("e1", "0.1.0", 1, 1, "p1")
    fence = CommitFence(1, 1)
    with pytest.raises(VersionMismatch):
        fence.validate(pin, 2, 1)


def test_delegator_without_grant() -> None:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    parent = AuthorityGrant(
        grant_id="p",
        tenant_id="t",
        subject=AuthoritySubject("parent", "t"),
        issuer_id="root",
        delegator_id=None,
        actions=frozenset({"read"}),
        resources=frozenset({"x"}),
        purposes=frozenset({"p"}),
        context=AuthorityContext(),
        not_before=now,
        expires_at=now + timedelta(days=1),
        risk_ceiling=5,
        constraints=AuthorityConstraint(allow_delegation=True),
        lifecycle=AuthorityLifecycle.ACTIVE,
    )
    eff = EffectiveAuthorityEvaluator().effective((parent,), (), "child", now)
    assert not any(t.action == "read" for t in eff)
