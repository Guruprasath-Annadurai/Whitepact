# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""Gate 2D — control-path consistency (delegation ceiling, conditions, effective risk)."""

from __future__ import annotations

import pytest
from tests.formula.helpers import make_grant

from responsibleai.formula.authority.algebra import (
    EffectiveAuthorityEvaluator,
    grant_restriction,
    grant_union,
    validate_delegation,
)
from responsibleai.formula.authority.containment import effective_risk_ceiling
from responsibleai.formula.authority.creation import apply_delegation
from responsibleai.formula.authority.delegation import DelegationChain
from responsibleai.formula.authority.models import OrgAuthorityCeilingModel
from responsibleai.formula.errors import AuthorityExpansion, CrossTenantReference, InvalidDelegation
from responsibleai.formula.serialization import serialize_authority_evaluation


def _ceiling(max_depth: int, tenant: str = "t1") -> OrgAuthorityCeilingModel:
    return OrgAuthorityCeilingModel(tenant_id=tenant, org_id="o", max_delegation_depth=max_depth)


def test_max_depth_zero_root_cannot_delegate_via_apply_delegation() -> None:
    ceiling = _ceiling(0)
    parent = make_grant("p", "org", allow_delegation=True, delegation_depth=0)
    child = make_grant("c", "agent", delegator="org", delegation_depth=1)
    with pytest.raises(InvalidDelegation):
        apply_delegation(parent, child, ceiling=ceiling)


def test_max_depth_one_depth0_to_depth1_leaf_succeeds() -> None:
    ceiling = _ceiling(1)
    parent = make_grant("p", "org", allow_delegation=True, delegation_depth=0)
    child = make_grant(
        "c",
        "agent",
        delegator="org",
        delegation_depth=1,
        allow_delegation=False,
    )
    out = apply_delegation(parent, child, ceiling=ceiling)
    assert out.grant_id == "c"


def test_max_depth_one_delegable_child_at_depth1_rejected() -> None:
    ceiling = _ceiling(1)
    parent = make_grant("p", "org", allow_delegation=True, delegation_depth=0)
    child = make_grant(
        "c",
        "agent",
        delegator="org",
        delegation_depth=1,
        allow_delegation=True,
    )
    with pytest.raises(InvalidDelegation):
        apply_delegation(parent, child, ceiling=ceiling)


def test_max_depth_one_depth1_to_depth2_rejected() -> None:
    ceiling = _ceiling(1)
    parent = make_grant("p", "agent", allow_delegation=True, delegation_depth=1)
    child = make_grant("c", "sub", delegator="agent", delegation_depth=2)
    with pytest.raises(InvalidDelegation):
        apply_delegation(parent, child, ceiling=ceiling)


def test_max_depth_two_chain_hops() -> None:
    ceiling = _ceiling(2)
    g0 = make_grant("g0", "root", allow_delegation=True, delegation_depth=0)
    g1 = make_grant(
        "g1",
        "mid",
        delegator="root",
        delegation_depth=1,
        allow_delegation=True,
    )
    g2 = make_grant(
        "g2",
        "leaf",
        delegator="mid",
        delegation_depth=2,
        allow_delegation=False,
    )
    apply_delegation(g0, g1, ceiling=ceiling)
    apply_delegation(g1, g2, ceiling=ceiling)
    DelegationChain((g0, g1, g2)).validate(ceiling=ceiling)


def test_max_depth_two_depth2_to_depth3_rejected() -> None:
    ceiling = _ceiling(2)
    parent = make_grant("p", "mid", allow_delegation=True, delegation_depth=2)
    child = make_grant("c", "leaf", delegator="mid", delegation_depth=3)
    with pytest.raises(InvalidDelegation):
        apply_delegation(parent, child, ceiling=ceiling)


def test_wrong_depth_increment_rejected() -> None:
    parent = make_grant("p", "org", allow_delegation=True, delegation_depth=0)
    child = make_grant("c", "agent", delegator="org", delegation_depth=2)
    with pytest.raises(InvalidDelegation, match="depth"):
        apply_delegation(parent, child)


def test_depth_reset_rejected() -> None:
    parent = make_grant("p", "org", allow_delegation=True, delegation_depth=2)
    child = make_grant("c", "agent", delegator="org", delegation_depth=0)
    with pytest.raises(InvalidDelegation, match="depth"):
        apply_delegation(parent, child)


def test_cross_tenant_ceiling_rejected() -> None:
    ceiling = OrgAuthorityCeilingModel(tenant_id="t2", org_id="o", max_delegation_depth=2)
    parent = make_grant("p", "org", tenant="t1", allow_delegation=True, delegation_depth=0)
    child = make_grant("c", "agent", tenant="t1", delegator="org", delegation_depth=1)
    with pytest.raises(CrossTenantReference):
        apply_delegation(parent, child, ceiling=ceiling)


def test_bypass_without_ceiling_still_validates_subset_only() -> None:
    """Without ceiling, validate_delegation does not enforce org max depth policy."""
    ceiling = _ceiling(1)
    parent = make_grant("p", "org", allow_delegation=True, delegation_depth=0)
    child = make_grant(
        "c",
        "agent",
        delegator="org",
        delegation_depth=1,
        allow_delegation=True,
    )
    validate_delegation(parent, child)
    with pytest.raises(InvalidDelegation):
        apply_delegation(parent, child, ceiling=ceiling)


def test_condition_missing_no_effective_authority() -> None:
    g = make_grant("g", "s", conditions={"mfa": True})
    ev = EffectiveAuthorityEvaluator()
    assert ev.effective((g,), (), "s", "t1", g.not_before, conditions={}) == frozenset()
    assert (
        ev.effective((g,), (), "s", "t1", g.not_before, conditions={"other": True}) == frozenset()
    )


def test_condition_wrong_value_no_authority() -> None:
    g = make_grant("g", "s", conditions={"mfa": True})
    ev = EffectiveAuthorityEvaluator()
    assert ev.effective((g,), (), "s", "t1", g.not_before, conditions={"mfa": False}) == frozenset()


def test_condition_match_authority_activates() -> None:
    g = make_grant("g", "s", conditions={"mfa": True})
    ev = EffectiveAuthorityEvaluator()
    eff = ev.effective((g,), (), "s", "t1", g.not_before, conditions={"mfa": True})
    assert len(eff) == 1


def test_no_conditions_unchanged() -> None:
    g = make_grant("g", "s")
    ev = EffectiveAuthorityEvaluator()
    assert len(ev.effective((g,), (), "s", "t1", g.not_before)) == 1


def test_child_removes_parent_condition_rejected() -> None:
    parent = make_grant("p", "org", allow_delegation=True, conditions={"mfa": True})
    child = make_grant("c", "agent", delegator="org", allow_delegation=False)
    with pytest.raises(AuthorityExpansion):
        validate_delegation(parent, child)


def test_child_strengthens_parent_conditions_allowed() -> None:
    parent = make_grant("p", "org", allow_delegation=True, conditions={"mfa": True})
    child = make_grant(
        "c",
        "agent",
        delegator="org",
        allow_delegation=False,
        conditions={"mfa": True, "device_trusted": True},
    )
    validate_delegation(parent, child)
    apply_delegation(parent, child)


def test_multiple_conditions_all_required() -> None:
    g = make_grant("g", "s", conditions={"mfa": True, "device_trusted": True})
    ev = EffectiveAuthorityEvaluator()
    assert ev.effective((g,), (), "s", "t1", g.not_before, conditions={"mfa": True}) == frozenset()
    eff = ev.effective(
        (g,),
        (),
        "s",
        "t1",
        g.not_before,
        conditions={"device_trusted": True, "mfa": True},
    )
    assert len(eff) == 1


def test_condition_map_order_independent() -> None:
    g = make_grant("g", "s", conditions={"a": 1, "b": 2})
    ev = EffectiveAuthorityEvaluator()
    e1 = ev.effective((g,), (), "s", "t1", g.not_before, conditions={"a": 1, "b": 2})
    e2 = ev.effective((g,), (), "s", "t1", g.not_before, conditions={"b": 2, "a": 1})
    assert e1 == e2


def test_effective_risk_ceiling_on_union_tuples() -> None:
    g = make_grant("g", "s", risk=10, max_risk_class=3)
    assert effective_risk_ceiling(g) == 3
    tuples = grant_union((g,))
    assert all(t.risk_ceiling == 3 for t in tuples)


def test_effective_risk_org_ceiling_accepts_effective_not_nominal() -> None:
    g = make_grant("g", "s", risk=10, max_risk_class=3)
    tuples = grant_union((g,))
    ceiling = OrgAuthorityCeilingModel(tenant_id="t1", org_id="o", max_risk_class=5)
    restricted = grant_restriction(tuples, ceiling)
    assert len(restricted) == 1
    ceiling_strict = OrgAuthorityCeilingModel(tenant_id="t1", org_id="o", max_risk_class=2)
    assert grant_restriction(tuples, ceiling_strict) == frozenset()


def test_serialization_records_effective_risk() -> None:
    g = make_grant("g", "s", risk=10, max_risk_class=3)
    tuples = grant_union((g,))
    blob = serialize_authority_evaluation(tuples, EffectiveAuthorityEvaluator(), "s", "t1")
    assert blob["tuples"][0]["risk_ceiling"] == 3
    assert all(t.risk_ceiling == 3 for t in tuples)
