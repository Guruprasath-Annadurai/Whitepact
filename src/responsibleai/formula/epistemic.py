# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Epistemic status and evidence strength."""

from __future__ import annotations

from enum import StrEnum


class EpistemicStatus(StrEnum):
    VERIFIED = "VERIFIED"
    OBSERVED = "OBSERVED"
    DECLARED = "DECLARED"
    INFERRED = "INFERRED"
    ASSUMED = "ASSUMED"
    UNKNOWN = "UNKNOWN"


class EvidenceStrength(StrEnum):
    """Ordered classification; higher index = stronger for proof."""

    UNKNOWN = "UNKNOWN"
    ASSUMED = "ASSUMED"
    INFERRED = "INFERRED"
    DECLARED = "DECLARED"
    OBSERVED = "OBSERVED"
    VERIFIED = "VERIFIED"


_STRENGTH_ORDER: tuple[EvidenceStrength, ...] = (
    EvidenceStrength.UNKNOWN,
    EvidenceStrength.ASSUMED,
    EvidenceStrength.INFERRED,
    EvidenceStrength.DECLARED,
    EvidenceStrength.OBSERVED,
    EvidenceStrength.VERIFIED,
)


def strength_at_least(actual: EvidenceStrength, required: EvidenceStrength) -> bool:
    return _STRENGTH_ORDER.index(actual) >= _STRENGTH_ORDER.index(required)


def epistemic_to_strength(status: EpistemicStatus) -> EvidenceStrength:
    return EvidenceStrength(status.value)


def is_authoritative_for_hard_proof(status: EpistemicStatus) -> bool:
    """INFERRED/ASSUMED/UNKNOWN cannot silently satisfy hard proof."""
    return status in (EpistemicStatus.VERIFIED, EpistemicStatus.OBSERVED)
