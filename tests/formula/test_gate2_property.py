# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st
from tests.formula.helpers import make_grant

from responsibleai.formula.authority.algebra import authority_subset
from responsibleai.formula.serialization import canonical_sha256


@given(
    st.sets(st.text(min_size=1, max_size=8), min_size=1, max_size=4),
    st.sets(st.text(min_size=1, max_size=8), min_size=1, max_size=4),
)
def test_canonical_hash_deterministic(actions: set[str], resources: set[str]) -> None:
    payload = {"actions": sorted(actions), "resources": sorted(resources)}
    assert canonical_sha256(payload) == canonical_sha256(payload)


@given(st.integers(min_value=1, max_value=9), st.integers(min_value=1, max_value=9))
def test_delegation_risk_widen_fails(child_risk: int, parent_risk: int) -> None:
    parent = make_grant("p", "s", risk=parent_risk, allow_delegation=True)
    child = make_grant("c", "s2", risk=child_risk, delegator="s")
    if child_risk > parent_risk:
        assert not authority_subset(child, parent)
