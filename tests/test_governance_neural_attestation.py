"""Tests for Enterprise Neural Phase 7 —
`governance/neural/attestation.py`'s `NeuralIntentAttestation`,
`mint_neural_intent_attestation`, `verify_neural_intent_attestation`,
and `compute_neural_action_digest`. See
`docs/enterprise-neural/07_PHASE7_DESIGN.md`.

The core property under test throughout is the master directive §9's
mutation-invalidates-authorization requirement: changing any
security-relevant field of a proposed action (target, purpose,
arguments) after attestation must invalidate it.
"""

from __future__ import annotations

import dataclasses
import os
from datetime import UTC, datetime, timedelta

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.crypto import KeyId, KeyPurpose
from responsibleai.governance.neural import (
    ConsentCategory,
    DeviceTrustLevel,
    NeuralAttestationRejectReason,
    NeuralDecision,
    NeuralDecisionStatus,
    NeuralIntentAttestation,
    compute_neural_action_digest,
    mint_neural_intent_attestation,
    verify_neural_intent_attestation,
)

_NOW = datetime.now(UTC)


def _decision(status: NeuralDecisionStatus = NeuralDecisionStatus.VALID) -> NeuralDecision:
    return NeuralDecision(
        schema_version=1,
        prediction="yes",
        calibrated_probability=0.9,
        uncertainty=0.1,
        signal_quality=0.8,
        decoder_id="d1",
        decoder_version="1.0",
        decoder_hash="abc123",
        calibration_id="c1",
        calibration_version="1.0",
        subject_id="u1",
        session_id="s1",
        device_reference="dev1",
        device_trust=DeviceTrustLevel.TRUST_A,
        issued_at=_NOW,
        expires_at=_NOW + timedelta(seconds=30),
        status=status,
    )


def _key_id(version: int = 1) -> KeyId:
    return KeyId(
        purpose=KeyPurpose.NEURAL_ATTESTATION, tenant_id=None, version=version, environment="test"
    )


def _mint(
    *,
    dek: bytes,
    key_id: KeyId | None = None,
    decision: NeuralDecision | None = None,
    purpose: str = "payment",
    target: str = "account-A",
    action_digest: str | None = None,
    ttl_seconds: float = 30.0,
) -> NeuralIntentAttestation:
    digest = action_digest or compute_neural_action_digest(
        "transfer", target, purpose, {"amount": 1000}
    )
    return mint_neural_intent_attestation(
        decision or _decision(),
        purpose=purpose,
        target=target,
        action_digest=digest,
        consent_scope=(ConsentCategory.INFERENCE_SHARING,),
        dek=dek,
        key_id=key_id or _key_id(),
        attestation_id="att1",
        nonce="nonce1",
        issued_at=_NOW,
        ttl_seconds=ttl_seconds,
    )


class TestComputeNeuralActionDigest:
    def test_deterministic_for_same_inputs(self) -> None:
        a = compute_neural_action_digest("transfer", "acct-A", "payment", {"amount": 1000})
        b = compute_neural_action_digest("transfer", "acct-A", "payment", {"amount": 1000})
        assert a == b

    def test_differs_when_amount_changes(self) -> None:
        a = compute_neural_action_digest("transfer", "acct-A", "payment", {"amount": 1000})
        b = compute_neural_action_digest("transfer", "acct-A", "payment", {"amount": 100000})
        assert a != b

    def test_differs_when_target_changes(self) -> None:
        a = compute_neural_action_digest("transfer", "acct-A", "payment", {"amount": 1000})
        b = compute_neural_action_digest("transfer", "acct-B", "payment", {"amount": 1000})
        assert a != b

    def test_differs_when_purpose_changes(self) -> None:
        a = compute_neural_action_digest("transfer", "acct-A", "payment", {"amount": 1000})
        b = compute_neural_action_digest("transfer", "acct-A", "other", {"amount": 1000})
        assert a != b

    def test_argument_key_order_does_not_affect_digest(self) -> None:
        a = compute_neural_action_digest("t", "x", "p", {"a": 1, "b": 2})
        b = compute_neural_action_digest("t", "x", "p", {"b": 2, "a": 1})
        assert a == b


class TestNeuralIntentAttestationConstruction:
    def test_rejects_empty_attestation_id(self) -> None:
        with pytest.raises(ValueError, match="attestation_id"):
            NeuralIntentAttestation(
                schema_version=1,
                attestation_id="",
                session_id="s1",
                subject_id="u1",
                decision=_decision(),
                purpose="p",
                target="t",
                action_digest="d",
                consent_scope=(),
                issued_at=_NOW,
                expires_at=_NOW + timedelta(seconds=30),
                nonce="n1",
                signing_key_id=_key_id(),
                signature="sig",
            )

    def test_rejects_empty_session_id(self) -> None:
        with pytest.raises(ValueError, match="session_id"):
            NeuralIntentAttestation(
                schema_version=1,
                attestation_id="a1",
                session_id="",
                subject_id="u1",
                decision=_decision(),
                purpose="p",
                target="t",
                action_digest="d",
                consent_scope=(),
                issued_at=_NOW,
                expires_at=_NOW + timedelta(seconds=30),
                nonce="n1",
                signing_key_id=_key_id(),
                signature="sig",
            )

    def test_rejects_empty_subject_id(self) -> None:
        with pytest.raises(ValueError, match="subject_id"):
            NeuralIntentAttestation(
                schema_version=1,
                attestation_id="a1",
                session_id="s1",
                subject_id="",
                decision=_decision(),
                purpose="p",
                target="t",
                action_digest="d",
                consent_scope=(),
                issued_at=_NOW,
                expires_at=_NOW + timedelta(seconds=30),
                nonce="n1",
                signing_key_id=_key_id(),
                signature="sig",
            )

    def test_rejects_empty_action_digest(self) -> None:
        with pytest.raises(ValueError, match="action_digest"):
            NeuralIntentAttestation(
                schema_version=1,
                attestation_id="a1",
                session_id="s1",
                subject_id="u1",
                decision=_decision(),
                purpose="p",
                target="t",
                action_digest="",
                consent_scope=(),
                issued_at=_NOW,
                expires_at=_NOW + timedelta(seconds=30),
                nonce="n1",
                signing_key_id=_key_id(),
                signature="sig",
            )

    def test_rejects_empty_nonce(self) -> None:
        with pytest.raises(ValueError, match="nonce"):
            NeuralIntentAttestation(
                schema_version=1,
                attestation_id="a1",
                session_id="s1",
                subject_id="u1",
                decision=_decision(),
                purpose="p",
                target="t",
                action_digest="d",
                consent_scope=(),
                issued_at=_NOW,
                expires_at=_NOW + timedelta(seconds=30),
                nonce="",
                signing_key_id=_key_id(),
                signature="sig",
            )

    def test_rejects_expires_at_not_after_issued_at(self) -> None:
        with pytest.raises(ValueError, match="expires_at"):
            NeuralIntentAttestation(
                schema_version=1,
                attestation_id="a1",
                session_id="s1",
                subject_id="u1",
                decision=_decision(),
                purpose="p",
                target="t",
                action_digest="d",
                consent_scope=(),
                issued_at=_NOW,
                expires_at=_NOW,
                nonce="n1",
                signing_key_id=_key_id(),
                signature="sig",
            )


class TestMintAndVerify:
    def test_valid_round_trip(self) -> None:
        dek = os.urandom(32)
        digest = compute_neural_action_digest("transfer", "account-A", "payment", {"amount": 1000})
        att = _mint(dek=dek, action_digest=digest)
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=digest, now=_NOW
        )
        assert result.is_valid
        assert result.reason is None

    def test_wrong_key_rejects_with_invalid_signature(self) -> None:
        dek = os.urandom(32)
        wrong_dek = os.urandom(32)
        digest = compute_neural_action_digest("transfer", "account-A", "payment", {"amount": 1000})
        att = _mint(dek=dek, action_digest=digest)
        result = verify_neural_intent_attestation(
            att, dek=wrong_dek, current_action_digest=digest, now=_NOW
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.INVALID_SIGNATURE

    def test_tampered_signature_rejects(self) -> None:
        dek = os.urandom(32)
        digest = compute_neural_action_digest("transfer", "account-A", "payment", {"amount": 1000})
        att = _mint(dek=dek, action_digest=digest)
        tampered = dataclasses.replace(
            att, signature=("0" if att.signature[0] != "0" else "1") + att.signature[1:]
        )
        result = verify_neural_intent_attestation(
            tampered, dek=dek, current_action_digest=digest, now=_NOW
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.INVALID_SIGNATURE

    def test_expired_attestation_rejects(self) -> None:
        dek = os.urandom(32)
        digest = compute_neural_action_digest("transfer", "account-A", "payment", {"amount": 1000})
        att = _mint(dek=dek, action_digest=digest, ttl_seconds=10.0)
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=digest, now=_NOW + timedelta(seconds=11)
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.EXPIRED

    def test_not_yet_expired_at_the_boundary_is_still_expired(self) -> None:
        """now == expires_at is treated as expired -- no off-by-one
        grace window."""
        dek = os.urandom(32)
        digest = compute_neural_action_digest("transfer", "account-A", "payment", {"amount": 1000})
        att = _mint(dek=dek, action_digest=digest, ttl_seconds=10.0)
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=digest, now=att.expires_at
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.EXPIRED

    def test_ambiguous_decision_attestation_is_always_rejected_at_verify(self) -> None:
        dek = os.urandom(32)
        digest = compute_neural_action_digest("transfer", "account-A", "payment", {"amount": 1000})
        att = _mint(
            dek=dek, decision=_decision(NeuralDecisionStatus.AMBIGUOUS), action_digest=digest
        )
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=digest, now=_NOW
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.DECISION_NOT_VALID

    def test_rejected_decision_attestation_is_always_rejected_at_verify(self) -> None:
        dek = os.urandom(32)
        digest = compute_neural_action_digest("transfer", "account-A", "payment", {"amount": 1000})
        att = _mint(
            dek=dek, decision=_decision(NeuralDecisionStatus.REJECTED), action_digest=digest
        )
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=digest, now=_NOW
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.DECISION_NOT_VALID


class TestMutationInvalidatesAuthorization:
    """The actual security property this module exists to implement --
    directive §9's worked example (change the amount, change the
    recipient), reproduced exactly."""

    def test_amount_change_invalidates(self) -> None:
        dek = os.urandom(32)
        original_digest = compute_neural_action_digest(
            "transfer", "account-A", "payment", {"amount": 1000}
        )
        att = _mint(dek=dek, action_digest=original_digest)
        mutated_digest = compute_neural_action_digest(
            "transfer", "account-A", "payment", {"amount": 100000}
        )
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=mutated_digest, now=_NOW
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.ACTION_MUTATED

    def test_recipient_change_invalidates(self) -> None:
        dek = os.urandom(32)
        original_digest = compute_neural_action_digest(
            "transfer", "account-A", "payment", {"amount": 1000}
        )
        att = _mint(dek=dek, action_digest=original_digest)
        mutated_digest = compute_neural_action_digest(
            "transfer", "account-B", "payment", {"amount": 1000}
        )
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=mutated_digest, now=_NOW
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.ACTION_MUTATED

    def test_purpose_change_invalidates(self) -> None:
        dek = os.urandom(32)
        original_digest = compute_neural_action_digest(
            "transfer", "account-A", "payment", {"amount": 1000}
        )
        att = _mint(dek=dek, action_digest=original_digest)
        mutated_digest = compute_neural_action_digest(
            "transfer", "account-A", "different_purpose", {"amount": 1000}
        )
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=mutated_digest, now=_NOW
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.ACTION_MUTATED

    def test_identical_action_still_verifies(self) -> None:
        """Sanity check: it's specifically mutation that's rejected,
        not verification in general."""
        dek = os.urandom(32)
        digest = compute_neural_action_digest("transfer", "account-A", "payment", {"amount": 1000})
        att = _mint(dek=dek, action_digest=digest)
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=digest, now=_NOW
        )
        assert result.is_valid


class TestProperties:
    @given(
        amount=st.integers(min_value=1, max_value=1_000_000),
        mutated_amount=st.integers(min_value=1, max_value=1_000_000),
    )
    def test_any_amount_mutation_invalidates(self, amount: int, mutated_amount: int) -> None:
        if amount == mutated_amount:
            return
        dek = os.urandom(32)
        original_digest = compute_neural_action_digest(
            "transfer", "account-A", "payment", {"amount": amount}
        )
        att = _mint(dek=dek, action_digest=original_digest)
        mutated_digest = compute_neural_action_digest(
            "transfer", "account-A", "payment", {"amount": mutated_amount}
        )
        result = verify_neural_intent_attestation(
            att, dek=dek, current_action_digest=mutated_digest, now=_NOW
        )
        assert not result.is_valid
        assert result.reason is NeuralAttestationRejectReason.ACTION_MUTATED

    @given(
        key_bytes_a=st.binary(min_size=32, max_size=32),
        key_bytes_b=st.binary(min_size=32, max_size=32),
    )
    def test_verification_only_succeeds_under_the_signing_key(
        self, key_bytes_a: bytes, key_bytes_b: bytes
    ) -> None:
        if key_bytes_a == key_bytes_b:
            return
        digest = compute_neural_action_digest("transfer", "account-A", "payment", {"amount": 1000})
        att = _mint(dek=key_bytes_a, action_digest=digest)
        result = verify_neural_intent_attestation(
            att, dek=key_bytes_b, current_action_digest=digest, now=_NOW
        )
        assert not result.is_valid
