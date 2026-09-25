# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import timedelta

from hypothesis import given
from hypothesis import strategies as st
from tests.formula.helpers import make_grant

from responsibleai.formula.authority.algebra import (
    EffectiveAuthorityEvaluator,
    authority_subset,
    grant_union,
)
from responsibleai.formula.authority.lifecycle import consume_grant, lifecycle_at
from responsibleai.formula.authority.models import (
    AuthorityLifecycle,
    ExplicitDeny,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.authority.wildcard import WILDCARD
from responsibleai.formula.errors import CrossTenantReference
from responsibleai.formula.graph.elements import GraphNode
from responsibleai.formula.graph.graph import CanonicalAISystemGraph
from responsibleai.formula.graph.kinds import NodeKind
from responsibleai.formula.invariants import FormulaInvariantChecker
from responsibleai.formula.serialization import canonical_sha256, serialize_grant


def test_p1_capability_not_authority() -> None:
    v = FormulaInvariantChecker().check_capability_not_authority(True, True, False)
    assert v


def test_p2_restriction_not_widen() -> None:
    parent = make_grant("p", "s", actions=frozenset({WILDCARD}))
    child = make_grant("c", "s2", actions=frozenset({"read"}))
    assert authority_subset(child, parent)


@given(st.integers(min_value=1, max_value=8), st.integers(min_value=1, max_value=8))
def test_p3_delegation_risk(child_risk: int, parent_risk: int) -> None:
    parent = make_grant("p", "s", risk=parent_risk, allow_delegation=True)
    child = make_grant("c", "s2", risk=child_risk, delegator="s")
    if child_risk > parent_risk:
        assert not authority_subset(child, parent)


def test_p4_expiry_not_restore() -> None:
    g = make_grant("g", "s")
    assert lifecycle_at(g, g.expires_at + timedelta(seconds=1)) == AuthorityLifecycle.EXPIRED


def test_p5_revoked_not_increase() -> None:
    g = make_grant("g", "s", lifecycle=AuthorityLifecycle.REVOKED)
    assert not g.valid_at(g.not_before)


def test_p6_consumed_not_increase() -> None:
    g = consume_grant(make_grant("g", "s", one_shot=True))
    assert g.lifecycle == AuthorityLifecycle.CONSUMED


def test_p7_deny_never_increases() -> None:
    g = make_grant("g", "s")
    ev = EffectiveAuthorityEvaluator()
    before = ev.effective((g,), (), "s", "t1", g.not_before)
    deny = ExplicitDeny("d", "t1", "s", frozenset({WILDCARD}), frozenset({WILDCARD}))
    after = ev.effective((g,), (deny,), "s", "t1", g.not_before)
    assert len(after) <= len(before)


def test_p8_org_ceiling() -> None:
    g = make_grant("g", "s", actions=frozenset({"pay"}), risk=9)
    ceiling = OrgAuthorityCeilingModel(
        "t1", "o", allowed_actions=frozenset({"read"}), max_risk_class=3
    )
    eff = EffectiveAuthorityEvaluator(ceiling).effective((g,), (), "s", "t1", g.not_before)
    assert len(eff) == 0


def test_p9_serialization_deterministic() -> None:
    g = make_grant("g", "s")
    assert canonical_sha256(serialize_grant(g)) == canonical_sha256(serialize_grant(g))


def test_p10_cross_tenant() -> None:
    g = CanonicalAISystemGraph("t1")
    try:
        g.add_node(GraphNode.build("n", "t2", NodeKind.AGENT))
        raise AssertionError("expected CrossTenantReference")
    except CrossTenantReference:
        pass


def test_p11_delegation_chain_subset() -> None:
    g0 = make_grant("g0", "org", allow_delegation=True)
    g1 = make_grant("g1", "a", delegator="org", allow_delegation=True)
    g2 = make_grant("g2", "b", delegator="a")
    from responsibleai.formula.authority.delegation import DelegationChain

    chain = DelegationChain((g0, g1, g2))
    assert chain.root_effective_subset()


def test_p12_grant_order_commutative() -> None:
    g1 = make_grant("g1", "s", actions=frozenset({"a", "b"}))
    g2 = make_grant("g2", "s", actions=frozenset({"b", "c"}))
    assert grant_union((g1, g2)) == grant_union((g2, g1))
