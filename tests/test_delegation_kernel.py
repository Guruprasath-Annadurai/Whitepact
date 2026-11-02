"""Tests for Heart Phase H6 — Delegation Kernel
(`governance/delegation_kernel.py`).

Covers every `DelegationLegitimacyStatus` branch of
`validate_delegation_legitimacy()` plus Hypothesis property tests for
the composition invariant: a delegation can only be LEGITIMATE when
all three upstream Heart legitimacy checks (root, consent, purpose)
are valid AND the delegation record itself is currently active.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.consent_proof import (
    ConsentMethod,
    build_consent_proof,
    validate_consent_proof,
)
from responsibleai.governance.delegation import DelegationRecord
from responsibleai.governance.delegation_kernel import (
    DelegationLegitimacyStatus,
    validate_delegation_legitimacy,
)
from responsibleai.governance.intent import IntentContract
from responsibleai.governance.purpose_binding import build_purpose_binding, validate_purpose_binding
from responsibleai.governance.root_authority import (
    RootType,
    build_root_authority_record,
    validate_root_chain,
)


def _make_delegation(**overrides: object) -> DelegationRecord:
    defaults: dict[str, object] = {
        "delegation_id": "d1",
        "org_id": "org1",
        "from_identity_id": None,
        "to_identity_id": "agent1",
        "granted_action_types": frozenset({"payment.execute"}),
        "constraints": {},
        "require_approval_for": frozenset(),
        "purpose": "vendor payments",
        "granted_by": "u1",
        "granted_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return DelegationRecord(**defaults)  # type: ignore[arg-type]


def _legitimate_chain(purpose: str = "vendor payments"):
    human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
    root_result = validate_root_chain(human, lambda rid: None)
    proof = build_consent_proof(
        "u1",
        human.root_id,
        "agent1",
        "payment.execute up to 500000",
        purpose,
        ConsentMethod.EXPLICIT_UI_ACTION,
    )
    consent_result = validate_consent_proof(proof, root_result)
    intent = IntentContract(organization_id="org1", agent_id="agent1", goal="pay vendor")
    binding = build_purpose_binding(purpose, intent.contract_id, proof.consent_id)
    purpose_result = validate_purpose_binding(binding, proof, consent_result, intent)
    return root_result, consent_result, purpose_result


class TestValidateDelegationLegitimacyHappyPath:
    def test_fully_legitimate_delegation_is_legitimate(self) -> None:
        root_result, consent_result, purpose_result = _legitimate_chain()
        delegation = _make_delegation()
        result = validate_delegation_legitimacy(
            delegation, root_result, consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.LEGITIMATE
        assert result.is_legitimate


class TestValidateDelegationLegitimacyRootFailure:
    def test_revoked_root_denies_delegation(self) -> None:
        _, consent_result, purpose_result = _legitimate_chain()
        human = build_root_authority_record("u2", RootType.HUMAN, "issuer", "oidc")
        object.__setattr__(human, "revoked_at", datetime.now(UTC))
        bad_root_result = validate_root_chain(human, lambda rid: None)
        delegation = _make_delegation()
        result = validate_delegation_legitimacy(
            delegation, bad_root_result, consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.ROOT_NOT_LEGITIMATE
        assert not result.is_legitimate

    def test_non_terminal_root_with_no_source_denies_delegation(self) -> None:
        _, consent_result, purpose_result = _legitimate_chain()
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        bad_root_result = validate_root_chain(sp, lambda rid: None)
        delegation = _make_delegation()
        result = validate_delegation_legitimacy(
            delegation, bad_root_result, consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.ROOT_NOT_LEGITIMATE


class TestValidateDelegationLegitimacyConsentFailure:
    def test_revoked_consent_denies_delegation(self) -> None:
        root_result, _, purpose_result = _legitimate_chain()
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        proof = build_consent_proof(
            "u1", human.root_id, "agent1", "scope", "vendor payments", ConsentMethod.SIGNED_DOCUMENT
        )
        object.__setattr__(proof, "revoked_at", datetime.now(UTC))
        bad_consent_result = validate_consent_proof(proof, root_result)
        delegation = _make_delegation()
        result = validate_delegation_legitimacy(
            delegation, root_result, bad_consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.CONSENT_NOT_LEGITIMATE


class TestValidateDelegationLegitimacyPurposeFailure:
    def test_purpose_mismatch_denies_delegation(self) -> None:
        root_result, _, _ = _legitimate_chain(purpose="vendor payments")
        proof = build_consent_proof(
            "u1",
            root_result.root_id,
            "agent1",
            "scope",
            "vendor payments",
            ConsentMethod.EXPLICIT_UI_ACTION,
        )
        consent_result2 = validate_consent_proof(proof, root_result)
        intent = IntentContract(organization_id="org1", agent_id="agent1", goal="pay vendor")
        binding = build_purpose_binding("WRONG PURPOSE", intent.contract_id, proof.consent_id)
        bad_purpose_result = validate_purpose_binding(binding, proof, consent_result2, intent)
        delegation = _make_delegation()
        result = validate_delegation_legitimacy(
            delegation, root_result, consent_result2, bad_purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.PURPOSE_NOT_BOUND


class TestValidateDelegationLegitimacyOwnState:
    def test_revoked_delegation_denied_even_with_legitimate_chain(self) -> None:
        root_result, consent_result, purpose_result = _legitimate_chain()
        delegation = _make_delegation(revoked_at=datetime.now(UTC))
        result = validate_delegation_legitimacy(
            delegation, root_result, consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.DELEGATION_NOT_ACTIVE

    def test_expired_delegation_denied_even_with_legitimate_chain(self) -> None:
        root_result, consent_result, purpose_result = _legitimate_chain()
        delegation = _make_delegation(expires_at=datetime.now(UTC) - timedelta(days=1))
        result = validate_delegation_legitimacy(
            delegation, root_result, consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.DELEGATION_NOT_ACTIVE

    def test_not_yet_expired_delegation_with_legitimate_chain_is_legitimate(self) -> None:
        root_result, consent_result, purpose_result = _legitimate_chain()
        delegation = _make_delegation(expires_at=datetime.now(UTC) + timedelta(days=1))
        result = validate_delegation_legitimacy(
            delegation, root_result, consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.LEGITIMATE


class TestValidateDelegationLegitimacyOrdering:
    def test_root_failure_reported_before_consent_and_purpose_failure(self) -> None:
        """When root, consent, AND purpose are all simultaneously
        illegitimate, the most foundational problem (root) must
        surface, not a downstream one."""
        human = build_root_authority_record("u3", RootType.HUMAN, "issuer", "oidc")
        object.__setattr__(human, "revoked_at", datetime.now(UTC))
        bad_root_result = validate_root_chain(human, lambda rid: None)

        proof = build_consent_proof(
            "u3", human.root_id, "agent1", "scope", "purpose-a", ConsentMethod.VERBAL_RECORDED
        )
        object.__setattr__(proof, "revoked_at", datetime.now(UTC))
        bad_consent_result = validate_consent_proof(proof, bad_root_result)

        intent = IntentContract(organization_id="org1", agent_id="agent1", goal="x")
        binding = build_purpose_binding("purpose-b", intent.contract_id, proof.consent_id)
        bad_purpose_result = validate_purpose_binding(binding, proof, bad_consent_result, intent)

        delegation = _make_delegation(revoked_at=datetime.now(UTC))
        result = validate_delegation_legitimacy(
            delegation, bad_root_result, bad_consent_result, bad_purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.ROOT_NOT_LEGITIMATE

    def test_delegation_own_state_checked_last(self) -> None:
        """A revoked delegation whose upstream chain IS legitimate
        must still be denied, but for DELEGATION_NOT_ACTIVE, not
        misreported as an upstream failure."""
        root_result, consent_result, purpose_result = _legitimate_chain()
        delegation = _make_delegation(revoked_at=datetime.now(UTC))
        result = validate_delegation_legitimacy(
            delegation, root_result, consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.DELEGATION_NOT_ACTIVE


class TestDelegationKernelProperties:
    """Hypothesis property tests for the composition invariant."""

    @given(purpose=st.text(min_size=1, max_size=30))
    def test_legitimate_chain_with_active_delegation_always_legitimate(self, purpose: str) -> None:
        root_result, consent_result, purpose_result = _legitimate_chain(purpose=purpose)
        delegation = _make_delegation(purpose=purpose)
        result = validate_delegation_legitimacy(
            delegation, root_result, consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.LEGITIMATE

    @given(root_type=st.sampled_from([RootType.SERVICE_PRINCIPAL, RootType.WORKLOAD_IDENTITY]))
    def test_illegitimate_root_never_yields_legitimate_delegation(self, root_type) -> None:  # type: ignore[no-untyped-def]
        _, consent_result, purpose_result = _legitimate_chain()
        bad_root = build_root_authority_record("bad", root_type, "issuer", "method")
        bad_root_result = validate_root_chain(bad_root, lambda rid: None)
        delegation = _make_delegation()
        result = validate_delegation_legitimacy(
            delegation, bad_root_result, consent_result, purpose_result
        )
        assert not result.is_legitimate
        assert result.status == DelegationLegitimacyStatus.ROOT_NOT_LEGITIMATE
