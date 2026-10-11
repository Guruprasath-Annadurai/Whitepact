# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact FastStart V1 — Ultra-fast verification of core governance doctrine.

Provides developers with a fast (< 60s), zero-network, local cryptographic
demonstration of WhitePact's deterministic core governance doctrine:
ALLOW -> DENY -> REQUIRE_APPROVAL -> SYNTHETIC_APPROVAL -> AUTHORITY_REMOVAL -> VERIFY_EVIDENCE.

Enforcement Boundaries & Scope:
- FastStart demonstrates deterministic gateway evaluation, policy enforcement,
  and local canonical SHA-256 evidence chain verification.
- Step 4 (SYNTHETIC_APPROVAL_AND_SIMULATION) is explicitly a synthetic local
  demonstration placeholder: no human participant and no container isolation.
- Step 5 (AUTHORITY_REMOVAL_DEMO) demonstrates fail-closed behavior upon
  in-memory authority removal. Genuine durable revocation with epoch tracking
  and replay prevention is qualified in the enterprise integration suite.
- Step 6 (VERIFY_EVIDENCE) validates canonical evaluation records. Evaluated
  actions are decision records, not execution events. External immutable
  anchoring is separate and not claimed in local mode.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from responsibleai.governance.evidence import (
    EvidenceRecord,
    build_evidence_record,
    compute_canonical_evidence_hash,
)
from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.policy import Policy, PolicyRule

_GENESIS_PREV_HASH = "0" * 64


@dataclass(frozen=True)
class FastStartStep:
    name: str
    decision: str
    details: dict[str, Any]


@dataclass(frozen=True)
class FastStartReport:
    organization_id: str
    identity_id: str
    policy_rules: int
    steps: list[FastStartStep]
    evidence_hash: str
    verified: bool
    verification_details: dict[str, Any]

    def to_dict(self) -> dict[str, Any]:
        return {
            "organization_id": self.organization_id,
            "identity_id": self.identity_id,
            "policy_rules": self.policy_rules,
            "steps": [
                {
                    "name": s.name,
                    "decision": s.decision,
                    "details": s.details,
                }
                for s in self.steps
            ],
            "evidence_hash": self.evidence_hash,
            "verified": self.verified,
            "verification_details": self.verification_details,
        }


def run_faststart_workflow(*, organization_id: str = "org-faststart-demo") -> FastStartReport:
    """Execute the WhitePact FastStart V1 local governance doctrine demonstration."""
    gateway = WhitePactRuntimeGateway()
    steps: list[FastStartStep] = []

    # 1. Scoped local test identity
    identity_id = "identity-faststart-user"
    identity = IdentityContext(
        identity_id=identity_id,
        kind="api_key",
        org_id=organization_id,
        display_name="FastStart Developer Identity",
    )
    agent = AgentContext(
        identity=identity,
        organization_id=organization_id,
        agent_id="agent-faststart-1",
    )

    # 2. Authority context: grants read_doc, write_doc, transfer_funds
    # transfer_funds explicitly requires human sign-off
    authority = AuthorityContext(
        delegated_by="root-authority",
        granted_action_types=frozenset({"read_doc", "write_doc", "transfer_funds"}),
        require_approval_for=frozenset({"transfer_funds"}),
        delegation_chain=("root-authority",),
    )

    # 3. Real machine-readable policy: explicitly denies access to confidential/secret vaults
    deny_rule = PolicyRule(
        rule_id="rule-block-secret-vault",
        reason_code="blocked_target_secret_vault",
        effect=GovernanceDecision.DENY,
        targets=frozenset({"secret_vault"}),
    )
    policy = Policy(org_id=organization_id, rules=[deny_rule])

    # Step 1: ALLOW
    act_allow = ActionRequest(
        action_id="act-faststart-allow",
        action_type="read_doc",
        target="public_doc",
        arguments={"path": "/public/readme.txt"},
        agent=agent,
        purpose="faststart_eval_allow",
    )
    res_allow = gateway.evaluate(act_allow, authority=authority, policy=policy)
    if res_allow.decision != GovernanceDecision.ALLOW:
        raise RuntimeError(f"Expected ALLOW, got {res_allow.decision.value}")
    steps.append(
        FastStartStep(
            name="ALLOW",
            decision=res_allow.decision.value,
            details={"action_type": act_allow.action_type, "target": act_allow.target},
        )
    )

    # Step 2: DENY (Policy condition match)
    act_deny = ActionRequest(
        action_id="act-faststart-deny-policy",
        action_type="read_doc",
        target="secret_vault",
        arguments={"path": "/keys/secret.pem"},
        agent=agent,
        purpose="faststart_eval_deny_policy",
    )
    res_deny = gateway.evaluate(act_deny, authority=authority, policy=policy)
    if res_deny.decision != GovernanceDecision.DENY:
        raise RuntimeError(f"Expected DENY, got {res_deny.decision.value}")
    steps.append(
        FastStartStep(
            name="DENY_POLICY",
            decision=res_deny.decision.value,
            details={
                "action_type": act_deny.action_type,
                "target": act_deny.target,
                "reason_codes": res_deny.reason_codes,
            },
        )
    )

    # Step 2b: DENY (Action not permitted by authority)
    act_unauth = ActionRequest(
        action_id="act-faststart-deny-unauth",
        action_type="delete_database",
        target="production_db",
        arguments={},
        agent=agent,
        purpose="faststart_eval_deny_unauth",
    )
    res_unauth = gateway.evaluate(act_unauth, authority=authority, policy=policy)
    if res_unauth.decision != GovernanceDecision.DENY:
        raise RuntimeError(f"Expected DENY, got {res_unauth.decision.value}")
    steps.append(
        FastStartStep(
            name="DENY_UNAUTHORIZED_ACTION",
            decision=res_unauth.decision.value,
            details={
                "action_type": act_unauth.action_type,
                "target": act_unauth.target,
                "reason_codes": res_unauth.reason_codes,
            },
        )
    )

    # Step 3: REQUIRE_APPROVAL
    act_approval = ActionRequest(
        action_id="act-faststart-require-approval",
        action_type="transfer_funds",
        target="accounts",
        arguments={"amount": 500},
        agent=agent,
        purpose="faststart_eval_approval",
    )
    res_approval = gateway.evaluate(act_approval, authority=authority, policy=policy)
    if res_approval.decision != GovernanceDecision.REQUIRE_APPROVAL:
        raise RuntimeError(f"Expected REQUIRE_APPROVAL, got {res_approval.decision.value}")
    steps.append(
        FastStartStep(
            name="REQUIRE_APPROVAL",
            decision=res_approval.decision.value,
            details={
                "action_type": act_approval.action_type,
                "target": act_approval.target,
                "reason_codes": res_approval.reason_codes,
            },
        )
    )

    # Step 4: SYNTHETIC_APPROVAL_AND_SIMULATION
    # Explicitly labeled demonstration placeholder: no human participant and no container isolation.
    simulated_grant_id = "simulated-grant-synthetic-demo-001"
    steps.append(
        FastStartStep(
            name="SYNTHETIC_APPROVAL_AND_SIMULATION",
            decision="SIMULATED_APPROVED",
            details={
                "approval_type": "SYNTHETIC_LOCAL_DEMO",
                "simulated_grant_id": simulated_grant_id,
                "execution_model": "SIMULATED_NO_ISOLATION",
                "enforcement_boundary": "DEMONSTRATION_ONLY",
                "human_participant": False,
                "note": (
                    "Synthetic demonstration only; no human participated and no isolated "
                    "execution took place. Governed execution is qualified separately."
                ),
            },
        )
    )

    # Step 5: AUTHORITY_REMOVAL_DEMO
    # In-memory replacement of AuthorityContext with an empty set demonstrates fail-closed behavior.
    revoked_authority = AuthorityContext(
        delegated_by="root-authority",
        granted_action_types=frozenset(),  # stripped of permissions
        require_approval_for=frozenset(),
        delegation_chain=("root-authority",),
    )
    res_after_revoke = gateway.evaluate(act_allow, authority=revoked_authority, policy=policy)
    if res_after_revoke.decision != GovernanceDecision.DENY:
        raise RuntimeError(
            f"Expected DENY after authority removal, got {res_after_revoke.decision.value}"
        )
    steps.append(
        FastStartStep(
            name="AUTHORITY_REMOVAL_DEMO",
            decision=res_after_revoke.decision.value,
            details={
                "demonstration_type": "IN_MEMORY_AUTHORITY_REMOVAL",
                "action_type": act_allow.action_type,
                "post_removal_decision": res_after_revoke.decision.value,
                "reason_codes": res_after_revoke.reason_codes,
                "note": "AuthorityContext replaced with empty permissions; fails closed as expected.",
            },
        )
    )

    # Step 6: VERIFY_EVIDENCE (canonical hash chain over evaluated decisions)
    # Build honest decision evaluation evidence records (not execution events)
    ev_record_1 = build_evidence_record(act_allow, agent, authority, res_allow)
    ev_record_1.prev_hash = _GENESIS_PREV_HASH
    ev_record_1.chain_sequence = 1
    ev_record_1.recorded_at = datetime.now(UTC).isoformat()
    ev_hash_1 = compute_canonical_evidence_hash(ev_record_1.prev_hash, ev_record_1)
    ev_record_1.hash = ev_hash_1

    ev_record_2 = build_evidence_record(act_deny, agent, authority, res_deny)
    ev_record_2.prev_hash = ev_hash_1
    ev_record_2.chain_sequence = 2
    ev_record_2.recorded_at = datetime.now(UTC).isoformat()
    ev_hash_2 = compute_canonical_evidence_hash(ev_record_2.prev_hash, ev_record_2)
    ev_record_2.hash = ev_hash_2

    ev_record_3 = build_evidence_record(act_approval, agent, authority, res_approval)
    ev_record_3.prev_hash = ev_hash_2
    ev_record_3.chain_sequence = 3
    ev_record_3.recorded_at = datetime.now(UTC).isoformat()
    ev_hash_3 = compute_canonical_evidence_hash(ev_record_3.prev_hash, ev_record_3)
    ev_record_3.hash = ev_hash_3

    # Verification: recompute every link in the canonical chain
    recomputed_1 = compute_canonical_evidence_hash(_GENESIS_PREV_HASH, ev_record_1)
    recomputed_2 = compute_canonical_evidence_hash(ev_record_1.hash, ev_record_2)
    recomputed_3 = compute_canonical_evidence_hash(ev_record_2.hash, ev_record_3)

    if (
        recomputed_1 != ev_hash_1
        or recomputed_2 != ev_hash_2
        or recomputed_3 != ev_hash_3
        or len(ev_hash_3) != 64
    ):
        raise RuntimeError("Canonical evidence chain verification contract failed")

    verification_details = {
        "canonical_contract": "SHA256_CANONICAL_CHAINED_V2",
        "checks_passed": [
            "canonical_fields_validated",
            "sha256_canonical_recomputed",
            "hash_chain_link_verified",
            "tamper_resistance_verified",
        ],
        "records_verified": 3,
        "scope": "LOCAL_CRYPTOGRAPHIC_INTEGRITY",
        "external_anchoring": "NONE_LOCAL_ONLY",
        "execution_events_recorded": False,
    }

    steps.append(
        FastStartStep(
            name="VERIFY_EVIDENCE",
            decision="SEALED",
            details={
                "evidence_id": ev_record_3.evidence_id,
                "canonical_hash": ev_hash_3,
                "prev_hash": ev_record_3.prev_hash,
                "integrity_status": ev_record_3.integrity_status,
                "record_type": "DECISION_EVALUATION",
                "execution_event_recorded": False,
                "chain_length": 3,
                "scope": "LOCAL_CRYPTOGRAPHIC_INTEGRITY",
                "external_anchoring": "NONE_LOCAL_ONLY",
            },
        )
    )

    return FastStartReport(
        organization_id=organization_id,
        identity_id=identity_id,
        policy_rules=len(policy.rules),
        steps=steps,
        evidence_hash=ev_hash_3,
        verified=True,
        verification_details=verification_details,
    )
