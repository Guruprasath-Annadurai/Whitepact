# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Evidence correlation across canonical artifacts."""

from __future__ import annotations

from pydantic import BaseModel, Field

from responsibleai.sovereign.context import SovereignContext
from responsibleai.sovereign.sources import SovereignCanonicalStore
from responsibleai.sovereign.zero_effect import zero_effect_operation


class EvidenceLink(BaseModel):
    kind: str
    identifier: str
    verification: str  # INCOMPLETE | VERIFIED | UNSIGNED | UNKNOWN


class EvidenceCorrelationGraph(BaseModel):
    organization_id: str
    root_evidence_id: str
    links: list[EvidenceLink] = Field(default_factory=list)


@zero_effect_operation
async def correlate_evidence(
    store: SovereignCanonicalStore,
    ctx: SovereignContext,
    evidence_id: str,
) -> EvidenceCorrelationGraph:
    record = await store.evidence.get_for_org(evidence_id, ctx.organization_id)
    links: list[EvidenceLink] = []
    if record is None:
        return EvidenceCorrelationGraph(
            organization_id=ctx.organization_id,
            root_evidence_id=evidence_id,
            links=[],
        )
    integrity = getattr(record, "integrity_status", None) or "INCOMPLETE"
    verification = "VERIFIED" if str(integrity).endswith("VERIFIED") else "INCOMPLETE"
    links.append(
        EvidenceLink(
            kind="evidence",
            identifier=record.evidence_id,
            verification=verification,
        )
    )
    if record.approval_id:
        links.append(
            EvidenceLink(
                kind="approval",
                identifier=record.approval_id,
                verification="INCOMPLETE",
            )
        )
    outcome = await store.outcomes.get_for_org(record.evidence_id, ctx.organization_id)
    if outcome:
        status = outcome.status.value
        links.append(
            EvidenceLink(
                kind="outcome",
                identifier=outcome.outcome_id,
                verification="UNKNOWN" if status == "UNKNOWN" else "INCOMPLETE",
            )
        )
    return EvidenceCorrelationGraph(
        organization_id=ctx.organization_id,
        root_evidence_id=evidence_id,
        links=links,
    )
