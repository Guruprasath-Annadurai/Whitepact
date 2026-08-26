"""Heart Phase H15 — Adversarial Heart Gauntlet.

A curated set of deliberately adversarial scenarios attacking the
Heart's own assumptions and known documented gaps, each with an
honest verdict: `CONFIRMED VULNERABILITY (fixed this phase)`,
`CONFIRMED PROTECTION`, or `ACCEPTED DESIGN TRADEOFF`. Two real
vulnerabilities were found and fixed as part of this phase:

1. **Cross-reference confusion** — a `DelegationRecord` for a
   completely unrelated identity and purpose, supplied alongside a
   genuinely legitimate but unrelated root/consent/purpose chain, was
   validated as `LEGITIMATE` end-to-end via
   `governance/sovereignty_kernel.py`'s `evaluate()`. Fixed by adding
   `expected_subject_identity_id`/`expected_purpose` cross-reference
   parameters to `governance/delegation_kernel.py`'s
   `validate_delegation_legitimacy()` (Phase H6), now wired from
   `evaluate()`.
2. **Case-relabeling bypass** — `governance/non_delegable_authority.py`'s
   `check_non_delegable_authority()` (Phase H7) relied on
   `fnmatch.fnmatch()`'s platform-dependent case sensitivity, so a
   request for `"HEART.VETO.OVERRIDE"` was silently not caught by the
   all-lowercase registry on this codebase's actual deployment
   platform. Fixed by explicitly `.casefold()`-ing both sides before
   comparison.

See `docs/heart/HEART_INVARIANTS.md` for how these fixes update the
invariants ledger, and `MIGRATION_WHITEPACT_V2.md`'s Phase H15 section
for the full gauntlet report.
"""

from __future__ import annotations

from datetime import UTC, datetime

from responsibleai.governance import sovereignty_kernel as sk
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
from responsibleai.governance.non_delegable_authority import (
    NonDelegableScope,
    check_non_delegable_authority,
)
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


class TestCrossReferenceConfusionFixed:
    """CONFIRMED VULNERABILITY, fixed this phase: a delegation for an
    unrelated identity/purpose must never ride on the coattails of an
    unrelated legitimate chain."""

    def test_delegation_for_wrong_identity_and_purpose_is_now_rejected_end_to_end(self) -> None:
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        proof = build_consent_proof(
            "u1", human.root_id, "agent-A", "scope", "purpose-A", ConsentMethod.EXPLICIT_UI_ACTION
        )
        intent = IntentContract(organization_id="org1", agent_id="agent-A", goal="g")
        binding = build_purpose_binding("purpose-A", intent.contract_id, proof.consent_id)
        malicious_delegation = DelegationRecord(
            delegation_id="evil-d1",
            org_id="org1",
            from_identity_id=None,
            to_identity_id="agent-EVIL",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={},
            require_approval_for=frozenset(),
            purpose="COMPLETELY UNRELATED PURPOSE",
            granted_by="someone-else",
            granted_at=datetime.now(UTC),
        )
        env = sk.evaluate(
            "org1",
            "agent-EVIL",
            root=human,
            consent=proof,
            intent=intent,
            purpose_binding=binding,
            delegation=malicious_delegation,
        )
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "DELEGATION_NOT_LEGITIMATE"

    def test_mismatched_identity_alone_is_caught(self) -> None:
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        root_result = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u1", human.root_id, "agent-A", "scope", "p", ConsentMethod.EXPLICIT_UI_ACTION
        )
        consent_result = validate_consent_proof(proof, root_result)
        intent = IntentContract(organization_id="org1", agent_id="agent-A", goal="g")
        binding = build_purpose_binding("p", intent.contract_id, proof.consent_id)
        purpose_result = validate_purpose_binding(binding, proof, consent_result, intent)
        delegation = DelegationRecord(
            delegation_id="d1",
            org_id="org1",
            from_identity_id=None,
            to_identity_id="agent-WRONG",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={},
            require_approval_for=frozenset(),
            purpose="p",
            granted_by="u1",
            granted_at=datetime.now(UTC),
        )
        result = validate_delegation_legitimacy(
            delegation,
            root_result,
            consent_result,
            purpose_result,
            expected_subject_identity_id="agent-CORRECT",
            expected_purpose="p",
        )
        assert result.status == DelegationLegitimacyStatus.DELEGATION_MISMATCH

    def test_mismatched_purpose_alone_is_caught(self) -> None:
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        root_result = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u1", human.root_id, "agent-A", "scope", "p", ConsentMethod.EXPLICIT_UI_ACTION
        )
        consent_result = validate_consent_proof(proof, root_result)
        intent = IntentContract(organization_id="org1", agent_id="agent-A", goal="g")
        binding = build_purpose_binding("p", intent.contract_id, proof.consent_id)
        purpose_result = validate_purpose_binding(binding, proof, consent_result, intent)
        delegation = DelegationRecord(
            delegation_id="d1",
            org_id="org1",
            from_identity_id=None,
            to_identity_id="agent-A",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={},
            require_approval_for=frozenset(),
            purpose="WRONG PURPOSE",
            granted_by="u1",
            granted_at=datetime.now(UTC),
        )
        result = validate_delegation_legitimacy(
            delegation,
            root_result,
            consent_result,
            purpose_result,
            expected_subject_identity_id="agent-A",
            expected_purpose="p",
        )
        assert result.status == DelegationLegitimacyStatus.DELEGATION_MISMATCH

    def test_backward_compatible_when_cross_reference_params_omitted(self) -> None:
        """Existing callers that don't supply expected_subject_identity_id/
        expected_purpose get the exact prior behavior -- no regression
        for code written before this phase."""
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        root_result = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u1", human.root_id, "agent-ANYONE", "scope", "p", ConsentMethod.EXPLICIT_UI_ACTION
        )
        consent_result = validate_consent_proof(proof, root_result)
        intent = IntentContract(organization_id="org1", agent_id="agent-ANYONE", goal="g")
        binding = build_purpose_binding("p", intent.contract_id, proof.consent_id)
        purpose_result = validate_purpose_binding(binding, proof, consent_result, intent)
        delegation = DelegationRecord(
            delegation_id="d1",
            org_id="org1",
            from_identity_id=None,
            to_identity_id="agent-DIFFERENT",
            granted_action_types=frozenset({"payment.execute"}),
            constraints={},
            require_approval_for=frozenset(),
            purpose="totally different purpose",
            granted_by="u1",
            granted_at=datetime.now(UTC),
        )
        result = validate_delegation_legitimacy(
            delegation, root_result, consent_result, purpose_result
        )
        assert result.status == DelegationLegitimacyStatus.LEGITIMATE


class TestCaseRelabelingBypassFixed:
    """CONFIRMED VULNERABILITY, fixed this phase: the non-delegable
    registry must not be bypassable by relabeling a reserved action
    type's case."""

    def test_uppercase_reserved_action_type_is_now_caught(self) -> None:
        result = check_non_delegable_authority(frozenset({"HEART.VETO.OVERRIDE"}))
        assert result is not None
        assert result.scope == NonDelegableScope.NON_DELEGABLE

    def test_mixed_case_reserved_action_type_is_now_caught(self) -> None:
        result = check_non_delegable_authority(frozenset({"Heart.Constitution.Amend"}))
        assert result is not None
        assert result.scope == NonDelegableScope.NON_DELEGABLE

    def test_uppercase_human_reserved_action_type_is_also_caught(self) -> None:
        result = check_non_delegable_authority(frozenset({"LEGAL.ATTESTATION.SIGN"}))
        assert result is not None
        assert result.scope == NonDelegableScope.HUMAN_RESERVED

    def test_case_insensitivity_does_not_cause_false_positives_on_ordinary_actions(self) -> None:
        result = check_non_delegable_authority(frozenset({"PAYMENT.EXECUTE", "Deployment"}))
        assert result is None


class TestChainDepthBoundaryExactness:
    """CONFIRMED PROTECTION: the chain-too-deep circuit breaker fires
    at exactly the documented boundary, not off by one in either
    direction."""

    def test_exactly_at_max_depth_is_still_valid(self) -> None:
        prev = build_root_authority_record("root0", RootType.ORGANIZATION, "issuer", "saml")
        store = {prev.root_id: prev}
        for i in range(32):
            nxt = build_root_authority_record(
                f"sp{i}", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=prev.root_id
            )
            store[nxt.root_id] = nxt
            prev = nxt
        result = validate_root_chain(prev, lambda rid: store.get(rid))
        assert result.status.value == "VALID"

    def test_one_hop_over_max_depth_is_chain_too_deep(self) -> None:
        prev = build_root_authority_record("root0", RootType.ORGANIZATION, "issuer", "saml")
        store = {prev.root_id: prev}
        for i in range(33):
            nxt = build_root_authority_record(
                f"sp{i}", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=prev.root_id
            )
            store[nxt.root_id] = nxt
            prev = nxt
        result = validate_root_chain(prev, lambda rid: store.get(rid))
        assert result.status.value == "CHAIN_TOO_DEEP"


class TestPurposeExactMatchResistsLookalikeAttacks:
    """CONFIRMED PROTECTION: purpose matching (H5) has no leniency
    that could be exploited via whitespace or Unicode homoglyph
    tricks -- a purpose string must match exactly, byte for byte."""

    def test_trailing_whitespace_does_not_match(self) -> None:
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        root_result = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u1", human.root_id, "a1", "s", "pay vendor", ConsentMethod.EXPLICIT_UI_ACTION
        )
        consent_result = validate_consent_proof(proof, root_result)
        intent = IntentContract(organization_id="org1", agent_id="a1", goal="g")
        binding = build_purpose_binding("pay vendor ", intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status.value == "PURPOSE_MISMATCH"

    def test_unicode_homoglyph_does_not_match(self) -> None:
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        root_result = validate_root_chain(human, lambda rid: None)
        proof = build_consent_proof(
            "u1", human.root_id, "a1", "s", "pay vendor", ConsentMethod.EXPLICIT_UI_ACTION
        )
        consent_result = validate_consent_proof(proof, root_result)
        intent = IntentContract(organization_id="org1", agent_id="a1", goal="g")
        homoglyph_purpose = "pay vendor".replace("a", "а")  # Cyrillic а
        binding = build_purpose_binding(homoglyph_purpose, intent.contract_id, proof.consent_id)
        result = validate_purpose_binding(binding, proof, consent_result, intent)
        assert result.status.value == "PURPOSE_MISMATCH"


class TestRevocationEpochTrustBoundary:
    """ACCEPTED DESIGN TRADEOFF, not a bug: check_revocation_epoch()
    (H9) is only as trustworthy as the epochs it's given. A caller
    that supplies a fabricated "current" epoch equal to the issuance
    epoch will get CURRENT even if the true current epoch has actually
    advanced -- this module has no independent way to know the real
    current epoch, by design (TCB-minimization: no live database
    dependency). Real safety depends entirely on whoever calls this
    function sourcing `current` from an actually-trustworthy epoch
    store, which this module deliberately does not provide or assume."""

    def test_caller_supplied_stale_current_epoch_is_trusted_as_is(self) -> None:
        real_issued_at = RevocationEpoch(organization_id="org1", scope="delegation")
        real_current = bump_epoch(real_issued_at)  # the TRUE current epoch has advanced

        # An attacker (or a caller with stale cached state) supplies a
        # fabricated "current" that hasn't actually advanced.
        fabricated_current = RevocationEpoch(organization_id="org1", scope="delegation")
        result = check_revocation_epoch(real_issued_at, fabricated_current)
        assert result.is_current  # trusts the input, as documented -- not a bug in this function

        # The real current epoch, honestly supplied, correctly catches it.
        honest_result = check_revocation_epoch(real_issued_at, real_current)
        assert not honest_result.is_current
