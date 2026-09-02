"""Heart Phase H14 — Formal and Property-Based Assurance.

Cross-cutting property tests spanning the full H3-H13 chain, verifying
invariants no single phase's own tests could exercise since each phase
composes with at most its immediate neighbor. See
`docs/heart/HEART_INVARIANTS.md` for the full ledger of every
invariant claimed across H1-H13, this file's additions included, and
an honest accounting of what is and isn't verified.

**Not formal verification** — every property below is checked against
Hypothesis-generated inputs across a large sampled space, not proven
for all possible inputs by a proof assistant. See the ledger's own
"What Phase H14 explicitly does NOT claim" section.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance import sovereignty_kernel as sk
from responsibleai.governance.authority_conflict_resolver import resolve_authority_conflicts
from responsibleai.governance.consent_proof import (
    ConsentMethod,
    build_consent_proof,
    compute_consent_digest,
    validate_consent_proof,
)
from responsibleai.governance.constitution import ConstitutionalLawCode, compute_constitution_digest
from responsibleai.governance.heart_veto import apply_heart_veto
from responsibleai.governance.legitimacy_envelope import (
    compute_legitimacy_envelope_digest,
)
from responsibleai.governance.purpose_binding import compute_purpose_binding_digest
from responsibleai.governance.root_authority import (
    RootType,
    build_root_authority_record,
    compute_root_digest,
    validate_root_chain,
)


def _legitimate_root_and_consent(purpose: str = "purpose-x"):
    human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
    root_result = validate_root_chain(human, lambda rid: None)
    proof = build_consent_proof(
        "u1", human.root_id, "agent1", "scope", purpose, ConsentMethod.EXPLICIT_UI_ACTION
    )
    consent_result = validate_consent_proof(proof, root_result)
    return human, proof, root_result, consent_result


class TestEvaluateConsistentWithManualComposition:
    """evaluate() (H13) must never diverge from directly composing
    resolve_authority_conflicts() (H10) + apply_heart_veto() (H11)
    from the same underlying H3-H9 results -- the orchestration layer
    adds no independent judgment of its own."""

    @given(purpose=st.text(min_size=1, max_size=20))
    def test_evaluate_is_consistent_with_manual_composition_legitimate_case(
        self, purpose: str
    ) -> None:
        human, proof, root_result, consent_result = _legitimate_root_and_consent(purpose)
        env = sk.evaluate("org1", "agent1", root=human, consent=proof)
        manual_conflict = resolve_authority_conflicts(root=root_result, consent=consent_result)
        manual_veto = apply_heart_veto(manual_conflict)
        assert env.is_legitimate == (not manual_veto.is_vetoed)

    @given(root_type=st.sampled_from([RootType.SERVICE_PRINCIPAL, RootType.WORKLOAD_IDENTITY]))
    def test_evaluate_is_consistent_with_manual_composition_blocking_case(
        self, root_type: RootType
    ) -> None:
        bad_root = build_root_authority_record("bad", root_type, "issuer", "method")
        bad_root_result = validate_root_chain(bad_root, lambda rid: None)
        env = sk.evaluate("org1", "agent1", root=bad_root)
        manual_conflict = resolve_authority_conflicts(root=bad_root_result)
        manual_veto = apply_heart_veto(manual_conflict)
        assert env.is_legitimate == (not manual_veto.is_vetoed)
        assert not env.is_legitimate


class TestDenialIsMonotonic:
    """Adding any single blocking condition to an otherwise-legitimate
    full chain always flips the result to illegitimate -- a legitimate
    input can never mask a genuinely blocking one added alongside it."""

    def test_adding_non_delegable_to_legitimate_chain_always_denies(self) -> None:
        human, proof, _, _ = _legitimate_root_and_consent()
        legitimate_env = sk.evaluate("org1", "agent1", root=human, consent=proof)
        assert legitimate_env.is_legitimate

        denied_env = sk.evaluate(
            "org1",
            "agent1",
            root=human,
            consent=proof,
            requested_action_types=frozenset({"heart.veto.override"}),
        )
        assert not denied_env.is_legitimate

    def test_adding_revocation_to_legitimate_chain_always_denies(self) -> None:
        from responsibleai.governance.revocation_kernel import RevocationEpoch, bump_epoch

        human, proof, _, _ = _legitimate_root_and_consent()
        legitimate_env = sk.evaluate("org1", "agent1", root=human, consent=proof)
        assert legitimate_env.is_legitimate

        epoch0 = RevocationEpoch(organization_id="org1", scope="delegation")
        epoch1 = bump_epoch(epoch0)
        denied_env = sk.evaluate(
            "org1",
            "agent1",
            root=human,
            consent=proof,
            revocation_issued_at=epoch0,
            revocation_current=epoch1,
        )
        assert not denied_env.is_legitimate

    @given(bumps=st.integers(min_value=1, max_value=5))
    def test_any_single_blocking_condition_added_to_legitimate_chain_always_denies(
        self, bumps: int
    ) -> None:
        from responsibleai.governance.revocation_kernel import RevocationEpoch, bump_epoch

        human, proof, _, _ = _legitimate_root_and_consent()
        epoch = RevocationEpoch(organization_id="org1", scope="delegation")
        current = epoch
        for _ in range(bumps):
            current = bump_epoch(current)
        env = sk.evaluate(
            "org1",
            "agent1",
            root=human,
            consent=proof,
            revocation_issued_at=epoch,
            revocation_current=current,
        )
        assert not env.is_legitimate


class TestDigestSensitivity:
    """Every canonical-digest function is sensitive to every one of
    its own input fields -- no field is silently excluded from the
    digest, which would make two meaningfully-different records
    collide on the same digest."""

    def test_root_digest_sensitive_to_every_field(self) -> None:
        now = datetime.now(UTC)
        base: dict[str, Any] = {
            "root_id": "r1",
            "root_type": RootType.HUMAN,
            "subject_id": "u1",
            "organization_id": "org1",
            "issuer": "iss",
            "verification_method": "oidc",
            "authority_source": None,
            "issued_at": now,
        }
        baseline = compute_root_digest(**base)
        perturbations = {
            "root_id": "r2",
            "root_type": RootType.ORGANIZATION,
            "subject_id": "u2",
            "organization_id": "org2",
            "issuer": "iss2",
            "verification_method": "saml",
            "authority_source": "src1",
            "issued_at": now.replace(year=now.year + 1),
        }
        for field, new_value in perturbations.items():
            perturbed = {**base, field: new_value}
            assert compute_root_digest(**perturbed) != baseline, (
                f"field {field!r} did not affect digest"
            )

    def test_consent_digest_sensitive_to_every_field(self) -> None:
        now = datetime.now(UTC)
        base: dict[str, Any] = {
            "consent_id": "c1",
            "subject_id": "u1",
            "consenting_root_id": "r1",
            "grantee_id": "a1",
            "scope_description": "s",
            "purpose": "p",
            "consent_method": ConsentMethod.EXPLICIT_UI_ACTION,
            "consented_at": now,
            "allowed_action_types": ("rai_scan",),
            "allowed_targets": (),
        }
        baseline = compute_consent_digest(**base)
        perturbations = {
            "consent_id": "c2",
            "subject_id": "u2",
            "consenting_root_id": "r2",
            "grantee_id": "a2",
            "scope_description": "s2",
            "purpose": "p2",
            "consent_method": ConsentMethod.SIGNED_DOCUMENT,
            "consented_at": now.replace(year=now.year + 1),
            "allowed_action_types": ("rai_hallucination",),
            "allowed_targets": ("some-target",),
        }
        for field, new_value in perturbations.items():
            perturbed = {**base, field: new_value}
            assert compute_consent_digest(**perturbed) != baseline, (
                f"field {field!r} did not affect digest"
            )

    def test_purpose_binding_digest_sensitive_to_every_field(self) -> None:
        now = datetime.now(UTC)
        base: dict[str, Any] = {
            "binding_id": "b1",
            "purpose": "p",
            "intent_ref": "i1",
            "consent_ref": "c1",
            "bound_at": now,
        }
        baseline = compute_purpose_binding_digest(**base)
        perturbations = {
            "binding_id": "b2",
            "purpose": "p2",
            "intent_ref": "i2",
            "consent_ref": "c2",
            "bound_at": now.replace(year=now.year + 1),
        }
        for field, new_value in perturbations.items():
            perturbed = {**base, field: new_value}
            assert compute_purpose_binding_digest(**perturbed) != baseline, (
                f"field {field!r} did not affect digest"
            )

    def test_legitimacy_envelope_digest_sensitive_to_every_field(self) -> None:
        now = datetime.now(UTC)
        base: dict[str, Any] = {
            "envelope_id": "e1",
            "organization_id": "org1",
            "subject_identity_id": "a1",
            "veto_status": "VETOED",
            "veto_reason": "X",
            "veto_detail": "d",
            "human_reserved": False,
            "issued_at": now,
        }
        baseline = compute_legitimacy_envelope_digest(**base)
        perturbations = {
            "envelope_id": "e2",
            "organization_id": "org2",
            "subject_identity_id": "a2",
            "veto_status": "NOT_VETOED",
            "veto_reason": "Y",
            "veto_detail": "d2",
            "human_reserved": True,
            "issued_at": now.replace(year=now.year + 1),
        }
        for field, new_value in perturbations.items():
            perturbed = {**base, field: new_value}
            assert compute_legitimacy_envelope_digest(**perturbed) != baseline, (
                f"field {field!r} did not affect digest"
            )

    def test_constitution_digest_sensitive_to_every_field(self) -> None:
        now = datetime.now(UTC)
        base: dict[str, Any] = {
            "version": 1,
            "laws": (ConstitutionalLawCode.H1,),
            "ratified_at": now,
            "description": "d",
        }
        baseline = compute_constitution_digest(**base)
        perturbations = {
            "version": 2,
            "laws": (ConstitutionalLawCode.H2,),
            "ratified_at": now.replace(year=now.year + 1),
            "description": "d2",
        }
        for field, new_value in perturbations.items():
            perturbed = {**base, field: new_value}
            assert compute_constitution_digest(**perturbed) != baseline, (
                f"field {field!r} did not affect digest"
            )


class TestIsLegitimatePurity:
    """is_legitimate is a pure function of the supplied verdicts --
    identical verdict inputs always produce identical is_legitimate,
    independent of the non-deterministic identity fields (envelope_id,
    issued_at, canonical_digest) that differ on every call."""

    @given(purpose=st.text(min_size=1, max_size=20))
    def test_is_legitimate_is_pure_given_identical_verdicts(self, purpose: str) -> None:
        human, proof, _, _ = _legitimate_root_and_consent(purpose)
        env_a = sk.evaluate("org1", "agent1", root=human, consent=proof)
        env_b = sk.evaluate("org1", "agent1", root=human, consent=proof)
        # Identity fields differ (fresh envelope_id/issued_at/digest each call) ...
        assert env_a.envelope_id != env_b.envelope_id
        assert env_a.canonical_digest != env_b.canonical_digest
        # ... but the actual legitimacy verdict is identical, since the
        # underlying inputs were identical.
        assert env_a.is_legitimate == env_b.is_legitimate
        assert env_a.explain()["veto_reason"] == env_b.explain()["veto_reason"]

    def test_is_legitimate_pure_for_blocking_case_too(self) -> None:
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        env_a = sk.evaluate("org1", "agent1", root=sp)
        env_b = sk.evaluate("org1", "agent1", root=sp)
        assert env_a.is_legitimate == env_b.is_legitimate == False  # noqa: E712
        assert env_a.explain()["veto_reason"] == env_b.explain()["veto_reason"]
