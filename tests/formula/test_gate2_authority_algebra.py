# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from tests.formula.helpers import make_grant

from responsibleai.formula.authority.algebra import (
    EffectiveAuthorityEvaluator,
    authority_subset,
    grant_intersection,
    validate_delegation,
)
from responsibleai.formula.authority.context_match import grant_context_matches
from responsibleai.formula.authority.creation import (
    issuer_can_grant,
)
from responsibleai.formula.authority.lifecycle import (
    assert_grant_usable,
    consume_grant,
    lifecycle_at,
)
from responsibleai.formula.authority.models import (
    AuthorityContext,
    AuthorityGrant,
    AuthorityLifecycle,
    ExplicitDeny,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.authority.root import TenantRootPrincipal
from responsibleai.formula.authority.wildcard import WILDCARD
from responsibleai.formula.errors import (
    AuthorityExpansion,
    ConsumedGrant,
    ExpiredGrant,
)


def test_context_missing_required_not_applicable() -> None:
    g = make_grant("g", "s1", context=AuthorityContext.from_mapping({"environment": "prod"}))
    assert grant_context_matches(g.context, AuthorityContext.from_mapping()) is False
    ev = EffectiveAuthorityEvaluator()
    assert (
        len(ev.effective((g,), (), "s1", "t1", g.not_before, AuthorityContext.from_mapping())) == 0
    )


def test_multiple_grants_union() -> None:
    g_read = make_grant("g1", "s1", actions=frozenset({"read"}), resources=frozenset({"x"}))
    g_write = make_grant("g2", "s1", actions=frozenset({"write"}), resources=frozenset({"y"}))
    eff = EffectiveAuthorityEvaluator().effective(
        (g_read, g_write), (), "s1", "t1", g_read.not_before
    )
    assert {t.action for t in eff} == {"read", "write"}


def test_org_ceiling_drops_high_risk() -> None:
    g = make_grant("g1", "s1", actions=frozenset({"read", "write"}), risk=9)
    ceiling = OrgAuthorityCeilingModel(
        tenant_id="t1", org_id="o1", allowed_actions=frozenset({"read"}), max_risk_class=5
    )
    eff = EffectiveAuthorityEvaluator(ceiling=ceiling).effective((g,), (), "s1", "t1", g.not_before)
    assert eff == frozenset() or all(t.risk_ceiling <= 5 for t in eff)


def test_explicit_deny_wins() -> None:
    g = make_grant("g1", "s1")
    deny = ExplicitDeny("d1", "t1", "s1", frozenset({"read"}), frozenset({"x"}))
    eff = EffectiveAuthorityEvaluator().effective((g,), (deny,), "s1", "t1", g.not_before)
    assert eff == frozenset()


def test_delegation_context_child_broader_fails() -> None:
    parent = make_grant(
        "p",
        "org",
        allow_delegation=True,
        context=AuthorityContext.from_mapping({"environment": "prod"}),
    )
    child = make_grant(
        "c",
        "agent",
        delegator="org",
        context=AuthorityContext.from_mapping(),
    )
    with pytest.raises(AuthorityExpansion):
        validate_delegation(parent, child)


def test_purpose_wildcard_subset() -> None:
    parent = make_grant("p", "s", purposes=frozenset({"ops"}))
    child_wild = make_grant("c", "s2", purposes=frozenset({WILDCARD}))
    assert not authority_subset(child_wild, parent)
    parent_w = make_grant("pw", "s", purposes=frozenset({WILDCARD}))
    child_specific = make_grant("cs", "s2", purposes=frozenset({"ops"}))
    assert authority_subset(child_specific, parent_w)


def test_grant_intersection_ignores_grant_id() -> None:
    g1 = make_grant("g1", "s")
    g2 = make_grant("g2", "s")
    u1 = EffectiveAuthorityEvaluator().effective((g1,), (), "s", "t1", g1.not_before)
    u2 = EffectiveAuthorityEvaluator().effective((g2,), (), "s", "t1", g2.not_before)
    assert grant_intersection(u1, u2) == u1


def test_temporal_half_open_boundary() -> None:
    start = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 6, 2, 0, 0, 0, tzinfo=UTC)
    g = make_grant("g", "s", nb=start, exp=end)
    assert lifecycle_at(g, start) == AuthorityLifecycle.ACTIVE
    assert lifecycle_at(g, end) == AuthorityLifecycle.EXPIRED
    with pytest.raises(ExpiredGrant):
        assert_grant_usable(g, end)


def test_pending_not_usable() -> None:
    g = make_grant("g", "s", lifecycle=AuthorityLifecycle.PENDING)
    with pytest.raises(ConsumedGrant):
        assert_grant_usable(g, g.not_before)


def test_one_shot_consume() -> None:
    g = make_grant("g", "s", one_shot=True)
    used = consume_grant(g)
    assert used.lifecycle == AuthorityLifecycle.CONSUMED
    with pytest.raises(ConsumedGrant):
        assert_grant_usable(used, g.not_before)


def test_issuer_cannot_mint_broader_grant() -> None:
    issuer_g = make_grant(
        "ig",
        "issuer",
        actions=frozenset({"read"}),
        purposes=frozenset({"ops"}),
        risk=3,
        allow_delegation=True,
        exp=datetime(2026, 6, 1, 12, 10, 0, tzinfo=UTC),
    )
    new_g = make_grant(
        "ng",
        "agent",
        actions=frozenset({"read"}),
        purposes=frozenset({WILDCARD}),
        risk=10,
        allow_delegation=True,
        issuer_id="issuer",
    )
    assert not issuer_can_grant(
        "issuer", new_g, (issuer_g,), EffectiveAuthorityEvaluator(), issuer_g.not_before
    )


def test_root_requires_evidence_not_prefix() -> None:
    g = make_grant("g", "agent", issuer_id="not-a-real-root")
    assert not issuer_can_grant(
        "not-a-real-root", g, (), EffectiveAuthorityEvaluator(), g.not_before
    )
    root = TenantRootPrincipal("t1", "root-1", "org", "ev-root", "pol-1")
    g2 = AuthorityGrant(
        grant_id="g2",
        tenant_id="t1",
        subject=make_grant("x", "agent").subject,
        issuer_id="root-1",
        delegator_id=None,
        actions=frozenset({"read"}),
        resources=frozenset({"x"}),
        purposes=frozenset({"ops"}),
        not_before=make_grant("x", "agent").not_before,
        expires_at=make_grant("x", "agent").expires_at,
        risk_ceiling=5,
        constraints=make_grant("x", "agent").constraints,
        evidence_ref="",
    )
    assert not issuer_can_grant(
        "root-1", g2, (), EffectiveAuthorityEvaluator(), g2.not_before, root=root
    )
