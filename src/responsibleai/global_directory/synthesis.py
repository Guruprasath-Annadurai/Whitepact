# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.global_directory.enums import EvidenceState
from responsibleai.global_directory.models import DirectoryClaim, DirectoryEntity


def grounded_summary(entity: DirectoryEntity, claims: list[DirectoryClaim]) -> str:
    if not entity:
        return "No entity resolved."
    verified = [c for c in claims if c.evidence_state == EvidenceState.VERIFIED_FACT]
    inferred = [c for c in claims if c.evidence_state == EvidenceState.INFERRED_SIGNAL]
    conflicting = [c for c in claims if c.evidence_state == EvidenceState.CONFLICTING_EVIDENCE]
    parts = [f"{entity.canonical_name} ({entity.entity_type.value})"]
    if entity.description:
        parts.append(entity.description)
    if verified:
        parts.append(
            "Verified claims: "
            + "; ".join(f"{c.predicate} {c.normalized_value or c.object_entity_id}" for c in verified[:5])
        )
    if inferred:
        parts.append(
            "Inferred signals: "
            + "; ".join(f"{c.predicate} {c.normalized_value or ''}".strip() for c in inferred[:5])
        )
    if conflicting:
        parts.append(f"{len(conflicting)} conflicting claim(s) require review.")
    if not claims:
        parts.append("Insufficient public evidence to support additional claims.")
    return " ".join(parts)
