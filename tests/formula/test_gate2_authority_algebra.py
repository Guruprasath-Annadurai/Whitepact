# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from responsibleai.formula.authority.algebra import (
    EffectiveAuthorityEvaluator,
    authority_subset,
    validate_delegation,
)
from responsibleai.formula.authority.creation import (
    AuthorityCreationEvent,
    apply_creation_event,
    issuer_can_grant,
)
from responsibleai.formula.authority.delegation import DelegationChain
from responsibleai.formula.authority.lifecycle import (
    assert_grant_usable,
    consume_grant,
    lifecycle_at,
)
from responsibleai.formula.authority.models import (
    AuthorityConstraint,
    AuthorityContext,
    AuthorityGrant,
    AuthorityLifecycle,
    AuthoritySubject,
    ExplicitDeny,
    OrgAuthorityCeilingModel,
)
from responsibleai.formula.errors import (
    AuthorityExpansion,
    ConsumedGrant,
    ExpiredGrant,
)


def _grant(
    gid: str,
    subject: str,
    actions: frozenset[str],
    resources: frozenset[str],
    *,
    allow_delegation: bool = False,
    one_shot: bool = False,
    risk: int = 5,
    delegator: str | None = None,
    nb: datetime | None = None,
    exp: datetime | None = None,
) -> AuthorityGrant:
    now = datetime(2026, 6, 1, 12, 0, 0, tzinfo=UTC)
    return AuthorityGrant(
        grant_id=gid,
        tenant_id="t1",
        subject=AuthoritySubject(subject_id=subject, tenant_id="t1"),
        issuer_id="tenant_root:t1",
        delegator_id=delegator,
        actions=actions,
        resources=resources,
        purposes=frozenset({"ops"}),
        context=AuthorityContext(),
        not_before=nb or now,
        expires_at=exp or (now + timedelta(days=1)),
        risk_ceiling=risk,
        constraints=AuthorityConstraint(allow_delegation=allow_delegation, one_shot=one_shot),
        lifecycle=AuthorityLifecycle.ACTIVE,
    )


def test_multiple_grants_union_not_intersection() -> None:
    g_read = _grant("g1", "s1", frozenset({"read"}), frozenset({"x"}))
    g_write = _grant("g2", "s1", frozenset({"write"}), frozenset({"y"}))
    eff = EffectiveAuthorityEvaluator().effective((g_read, g_write), (), "s1", g_read.not_before)
    actions = {t.action for t in eff}
    assert actions == {"read", "write"}


def test_org_ceiling_restricts_union() -> None:
    g = _grant("g1", "s1", frozenset({"read", "write"}), frozenset({"x"}))
    ceiling = OrgAuthorityCeilingModel(
        tenant_id="t1", org_id="o1", allowed_actions=frozenset({"read"})
    )
    eff = EffectiveAuthorityEvaluator(ceiling=ceiling).effective((g,), (), "s1", g.not_before)
    assert {t.action for t in eff} == {"read"}


def test_explicit_deny_wins() -> None:
    g = _grant("g1", "s1", frozenset({"read"}), frozenset({"x"}))
    deny = ExplicitDeny("d1", "t1", "s1", frozenset({"read"}), frozenset({"x"}))
    eff = EffectiveAuthorityEvaluator().effective((g,), (deny,), "s1", g.not_before)
    assert eff == frozenset()


def test_delegation_cannot_widen_resources() -> None:
    parent = _grant("p", "org", frozenset({"read"}), frozenset({"x"}), allow_delegation=True)
    child = _grant(
        "c",
        "agent",
        frozenset({"read"}),
        frozenset({"x", "y"}),
        delegator="org",
        allow_delegation=False,
    )
    with pytest.raises(AuthorityExpansion):
        validate_delegation(parent, child)


def test_delegation_chain_valid() -> None:
    g0 = _grant("g0", "org", frozenset({"read"}), frozenset({"x"}), allow_delegation=True)
    g1 = _grant(
        "g1", "a", frozenset({"read"}), frozenset({"x"}), delegator="org", allow_delegation=True
    )
    g2 = _grant("g2", "b", frozenset({"read"}), frozenset({"x"}), delegator="a")
    chain = DelegationChain((g0, g1, g2))
    chain.validate()
    assert chain.root_effective_subset()


def test_temporal_half_open_boundary() -> None:
    start = datetime(2026, 6, 1, 0, 0, 0, tzinfo=UTC)
    end = datetime(2026, 6, 2, 0, 0, 0, tzinfo=UTC)
    g = _grant("g", "s", frozenset({"read"}), frozenset({"x"}), nb=start, exp=end)
    assert lifecycle_at(g, start) == AuthorityLifecycle.ACTIVE
    assert lifecycle_at(g, end) == AuthorityLifecycle.EXPIRED
    with pytest.raises(ExpiredGrant):
        assert_grant_usable(g, end)


def test_one_shot_consume() -> None:
    g = _grant("g", "s", frozenset({"read"}), frozenset({"x"}), one_shot=True)
    used = consume_grant(g)
    assert used.lifecycle == AuthorityLifecycle.CONSUMED
    with pytest.raises(ConsumedGrant):
        assert_grant_usable(used, g.not_before)


def test_self_issued_grant_rejected() -> None:
    g = _grant("g", "s", frozenset({"read"}), frozenset({"x"}))
    ev = AuthorityCreationEvent("s", "s", g, "bad", g.not_before, "e1", "p1")
    with pytest.raises(AuthorityExpansion):
        apply_creation_event((), ev, EffectiveAuthorityEvaluator())


def test_issuer_must_hold_authority() -> None:
    g_child = _grant("c", "agent", frozenset({"pay"}), frozenset({"acct"}))
    g_child = AuthorityGrant(
        grant_id=g_child.grant_id,
        tenant_id=g_child.tenant_id,
        subject=g_child.subject,
        issuer_id="weak",
        delegator_id=None,
        actions=g_child.actions,
        resources=g_child.resources,
        purposes=g_child.purposes,
        context=g_child.context,
        not_before=g_child.not_before,
        expires_at=g_child.expires_at,
        risk_ceiling=g_child.risk_ceiling,
        constraints=g_child.constraints,
        lifecycle=g_child.lifecycle,
    )
    assert not issuer_can_grant(
        "weak", g_child, (), EffectiveAuthorityEvaluator(), g_child.not_before
    )


def test_authority_subset_dimensions() -> None:
    parent = _grant("p", "s", frozenset({"read", "write"}), frozenset({"a", "b"}), risk=5)
    child_ok = _grant("c", "s2", frozenset({"read"}), frozenset({"a"}), risk=3, delegator="s")
    child_bad = _grant("c2", "s2", frozenset({"read"}), frozenset({"a"}), risk=9, delegator="s")
    assert authority_subset(child_ok, parent)
    assert not authority_subset(child_bad, parent)
