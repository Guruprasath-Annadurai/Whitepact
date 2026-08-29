"""Tests for Heart Phase H4 — Consent Proof (`governance/consent_proof.py`).

Covers every `ConsentValidationStatus` branch of `validate_consent_proof()`
plus Hypothesis property tests for the composition invariant: a
`ConsentProof` can only be VALID when both the proof itself is
temporally valid AND the `RootValidationResult` passed in is both VALID
and for the exact root the proof claims.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.consent_proof import (
    ConsentMethod,
    ConsentValidationResult,
    ConsentValidationStatus,
    build_consent_proof,
    compute_consent_digest,
    validate_consent_proof,
)
from responsibleai.governance.root_authority import (
    RootType,
    RootValidationResult,
    RootValidationStatus,
    build_root_authority_record,
    validate_root_chain,
)


def _valid_root_and_result() -> tuple[str, RootValidationResult]:
    human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
    result = validate_root_chain(human, lambda rid: None)
    return human.root_id, result


class TestConsentProofRecord:
    def test_canonical_digest_is_deterministic(self) -> None:
        proof = build_consent_proof(
            "u1", "root1", "agent1", "scope", "purpose", ConsentMethod.EXPLICIT_UI_ACTION
        )
        expected = compute_consent_digest(
            proof.consent_id,
            proof.subject_id,
            proof.consenting_root_id,
            proof.grantee_id,
            proof.scope_description,
            proof.purpose,
            proof.consent_method,
            proof.consented_at,
            proof.allowed_action_types,
            proof.allowed_targets,
        )
        assert proof.canonical_digest == expected

    def test_two_proofs_same_fields_different_digest(self) -> None:
        p1 = build_consent_proof(
            "u1", "root1", "agent1", "scope", "purpose", ConsentMethod.EXPLICIT_UI_ACTION
        )
        p2 = build_consent_proof(
            "u1", "root1", "agent1", "scope", "purpose", ConsentMethod.EXPLICIT_UI_ACTION
        )
        assert p1.canonical_digest != p2.canonical_digest  # distinct consent_id/consented_at

    def test_to_dict_round_trips_key_fields(self) -> None:
        proof = build_consent_proof(
            "u1", "root1", "agent1", "scope", "purpose", ConsentMethod.SIGNED_DOCUMENT
        )
        d = proof.to_dict()
        assert d["consent_id"] == proof.consent_id
        assert d["subject_id"] == "u1"
        assert d["consenting_root_id"] == "root1"
        assert d["grantee_id"] == "agent1"
        assert d["consent_method"] == "SIGNED_DOCUMENT"
        assert d["canonical_digest"] == proof.canonical_digest

    def test_is_temporally_valid_true_by_default(self) -> None:
        proof = build_consent_proof(
            "u1", "root1", "agent1", "scope", "purpose", ConsentMethod.VERBAL_RECORDED
        )
        assert proof.is_temporally_valid()

    def test_is_temporally_valid_false_when_revoked(self) -> None:
        proof = build_consent_proof(
            "u1", "root1", "agent1", "scope", "purpose", ConsentMethod.VERBAL_RECORDED
        )
        object.__setattr__(proof, "revoked_at", datetime.now(UTC))
        assert not proof.is_temporally_valid()

    def test_is_temporally_valid_false_when_not_yet_valid(self) -> None:
        proof = build_consent_proof(
            "u1",
            "root1",
            "agent1",
            "scope",
            "purpose",
            ConsentMethod.API_AUTHENTICATED_REQUEST,
            not_before=datetime.now(UTC) + timedelta(days=1),
        )
        assert not proof.is_temporally_valid()

    def test_is_temporally_valid_false_when_expired(self) -> None:
        proof = build_consent_proof(
            "u1",
            "root1",
            "agent1",
            "scope",
            "purpose",
            ConsentMethod.DELEGATED_POLICY,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        assert not proof.is_temporally_valid()

    def test_expiry_boundary_is_expired(self) -> None:
        now = datetime.now(UTC)
        proof = build_consent_proof(
            "u1",
            "root1",
            "agent1",
            "scope",
            "purpose",
            ConsentMethod.SIGNED_DOCUMENT,
            expires_at=now,
        )
        assert not proof.is_temporally_valid(now=now)


class TestValidateConsentProofHappyPath:
    def test_valid_proof_with_valid_root_is_valid(self) -> None:
        root_id, root_result = _valid_root_and_result()
        proof = build_consent_proof(
            "u1",
            root_id,
            "agent1",
            "payment.execute",
            "vendor payments",
            ConsentMethod.EXPLICIT_UI_ACTION,
        )
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.VALID
        assert result.is_valid

    def test_organization_root_backing_consent_is_valid(self) -> None:
        org = build_root_authority_record("org1", RootType.ORGANIZATION, "issuer", "saml")
        root_result = validate_root_chain(org, lambda rid: None)
        proof = build_consent_proof(
            "org1", org.root_id, "agent1", "scope", "purpose", ConsentMethod.DELEGATED_POLICY
        )
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.VALID


class TestValidateConsentProofRootFailures:
    def test_root_mismatch_when_result_is_for_different_root(self) -> None:
        _, root_result = _valid_root_and_result()
        proof = build_consent_proof(
            "u1", "some-other-root-id", "agent1", "scope", "purpose", ConsentMethod.SIGNED_DOCUMENT
        )
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.ROOT_MISMATCH
        assert not result.is_valid

    def test_root_not_legitimate_when_root_revoked(self) -> None:
        human = build_root_authority_record("u2", RootType.HUMAN, "issuer", "oidc")
        object.__setattr__(human, "revoked_at", datetime.now(UTC))
        root_result = validate_root_chain(human, lambda rid: None)
        assert root_result.status == RootValidationStatus.REVOKED
        proof = build_consent_proof(
            "u2", human.root_id, "agent1", "scope", "purpose", ConsentMethod.VERBAL_RECORDED
        )
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.ROOT_NOT_LEGITIMATE

    def test_root_not_legitimate_when_root_chain_broken(self) -> None:
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        root_result = validate_root_chain(sp, lambda rid: None)
        assert root_result.status == RootValidationStatus.ROOT_TYPE_CANNOT_SELF_ORIGINATE
        proof = build_consent_proof(
            "sp1", sp.root_id, "agent1", "scope", "purpose", ConsentMethod.API_AUTHENTICATED_REQUEST
        )
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.ROOT_NOT_LEGITIMATE


class TestValidateConsentProofOwnTemporalFailures:
    def test_revoked_consent_denied_even_with_legitimate_root(self) -> None:
        root_id, root_result = _valid_root_and_result()
        proof = build_consent_proof(
            "u1", root_id, "agent1", "scope", "purpose", ConsentMethod.EXPLICIT_UI_ACTION
        )
        object.__setattr__(proof, "revoked_at", datetime.now(UTC))
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.REVOKED

    def test_not_yet_valid_consent_denied(self) -> None:
        root_id, root_result = _valid_root_and_result()
        proof = build_consent_proof(
            "u1",
            root_id,
            "agent1",
            "scope",
            "purpose",
            ConsentMethod.SIGNED_DOCUMENT,
            not_before=datetime.now(UTC) + timedelta(days=1),
        )
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.NOT_YET_VALID

    def test_expired_consent_denied(self) -> None:
        root_id, root_result = _valid_root_and_result()
        proof = build_consent_proof(
            "u1",
            root_id,
            "agent1",
            "scope",
            "purpose",
            ConsentMethod.DELEGATED_POLICY,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.EXPIRED

    def test_root_legitimacy_is_checked_before_temporal_state(self) -> None:
        """An illegitimate root should be reported as ROOT_NOT_LEGITIMATE
        even if the consent proof itself is also independently expired --
        the root problem is the more fundamental one to surface."""
        human = build_root_authority_record("u3", RootType.HUMAN, "issuer", "oidc")
        object.__setattr__(human, "revoked_at", datetime.now(UTC))
        root_result = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u3",
            human.root_id,
            "agent1",
            "scope",
            "purpose",
            ConsentMethod.VERBAL_RECORDED,
            expires_at=datetime.now(UTC) - timedelta(days=1),
        )
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.ROOT_NOT_LEGITIMATE


class TestConsentValidationResult:
    def test_is_valid_true_only_for_valid_status(self) -> None:
        assert ConsentValidationResult(ConsentValidationStatus.VALID, "c1").is_valid
        assert not ConsentValidationResult(ConsentValidationStatus.REVOKED, "c1").is_valid
        assert not ConsentValidationResult(ConsentValidationStatus.ROOT_MISMATCH, "c1").is_valid


class TestConsentProofProperties:
    """Hypothesis property tests for the composition invariant between
    a `ConsentProof`'s own temporal validity and the `RootValidationResult`
    passed in for its consenting root."""

    @given(
        method=st.sampled_from(list(ConsentMethod)),
        root_type=st.sampled_from([RootType.HUMAN, RootType.ORGANIZATION]),
    )
    def test_fresh_proof_with_valid_terminal_root_is_always_valid(
        self, method: ConsentMethod, root_type: RootType
    ) -> None:
        root = build_root_authority_record("subj", root_type, "issuer", "method")
        root_result = validate_root_chain(root, lambda rid: None)
        proof = build_consent_proof("subj", root.root_id, "agent1", "scope", "purpose", method)
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.VALID

    @given(root_type=st.sampled_from([RootType.HUMAN, RootType.ORGANIZATION]))
    def test_revoked_root_never_yields_valid_consent(self, root_type: RootType) -> None:
        root = build_root_authority_record("subj", root_type, "issuer", "method")
        object.__setattr__(root, "revoked_at", datetime.now(UTC))
        root_result = validate_root_chain(root, lambda rid: None)
        proof = build_consent_proof(
            "subj", root.root_id, "agent1", "scope", "purpose", ConsentMethod.EXPLICIT_UI_ACTION
        )
        result = validate_consent_proof(proof, root_result)
        assert not result.is_valid
        assert result.status == ConsentValidationStatus.ROOT_NOT_LEGITIMATE

    @given(claimed_root_id=st.text(min_size=1, max_size=20).filter(lambda s: s != "actual-root"))
    def test_mismatched_root_id_never_yields_valid_consent(self, claimed_root_id: str) -> None:
        root = build_root_authority_record("subj", RootType.HUMAN, "issuer", "method")
        object.__setattr__(root, "root_id", "actual-root")
        root_result = validate_root_chain(root, lambda rid: None)
        proof = build_consent_proof(
            "subj", claimed_root_id, "agent1", "scope", "purpose", ConsentMethod.EXPLICIT_UI_ACTION
        )
        result = validate_consent_proof(proof, root_result)
        assert result.status == ConsentValidationStatus.ROOT_MISMATCH
        assert not result.is_valid
