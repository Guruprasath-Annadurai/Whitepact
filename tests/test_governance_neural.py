"""Tests for Enterprise Neural Phase 4 — `governance/neural/`: the
`NeuralDataClass`/`NeuralPayload` classification vocabulary, the
per-category `ConsentRecord` model, and the fail-closed
`evaluate_neural_data_flow` policy evaluator. See
`docs/enterprise-neural/04_PHASE4_DESIGN.md`.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.neural import (
    LOCAL_ONLY_BY_DEFAULT,
    ConsentCategory,
    ConsentRecord,
    ConsentStatus,
    NeuralDataClass,
    NeuralPayload,
    NeuralPolicyDecision,
    NeuralPolicyReason,
    evaluate_neural_data_flow,
)


def _payload(data_class: NeuralDataClass, payload: bytes = b"x") -> NeuralPayload:
    return NeuralPayload(
        data_class=data_class,
        subject_id="u1",
        session_id="s1",
        payload=payload,
        captured_at=datetime.now(UTC),
    )


def _consent(
    category: ConsentCategory,
    status: ConsentStatus,
    version: int = 1,
) -> ConsentRecord:
    return ConsentRecord(
        consent_id=f"c{version}",
        subject_id="u1",
        organization_id=None,
        category=category,
        status=status,
        version=version,
        granted_at=datetime.now(UTC),
        revoked_at=datetime.now(UTC) if status is ConsentStatus.REVOKED else None,
    )


class TestNeuralPayload:
    def test_rejects_empty_subject_id(self) -> None:
        with pytest.raises(ValueError, match="subject_id"):
            NeuralPayload(
                data_class=NeuralDataClass.N0_RAW_NEURAL,
                subject_id="",
                session_id="s1",
                payload=b"x",
                captured_at=datetime.now(UTC),
            )

    def test_rejects_empty_session_id(self) -> None:
        with pytest.raises(ValueError, match="session_id"):
            NeuralPayload(
                data_class=NeuralDataClass.N0_RAW_NEURAL,
                subject_id="u1",
                session_id="",
                payload=b"x",
                captured_at=datetime.now(UTC),
            )

    def test_repr_never_contains_raw_payload_bytes(self) -> None:
        secret = b"SECRET_RAW_EEG_STREAM_CONTENT"
        p = _payload(NeuralDataClass.N0_RAW_NEURAL, payload=secret)
        rendered = repr(p)
        assert secret.decode() not in rendered
        assert "redacted" in rendered

    def test_str_uses_the_same_redacted_repr(self) -> None:
        secret = b"ANOTHER_SECRET_PAYLOAD"
        p = _payload(NeuralDataClass.N1_NEURAL_FEATURES, payload=secret)
        assert secret.decode() not in str(p)

    @pytest.mark.parametrize(
        "data_class",
        [
            NeuralDataClass.N0_RAW_NEURAL,
            NeuralDataClass.N1_NEURAL_FEATURES,
            NeuralDataClass.N2_PERSONAL_NEURAL_MODEL,
        ],
    )
    def test_n0_n1_n2_are_local_only_by_default(self, data_class: NeuralDataClass) -> None:
        assert _payload(data_class).is_local_only_by_default()

    @pytest.mark.parametrize(
        "data_class",
        [
            NeuralDataClass.N3_NEURAL_INFERENCE,
            NeuralDataClass.N4_NEURAL_AUTHORITY_EVIDENCE,
            NeuralDataClass.N5_OPERATIONAL_METADATA,
        ],
    )
    def test_n3_n4_n5_are_not_local_only_by_default(self, data_class: NeuralDataClass) -> None:
        assert not _payload(data_class).is_local_only_by_default()

    def test_local_only_by_default_constant_matches_the_method(self) -> None:
        for data_class in NeuralDataClass:
            expected = data_class in LOCAL_ONLY_BY_DEFAULT
            assert _payload(data_class).is_local_only_by_default() == expected


class TestConsentRequiredError:
    def test_carries_subject_and_category_and_a_readable_message(self) -> None:
        from responsibleai.governance.neural import ConsentRequiredError

        exc = ConsentRequiredError("u1", ConsentCategory.EXTERNAL_LLM_SHARING)
        assert exc.subject_id == "u1"
        assert exc.category is ConsentCategory.EXTERNAL_LLM_SHARING
        assert "u1" in str(exc)
        assert "external_llm_sharing" in str(exc)


class TestConsentRecord:
    def test_rejects_version_below_one(self) -> None:
        with pytest.raises(ValueError, match="version"):
            ConsentRecord(
                consent_id="c1",
                subject_id="u1",
                organization_id=None,
                category=ConsentCategory.BCI_CONNECTION,
                status=ConsentStatus.GRANTED,
                version=0,
                granted_at=datetime.now(UTC),
            )

    def test_revoked_without_revoked_at_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="REVOKED"):
            ConsentRecord(
                consent_id="c1",
                subject_id="u1",
                organization_id=None,
                category=ConsentCategory.BCI_CONNECTION,
                status=ConsentStatus.REVOKED,
                version=1,
                granted_at=datetime.now(UTC),
                revoked_at=None,
            )

    def test_granted_with_revoked_at_set_is_rejected(self) -> None:
        with pytest.raises(ValueError, match="GRANTED"):
            ConsentRecord(
                consent_id="c1",
                subject_id="u1",
                organization_id=None,
                category=ConsentCategory.BCI_CONNECTION,
                status=ConsentStatus.GRANTED,
                version=1,
                granted_at=datetime.now(UTC),
                revoked_at=datetime.now(UTC),
            )

    def test_is_active_true_for_granted(self) -> None:
        assert _consent(ConsentCategory.BCI_CONNECTION, ConsentStatus.GRANTED).is_active

    def test_is_active_false_for_revoked(self) -> None:
        assert not _consent(ConsentCategory.BCI_CONNECTION, ConsentStatus.REVOKED).is_active


class TestEvaluateNeuralDataFlow:
    def test_no_record_denies(self) -> None:
        result = evaluate_neural_data_flow(ConsentCategory.EXTERNAL_LLM_SHARING, ())
        assert result.decision is NeuralPolicyDecision.DENY
        assert result.reason is NeuralPolicyReason.NO_CONSENT_RECORD
        assert not result.is_allowed

    def test_granted_record_allows(self) -> None:
        granted = _consent(ConsentCategory.EXTERNAL_LLM_SHARING, ConsentStatus.GRANTED)
        result = evaluate_neural_data_flow(ConsentCategory.EXTERNAL_LLM_SHARING, (granted,))
        assert result.decision is NeuralPolicyDecision.ALLOW
        assert result.reason is NeuralPolicyReason.CONSENT_GRANTED
        assert result.is_allowed

    def test_revoked_record_denies(self) -> None:
        revoked = _consent(ConsentCategory.EXTERNAL_LLM_SHARING, ConsentStatus.REVOKED)
        result = evaluate_neural_data_flow(ConsentCategory.EXTERNAL_LLM_SHARING, (revoked,))
        assert result.decision is NeuralPolicyDecision.DENY
        assert result.reason is NeuralPolicyReason.CONSENT_REVOKED

    def test_latest_version_wins_when_later_is_revocation(self) -> None:
        granted = _consent(ConsentCategory.EXTERNAL_LLM_SHARING, ConsentStatus.GRANTED, version=1)
        revoked = _consent(ConsentCategory.EXTERNAL_LLM_SHARING, ConsentStatus.REVOKED, version=2)
        result = evaluate_neural_data_flow(ConsentCategory.EXTERNAL_LLM_SHARING, (granted, revoked))
        assert result.decision is NeuralPolicyDecision.DENY

    def test_latest_version_wins_when_later_is_regrant(self) -> None:
        revoked = _consent(ConsentCategory.EXTERNAL_LLM_SHARING, ConsentStatus.REVOKED, version=1)
        granted = _consent(ConsentCategory.EXTERNAL_LLM_SHARING, ConsentStatus.GRANTED, version=2)
        result = evaluate_neural_data_flow(ConsentCategory.EXTERNAL_LLM_SHARING, (revoked, granted))
        assert result.decision is NeuralPolicyDecision.ALLOW

    def test_records_for_other_categories_are_ignored(self) -> None:
        other = _consent(ConsentCategory.RESEARCH_CONTRIBUTION, ConsentStatus.GRANTED)
        result = evaluate_neural_data_flow(ConsentCategory.EXTERNAL_LLM_SHARING, (other,))
        assert result.decision is NeuralPolicyDecision.DENY
        assert result.reason is NeuralPolicyReason.NO_CONSENT_RECORD

    def test_result_category_matches_the_requested_category(self) -> None:
        result = evaluate_neural_data_flow(ConsentCategory.PROFILE_STORAGE, ())
        assert result.category is ConsentCategory.PROFILE_STORAGE


class TestProperties:
    @given(
        categories=st.lists(st.sampled_from(list(ConsentCategory)), min_size=0, max_size=5),
        requested=st.sampled_from(list(ConsentCategory)),
    )
    def test_no_record_for_requested_category_always_denies(
        self, categories: list[ConsentCategory], requested: ConsentCategory
    ) -> None:
        records = tuple(
            _consent(c, ConsentStatus.GRANTED, version=i + 1)
            for i, c in enumerate(categories)
            if c != requested
        )
        result = evaluate_neural_data_flow(requested, records)
        assert result.decision is NeuralPolicyDecision.DENY
        assert result.reason is NeuralPolicyReason.NO_CONSENT_RECORD

    @given(num_versions=st.integers(min_value=1, max_value=6))
    def test_decision_always_matches_the_highest_version_record(self, num_versions: int) -> None:
        records = tuple(
            _consent(
                ConsentCategory.BCI_CONNECTION,
                ConsentStatus.GRANTED if v % 2 == 0 else ConsentStatus.REVOKED,
                version=v,
            )
            for v in range(1, num_versions + 1)
        )
        result = evaluate_neural_data_flow(ConsentCategory.BCI_CONNECTION, records)
        highest = max(records, key=lambda r: r.version)
        expected_allowed = highest.is_active
        assert result.is_allowed == expected_allowed
