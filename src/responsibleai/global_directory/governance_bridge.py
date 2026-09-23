# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.global_directory.enums import EvidenceState, FreshnessState
from responsibleai.global_directory.models import (
    DirectoryClaim,
    DirectoryEntity,
    TrustContext,
    TrustContextSignal,
)


@dataclass(frozen=True)
class GovernanceDirectoryContext:
    """Read-only risk inputs for policy evaluation. Never grants authority."""

    entity_id: str | None
    trust_context: TrustContext
    recommended_posture: str
    authority_note: str = "Directory intelligence does not mint execution authority."


def build_governance_context(
    entity: DirectoryEntity | None,
    claims: list[DirectoryClaim],
) -> GovernanceDirectoryContext:
    signals: list[TrustContextSignal] = []
    if entity is None:
        return GovernanceDirectoryContext(
            entity_id=None,
            trust_context=TrustContext(entity_id="", signals=[], freshness_state=FreshnessState.REFRESH_REQUIRED),
            recommended_posture="UNKNOWN_ENTITY",
        )
    if entity.evidence_state == EvidenceState.CONFLICTING_EVIDENCE:
        signals.append(
            TrustContextSignal(
                code="CONFLICTING_IDENTITY_EVIDENCE",
                label="Conflicting identity evidence",
                evidence_state=EvidenceState.CONFLICTING_EVIDENCE,
            )
        )
    if entity.freshness_state in {FreshnessState.STALE, FreshnessState.REFRESH_REQUIRED}:
        signals.append(
            TrustContextSignal(
                code="STALE_DIRECTORY_EVIDENCE",
                label="Stale directory evidence",
                evidence_state=EvidenceState.STALE,
            )
        )
    unknown_claims = [c for c in claims if c.evidence_state == EvidenceState.UNKNOWN]
    if unknown_claims:
        signals.append(
            TrustContextSignal(
                code="UNKNOWN_RELATIONSHIP",
                label="Material unknown relationships",
                evidence_state=EvidenceState.UNKNOWN,
                detail=f"{len(unknown_claims)} unknown claim(s)",
            )
        )
    posture = "LOW"
    if any(s.code == "CONFLICTING_IDENTITY_EVIDENCE" for s in signals):
        posture = "HIGH"
    elif unknown_claims:
        posture = "MEDIUM"
    trust = TrustContext(
        entity_id=entity.entity_id,
        signals=signals,
        freshness_state=entity.freshness_state,
    )
    return GovernanceDirectoryContext(
        entity_id=entity.entity_id,
        trust_context=trust,
        recommended_posture=posture,
    )
