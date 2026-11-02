"""Tests for the Authority Lattice (Heart Phase H2) --
`governance/authority_lattice.py`'s `AuthorityEnvelope`,
`compare_envelopes()`, `intersect_envelopes()`, and the
`AuthorityContext` adapters.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.authority_lattice import (
    AuthorityEnvelope,
    LatticeComparisonStatus,
    UnrepresentableConstraintError,
    authority_context_to_envelope,
    compare_authority_contexts,
    compare_envelopes,
    envelope_to_authority_context,
    intersect_envelopes,
)
from responsibleai.governance.models import AuthorityContext


class TestCompareEnvelopesAllowlistDimensions:
    def test_empty_envelopes_are_legitimate_subset(self) -> None:
        result = compare_envelopes(AuthorityEnvelope(), AuthorityEnvelope())
        assert result.status == LatticeComparisonStatus.LEGITIMATE_SUBSET

    def test_child_subset_of_parent_action_types_passes(self) -> None:
        parent = AuthorityEnvelope(action_types=frozenset({"a", "b", "c"}))
        child = AuthorityEnvelope(action_types=frozenset({"a", "b"}))
        assert compare_envelopes(parent, child).status == LatticeComparisonStatus.LEGITIMATE_SUBSET

    def test_child_adding_new_action_type_escalates(self) -> None:
        parent = AuthorityEnvelope(action_types=frozenset({"a"}))
        child = AuthorityEnvelope(action_types=frozenset({"a", "b"}))
        result = compare_envelopes(parent, child)
        assert result.status == LatticeComparisonStatus.ESCALATION
        assert result.dimension == "action_types"

    def test_parent_unconstrained_child_anything_passes(self) -> None:
        parent = AuthorityEnvelope(action_types=None)
        child = AuthorityEnvelope(action_types=frozenset({"a", "b", "c"}))
        assert compare_envelopes(parent, child).status == LatticeComparisonStatus.LEGITIMATE_SUBSET

    def test_parent_constrained_child_unset_escalates(self) -> None:
        parent = AuthorityEnvelope(targets=frozenset({"a"}))
        child = AuthorityEnvelope(targets=None)
        result = compare_envelopes(parent, child)
        assert result.status == LatticeComparisonStatus.ESCALATION
        assert result.dimension == "targets"


class TestCompareEnvelopesDenylistDimensions:
    def test_child_keeping_all_parent_denials_passes(self) -> None:
        parent = AuthorityEnvelope(denied_targets=frozenset({"admin"}))
        child = AuthorityEnvelope(denied_targets=frozenset({"admin", "billing"}))
        assert compare_envelopes(parent, child).status == LatticeComparisonStatus.LEGITIMATE_SUBSET

    def test_child_lifting_a_denial_escalates(self) -> None:
        parent = AuthorityEnvelope(denied_targets=frozenset({"admin"}))
        child = AuthorityEnvelope(denied_targets=frozenset())
        result = compare_envelopes(parent, child)
        assert result.status == LatticeComparisonStatus.ESCALATION
        assert result.dimension == "denied_targets"

    def test_child_dropping_an_approval_requirement_escalates(self) -> None:
        parent = AuthorityEnvelope(approval_requirements=frozenset({"deployment"}))
        child = AuthorityEnvelope(approval_requirements=frozenset())
        result = compare_envelopes(parent, child)
        assert result.status == LatticeComparisonStatus.ESCALATION
        assert result.dimension == "approval_requirements"


class TestCompareEnvelopesNumericDimensions:
    def test_child_lower_max_value_passes(self) -> None:
        parent = AuthorityEnvelope(max_value=1000)
        child = AuthorityEnvelope(max_value=500)
        assert compare_envelopes(parent, child).status == LatticeComparisonStatus.LEGITIMATE_SUBSET

    def test_child_higher_max_value_escalates(self) -> None:
        parent = AuthorityEnvelope(max_value=1000)
        child = AuthorityEnvelope(max_value=1001)
        result = compare_envelopes(parent, child)
        assert result.status == LatticeComparisonStatus.ESCALATION
        assert result.dimension == "max_value"

    def test_child_unset_numeric_when_parent_constrains_escalates(self) -> None:
        parent = AuthorityEnvelope(max_total_value=1000)
        child = AuthorityEnvelope(max_total_value=None)
        result = compare_envelopes(parent, child)
        assert result.status == LatticeComparisonStatus.ESCALATION
        assert result.dimension == "max_total_value"


class TestCompareEnvelopesHoursWindow:
    def test_child_narrower_window_passes(self) -> None:
        parent = AuthorityEnvelope(allowed_hours_utc=(22, 6))
        child = AuthorityEnvelope(allowed_hours_utc=(23, 5))
        assert compare_envelopes(parent, child).status == LatticeComparisonStatus.LEGITIMATE_SUBSET

    def test_child_wider_window_escalates(self) -> None:
        parent = AuthorityEnvelope(allowed_hours_utc=(22, 6))
        child = AuthorityEnvelope(allowed_hours_utc=(20, 6))
        result = compare_envelopes(parent, child)
        assert result.status == LatticeComparisonStatus.ESCALATION
        assert result.dimension == "allowed_hours_utc"

    def test_child_no_window_when_parent_restricts_escalates(self) -> None:
        parent = AuthorityEnvelope(allowed_hours_utc=(9, 17))
        child = AuthorityEnvelope(allowed_hours_utc=None)
        result = compare_envelopes(parent, child)
        assert result.status == LatticeComparisonStatus.ESCALATION


class TestIntersectEnvelopesNeverWidens:
    def test_intersection_of_action_types_is_intersection(self) -> None:
        e1 = AuthorityEnvelope(action_types=frozenset({"a", "b"}))
        e2 = AuthorityEnvelope(action_types=frozenset({"b", "c"}))
        result = intersect_envelopes(e1, e2)
        assert result.action_types == frozenset({"b"})

    def test_intersection_of_max_value_is_the_minimum(self) -> None:
        e1 = AuthorityEnvelope(max_value=1000)
        e2 = AuthorityEnvelope(max_value=500)
        assert intersect_envelopes(e1, e2).max_value == 500

    def test_unconstrained_dimension_does_not_narrow_result(self) -> None:
        e1 = AuthorityEnvelope(max_value=1000)
        e2 = AuthorityEnvelope(max_value=None)
        assert intersect_envelopes(e1, e2).max_value == 1000

    def test_denylists_union_not_intersect(self) -> None:
        """A denial from any source must still hold -- the union of
        denials, not the intersection, matches "effective restriction
        can only ever grow, never shrink"."""
        e1 = AuthorityEnvelope(denied_targets=frozenset({"admin"}))
        e2 = AuthorityEnvelope(denied_targets=frozenset({"billing"}))
        result = intersect_envelopes(e1, e2)
        assert result.denied_targets == frozenset({"admin", "billing"})

    def test_disjoint_action_types_intersect_to_empty(self) -> None:
        e1 = AuthorityEnvelope(action_types=frozenset({"a"}))
        e2 = AuthorityEnvelope(action_types=frozenset({"b"}))
        result = intersect_envelopes(e1, e2)
        assert result.action_types == frozenset()

    def test_intersecting_result_is_always_legitimate_subset_of_every_input(self) -> None:
        e1 = AuthorityEnvelope(action_types=frozenset({"a", "b"}), max_value=1000)
        e2 = AuthorityEnvelope(action_types=frozenset({"a", "c"}), max_value=500)
        e3 = AuthorityEnvelope(action_types=frozenset({"a"}), max_value=800)
        effective = intersect_envelopes(e1, e2, e3)
        for source in (e1, e2, e3):
            assert compare_envelopes(source, effective).status == (
                LatticeComparisonStatus.LEGITIMATE_SUBSET
            )

    def test_no_envelopes_returns_fully_unconstrained(self) -> None:
        result = intersect_envelopes()
        assert result == AuthorityEnvelope()

    def test_single_envelope_returns_itself(self) -> None:
        e = AuthorityEnvelope(action_types=frozenset({"a"}))
        assert intersect_envelopes(e) == e

    def test_hours_window_intersection(self) -> None:
        e1 = AuthorityEnvelope(allowed_hours_utc=(9, 17))
        e2 = AuthorityEnvelope(allowed_hours_utc=(12, 20))
        result = intersect_envelopes(e1, e2)
        # overlap is [12, 17)
        assert result.allowed_hours_utc == (12, 17)

    def test_disjoint_hours_window_intersects_to_empty(self) -> None:
        e1 = AuthorityEnvelope(allowed_hours_utc=(0, 6))
        e2 = AuthorityEnvelope(allowed_hours_utc=(12, 18))
        result = intersect_envelopes(e1, e2)
        assert result.allowed_hours_utc == (0, 0)


class TestAuthorityContextAdapters:
    def test_round_trip_preserves_known_dimensions(self) -> None:
        ctx = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"rai_scan"}),
            constraints={"max_value_usd": 500, "allowed_targets": ["a", "b"]},
            require_approval_for=frozenset({"deployment"}),
        )
        envelope = authority_context_to_envelope(ctx)
        back = envelope_to_authority_context(envelope, delegated_by="org-1")
        assert back.granted_action_types == ctx.granted_action_types
        assert back.constraints["max_value_usd"] == 500
        assert set(back.constraints["allowed_targets"]) == {"a", "b"}
        assert back.require_approval_for == ctx.require_approval_for

    def test_unmapped_constraint_raises(self) -> None:
        ctx = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"x"}),
            constraints={"memory_scope": "org:acme"},
        )
        try:
            authority_context_to_envelope(ctx)
            raise AssertionError("expected UnrepresentableConstraintError")
        except UnrepresentableConstraintError as exc:
            assert "memory_scope" in exc.unmapped_keys

    def test_compare_authority_contexts_delegates_correctly(self) -> None:
        parent = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"a", "b"}))
        child = AuthorityContext(delegated_by="p", granted_action_types=frozenset({"a"}))
        result = compare_authority_contexts(parent, child)
        assert result.status == LatticeComparisonStatus.LEGITIMATE_SUBSET

    def test_compare_authority_contexts_surfaces_unrepresentable(self) -> None:
        ctx_with_memory_scope = AuthorityContext(
            delegated_by="org-1",
            granted_action_types=frozenset({"x"}),
            constraints={"memory_scope": "org:acme"},
        )
        clean_ctx = AuthorityContext(delegated_by="org-1", granted_action_types=frozenset({"x"}))
        result = compare_authority_contexts(ctx_with_memory_scope, clean_ctx)
        assert result.status == LatticeComparisonStatus.UNREPRESENTABLE_CONSTRAINT


# ── Property tests (Hypothesis) -- reusing tests/test_property_based.py's
# established pattern for pure, synchronous governance functions. ──────────

_action_type = st.text(alphabet=st.characters(whitelist_categories=("Ll",)), min_size=1, max_size=8)


class TestLatticeProperties:
    @given(
        parent_types=st.sets(_action_type, min_size=0, max_size=8),
        subset_fraction=st.floats(min_value=0.0, max_value=1.0),
    )
    def test_genuine_subset_action_types_always_legitimate(
        self, parent_types: set[str], subset_fraction: float
    ) -> None:
        parent = AuthorityEnvelope(action_types=frozenset(parent_types))
        parent_list = sorted(parent_types)
        cut = round(len(parent_list) * subset_fraction)
        child = AuthorityEnvelope(action_types=frozenset(parent_list[:cut]))
        assert compare_envelopes(parent, child).status == LatticeComparisonStatus.LEGITIMATE_SUBSET

    @given(
        parent_types=st.sets(_action_type, min_size=0, max_size=8),
        extra=_action_type,
    )
    def test_any_added_action_type_always_escalates(
        self, parent_types: set[str], extra: str
    ) -> None:
        from hypothesis import assume

        assume(extra not in parent_types)
        parent = AuthorityEnvelope(action_types=frozenset(parent_types))
        child = AuthorityEnvelope(action_types=frozenset({*parent_types, extra}))
        result = compare_envelopes(parent, child)
        assert result.status == LatticeComparisonStatus.ESCALATION

    @given(
        a=st.floats(min_value=0, max_value=1_000_000, allow_nan=False),
        b=st.floats(min_value=0, max_value=1_000_000, allow_nan=False),
    )
    def test_intersection_max_value_never_exceeds_either_input(self, a: float, b: float) -> None:
        e1 = AuthorityEnvelope(max_value=a)
        e2 = AuthorityEnvelope(max_value=b)
        result = intersect_envelopes(e1, e2)
        assert result.max_value is not None
        assert result.max_value <= a
        assert result.max_value <= b

    @given(
        types_a=st.sets(_action_type, min_size=0, max_size=6),
        types_b=st.sets(_action_type, min_size=0, max_size=6),
    )
    def test_intersection_is_always_subset_of_both_inputs(
        self, types_a: set[str], types_b: set[str]
    ) -> None:
        e1 = AuthorityEnvelope(action_types=frozenset(types_a))
        e2 = AuthorityEnvelope(action_types=frozenset(types_b))
        result = intersect_envelopes(e1, e2)
        assert result.action_types is not None
        assert result.action_types <= frozenset(types_a)
        assert result.action_types <= frozenset(types_b)

    @given(
        h1_start=st.integers(min_value=0, max_value=23),
        h1_end=st.integers(min_value=0, max_value=23),
        h2_start=st.integers(min_value=0, max_value=23),
        h2_end=st.integers(min_value=0, max_value=23),
    )
    def test_hours_intersection_never_covers_an_hour_outside_either_window(
        self, h1_start: int, h1_end: int, h2_start: int, h2_end: int
    ) -> None:
        from responsibleai.governance.authority_lattice import _hours_in_window

        e1 = AuthorityEnvelope(allowed_hours_utc=(h1_start, h1_end))
        e2 = AuthorityEnvelope(allowed_hours_utc=(h2_start, h2_end))
        result = intersect_envelopes(e1, e2)
        assert result.allowed_hours_utc is not None
        result_hours = _hours_in_window(*result.allowed_hours_utc)
        w1 = _hours_in_window(h1_start, h1_end)
        w2 = _hours_in_window(h2_start, h2_end)
        assert result_hours <= w1
        assert result_hours <= w2
