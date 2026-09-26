# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import replace

from tests.formula.helpers import make_grant

from responsibleai.formula.authority.algebra import EffectiveAuthorityEvaluator
from responsibleai.formula.authority.containment import grant_within_org_ceiling
from responsibleai.formula.authority.creation import issuer_can_grant
from responsibleai.formula.authority.models import (
    AuthorityContext,
    ExplicitDeny,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.authority.root import TenantRootPrincipal
from responsibleai.formula.authority.wildcard import WILDCARD
from responsibleai.formula.epistemic import EpistemicStatus
from responsibleai.formula.graph.elements import GraphNode
from responsibleai.formula.graph.graph import CanonicalAISystemGraph
from responsibleai.formula.graph.kinds import NodeKind
from responsibleai.formula.immutability import freeze_value
from responsibleai.formula.serialization import canonical_sha256


def _effective(
    grant_actions: frozenset[str],
    grant_resources: frozenset[str],
    denies: tuple[ExplicitDeny, ...],
) -> frozenset[tuple[str, str]]:
    g = make_grant("g", "s", actions=grant_actions, resources=grant_resources)
    eff = EffectiveAuthorityEvaluator().effective((g,), denies, "s", "t1", g.not_before)
    return frozenset((t.action, t.resource) for t in eff)


def test_allow_star_deny_read_blocks_read() -> None:
    deny = ExplicitDeny("d", "t1", "s", frozenset({"read"}), frozenset({WILDCARD}))
    eff = _effective(frozenset({WILDCARD}), frozenset({WILDCARD}), (deny,))
    assert ("read", "x") not in eff and ("read", "account-1") not in eff
    assert ("write", "x") in eff


def test_allow_star_deny_write_blocks_write() -> None:
    deny = ExplicitDeny("d", "t1", "s", frozenset({"write"}), frozenset({WILDCARD}))
    eff = _effective(frozenset({WILDCARD}), frozenset({WILDCARD}), (deny,))
    assert ("write", "x") not in eff
    assert ("read", "x") in eff


def test_allow_star_resource_star_deny_read_account1() -> None:
    deny = ExplicitDeny("d", "t1", "s", frozenset({"read"}), frozenset({"account-1"}))
    eff = _effective(frozenset({WILDCARD}), frozenset({WILDCARD}), (deny,))
    assert ("read", "account-1") not in eff
    assert ("read", "x") in eff


def test_allow_read_deny_star_blocks_read() -> None:
    deny = ExplicitDeny("d", "t1", "s", frozenset({WILDCARD}), frozenset({WILDCARD}))
    eff = _effective(frozenset({"read"}), frozenset({"x"}), (deny,))
    assert eff == frozenset()


def test_allow_star_deny_star_no_authority() -> None:
    deny = ExplicitDeny("d", "t1", "s", frozenset({WILDCARD}), frozenset({WILDCARD}))
    eff = _effective(frozenset({WILDCARD}), frozenset({WILDCARD}), (deny,))
    assert eff == frozenset()


def test_deny_order_independent() -> None:
    g = make_grant("g", "s", actions=frozenset({WILDCARD}), resources=frozenset({WILDCARD}))
    d1 = ExplicitDeny("d1", "t1", "s", frozenset({"read"}), frozenset({WILDCARD}), specificity=1)
    d2 = ExplicitDeny("d2", "t1", "s", frozenset({"write"}), frozenset({WILDCARD}), specificity=10)
    ev = EffectiveAuthorityEvaluator()
    e1 = ev.effective((g,), (d1, d2), "s", "t1", g.not_before)
    e2 = ev.effective((g,), (d2, d1), "s", "t1", g.not_before)
    assert {t.atom() for t in e1} == {t.atom() for t in e2}


def test_max_delegation_depth_zero_blocks_delegable_mint() -> None:
    ceiling = OrgAuthorityCeilingModel(tenant_id="t1", org_id="o", max_delegation_depth=0)
    grant = replace(
        make_grant("g", "a", allow_delegation=True, issuer_id="root-1"),
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    root = TenantRootPrincipal("t1", "root-1", "org", "ev", "pol", ceiling=ceiling)
    assert not grant_within_org_ceiling(grant, ceiling)
    assert not issuer_can_grant(
        "root-1",
        grant,
        (),
        EffectiveAuthorityEvaluator(ceiling=ceiling),
        grant.not_before,
        root=root,
    )


def test_max_delegation_depth_one_blocks_second_hop_delegation() -> None:
    from responsibleai.formula.authority.algebra import validate_delegation
    from responsibleai.formula.authority.models import AuthorityConstraint

    ceiling = OrgAuthorityCeilingModel(tenant_id="t1", org_id="o", max_delegation_depth=1)
    parent = replace(
        make_grant("p", "org", allow_delegation=True, delegation_depth=0),
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    child_leaf = replace(
        make_grant("c", "agent", delegator="org", delegation_depth=1),
        constraints=AuthorityConstraint.build(allow_delegation=False),
        epistemic_status=EpistemicStatus.OBSERVED,
    )
    child_delegable = replace(
        child_leaf,
        constraints=AuthorityConstraint.build(allow_delegation=True),
    )
    validate_delegation(parent, child_leaf)
    assert not grant_within_org_ceiling(child_delegable, ceiling)


def test_nested_set_freezing_canonical() -> None:
    a = freeze_value({"x", "y", "z"})
    b = freeze_value({"z", "x", "y"})
    assert a == b
    ctx1 = AuthorityContext.from_mapping({"tags": {"x", "y", "z"}})
    ctx2 = AuthorityContext.from_mapping({"tags": {"z", "x", "y"}})
    assert ctx1._pairs == ctx2._pairs
    g1 = CanonicalAISystemGraph("t1")
    g2 = CanonicalAISystemGraph("t1")
    g1.add_node(GraphNode.build("n1", "t1", NodeKind.AGENT, {"labels": {"x", "y", "z"}}))
    g2.add_node(GraphNode.build("n1", "t1", NodeKind.AGENT, {"labels": {"z", "x", "y"}}))
    assert g1.freeze().content_hash == g2.freeze().content_hash
    assert canonical_sha256({"tags": {"x", "y", "z"}}) == canonical_sha256(
        {"tags": {"z", "x", "y"}}
    )
