"""Tests for Heart Phase H10 — Authority Conflict Resolver
(`governance/authority_conflict_resolver.py`).

Covers every `ConflictResolutionStatus` branch, the full precedence
order across all seven possible inputs, the `human_reserved`
non-blocking signal, and Hypothesis property tests for the core
precedence invariant.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance.authority_conflict_resolver import (
    ConflictResolutionStatus,
    resolve_authority_conflicts,
)
from responsibleai.governance.authority_lifetime import LifetimeWindow, check_lifetime
from responsibleai.governance.consent_proof import (
    ConsentMethod,
    build_consent_proof,
    validate_consent_proof,
)
from responsibleai.governance.delegation import DelegationRecord
from responsibleai.governance.delegation_kernel import validate_delegation_legitimacy
from responsibleai.governance.intent import IntentContract
from responsibleai.governance.non_delegable_authority import check_non_delegable_authority
from responsibleai.governance.purpose_binding import build_purpose_binding, validate_purpose_binding
from responsibleai.governance.revocation_kernel import (
    RevocationEpoch,
    bump_epoch,
    check_revocation_epoch,
)
from responsibleai.governance.root_authority import (
    RootType,
    build_root_authority_record,
    validate_root_chain,
)


def _legitimate_chain(purpose: str = "purpose-x"):
    human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
    root_result = validate_root_chain(human, lambda rid: None)
    proof = build_consent_proof(
        "u1", human.root_id, "agent1", "scope", purpose, ConsentMethod.EXPLICIT_UI_ACTION
    )
    consent_result = validate_consent_proof(proof, root_result)
    intent = IntentContract(organization_id="org1", agent_id="agent1", goal="g")
    binding = build_purpose_binding(purpose, intent.contract_id, proof.consent_id)
    purpose_result = validate_purpose_binding(binding, proof, consent_result, intent)
    delegation = DelegationRecord(
        delegation_id="d1",
        org_id="org1",
        from_identity_id=None,
        to_identity_id="agent1",
        granted_action_types=frozenset({"payment.execute"}),
        constraints={},
        require_approval_for=frozenset(),
        purpose=purpose,
        granted_by="u1",
        granted_at=datetime.now(UTC),
    )
    delegation_result = validate_delegation_legitimacy(
        delegation, root_result, consent_result, purpose_result
    )
    lifetime_result = check_lifetime(datetime.now(UTC), LifetimeWindow(max_age_seconds=300))
    return root_result, consent_result, purpose_result, delegation_result, lifetime_result


class TestNoInputs:
    def test_no_inputs_is_legitimate(self) -> None:
        result = resolve_authority_conflicts()
        assert result.status == ConflictResolutionStatus.LEGITIMATE
        assert result.is_legitimate
        assert not result.human_reserved


class TestAllLegitimateTogether:
    def test_every_check_passing_is_legitimate(self) -> None:
        root_r, consent_r, purpose_r, delegation_r, lifetime_r = _legitimate_chain()
        epoch = RevocationEpoch(organization_id="org1", scope="delegation")
        revocation_r = check_revocation_epoch(epoch, epoch)
        result = resolve_authority_conflicts(
            revocation=revocation_r,
            root=root_r,
            consent=consent_r,
            purpose=purpose_r,
            delegation=delegation_r,
            lifetime=lifetime_r,
        )
        assert result.status == ConflictResolutionStatus.LEGITIMATE


class TestNonDelegable:
    def test_non_delegable_violation_blocks(self) -> None:
        nd = check_non_delegable_authority(frozenset({"heart.veto.override"}))
        result = resolve_authority_conflicts(non_delegable=nd)
        assert result.status == ConflictResolutionStatus.NON_DELEGABLE
        assert not result.is_legitimate
        assert not result.human_reserved

    def test_human_reserved_does_not_block(self) -> None:
        nd = check_non_delegable_authority(frozenset({"legal.attestation.sign"}))
        result = resolve_authority_conflicts(non_delegable=nd)
        assert result.status == ConflictResolutionStatus.LEGITIMATE
        assert result.is_legitimate
        assert result.human_reserved

    def test_human_reserved_flag_survives_alongside_other_legitimate_checks(self) -> None:
        root_r, consent_r, purpose_r, delegation_r, lifetime_r = _legitimate_chain()
        nd = check_non_delegable_authority(frozenset({"legal.attestation.sign"}))
        result = resolve_authority_conflicts(
            non_delegable=nd,
            root=root_r,
            consent=consent_r,
            purpose=purpose_r,
            delegation=delegation_r,
        )
        assert result.status == ConflictResolutionStatus.LEGITIMATE
        assert result.human_reserved


class TestRevocation:
    def test_revoked_since_issuance_blocks(self) -> None:
        epoch0 = RevocationEpoch(organization_id="org1", scope="delegation")
        epoch1 = bump_epoch(epoch0)
        revocation_r = check_revocation_epoch(epoch0, epoch1)
        result = resolve_authority_conflicts(revocation=revocation_r)
        assert result.status == ConflictResolutionStatus.REVOKED

    def test_scope_mismatch_also_blocks_fail_closed(self) -> None:
        epoch_a = RevocationEpoch(organization_id="org1", scope="delegation")
        epoch_b = RevocationEpoch(organization_id="org1", scope="root_authority")
        revocation_r = check_revocation_epoch(epoch_a, epoch_b)
        result = resolve_authority_conflicts(revocation=revocation_r)
        assert result.status == ConflictResolutionStatus.REVOKED


class TestIndividualBlockingChecks:
    def test_root_not_legitimate_blocks(self) -> None:
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        root_r = validate_root_chain(sp, lambda rid: None)
        result = resolve_authority_conflicts(root=root_r)
        assert result.status == ConflictResolutionStatus.ROOT_NOT_LEGITIMATE

    def test_consent_not_legitimate_blocks(self) -> None:
        human = build_root_authority_record("u2", RootType.HUMAN, "issuer", "oidc")
        object.__setattr__(human, "revoked_at", datetime.now(UTC))
        root_r = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u2", human.root_id, "agent1", "scope", "p", ConsentMethod.SIGNED_DOCUMENT
        )
        consent_r = validate_consent_proof(proof, root_r)
        result = resolve_authority_conflicts(consent=consent_r)
        assert result.status == ConflictResolutionStatus.CONSENT_NOT_LEGITIMATE

    def test_purpose_not_bound_blocks(self) -> None:
        human = build_root_authority_record("u3", RootType.HUMAN, "issuer", "oidc")
        root_r = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u3", human.root_id, "agent1", "scope", "purpose-x", ConsentMethod.EXPLICIT_UI_ACTION
        )
        consent_r = validate_consent_proof(proof, root_r)
        intent = IntentContract(organization_id="org1", agent_id="agent1", goal="g")
        binding = build_purpose_binding("WRONG", intent.contract_id, proof.consent_id)
        purpose_r = validate_purpose_binding(binding, proof, consent_r, intent)
        result = resolve_authority_conflicts(purpose=purpose_r)
        assert result.status == ConflictResolutionStatus.PURPOSE_NOT_BOUND

    def test_delegation_not_legitimate_blocks(self) -> None:
        root_r, consent_r, purpose_r, _, _ = _legitimate_chain()
        revoked_delegation = DelegationRecord(
            delegation_id="d2",
            org_id="org1",
            from_identity_id=None,
            to_identity_id="agent1",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={},
            require_approval_for=frozenset(),
            purpose="purpose-x",
            granted_by="u1",
            granted_at=datetime.now(UTC),
            revoked_at=datetime.now(UTC),
        )
        delegation_r = validate_delegation_legitimacy(
            revoked_delegation, root_r, consent_r, purpose_r
        )
        result = resolve_authority_conflicts(delegation=delegation_r)
        assert result.status == ConflictResolutionStatus.DELEGATION_NOT_LEGITIMATE

    def test_stale_blocks(self) -> None:
        stale = check_lifetime(
            datetime.now(UTC) - timedelta(seconds=1000), LifetimeWindow(max_age_seconds=1)
        )
        result = resolve_authority_conflicts(lifetime=stale)
        assert result.status == ConflictResolutionStatus.STALE


class TestPrecedenceOrder:
    def test_non_delegable_wins_over_everything_else(self) -> None:
        nd = check_non_delegable_authority(frozenset({"heart.veto.override"}))
        epoch0 = RevocationEpoch(organization_id="org1", scope="delegation")
        revocation_r = check_revocation_epoch(epoch0, bump_epoch(epoch0))
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        root_r = validate_root_chain(sp, lambda rid: None)
        result = resolve_authority_conflicts(non_delegable=nd, revocation=revocation_r, root=root_r)
        assert result.status == ConflictResolutionStatus.NON_DELEGABLE

    def test_revoked_wins_over_root_and_below(self) -> None:
        epoch0 = RevocationEpoch(organization_id="org1", scope="delegation")
        revocation_r = check_revocation_epoch(epoch0, bump_epoch(epoch0))
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        root_r = validate_root_chain(sp, lambda rid: None)
        result = resolve_authority_conflicts(revocation=revocation_r, root=root_r)
        assert result.status == ConflictResolutionStatus.REVOKED

    def test_root_wins_over_consent_and_below(self) -> None:
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        root_r = validate_root_chain(sp, lambda rid: None)
        human = build_root_authority_record("u4", RootType.HUMAN, "issuer", "oidc")
        object.__setattr__(human, "revoked_at", datetime.now(UTC))
        bad_root_r = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u4", human.root_id, "agent1", "scope", "p", ConsentMethod.SIGNED_DOCUMENT
        )
        consent_r = validate_consent_proof(proof, bad_root_r)
        result = resolve_authority_conflicts(root=root_r, consent=consent_r)
        assert result.status == ConflictResolutionStatus.ROOT_NOT_LEGITIMATE

    def test_stale_is_lowest_precedence_among_blocking_reasons(self) -> None:
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        root_r = validate_root_chain(sp, lambda rid: None)
        stale = check_lifetime(
            datetime.now(UTC) - timedelta(seconds=1000), LifetimeWindow(max_age_seconds=1)
        )
        result = resolve_authority_conflicts(root=root_r, lifetime=stale)
        assert result.status == ConflictResolutionStatus.ROOT_NOT_LEGITIMATE


class TestAuthorityConflictResolverProperties:
    """Hypothesis property tests for the precedence invariant."""

    @given(
        include_revocation=st.booleans(),
        include_root=st.booleans(),
    )
    def test_non_delegable_always_wins_when_present_regardless_of_other_inputs(
        self, include_revocation: bool, include_root: bool
    ) -> None:
        nd = check_non_delegable_authority(frozenset({"heart.constitution.amend"}))
        kwargs: dict[str, object] = {"non_delegable": nd}
        if include_revocation:
            epoch0 = RevocationEpoch(organization_id="org1", scope="delegation")
            kwargs["revocation"] = check_revocation_epoch(epoch0, epoch0)  # even a CURRENT one
        if include_root:
            human = build_root_authority_record("u5", RootType.HUMAN, "issuer", "oidc")
            kwargs["root"] = validate_root_chain(human, lambda rid: None)  # even a VALID one
        result = resolve_authority_conflicts(**kwargs)  # type: ignore[arg-type]
        assert result.status == ConflictResolutionStatus.NON_DELEGABLE

    @given(root_type=st.sampled_from([RootType.SERVICE_PRINCIPAL, RootType.WORKLOAD_IDENTITY]))
    def test_illegitimate_root_always_blocks_when_no_higher_precedence_failure_present(
        self, root_type: RootType
    ) -> None:
        bad_root = build_root_authority_record("bad", root_type, "issuer", "method")
        root_r = validate_root_chain(bad_root, lambda rid: None)
        result = resolve_authority_conflicts(root=root_r)
        assert result.status == ConflictResolutionStatus.ROOT_NOT_LEGITIMATE
        assert not result.is_legitimate
