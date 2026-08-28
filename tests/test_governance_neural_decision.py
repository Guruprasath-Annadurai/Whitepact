"""Tests for Enterprise Neural Phase 6 —
`governance/neural/decision.py`'s `NeuralDecision`,
`NeuralDecisionStatus`, `classify_decision_status`, `is_expired`,
`matches_context`, and `is_stale_decoder`. See
`docs/enterprise-neural/06_PHASE6_DESIGN.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.neural import (
    DeviceTrustLevel,
    NeuralDecision,
    NeuralDecisionStatus,
    classify_decision_status,
    is_expired,
    is_stale_decoder,
    matches_context,
)

_NOW = datetime.now(UTC)


def _decision(**overrides: object) -> NeuralDecision:
    defaults: dict[str, object] = {
        "schema_version": 1,
        "prediction": "yes",
        "calibrated_probability": 0.9,
        "uncertainty": 0.1,
        "signal_quality": 0.8,
        "decoder_id": "d1",
        "decoder_version": "1.0",
        "decoder_hash": "abc123",
        "calibration_id": "c1",
        "calibration_version": "1.0",
        "subject_id": "u1",
        "session_id": "s1",
        "device_reference": "dev1",
        "device_trust": DeviceTrustLevel.TRUST_A,
        "issued_at": _NOW,
        "expires_at": _NOW + timedelta(seconds=30),
        "status": NeuralDecisionStatus.VALID,
    }
    defaults.update(overrides)
    return NeuralDecision(**defaults)  # type: ignore[arg-type]


class TestNeuralDecisionConstruction:
    def test_valid_construction(self) -> None:
        d = _decision()
        assert d.status is NeuralDecisionStatus.VALID

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), float("-inf"), 1.5, -0.1])
    def test_rejects_bad_calibrated_probability(self, bad: float) -> None:
        with pytest.raises(ValueError, match="calibrated_probability"):
            _decision(calibrated_probability=bad)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), 1.5, -0.1])
    def test_rejects_bad_uncertainty(self, bad: float) -> None:
        with pytest.raises(ValueError, match="uncertainty"):
            _decision(uncertainty=bad)

    @pytest.mark.parametrize("bad", [float("nan"), float("inf"), 1.5, -0.1])
    def test_rejects_bad_signal_quality(self, bad: float) -> None:
        with pytest.raises(ValueError, match="signal_quality"):
            _decision(signal_quality=bad)

    def test_rejects_expires_at_equal_to_issued_at(self) -> None:
        with pytest.raises(ValueError, match="expires_at"):
            _decision(issued_at=_NOW, expires_at=_NOW)

    def test_rejects_expires_at_before_issued_at(self) -> None:
        with pytest.raises(ValueError, match="expires_at"):
            _decision(issued_at=_NOW, expires_at=_NOW - timedelta(seconds=1))

    @pytest.mark.parametrize(
        "field", ["decoder_id", "decoder_hash", "calibration_id", "subject_id", "session_id"]
    )
    def test_rejects_empty_required_strings(self, field: str) -> None:
        with pytest.raises(ValueError, match=field):
            _decision(**{field: ""})

    def test_accepts_boundary_probability_values(self) -> None:
        _decision(calibrated_probability=0.0)
        _decision(calibrated_probability=1.0)
        _decision(uncertainty=0.0)
        _decision(uncertainty=1.0)
        _decision(signal_quality=0.0)
        _decision(signal_quality=1.0)


class TestClassifyDecisionStatus:
    def test_low_uncertainty_high_probability_is_valid(self) -> None:
        result = classify_decision_status(
            0.9, 0.1, ambiguous_uncertainty_threshold=0.3, min_valid_probability=0.6
        )
        assert result is NeuralDecisionStatus.VALID

    def test_high_uncertainty_is_ambiguous_regardless_of_probability(self) -> None:
        result = classify_decision_status(
            0.9, 0.5, ambiguous_uncertainty_threshold=0.3, min_valid_probability=0.6
        )
        assert result is NeuralDecisionStatus.AMBIGUOUS

    def test_low_probability_with_low_uncertainty_is_rejected(self) -> None:
        result = classify_decision_status(
            0.4, 0.1, ambiguous_uncertainty_threshold=0.3, min_valid_probability=0.6
        )
        assert result is NeuralDecisionStatus.REJECTED

    def test_nan_probability_is_rejected(self) -> None:
        result = classify_decision_status(
            float("nan"), 0.1, ambiguous_uncertainty_threshold=0.3, min_valid_probability=0.6
        )
        assert result is NeuralDecisionStatus.REJECTED

    def test_inf_uncertainty_is_rejected(self) -> None:
        result = classify_decision_status(
            0.9, float("inf"), ambiguous_uncertainty_threshold=0.3, min_valid_probability=0.6
        )
        assert result is NeuralDecisionStatus.REJECTED

    def test_uncertainty_checked_before_probability(self) -> None:
        """A low-probability, high-uncertainty decision is AMBIGUOUS,
        not REJECTED -- uncertainty is checked first."""
        result = classify_decision_status(
            0.1, 0.9, ambiguous_uncertainty_threshold=0.3, min_valid_probability=0.6
        )
        assert result is NeuralDecisionStatus.AMBIGUOUS


class TestIsExpired:
    def test_not_expired_before_expiry(self) -> None:
        d = _decision()
        assert not is_expired(d, now=d.issued_at)

    def test_expired_exactly_at_expiry(self) -> None:
        d = _decision()
        assert is_expired(d, now=d.expires_at)

    def test_expired_after_expiry(self) -> None:
        d = _decision()
        assert is_expired(d, now=d.expires_at + timedelta(seconds=1))


class TestMatchesContext:
    def test_matches_when_all_three_match(self) -> None:
        d = _decision()
        assert matches_context(d, subject_id="u1", session_id="s1", device_reference="dev1")

    def test_wrong_subject_does_not_match(self) -> None:
        d = _decision()
        assert not matches_context(d, subject_id="wrong", session_id="s1", device_reference="dev1")

    def test_wrong_session_does_not_match(self) -> None:
        d = _decision()
        assert not matches_context(d, subject_id="u1", session_id="wrong", device_reference="dev1")

    def test_wrong_device_does_not_match(self) -> None:
        d = _decision()
        assert not matches_context(d, subject_id="u1", session_id="s1", device_reference="wrong")


class TestIsStaleDecoder:
    def test_matching_version_is_not_stale(self) -> None:
        d = _decision(decoder_version="1.0")
        assert not is_stale_decoder(d, current_decoder_version="1.0")

    def test_different_version_is_stale(self) -> None:
        d = _decision(decoder_version="1.0")
        assert is_stale_decoder(d, current_decoder_version="2.0")


class TestProperties:
    @given(
        probability=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        uncertainty=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_valid_range_inputs_never_raise_on_construction(
        self, probability: float, uncertainty: float
    ) -> None:
        _decision(calibrated_probability=probability, uncertainty=uncertainty)

    @given(
        probability=st.one_of(
            st.just(float("nan")),
            st.just(float("inf")),
            st.just(float("-inf")),
            st.floats(min_value=1.0001, max_value=1000.0),
            st.floats(min_value=-1000.0, max_value=-0.0001),
        )
    )
    def test_out_of_range_or_non_finite_probability_always_rejected(
        self, probability: float
    ) -> None:
        with pytest.raises(ValueError):
            _decision(calibrated_probability=probability)

    @given(
        uncertainty=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        threshold=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
    )
    def test_status_is_never_valid_when_uncertainty_exceeds_threshold(
        self, uncertainty: float, threshold: float
    ) -> None:
        result = classify_decision_status(
            0.9, uncertainty, ambiguous_uncertainty_threshold=threshold, min_valid_probability=0.0
        )
        if uncertainty > threshold:
            assert result is NeuralDecisionStatus.AMBIGUOUS
