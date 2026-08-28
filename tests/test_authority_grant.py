"""Tests for Heart Production Integration Phase 1 — the Authority
Contract (`governance/authority_grant.py`).

Covers `AuthorityGrant`'s derivation from a wrapped `LegitimacyEnvelope`
(`is_legitimate`/`is_expired`/`is_usable`), digest determinism,
`to_authority_context()`'s reuse of the existing H2 adapter, and
Hypothesis property tests for the core invariant: `is_usable` is true
if and only if both the wrapped verdict is legitimate and the grant
has not expired.
"""

from __future__ import annotations

import pytest
from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.authority_conflict_resolver import (
    ConflictResolutionResult,
    ConflictResolutionStatus,
)
from responsibleai.governance.authority_grant import (
    build_authority_grant,
    compute_authority_grant_digest,
)
from responsibleai.governance.authority_lattice import AuthorityEnvelope
from responsibleai.governance.heart_veto import apply_heart_veto
from responsibleai.governance.legitimacy_envelope import build_legitimacy_envelope


def _legitimacy(
    status: ConflictResolutionStatus = ConflictResolutionStatus.LEGITIMATE,
    detail: str | None = None,
):
    cr = ConflictResolutionResult(status, detail=detail)
    veto = apply_heart_veto(cr)
    return build_legitimacy_envelope("org1", "agent1", veto)


def _envelope(**overrides: object) -> AuthorityEnvelope:
    defaults: dict[str, object] = {
        "action_types": frozenset({"payment.execute"}),
        "max_value": 500000.0,
    }
    defaults.update(overrides)
    return AuthorityEnvelope(**defaults)  # type: ignore[arg-type]


class TestAuthorityGrantConstruction:
    def test_legitimate_grant_is_usable(self) -> None:
        grant = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", _envelope(), _legitimacy()
        )
        assert grant.is_legitimate
        assert not grant.is_expired
        assert grant.is_usable

    def test_illegitimate_grant_is_not_usable(self) -> None:
        legitimacy = _legitimacy(ConflictResolutionStatus.ROOT_NOT_LEGITIMATE, detail="bad root")
        grant = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", _envelope(), legitimacy
        )
        assert not grant.is_legitimate
        assert not grant.is_usable

    def test_expired_legitimate_grant_is_not_usable(self) -> None:
        grant = build_authority_grant(
            "org1",
            "u1",
            "agent1",
            "payment.execute",
            "vendor_x",
            _envelope(),
            _legitimacy(),
            ttl_seconds=-1,
        )
        assert grant.is_legitimate
        assert grant.is_expired
        assert not grant.is_usable

    def test_grant_carries_request_context_fields(self) -> None:
        grant = build_authority_grant(
            "org-42",
            "u1",
            "agent-99",
            "payment.execute",
            "vendor_x",
            _envelope(),
            _legitimacy(),
            requested_purpose="pay vendor",
            root_reference="root-1",
            consent_reference="consent-1",
            delegation_reference="delegation-1",
        )
        assert grant.organization_id == "org-42"
        assert grant.acting_agent_id == "agent-99"
        assert grant.requested_purpose == "pay vendor"
        assert grant.root_reference == "root-1"
        assert grant.consent_reference == "consent-1"
        assert grant.delegation_reference == "delegation-1"


class TestToAuthorityContext:
    def test_conversion_reuses_existing_h2_adapter(self) -> None:
        grant = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", _envelope(), _legitimacy()
        )
        ac = grant.to_authority_context()
        assert ac.permits("payment.execute")
        assert not ac.permits("payment.delete")
        assert ac.constraints["max_value_usd"] == 500000.0
        assert ac.delegated_by == "u1"

    def test_conversion_reflects_effective_authority_not_request(self) -> None:
        """The converted AuthorityContext must reflect effective_authority
        (the Heart-verified grant), never requested_action_type -- even
        if a caller requests something the envelope doesn't grant."""
        narrow_envelope = _envelope(action_types=frozenset({"read.only"}))
        grant = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", narrow_envelope, _legitimacy()
        )
        ac = grant.to_authority_context()
        assert not ac.permits("payment.execute")
        assert ac.permits("read.only")


class TestCanonicalDigest:
    def test_digest_is_deterministic(self) -> None:
        grant = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", _envelope(), _legitimacy()
        )
        expected = compute_authority_grant_digest(
            grant.grant_id,
            grant.organization_id,
            grant.principal_id,
            grant.acting_agent_id,
            grant.requested_action_type,
            grant.requested_target,
            grant.requested_purpose,
            grant.legitimacy.canonical_digest,
            grant.root_reference,
            grant.consent_reference,
            grant.delegation_reference,
            grant.issued_at,
            grant.expires_at,
            grant.effective_authority,
            grant.policy_constraints,
        )
        assert grant.canonical_digest == expected

    def test_digest_covers_effective_authority_and_policy_constraints(self) -> None:
        legitimacy = _legitimacy()
        narrow = build_authority_grant(
            "org1",
            "u1",
            "agent1",
            "payment.execute",
            "vendor_x",
            _envelope(max_value=100.0),
            legitimacy,
            policy_constraints={"region": "eu"},
        )
        broad = build_authority_grant(
            "org1",
            "u1",
            "agent1",
            "payment.execute",
            "vendor_x",
            _envelope(max_value=500000.0),
            legitimacy,
            policy_constraints={"region": "us"},
        )
        assert narrow.canonical_digest != broad.canonical_digest

    def test_policy_constraints_are_immutable_after_issue(self) -> None:
        grant = build_authority_grant(
            "org1",
            "u1",
            "agent1",
            "payment.execute",
            "vendor_x",
            _envelope(),
            _legitimacy(),
            policy_constraints={"region": "eu"},
        )
        with pytest.raises(TypeError):
            grant.policy_constraints["region"] = "us"  # type: ignore[index]

    def test_two_grants_same_inputs_have_distinct_ids_and_digests(self) -> None:
        legitimacy = _legitimacy()
        envelope = _envelope()
        g1 = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", envelope, legitimacy
        )
        g2 = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", envelope, legitimacy
        )
        assert g1.grant_id != g2.grant_id
        assert g1.canonical_digest != g2.canonical_digest

    def test_digest_changes_if_legitimacy_differs(self) -> None:
        envelope = _envelope()
        legit = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", envelope, _legitimacy()
        )
        illegit = build_authority_grant(
            "org1",
            "u1",
            "agent1",
            "payment.execute",
            "vendor_x",
            envelope,
            _legitimacy(ConflictResolutionStatus.NON_DELEGABLE),
        )
        assert legit.canonical_digest != illegit.canonical_digest


class TestExplain:
    def test_explain_includes_legitimacy_and_identity_fields(self) -> None:
        legitimacy = _legitimacy(ConflictResolutionStatus.REVOKED, detail="epoch advanced")
        grant = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", _envelope(), legitimacy
        )
        explanation = grant.explain()
        assert explanation["grant_id"] == grant.grant_id
        assert explanation["is_legitimate"] is False
        assert explanation["is_usable"] is False
        assert explanation["legitimacy"]["veto_reason"] == "REVOKED"
        assert explanation["legitimacy"]["veto_detail"] == "epoch advanced"


class TestAuthorityGrantProperties:
    """Hypothesis property tests for the core invariant."""

    @given(
        status=st.sampled_from(list(ConflictResolutionStatus)),
        ttl_seconds=st.floats(min_value=-1000, max_value=1000, allow_nan=False),
    )
    def test_is_usable_iff_legitimate_and_not_expired(
        self, status: ConflictResolutionStatus, ttl_seconds: float
    ) -> None:
        legitimacy = _legitimacy(status)
        grant = build_authority_grant(
            "org1",
            "u1",
            "agent1",
            "payment.execute",
            "vendor_x",
            _envelope(),
            legitimacy,
            ttl_seconds=ttl_seconds,
        )
        assert grant.is_usable == (grant.is_legitimate and not grant.is_expired)

    @given(status=st.sampled_from(list(ConflictResolutionStatus)))
    def test_is_legitimate_always_matches_wrapped_legitimacy(
        self, status: ConflictResolutionStatus
    ) -> None:
        legitimacy = _legitimacy(status)
        grant = build_authority_grant(
            "org1", "u1", "agent1", "payment.execute", "vendor_x", _envelope(), legitimacy
        )
        assert grant.is_legitimate == legitimacy.is_legitimate
