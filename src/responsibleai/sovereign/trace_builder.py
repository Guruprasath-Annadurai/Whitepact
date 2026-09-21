# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic authority trace reconstruction from canonical facts."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, Field

from responsibleai.governance.models import GovernanceDecision
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.errors import SovereignTenantIsolationError
from responsibleai.sovereign.models import OutcomeDisposition, SovereignExecutionEnvelope
from responsibleai.sovereign.redaction import redact_for_debugger
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.tenant import assert_same_organization


class TraceStageKind(StrEnum):
    PRINCIPAL = "principal"
    AUTHORITY = "authority"
    DELEGATION = "delegation"
    CAPABILITY = "capability"
    POLICY = "policy"
    APPROVAL = "approval"
    JUDGMENT = "judgment"
    GRANT = "grant"
    EXECUTION = "execution"
    EFFECT = "effect"
    EVIDENCE = "evidence"
    OUTCOME = "outcome"


class TraceStage(BaseModel):
    stage: TraceStageKind
    status: str  # PRESENT | MISSING | UNKNOWN
    identifier: str | None = None
    timestamp: str | None = None
    provenance: str
    summary: str
    refs: list[str] = Field(default_factory=list)


class AuthorityTrace(BaseModel):
    organization_id: str
    trace_id: str
    stages: list[TraceStage] = Field(default_factory=list)
    envelope: SovereignExecutionEnvelope
    human_summary: str
    machine: dict[str, object] = Field(default_factory=dict)


def _ts(value: object) -> str | None:
    if value is None:
        return None
    if hasattr(value, "isoformat"):
        return value.isoformat()  # type: ignore[union-attr]
    return str(value)


async def build_trace_from_evidence(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    evidence_id: str,
) -> AuthorityTrace:
    record = await store.evidence.get_for_org(evidence_id, ctx.organization_id)
    if record is None:
        raise SovereignTenantIsolationError("trace not found")

    stages: list[TraceStage] = []
    principal = record.identity_id or record.agent_id
    if principal:
        stages.append(
            TraceStage(
                stage=TraceStageKind.PRINCIPAL,
                status="PRESENT",
                identifier=principal,
                timestamp=_ts(record.evaluated_at),
                provenance="DATABASE_FACT",
                summary=f"Principal/agent {principal}",
                refs=[f"evidence:{evidence_id}"],
            )
        )
        explain = await store.delegations.explain_authority(ctx.organization_id, principal)
        if explain.get("chain"):
            stages.append(
                TraceStage(
                    stage=TraceStageKind.DELEGATION,
                    status="PRESENT",
                    identifier=principal,
                    provenance="DERIVED_FROM_FACTS",
                    summary=f"Delegation chain length {len(explain['chain'])}",
                    refs=[h["delegation_id"] for h in explain["chain"]],
                )
            )
        else:
            stages.append(
                TraceStage(
                    stage=TraceStageKind.DELEGATION,
                    status="MISSING",
                    provenance="DATABASE_FACT",
                    summary="No delegation chain recorded for principal",
                )
            )
    else:
        stages.append(
            TraceStage(
                stage=TraceStageKind.PRINCIPAL,
                status="MISSING",
                provenance="DATABASE_FACT",
                summary="Evidence row has no identity_id or agent_id",
            )
        )

    if record.action_type:
        stages.append(
            TraceStage(
                stage=TraceStageKind.CAPABILITY,
                status="PRESENT",
                identifier=record.action_type,
                provenance="DATABASE_FACT",
                summary=f"Action type {record.action_type}",
            )
        )

    policy_version = record.policy_version
    if policy_version is not None:
        stages.append(
            TraceStage(
                stage=TraceStageKind.POLICY,
                status="PRESENT",
                identifier=str(policy_version),
                provenance="DATABASE_FACT",
                summary=f"Policy version {policy_version} recorded on evidence",
            )
        )
    else:
        stages.append(
            TraceStage(
                stage=TraceStageKind.POLICY,
                status="UNKNOWN",
                provenance="MISSING",
                summary="Policy version not recorded on evidence row",
            )
        )

    if record.approval_id:
        approval = await store.approvals.get(record.approval_id)
        if approval is None:
            stages.append(
                TraceStage(
                    stage=TraceStageKind.APPROVAL,
                    status="UNKNOWN",
                    identifier=record.approval_id,
                    provenance="MISSING",
                    summary="Approval id referenced but row not found",
                )
            )
        else:
            assert_same_organization(
                ctx.organization_id, approval.organization_id, resource_kind="approval"
            )
            stages.append(
                TraceStage(
                    stage=TraceStageKind.APPROVAL,
                    status="PRESENT",
                    identifier=record.approval_id,
                    provenance="DATABASE_FACT",
                    summary=f"Approval status {approval.status}",
                )
            )
    else:
        stages.append(
            TraceStage(
                stage=TraceStageKind.APPROVAL,
                status="MISSING",
                provenance="DATABASE_FACT",
                summary="No approval reference on evidence",
            )
        )

    decision: GovernanceDecision | None = None
    try:
        decision = GovernanceDecision(record.decision)
        stages.append(
            TraceStage(
                stage=TraceStageKind.JUDGMENT,
                status="PRESENT",
                identifier=record.decision,
                timestamp=_ts(record.evaluated_at),
                provenance="DATABASE_FACT",
                summary=f"Governance decision {record.decision}",
            )
        )
        outcome_disp = _map_decision_to_outcome(decision)
    except ValueError:
        stages.append(
            TraceStage(
                stage=TraceStageKind.JUDGMENT,
                status="UNKNOWN",
                identifier=record.decision,
                provenance="DATABASE_FACT",
                summary=f"Unrecognized decision value {record.decision}",
            )
        )
        outcome_disp = OutcomeDisposition.UNKNOWN

    if record.execution_authorization_id:
        stages.append(
            TraceStage(
                stage=TraceStageKind.GRANT,
                status="PRESENT",
                identifier=record.execution_authorization_id,
                provenance="DATABASE_FACT",
                summary="Execution authorization reference on evidence",
            )
        )
    else:
        stages.append(
            TraceStage(
                stage=TraceStageKind.GRANT,
                status="MISSING",
                provenance="DATABASE_FACT",
                summary="No execution authorization reference on evidence",
            )
        )

    stages.append(
        TraceStage(
            stage=TraceStageKind.EVIDENCE,
            status="PRESENT",
            identifier=evidence_id,
            timestamp=record.recorded_at,
            provenance="DATABASE_FACT",
            summary="Evidence record persisted",
        )
    )

    outcome = await store.outcomes.get_for_org(evidence_id, ctx.organization_id)
    if outcome is not None:
        stages.append(
            TraceStage(
                stage=TraceStageKind.OUTCOME,
                status="PRESENT",
                identifier=outcome.outcome_id,
                provenance="DATABASE_FACT",
                summary=f"Outcome disposition {outcome.disposition}",
            )
        )
    else:
        stages.append(
            TraceStage(
                stage=TraceStageKind.OUTCOME,
                status="MISSING",
                provenance="DATABASE_FACT",
                summary="No outcome row linked to evidence",
            )
        )

    envelope = SovereignExecutionEnvelope(
        organization_id=ctx.organization_id,
        environment=ctx.environment,
        principal_id=record.identity_id,
        agent_id=record.agent_id,
        action=record.action_type,
        target_fingerprint=record.request_fingerprint,
        delegation_chain=list(record.delegation_chain or []),
        authority_chain=[record.authority_delegated_by] if record.authority_delegated_by else [],
        policy_refs=[str(record.policy_version)] if record.policy_version else [],
        approval_refs=[record.approval_id] if record.approval_id else [],
        judgment=decision,
        governance_epoch=record.governance_epoch,
        execution_grant_ref=record.execution_authorization_id,
        nonce_ref=record.execution_nonce_reference,
        evidence_id=evidence_id,
        outcome_id=outcome.outcome_id if outcome else None,
        outcome=outcome_disp,
        reconciliation_required=outcome_disp == OutcomeDisposition.UNKNOWN,
        source_provenance=redact_for_debugger(
            {
                "evidence_id": evidence_id,
                "integrity_status": record.integrity_status,
            }
        ),
    )

    human = "; ".join(f"{s.stage.value}:{s.status}" for s in stages)
    return AuthorityTrace(
        organization_id=ctx.organization_id,
        trace_id=f"trace:{evidence_id}",
        stages=stages,
        envelope=envelope,
        human_summary=human,
        machine={"stages": [s.model_dump() for s in stages]},
    )


def _map_decision_to_outcome(decision: GovernanceDecision) -> OutcomeDisposition:
    if decision == GovernanceDecision.DENY:
        return OutcomeDisposition.DENIED
    if decision == GovernanceDecision.REQUIRE_APPROVAL:
        return OutcomeDisposition.APPROVAL_REQUIRED
    if decision in (GovernanceDecision.ALLOW, GovernanceDecision.ALLOW_WITH_REDACTION):
        return OutcomeDisposition.SUCCEEDED
    if decision == GovernanceDecision.QUARANTINE:
        return OutcomeDisposition.DENIED
    return OutcomeDisposition.UNKNOWN
