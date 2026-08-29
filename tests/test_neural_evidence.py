"""Tests for Enterprise Neural Phase 16 —
`governance/neural/evidence.py`'s `NeuralCapabilityEvidence`,
`NeuralEvidenceType`, and `evaluate_capability_validation_claim()`.
See `docs/enterprise-neural/16_PHASE16_DESIGN.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.neural import (
    CapabilityState,
    DeviceTrustLevel,
    NeuralCapabilityEvidence,
    NeuralCapabilityManifest,
    NeuralEvidenceDecision,
    NeuralEvidenceReason,
    NeuralEvidenceType,
    evaluate_capability_validation_claim,
)


def _manifest(capabilities: dict[str, CapabilityState]) -> NeuralCapabilityManifest:
    return NeuralCapabilityManifest(
        device_identity="dev1",
        adapter_version="0.1",
        manufacturer="Acme",
        model="X1",
        firmware_version="1.0",
        transport="usb",
        channel_count=8,
        sampling_rate_hz=250.0,
        trust_level=DeviceTrustLevel.TRUST_A,
        capabilities=capabilities,
    )


def _evidence(
    evidence_type: NeuralEvidenceType,
    capability_name: str = "motor_intent",
) -> NeuralCapabilityEvidence:
    return NeuralCapabilityEvidence(
        device_identity="dev1",
        capability_name=capability_name,
        evidence_type=evidence_type,
        description="a validation study",
        evidence_ref="doi:10.0000/example",
        recorded_at=datetime.now(UTC),
    )


class TestNeuralCapabilityEvidenceValidation:
    def test_empty_device_identity_rejected(self) -> None:
        with pytest.raises(ValueError, match="device_identity"):
            NeuralCapabilityEvidence(
                device_identity="",
                capability_name="x",
                evidence_type=NeuralEvidenceType.WHITEPACT_MEASURED,
                description="d",
                evidence_ref="r",
                recorded_at=datetime.now(UTC),
            )

    def test_empty_evidence_ref_rejected(self) -> None:
        with pytest.raises(ValueError, match="evidence_ref"):
            NeuralCapabilityEvidence(
                device_identity="dev1",
                capability_name="x",
                evidence_type=NeuralEvidenceType.WHITEPACT_MEASURED,
                description="d",
                evidence_ref="",
                recorded_at=datetime.now(UTC),
            )


class TestNotAValidatedClaim:
    def test_experimental_capability_returns_not_a_validated_claim(self) -> None:
        manifest = _manifest({"motor_intent": CapabilityState.EXPERIMENTAL})
        result = evaluate_capability_validation_claim(manifest, "motor_intent", ())
        assert result.reason == NeuralEvidenceReason.NOT_A_VALIDATED_CLAIM
        assert result.decision == NeuralEvidenceDecision.ALLOW

    def test_unlisted_capability_returns_not_a_validated_claim(self) -> None:
        manifest = _manifest({})
        result = evaluate_capability_validation_claim(manifest, "motor_intent", ())
        assert result.reason == NeuralEvidenceReason.NOT_A_VALIDATED_CLAIM


class TestFailClosedOnMissingOrInsufficientEvidence:
    def test_validated_with_no_evidence_at_all_is_denied(self) -> None:
        manifest = _manifest({"motor_intent": CapabilityState.VALIDATED})
        result = evaluate_capability_validation_claim(manifest, "motor_intent", ())
        assert result.decision == NeuralEvidenceDecision.DENY
        assert result.reason == NeuralEvidenceReason.NO_EVIDENCE_RECORD

    def test_validated_with_only_vendor_self_reported_evidence_is_denied(self) -> None:
        manifest = _manifest({"motor_intent": CapabilityState.VALIDATED})
        evidence = (_evidence(NeuralEvidenceType.VENDOR_SELF_REPORTED),)
        result = evaluate_capability_validation_claim(manifest, "motor_intent", evidence)
        assert result.decision == NeuralEvidenceDecision.DENY
        assert result.reason == NeuralEvidenceReason.EVIDENCE_INSUFFICIENT

    def test_evidence_for_a_different_capability_does_not_count(self) -> None:
        manifest = _manifest({"motor_intent": CapabilityState.VALIDATED})
        evidence = (_evidence(NeuralEvidenceType.WHITEPACT_MEASURED, capability_name="other"),)
        result = evaluate_capability_validation_claim(manifest, "motor_intent", evidence)
        assert result.decision == NeuralEvidenceDecision.DENY
        assert result.reason == NeuralEvidenceReason.NO_EVIDENCE_RECORD


class TestQualifyingEvidenceAllows:
    @pytest.mark.parametrize(
        "evidence_type",
        [
            NeuralEvidenceType.WHITEPACT_MEASURED,
            NeuralEvidenceType.INDEPENDENT_THIRD_PARTY,
            NeuralEvidenceType.REGULATORY_CLEARANCE,
        ],
    )
    def test_each_qualifying_type_allows(self, evidence_type: NeuralEvidenceType) -> None:
        manifest = _manifest({"motor_intent": CapabilityState.VALIDATED})
        evidence = (_evidence(evidence_type),)
        result = evaluate_capability_validation_claim(manifest, "motor_intent", evidence)
        assert result.decision == NeuralEvidenceDecision.ALLOW
        assert result.reason == NeuralEvidenceReason.EVIDENCE_QUALIFIES

    def test_a_qualifying_record_alongside_vendor_only_records_still_allows(self) -> None:
        manifest = _manifest({"motor_intent": CapabilityState.VALIDATED})
        evidence = (
            _evidence(NeuralEvidenceType.VENDOR_SELF_REPORTED),
            _evidence(NeuralEvidenceType.INDEPENDENT_THIRD_PARTY),
        )
        result = evaluate_capability_validation_claim(manifest, "motor_intent", evidence)
        assert result.decision == NeuralEvidenceDecision.ALLOW


class TestVendorReportedAloneCanNeverAllow:
    """Property: no set of purely VENDOR_SELF_REPORTED evidence records,
    of any size, can ever produce ALLOW for a VALIDATED claim -- the
    directive's own distinction ("WhitePact's own measured evidence")
    must hold regardless of how many vendor claims pile up."""

    @given(st.integers(min_value=1, max_value=20))
    def test_any_number_of_vendor_only_records_denies(self, count: int) -> None:
        manifest = _manifest({"motor_intent": CapabilityState.VALIDATED})
        evidence = tuple(_evidence(NeuralEvidenceType.VENDOR_SELF_REPORTED) for _ in range(count))
        result = evaluate_capability_validation_claim(manifest, "motor_intent", evidence)
        assert result.decision == NeuralEvidenceDecision.DENY
