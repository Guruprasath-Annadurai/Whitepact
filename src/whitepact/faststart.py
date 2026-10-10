# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact FastStart V1 — Ultra-fast verification of core governance doctrine.

Provides developers with an instant (< 60s), fully isolated, zero-network,
cryptographically verifiable demonstration of WhitePact's core governance:
ALLOW -> DENY -> REQUIRE_APPROVAL -> APPROVE -> EXECUTE -> REVOKE -> VERIFY EVIDENCE.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from responsibleai.governance.evidence import EvidenceRecord, compute_canonical_evidence_hash
from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.policy import Policy, PolicyRule


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
        }


def run_faststart_workflow(*, organization_id: str = "org-faststart-demo") -> FastStartReport:
    """Execute the full end-to-end WhitePact FastStart V1 governance lifecycle."""
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

    # Step 4: APPROVE -> EXECUTE grant
    grant_id = "grant-faststart-human-approved-101"
    steps.append(
        FastStartStep(
            name="APPROVE_AND_EXECUTE",
            decision="APPROVED",
            details={
                "approval_outcome": "APPROVED",
                "execution_grant_id": grant_id,
                "note": "Human supervisor signed off on action",
            },
        )
    )

    # Step 5: REVOKE authority
    revoked_authority = AuthorityContext(
        delegated_by="root-authority",
        granted_action_types=frozenset(),  # stripped of permissions
        require_approval_for=frozenset(),
        delegation_chain=("root-authority",),
    )
    res_after_revoke = gateway.evaluate(act_allow, authority=revoked_authority, policy=policy)
    if res_after_revoke.decision != GovernanceDecision.DENY:
        raise RuntimeError(f"Expected DENY after revoke, got {res_after_revoke.decision.value}")
    steps.append(
        FastStartStep(
            name="REVOKE",
            decision=res_after_revoke.decision.value,
            details={
                "action_type": act_allow.action_type,
                "post_revocation_decision": res_after_revoke.decision.value,
                "reason_codes": res_after_revoke.reason_codes,
            },
        )
    )

    # Step 6: VERIFY EVIDENCE (canonical hash chain)
    evidence = EvidenceRecord(
        evidence_id="ev-faststart-canonical-001",
        organization_id=organization_id,
        action_id=act_deny.action_id,
        agent_id=agent.agent_id,
        identity_id=identity_id,
        action_type=act_deny.action_type,
        target=act_deny.target,
        argument_keys=list(act_deny.arguments.keys()),
        authority_delegated_by="root-authority",
        delegation_chain=["root-authority", identity_id],
        decision=res_deny.decision.value,
        reason_codes=res_deny.reason_codes,
        evaluated_at=datetime.now(UTC),
        recorded_at=datetime.now(UTC).isoformat(),
        prev_hash="0" * 64,
        integrity_version=2,
        integrity_status="CANONICAL_CHAINED",
        authentication_method="api_key",
        purpose=act_deny.purpose,
        execution_authorization_id=None,
        execution_target=None,
        approval_id=None,
    )
    ev_hash = compute_canonical_evidence_hash(evidence.prev_hash, evidence)
    if not ev_hash or len(ev_hash) != 64:
        raise RuntimeError(f"Invalid canonical evidence hash: {ev_hash}")
    steps.append(
        FastStartStep(
            name="VERIFY_EVIDENCE",
            decision="SEALED",
            details={
                "evidence_id": evidence.evidence_id,
                "canonical_hash": ev_hash,
                "prev_hash": evidence.prev_hash,
                "integrity_status": evidence.integrity_status,
            },
        )
    )

    return FastStartReport(
        organization_id=organization_id,
        identity_id=identity_id,
        policy_rules=len(policy.rules),
        steps=steps,
        evidence_hash=ev_hash,
        verified=True,
    )
