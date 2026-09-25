# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.formula.authority.algebra import authority_subset, grant_union
from responsibleai.formula.authority.models import (
    AuthorityConstraint,
    AuthorityContext,
    AuthorityGrant,
    AuthorityLifecycle,
    AuthoritySubject,
)
from responsibleai.formula.serialization import canonical_sha256


def _mk_grant(actions: frozenset[str], resources: frozenset[str], risk: int) -> AuthorityGrant:
    now = datetime(2026, 1, 1, tzinfo=UTC)
    return AuthorityGrant(
        grant_id="g",
        tenant_id="t",
        subject=AuthoritySubject("s", "t"),
        issuer_id="root",
        delegator_id=None,
        actions=actions,
        resources=resources,
        purposes=frozenset({"p"}),
        context=AuthorityContext(),
        not_before=now,
        expires_at=now + timedelta(days=1),
        risk_ceiling=risk,
        constraints=AuthorityConstraint(),
        lifecycle=AuthorityLifecycle.ACTIVE,
    )


@given(
    st.sets(st.text(min_size=1, max_size=8), min_size=1, max_size=4),
    st.sets(st.text(min_size=1, max_size=8), min_size=1, max_size=4),
)
def test_p9_canonical_hash_deterministic(actions: set[str], resources: set[str]) -> None:
    payload = {"actions": sorted(actions), "resources": sorted(resources)}
    assert canonical_sha256(payload) == canonical_sha256(payload)


@given(st.integers(min_value=1, max_value=9), st.integers(min_value=1, max_value=9))
def test_p3_delegation_risk_widen_fails(child_risk: int, parent_risk: int) -> None:
    parent = _mk_grant(frozenset({"a"}), frozenset({"r"}), parent_risk)
    child = _mk_grant(frozenset({"a"}), frozenset({"r"}), child_risk)
    if child_risk > parent_risk:
        assert not authority_subset(child, parent)


@given(st.sets(st.text(min_size=1, max_size=5), min_size=1, max_size=3))
def test_p12_grant_order_invariant(actions: set[str]) -> None:
    g1 = _mk_grant(frozenset(actions), frozenset({"r"}), 5)
    g2 = _mk_grant(frozenset(actions), frozenset({"r"}), 5)
    u1 = grant_union((g1, g2))
    u2 = grant_union((g2, g1))
    assert u1 == u2
