# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Constitutional debugger — governance causality without model chain-of-thought."""

from __future__ import annotations

from responsibleai.governance.models import GovernanceDecision
from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.errors import SovereignTenantIsolationError
from responsibleai.sovereign.models import (
    ConstitutionalExplanation,
    ExplanationItem,
    ExplanationKind,
    OutcomeDisposition,
)
from responsibleai.sovereign.redaction import redact_for_debugger
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.tenant import assert_same_organization


async def explain_from_evidence(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    evidence_id: str,
) -> ConstitutionalExplanation:
    record = await store.evidence.get_for_org(evidence_id, ctx.organization_id)
    if record is None:
        raise SovereignTenantIsolationError("debugger context not found")

    items: list[ExplanationItem] = []
    safe = redact_for_debugger(
        {
            "action_type": record.action_type,
            "target": record.target,
            "argument_keys": record.argument_keys,
            "reason_codes": record.reason_codes,
            "risk_tier": record.risk_tier,
        }
    )
    for key, value in safe.items():
        items.append(
            ExplanationItem(
                kind=ExplanationKind.FACT,
                code=key,
                message=str(value),
                refs=[f"evidence:{evidence_id}"],
            )
        )

    principal = record.identity_id or record.agent_id
    if principal:
        explain = await store.delegations.explain_authority(ctx.organization_id, principal)
        items.append(
            ExplanationItem(
                kind=ExplanationKind.DERIVED,
                code="delegation_chain",
                message=f"Chain length {len(explain.get('chain', []))}; active={explain.get('currently_active')}",
                refs=[h["delegation_id"] for h in explain.get("chain", [])],
            )
        )
    else:
        items.append(
            ExplanationItem(
                kind=ExplanationKind.MISSING,
                code="principal",
                message="No principal/agent on evidence row",
            )
        )

    if record.policy_version is None:
        items.append(
            ExplanationItem(
                kind=ExplanationKind.MISSING,
                code="policy_version",
                message="Policy version not recorded on evidence",
            )
        )
    else:
        items.append(
            ExplanationItem(
                kind=ExplanationKind.FACT,
                code="policy_version",
                message=str(record.policy_version),
            )
        )

    disposition: GovernanceDecision | OutcomeDisposition
    reconciliation = False
    try:
        disposition = GovernanceDecision(record.decision)
    except ValueError:
        disposition = OutcomeDisposition.UNKNOWN
        reconciliation = True
        items.append(
            ExplanationItem(
                kind=ExplanationKind.MISSING,
                code="decision",
                message=f"Unknown decision value: {record.decision}",
            )
        )

    if record.approval_id:
        approval = await store.approvals.get(record.approval_id)
        if approval is None:
            items.append(
                ExplanationItem(
                    kind=ExplanationKind.MISSING,
                    code="approval",
                    message="Approval id present but row missing",
                    refs=[record.approval_id],
                )
            )
            reconciliation = True
        else:
            assert_same_organization(
                ctx.organization_id, approval.organization_id, resource_kind="approval"
            )
            items.append(
                ExplanationItem(
                    kind=ExplanationKind.FACT,
                    code="approval_status",
                    message=str(approval.status),
                    refs=[record.approval_id],
                )
            )

    if record.governance_epoch is not None:
        items.append(
            ExplanationItem(
                kind=ExplanationKind.FACT,
                code="governance_epoch",
                message=str(record.governance_epoch),
            )
        )
    else:
        items.append(
            ExplanationItem(
                kind=ExplanationKind.MISSING,
                code="governance_epoch",
                message="Epoch not recorded on evidence",
            )
        )

    epoch = await store.revocation_epochs.current(ctx.organization_id)
    items.append(
        ExplanationItem(
            kind=ExplanationKind.FACT,
            code="current_revocation_epoch",
            message=str(epoch.epoch),
        )
    )

    if disposition == OutcomeDisposition.UNKNOWN:
        reconciliation = True

    return ConstitutionalExplanation(
        disposition=disposition,
        items=items,
        reconciliation_required=reconciliation,
    )


async def explain_from_identity(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    identity_id: str,
) -> ConstitutionalExplanation:
    explain = await store.delegations.explain_authority(ctx.organization_id, identity_id)
    items: list[ExplanationItem] = [
        ExplanationItem(
            kind=ExplanationKind.FACT,
            code="identity_id",
            message=identity_id,
        ),
        ExplanationItem(
            kind=ExplanationKind.DERIVED,
            code="currently_active",
            message=str(explain.get("currently_active")),
        ),
    ]
    for hop in explain.get("chain", []):
        items.append(
            ExplanationItem(
                kind=ExplanationKind.FACT,
                code="delegation_hop",
                message=f"{hop['from_identity_id']} -> {hop['to_identity_id']}: {hop['granted_action_types']}",
                refs=[hop["delegation_id"]],
            )
        )
    if not explain.get("chain"):
        items.append(
            ExplanationItem(
                kind=ExplanationKind.MISSING,
                code="delegation_chain",
                message="No delegation chain for identity",
            )
        )
    disposition = (
        GovernanceDecision.ALLOW if explain.get("currently_active") else GovernanceDecision.DENY
    )
    return ConstitutionalExplanation(disposition=disposition, items=items)
