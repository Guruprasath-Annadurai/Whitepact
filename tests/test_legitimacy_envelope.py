"""Tests for Heart Phase H12 — Legitimacy Envelope
(`governance/legitimacy_envelope.py`).

Covers digest determinism, `is_legitimate`/`explain()`/`to_dict()`
derivation from the wrapped `HeartVetoRecord`, and Hypothesis property
tests for the core invariant: an envelope's `is_legitimate` always
matches the negation of its wrapped veto's `is_vetoed`.
"""

from __future__ import annotations

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.authority_conflict_resolver import (
    ConflictResolutionResult,
    ConflictResolutionStatus,
)
from responsibleai.governance.heart_veto import apply_heart_veto
from responsibleai.governance.legitimacy_envelope import (
    build_legitimacy_envelope,
    compute_legitimacy_envelope_digest,
)


def _veto(
    status: ConflictResolutionStatus, human_reserved: bool = False, detail: str | None = None
):
    cr = ConflictResolutionResult(status, human_reserved=human_reserved, detail=detail)
    return apply_heart_veto(cr)


class TestLegitimacyEnvelopeConstruction:
    def test_legitimate_veto_produces_legitimate_envelope(self) -> None:
        veto = _veto(ConflictResolutionStatus.LEGITIMATE)
        env = build_legitimacy_envelope("org1", "agent1", veto)
        assert env.is_legitimate

    def test_vetoed_veto_produces_illegitimate_envelope(self) -> None:
        veto = _veto(ConflictResolutionStatus.NON_DELEGABLE, detail="blocked")
        env = build_legitimacy_envelope("org1", "agent1", veto)
        assert not env.is_legitimate

    def test_envelope_carries_organization_and_subject(self) -> None:
        veto = _veto(ConflictResolutionStatus.LEGITIMATE)
        env = build_legitimacy_envelope("org-42", "agent-99", veto)
        assert env.organization_id == "org-42"
        assert env.subject_identity_id == "agent-99"

    def test_two_envelopes_for_same_inputs_have_distinct_ids_and_digests(self) -> None:
        veto = _veto(ConflictResolutionStatus.LEGITIMATE)
        env1 = build_legitimacy_envelope("org1", "agent1", veto)
        env2 = build_legitimacy_envelope("org1", "agent1", veto)
        assert env1.envelope_id != env2.envelope_id
        assert env1.canonical_digest != env2.canonical_digest


class TestCanonicalDigest:
    def test_digest_is_deterministic_given_the_same_fields(self) -> None:
        veto = _veto(ConflictResolutionStatus.STALE, human_reserved=True, detail="d")
        env = build_legitimacy_envelope("org1", "agent1", veto)
        expected = compute_legitimacy_envelope_digest(
            env.envelope_id,
            env.organization_id,
            env.subject_identity_id,
            env.heart_veto.status.value,
            env.heart_veto.reason,
            env.heart_veto.detail,
            env.heart_veto.human_reserved,
            env.issued_at,
        )
        assert env.canonical_digest == expected

    def test_digest_changes_if_veto_status_differs(self) -> None:
        legit = build_legitimacy_envelope(
            "org1", "agent1", _veto(ConflictResolutionStatus.LEGITIMATE)
        )
        vetoed = build_legitimacy_envelope(
            "org1", "agent1", _veto(ConflictResolutionStatus.NON_DELEGABLE)
        )
        assert legit.canonical_digest != vetoed.canonical_digest


class TestToDict:
    def test_to_dict_round_trips_key_fields(self) -> None:
        veto = _veto(ConflictResolutionStatus.PURPOSE_NOT_BOUND, detail="mismatch")
        env = build_legitimacy_envelope("org1", "agent1", veto)
        d = env.to_dict()
        assert d["envelope_id"] == env.envelope_id
        assert d["organization_id"] == "org1"
        assert d["subject_identity_id"] == "agent1"
        assert d["heart_veto"]["status"] == "VETOED"
        assert d["heart_veto"]["reason"] == "PURPOSE_NOT_BOUND"
        assert d["heart_veto"]["detail"] == "mismatch"
        assert d["canonical_digest"] == env.canonical_digest


class TestExplain:
    def test_explain_legitimate_envelope(self) -> None:
        veto = _veto(ConflictResolutionStatus.LEGITIMATE, human_reserved=True)
        env = build_legitimacy_envelope("org1", "agent1", veto)
        explanation = env.explain()
        assert explanation["is_legitimate"] is True
        assert explanation["vetoed"] is False
        assert explanation["veto_reason"] is None
        assert explanation["human_reserved"] is True

    def test_explain_vetoed_envelope(self) -> None:
        veto = _veto(ConflictResolutionStatus.REVOKED, detail="epoch advanced")
        env = build_legitimacy_envelope("org1", "agent1", veto)
        explanation = env.explain()
        assert explanation["is_legitimate"] is False
        assert explanation["vetoed"] is True
        assert explanation["veto_reason"] == "REVOKED"
        assert explanation["veto_detail"] == "epoch advanced"

    def test_explain_includes_envelope_identity_fields(self) -> None:
        veto = _veto(ConflictResolutionStatus.LEGITIMATE)
        env = build_legitimacy_envelope("org1", "agent1", veto)
        explanation = env.explain()
        assert explanation["envelope_id"] == env.envelope_id
        assert explanation["organization_id"] == "org1"
        assert explanation["subject_identity_id"] == "agent1"
        assert explanation["canonical_digest"] == env.canonical_digest


class TestLegitimacyEnvelopeProperties:
    """Hypothesis property tests for the core invariant."""

    @given(
        status=st.sampled_from(list(ConflictResolutionStatus)),
        human_reserved=st.booleans(),
        org=st.text(min_size=1, max_size=10),
        subject=st.text(min_size=1, max_size=10),
    )
    def test_is_legitimate_always_matches_negation_of_vetoed(
        self, status: ConflictResolutionStatus, human_reserved: bool, org: str, subject: str
    ) -> None:
        veto = _veto(status, human_reserved=human_reserved)
        env = build_legitimacy_envelope(org, subject, veto)
        assert env.is_legitimate == (not env.heart_veto.is_vetoed)

    @given(status=st.sampled_from(list(ConflictResolutionStatus)))
    def test_explain_vetoed_field_always_matches_veto_is_vetoed(
        self, status: ConflictResolutionStatus
    ) -> None:
        veto = _veto(status)
        env = build_legitimacy_envelope("org1", "agent1", veto)
        assert env.explain()["vetoed"] == veto.is_vetoed

    @given(human_reserved=st.booleans())
    def test_human_reserved_always_passes_through_to_explain(self, human_reserved: bool) -> None:
        veto = _veto(ConflictResolutionStatus.LEGITIMATE, human_reserved=human_reserved)
        env = build_legitimacy_envelope("org1", "agent1", veto)
        assert env.explain()["human_reserved"] == human_reserved
