"""Tests for Heart Phase H7 — Non-Delegable and Human-Reserved
Authority (`governance/non_delegable_authority.py`).

Covers every registered pattern, the severity-ordering invariant
(NON_DELEGABLE always reported before HUMAN_RESERVED when both match),
determinism, and Hypothesis property tests over arbitrary action-type
sets.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.non_delegable_authority import (
    NonDelegableScope,
    check_non_delegable_authority,
)

_ORDINARY_ACTION_TYPES = (
    "payment.execute",
    "beneficiary.create",
    "deployment",
    "mcp_tool_call",
    "rai_scan",
)

_NON_DELEGABLE_ACTION_TYPES = (
    "heart.constitution.amend",
    "heart.constitution.ratify",
    "heart.root_authority.issue",
    "heart.root_authority.revoke",
    "heart.veto.override",
    "heart.consent.revoke_on_behalf_of_other",
)

_HUMAN_RESERVED_ACTION_TYPES = (
    "legal.attestation.sign",
    "heart.authority.emergency_override",
)


class TestNoViolation:
    def test_ordinary_action_types_have_no_violation(self) -> None:
        result = check_non_delegable_authority(frozenset(_ORDINARY_ACTION_TYPES))
        assert result is None

    def test_empty_action_types_have_no_violation(self) -> None:
        result = check_non_delegable_authority(frozenset())
        assert result is None


class TestNonDelegableMatches:
    def test_every_registered_non_delegable_pattern_is_caught(self) -> None:
        for action_type in _NON_DELEGABLE_ACTION_TYPES:
            result = check_non_delegable_authority(frozenset({action_type}))
            assert result is not None, f"{action_type} should be NON_DELEGABLE"
            assert result.scope == NonDelegableScope.NON_DELEGABLE
            assert result.action_type == action_type
            assert result.reason

    def test_wildcard_pattern_matches_any_constitution_action(self) -> None:
        result = check_non_delegable_authority(frozenset({"heart.constitution.anything_at_all"}))
        assert result is not None
        assert result.matched_pattern == "heart.constitution.*"
        assert result.scope == NonDelegableScope.NON_DELEGABLE

    def test_non_delegable_mixed_with_ordinary_actions_still_caught(self) -> None:
        result = check_non_delegable_authority(
            frozenset({"payment.execute", "heart.root_authority.issue", "deployment"})
        )
        assert result is not None
        assert result.action_type == "heart.root_authority.issue"
        assert result.scope == NonDelegableScope.NON_DELEGABLE


class TestHumanReservedMatches:
    def test_every_registered_human_reserved_pattern_is_caught(self) -> None:
        for action_type in _HUMAN_RESERVED_ACTION_TYPES:
            result = check_non_delegable_authority(frozenset({action_type}))
            assert result is not None, f"{action_type} should be HUMAN_RESERVED"
            assert result.scope == NonDelegableScope.HUMAN_RESERVED
            assert result.action_type == action_type

    def test_human_reserved_mixed_with_ordinary_actions_still_caught(self) -> None:
        result = check_non_delegable_authority(
            frozenset({"payment.execute", "legal.attestation.sign"})
        )
        assert result is not None
        assert result.action_type == "legal.attestation.sign"
        assert result.scope == NonDelegableScope.HUMAN_RESERVED


class TestSeverityOrdering:
    def test_non_delegable_reported_before_human_reserved_when_both_present(self) -> None:
        result = check_non_delegable_authority(
            frozenset({"legal.attestation.sign", "heart.veto.override", "payment.execute"})
        )
        assert result is not None
        assert result.scope == NonDelegableScope.NON_DELEGABLE
        assert result.action_type == "heart.veto.override"

    def test_all_non_delegable_types_together_report_alphabetically_first(self) -> None:
        result = check_non_delegable_authority(
            frozenset({"heart.veto.override", "heart.constitution.amend"})
        )
        assert result is not None
        assert result.scope == NonDelegableScope.NON_DELEGABLE
        assert result.action_type == "heart.constitution.amend"  # alphabetically first


class TestDeterminism:
    def test_same_input_always_yields_same_result(self) -> None:
        action_types = frozenset({"legal.attestation.sign", "heart.authority.emergency_override"})
        r1 = check_non_delegable_authority(action_types)
        r2 = check_non_delegable_authority(action_types)
        assert r1 == r2


class TestNonDelegableAuthorityProperties:
    """Hypothesis property tests over arbitrary action-type sets."""

    @given(action_types=st.sets(st.sampled_from(_ORDINARY_ACTION_TYPES), min_size=0, max_size=5))
    def test_any_combination_of_ordinary_actions_never_violates(
        self, action_types: set[str]
    ) -> None:
        result = check_non_delegable_authority(frozenset(action_types))
        assert result is None

    @given(
        non_delegable=st.sets(st.sampled_from(_NON_DELEGABLE_ACTION_TYPES), min_size=1, max_size=3),
        ordinary=st.sets(st.sampled_from(_ORDINARY_ACTION_TYPES), min_size=0, max_size=3),
        human_reserved=st.sets(
            st.sampled_from(_HUMAN_RESERVED_ACTION_TYPES), min_size=0, max_size=2
        ),
    )
    def test_any_non_delegable_presence_always_wins_regardless_of_what_else_is_present(
        self, non_delegable: set[str], ordinary: set[str], human_reserved: set[str]
    ) -> None:
        combined = frozenset(non_delegable | ordinary | human_reserved)
        result = check_non_delegable_authority(combined)
        assert result is not None
        assert result.scope == NonDelegableScope.NON_DELEGABLE

    @given(
        human_reserved=st.sets(
            st.sampled_from(_HUMAN_RESERVED_ACTION_TYPES), min_size=1, max_size=2
        ),
        ordinary=st.sets(st.sampled_from(_ORDINARY_ACTION_TYPES), min_size=0, max_size=3),
    )
    def test_human_reserved_without_non_delegable_always_reports_human_reserved(
        self, human_reserved: set[str], ordinary: set[str]
    ) -> None:
        combined = frozenset(human_reserved | ordinary)
        result = check_non_delegable_authority(combined)
        assert result is not None
        assert result.scope == NonDelegableScope.HUMAN_RESERVED
