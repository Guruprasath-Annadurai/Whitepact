"""Tests for Heart Phase H11 — Heart Veto (`governance/heart_veto.py`).

Covers `apply_heart_veto()`'s derivation from every
`ConflictResolutionStatus`, `enforce_heart_veto()`'s raise/no-op
behavior, and Hypothesis property tests for the core invariant: a
veto is vetoed if and only if the source `ConflictResolutionResult`
was not legitimate, with no code path that suppresses it.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.authority_conflict_resolver import (
    ConflictResolutionResult,
    ConflictResolutionStatus,
)
from responsibleai.governance.heart_veto import (
    HeartVetoError,
    HeartVetoStatus,
    apply_heart_veto,
    enforce_heart_veto,
)


class TestApplyHeartVetoLegitimate:
    def test_legitimate_is_not_vetoed(self) -> None:
        cr = ConflictResolutionResult(ConflictResolutionStatus.LEGITIMATE)
        record = apply_heart_veto(cr)
        assert record.status == HeartVetoStatus.NOT_VETOED
        assert not record.is_vetoed

    def test_legitimate_carries_no_reason_or_detail(self) -> None:
        cr = ConflictResolutionResult(
            ConflictResolutionStatus.LEGITIMATE, detail="should be ignored"
        )
        record = apply_heart_veto(cr)
        assert record.reason is None
        assert record.detail is None

    def test_legitimate_preserves_human_reserved(self) -> None:
        cr = ConflictResolutionResult(ConflictResolutionStatus.LEGITIMATE, human_reserved=True)
        record = apply_heart_veto(cr)
        assert record.human_reserved is True


class TestApplyHeartVetoBlocking:
    @pytest.mark.parametrize(
        "status",
        [s for s in ConflictResolutionStatus if s != ConflictResolutionStatus.LEGITIMATE],
    )
    def test_every_non_legitimate_status_is_vetoed(self, status: ConflictResolutionStatus) -> None:
        cr = ConflictResolutionResult(status, detail="some detail")
        record = apply_heart_veto(cr)
        assert record.status == HeartVetoStatus.VETOED
        assert record.is_vetoed
        assert record.reason == status.value
        assert record.detail == "some detail"

    def test_human_reserved_preserved_on_vetoed_record(self) -> None:
        cr = ConflictResolutionResult(ConflictResolutionStatus.STALE, human_reserved=True)
        record = apply_heart_veto(cr)
        assert record.status == HeartVetoStatus.VETOED
        assert record.human_reserved is True


class TestEnforceHeartVeto:
    def test_not_vetoed_is_a_no_op(self) -> None:
        cr = ConflictResolutionResult(ConflictResolutionStatus.LEGITIMATE)
        record = apply_heart_veto(cr)
        enforce_heart_veto(record)  # must not raise

    def test_vetoed_raises_heart_veto_error(self) -> None:
        cr = ConflictResolutionResult(ConflictResolutionStatus.NON_DELEGABLE, detail="blocked")
        record = apply_heart_veto(cr)
        with pytest.raises(HeartVetoError) as exc_info:
            enforce_heart_veto(record)
        assert "NON_DELEGABLE" in str(exc_info.value)
        assert "blocked" in str(exc_info.value)

    def test_enforce_has_no_override_parameters(self) -> None:
        """Structural check, not just a docstring claim: enforce_heart_veto()
        accepts exactly one positional parameter and nothing else --
        no force flag, no override authority, no bypass reason."""
        import inspect

        sig = inspect.signature(enforce_heart_veto)
        assert list(sig.parameters.keys()) == ["record"]


class TestHeartVetoProperties:
    """Hypothesis property tests for the core invariant."""

    @given(status=st.sampled_from(list(ConflictResolutionStatus)))
    def test_vetoed_iff_not_legitimate(self, status: ConflictResolutionStatus) -> None:
        cr = ConflictResolutionResult(status)
        record = apply_heart_veto(cr)
        assert record.is_vetoed == (status != ConflictResolutionStatus.LEGITIMATE)

    @given(status=st.sampled_from(list(ConflictResolutionStatus)), human_reserved=st.booleans())
    def test_human_reserved_always_preserved_regardless_of_veto_outcome(
        self, status: ConflictResolutionStatus, human_reserved: bool
    ) -> None:
        cr = ConflictResolutionResult(status, human_reserved=human_reserved)
        record = apply_heart_veto(cr)
        assert record.human_reserved == human_reserved

    @given(status=st.sampled_from(list(ConflictResolutionStatus)))
    def test_enforce_raises_exactly_when_vetoed(self, status: ConflictResolutionStatus) -> None:
        cr = ConflictResolutionResult(status)
        record = apply_heart_veto(cr)
        if record.is_vetoed:
            with pytest.raises(HeartVetoError):
                enforce_heart_veto(record)
        else:
            enforce_heart_veto(record)  # must not raise
