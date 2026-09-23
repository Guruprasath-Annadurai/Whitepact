# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.global_directory.enums import EvidenceState, SourceQualityTier


def classify_claim_evidence(
    *,
    source_tiers: list[SourceQualityTier],
    independent_sources: int,
    contradicting: bool,
    stale: bool,
) -> EvidenceState:
    if contradicting:
        return EvidenceState.CONFLICTING_EVIDENCE
    if stale:
        return EvidenceState.STALE
    authoritative = {
        SourceQualityTier.AUTHORITATIVE_PRIMARY,
        SourceQualityTier.AUTHORITATIVE_REGISTRY,
        SourceQualityTier.FIRST_PARTY_PUBLICATION,
    }
    auth_count = sum(1 for t in source_tiers if t in authoritative)
    if auth_count >= 1 and independent_sources >= 2:
        return EvidenceState.VERIFIED_FACT
    if auth_count >= 1:
        return EvidenceState.INFERRED_SIGNAL
    if source_tiers:
        return EvidenceState.INFERRED_SIGNAL
    return EvidenceState.UNKNOWN
