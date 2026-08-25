"""Tests for Heart Phase H5 — Purpose Binding (`governance/purpose_binding.py`).

Covers every `PurposeBindingStatus` branch of `validate_purpose_binding()`
plus Hypothesis property tests for the composition invariant: a
`PurposeBinding` can only be VALID when it references the exact
`ConsentProof`/`IntentContract` supplied, that consent is itself
legitimate, the declared purpose matches the consented purpose
verbatim, and the referenced intent contract is currently active.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.consent_proof import (
    ConsentMethod,
    ConsentProof,
    ConsentValidationResult,
    build_consent_proof,
    validate_consent_proof,
)
from responsibleai.governance.intent import IntentContract
from responsibleai.governance.purpose_binding import (
    PurposeBindingStatus,
    build_purpose_binding,
    compute_purpose_binding_digest,
    validate_purpose_binding,
)
from responsibleai.governance.root_authority import (
    RootType,
    build_root_authority_record,
    validate_root_chain,
)


def _legitimate_consent(
    purpose: str = "vendor payments",
) -> tuple[ConsentProof, ConsentValidationResult]:
    human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
    root_result = validate_root_chain(human, lambda rid: None)
    proof = build_consent_proof(
        "u1",
        human.root_id,
        "agent-1",
        "payment.execute up to 500000",
        purpose,
        ConsentMethod.EXPLICIT_UI_ACTION,
    )
    return proof, validate_consent_proof(proof, root_result)


def _active_intent(**overrides: object) -> IntentContract:
    defaults: dict[str, object] = {
        "organization_id": "org1",
        "agent_id": "agent-1",
        "goal": "pay vendor X",
    }
    defaults.update(overrides)
    return IntentContract(**defaults)  # type: ignore[arg-type]


class TestPurposeBindingRecord:
    def test_canonical_digest_is_deterministic(self) -> None:
        binding = build_purpose_binding("purpose", "intent1", "consent1")
        expected = compute_purpose_binding_digest(
            binding.binding_id,
            binding.purpose,
            binding.intent_ref,
            binding.consent_ref,
            binding.bound_at,
        )
        assert binding.canonical_digest == expected

    def test_two_bindings_same_fields_different_digest(self) -> None:
        b1 = build_purpose_binding("purpose", "intent1", "consent1")
        b2 = build_purpose_binding("purpose", "intent1", "consent1")
        assert b1.canonical_digest != b2.canonical_digest  # distinct binding_id/bound_at

    def test_to_dict_round_trips_key_fields(self) -> None:
        binding = build_purpose_binding("purpose", "intent1", "consent1")
        d = binding.to_dict()
        assert d["binding_id"] == binding.binding_id
        assert d["purpose"] == "purpose"
        assert d["intent_ref"] == "intent1"
        assert d["consent_ref"] == "consent1"
        assert d["canonical_digest"] == binding.canonical_digest


class TestValidatePurposeBindingHappyPath:
    def test_valid_binding_is_valid(self) -> None:
        proof, consent_result = _legitimate_consent()
        intent = _active_intent()
        binding = build_purpose_binding("vendor payments", intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.VALID
        assert result.is_valid


class TestValidatePurposeBindingConsentFailures:
    def test_consent_ref_mismatch(self) -> None:
        proof, consent_result = _legitimate_consent()
        intent = _active_intent()
        binding = build_purpose_binding(
            "vendor payments", intent.contract_id, "some-other-consent-id"
        )
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.CONSENT_MISMATCH
        assert not result.is_valid

    def test_consent_validation_for_different_consent_id(self) -> None:
        """binding.consent_ref matches proof.consent_id, but the
        consent_validation passed in describes a different consent
        entirely -- caller error, must still be caught."""
        proof, _ = _legitimate_consent()
        other_proof, other_result = _legitimate_consent(purpose="other purpose")
        intent = _active_intent()
        binding = build_purpose_binding("vendor payments", intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, other_result, intent)
        assert result.status == PurposeBindingStatus.CONSENT_MISMATCH

    def test_consent_not_legitimate_when_root_revoked(self) -> None:
        human = build_root_authority_record("u2", RootType.HUMAN, "issuer", "oidc")
        object.__setattr__(human, "revoked_at", datetime.now(UTC))
        root_result = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u2",
            human.root_id,
            "agent-1",
            "scope",
            "vendor payments",
            ConsentMethod.SIGNED_DOCUMENT,
        )
        consent_result = validate_consent_proof(proof, root_result)
        intent = _active_intent()
        binding = build_purpose_binding("vendor payments", intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.CONSENT_NOT_LEGITIMATE


class TestValidatePurposeBindingPurposeMismatch:
    def test_purpose_does_not_match_consent_purpose(self) -> None:
        proof, consent_result = _legitimate_consent(purpose="vendor payments")
        intent = _active_intent()
        binding = build_purpose_binding(
            "a completely different purpose", intent.contract_id, proof.consent_id
        )
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.PURPOSE_MISMATCH

    def test_purpose_matching_is_case_sensitive_exact_string(self) -> None:
        proof, consent_result = _legitimate_consent(purpose="Vendor Payments")
        intent = _active_intent()
        binding = build_purpose_binding("vendor payments", intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.PURPOSE_MISMATCH


class TestValidatePurposeBindingIntentFailures:
    def test_intent_ref_mismatch(self) -> None:
        proof, consent_result = _legitimate_consent()
        intent = _active_intent()
        binding = build_purpose_binding("vendor payments", "some-other-intent-id", proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.INTENT_MISMATCH

    def test_intent_not_yet_valid(self) -> None:
        proof, consent_result = _legitimate_consent()
        intent = _active_intent(valid_from=datetime.now(UTC) + timedelta(days=1))
        binding = build_purpose_binding("vendor payments", intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.INTENT_NOT_ACTIVE

    def test_intent_expired(self) -> None:
        proof, consent_result = _legitimate_consent()
        intent = _active_intent(expires_at=datetime.now(UTC) - timedelta(days=1))
        binding = build_purpose_binding("vendor payments", intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.INTENT_NOT_ACTIVE


class TestValidatePurposeBindingOrdering:
    def test_consent_mismatch_reported_before_purpose_mismatch(self) -> None:
        """When both the consent_ref AND the purpose are wrong, the more
        fundamental problem (wrong consent referenced at all) must
        surface, not the purpose mismatch."""
        proof, consent_result = _legitimate_consent(purpose="vendor payments")
        intent = _active_intent()
        binding = build_purpose_binding(
            "totally different purpose", intent.contract_id, "wrong-consent-id"
        )
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.CONSENT_MISMATCH

    def test_purpose_mismatch_reported_before_intent_mismatch(self) -> None:
        proof, consent_result = _legitimate_consent(purpose="vendor payments")
        intent = _active_intent()
        binding = build_purpose_binding("different purpose", "wrong-intent-id", proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.PURPOSE_MISMATCH


class TestPurposeBindingProperties:
    """Hypothesis property tests for the composition invariant."""

    @given(purpose=st.text(min_size=1, max_size=50))
    def test_matching_purpose_and_refs_always_valid_when_consent_legitimate(
        self, purpose: str
    ) -> None:
        proof, consent_result = _legitimate_consent(purpose=purpose)
        intent = _active_intent()
        binding = build_purpose_binding(purpose, intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.VALID

    @given(
        declared_purpose=st.text(min_size=1, max_size=20),
        consented_purpose=st.text(min_size=1, max_size=20),
    )
    def test_mismatched_purpose_strings_never_yield_valid(
        self, declared_purpose: str, consented_purpose: str
    ) -> None:
        if declared_purpose == consented_purpose:
            return  # not the case under test
        proof, consent_result = _legitimate_consent(purpose=consented_purpose)
        intent = _active_intent()
        binding = build_purpose_binding(declared_purpose, intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.PURPOSE_MISMATCH
        assert not result.is_valid

    @given(bogus_consent_ref=st.text(min_size=1, max_size=20))
    def test_binding_consent_ref_not_matching_proof_never_yields_valid(
        self, bogus_consent_ref: str
    ) -> None:
        proof, consent_result = _legitimate_consent()
        if bogus_consent_ref == proof.consent_id:
            return
        intent = _active_intent()
        binding = build_purpose_binding("vendor payments", intent.contract_id, bogus_consent_ref)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status == PurposeBindingStatus.CONSENT_MISMATCH
        assert not result.is_valid
