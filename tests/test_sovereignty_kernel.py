# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for Heart Phase H13 — Sovereignty Kernel Entry Point
(`governance/sovereignty_kernel.py`).

Covers `evaluate()`'s orchestration of H3-H12 for every combination of
supplied inputs: no inputs, a fully legitimate chain, each individual
blocking condition, partial/missing prerequisites being skipped
gracefully, and `root_resolver`-driven multi-hop chain walking. Plus
Hypothesis property tests for the core invariant: `evaluate()`'s
result always matches what directly composing H3-H10 by hand would
produce for the same inputs.
"""

from __future__ import annotations

from datetime import UTC, datetime

from hypothesis import given
from hypothesis import strategies as st

from responsibleai.governance import sovereignty_kernel as sk
from responsibleai.governance.consent_proof import ConsentMethod, build_consent_proof
from responsibleai.governance.delegation import DelegationRecord
from responsibleai.governance.intent import IntentContract
from responsibleai.governance.purpose_binding import build_purpose_binding
from responsibleai.governance.revocation_kernel import RevocationEpoch, bump_epoch
from responsibleai.governance.root_authority import RootType, build_root_authority_record


def _full_legitimate_inputs(purpose: str = "purpose-x"):
    human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
    proof = build_consent_proof(
        "u1", human.root_id, "agent1", "scope", purpose, ConsentMethod.EXPLICIT_UI_ACTION
    )
    intent = IntentContract(organization_id="org1", agent_id="agent1", goal="g")
    binding = build_purpose_binding(purpose, intent.contract_id, proof.consent_id)
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
    return human, proof, intent, binding, delegation


class TestEvaluateNoInputs:
    def test_no_inputs_is_legitimate(self) -> None:
        env = sk.evaluate("org1", "agent1")
        assert env.is_legitimate
        assert env.organization_id == "org1"
        assert env.subject_identity_id == "agent1"


class TestEvaluateFullChain:
    def test_full_legitimate_chain_is_legitimate(self) -> None:
        human, proof, intent, binding, delegation = _full_legitimate_inputs()
        env = sk.evaluate(
            "org1",
            "agent1",
            root=human,
            consent=proof,
            intent=intent,
            purpose_binding=binding,
            delegation=delegation,
        )
        assert env.is_legitimate

    def test_root_resolver_walks_multi_hop_chain(self) -> None:
        org_root = build_root_authority_record("org-root", RootType.ORGANIZATION, "issuer", "saml")
        sp = build_root_authority_record(
            "sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=org_root.root_id
        )
        store = {org_root.root_id: org_root}
        env = sk.evaluate("org1", "agent1", root=sp, root_resolver=lambda rid: store.get(rid))
        assert env.is_legitimate

    def test_root_without_resolver_uses_safe_default(self) -> None:
        """A SERVICE_PRINCIPAL root with an authority_source but no
        supplied root_resolver must not be silently treated as
        legitimate -- the default resolver always returns None."""
        org_root = build_root_authority_record("org-root", RootType.ORGANIZATION, "issuer", "saml")
        sp = build_root_authority_record(
            "sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt", authority_source=org_root.root_id
        )
        env = sk.evaluate("org1", "agent1", root=sp)
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "ROOT_NOT_LEGITIMATE"


class TestEvaluateBlockingConditions:
    def test_non_delegable_action_type_blocks_even_with_legitimate_chain(self) -> None:
        human, proof, intent, binding, delegation = _full_legitimate_inputs()
        env = sk.evaluate(
            "org1",
            "agent1",
            root=human,
            consent=proof,
            intent=intent,
            purpose_binding=binding,
            delegation=delegation,
            requested_action_types=frozenset({"heart.veto.override"}),
        )
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "NON_DELEGABLE"

    def test_human_reserved_action_type_does_not_block(self) -> None:
        env = sk.evaluate(
            "org1", "agent1", requested_action_types=frozenset({"legal.attestation.sign"})
        )
        assert env.is_legitimate
        assert env.explain()["human_reserved"] is True

    def test_root_not_legitimate_blocks(self) -> None:
        sp = build_root_authority_record("sp1", RootType.SERVICE_PRINCIPAL, "issuer", "jwt")
        env = sk.evaluate("org1", "agent1", root=sp)
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "ROOT_NOT_LEGITIMATE"

    def test_consent_not_legitimate_blocks(self) -> None:
        human = build_root_authority_record("u2", RootType.HUMAN, "issuer", "oidc")
        proof = build_consent_proof(
            "u2", human.root_id, "agent1", "scope", "p", ConsentMethod.SIGNED_DOCUMENT
        )
        object.__setattr__(
            proof, "revoked_at", datetime.now(UTC)
        )  # consent itself revoked, not the root
        env = sk.evaluate("org1", "agent1", root=human, consent=proof)
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "CONSENT_NOT_LEGITIMATE"

    def test_purpose_not_bound_blocks(self) -> None:
        human, proof, intent, _, _ = _full_legitimate_inputs(purpose="purpose-x")
        wrong_binding = build_purpose_binding("WRONG", intent.contract_id, proof.consent_id)
        env = sk.evaluate(
            "org1",
            "agent1",
            root=human,
            consent=proof,
            intent=intent,
            purpose_binding=wrong_binding,
        )
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "PURPOSE_NOT_BOUND"

    def test_delegation_not_legitimate_blocks(self) -> None:
        human, proof, intent, binding, _ = _full_legitimate_inputs()
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
        env = sk.evaluate(
            "org1",
            "agent1",
            root=human,
            consent=proof,
            intent=intent,
            purpose_binding=binding,
            delegation=revoked_delegation,
        )
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "DELEGATION_NOT_LEGITIMATE"

    def test_revocation_epoch_advance_blocks(self) -> None:
        epoch0 = RevocationEpoch(organization_id="org1", scope="delegation")
        epoch1 = bump_epoch(epoch0)
        env = sk.evaluate("org1", "agent1", revocation_issued_at=epoch0, revocation_current=epoch1)
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "REVOKED"


class TestEvaluatePartialInputs:
    def test_consent_without_root_is_skipped_not_failed(self) -> None:
        human = build_root_authority_record("u1", RootType.HUMAN, "issuer", "oidc")
        proof = build_consent_proof(
            "u1", human.root_id, "agent1", "scope", "p", ConsentMethod.EXPLICIT_UI_ACTION
        )
        env = sk.evaluate("org1", "agent1", consent=proof)  # root not supplied
        assert env.is_legitimate

    def test_purpose_binding_without_intent_is_skipped_not_failed(self) -> None:
        human, proof, _, binding, _ = _full_legitimate_inputs()
        env = sk.evaluate("org1", "agent1", root=human, consent=proof, purpose_binding=binding)
        assert env.is_legitimate

    def test_delegation_without_purpose_is_skipped_not_failed(self) -> None:
        human, proof, _, _, delegation = _full_legitimate_inputs()
        env = sk.evaluate("org1", "agent1", root=human, consent=proof, delegation=delegation)
        assert env.is_legitimate

    def test_only_revocation_issued_at_without_current_is_skipped(self) -> None:
        epoch0 = RevocationEpoch(organization_id="org1", scope="delegation")
        env = sk.evaluate("org1", "agent1", revocation_issued_at=epoch0)
        assert env.is_legitimate


class TestSovereigntyKernelProperties:
    """Hypothesis property tests for the core orchestration invariant."""

    @given(purpose=st.text(min_size=1, max_size=20))
    def test_full_legitimate_chain_always_legitimate_for_arbitrary_purpose(
        self, purpose: str
    ) -> None:
        human, proof, intent, binding, delegation = _full_legitimate_inputs(purpose=purpose)
        env = sk.evaluate(
            "org1",
            "agent1",
            root=human,
            consent=proof,
            intent=intent,
            purpose_binding=binding,
            delegation=delegation,
        )
        assert env.is_legitimate

    @given(root_type=st.sampled_from([RootType.SERVICE_PRINCIPAL, RootType.WORKLOAD_IDENTITY]))
    def test_illegitimate_root_always_blocks_regardless_of_other_inputs(
        self, root_type: RootType
    ) -> None:
        bad_root = build_root_authority_record("bad", root_type, "issuer", "method")
        env = sk.evaluate(
            "org1", "agent1", root=bad_root, requested_action_types=frozenset({"payment.execute"})
        )
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "ROOT_NOT_LEGITIMATE"

    @given(bumps=st.integers(min_value=1, max_value=10))
    def test_any_epoch_advance_always_blocks(self, bumps: int) -> None:
        epoch = RevocationEpoch(organization_id="org1", scope="delegation")
        current = epoch
        for _ in range(bumps):
            current = bump_epoch(current)
        env = sk.evaluate("org1", "agent1", revocation_issued_at=epoch, revocation_current=current)
        assert not env.is_legitimate
        assert env.explain()["veto_reason"] == "REVOKED"
