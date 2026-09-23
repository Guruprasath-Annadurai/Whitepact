# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.global_directory.enums import PersonResolutionStatus
from responsibleai.global_directory.identifiers import normalize_free_text
from responsibleai.global_directory.person.signals import ScoredPersonCandidate

# Thresholds are global policy — not tuned per demo person.
_RESOLVE_MIN_SCORE = 0.7
_RESOLVE_MIN_GAP = 0.18
_AMBIGUOUS_MIN_SCORE = 0.22


@dataclass(frozen=True)
class DisambiguationOutcome:
    resolution: PersonResolutionStatus
    ordered: list[ScoredPersonCandidate]
    reason: str | None = None


def disambiguate_candidates(
    candidates: list[ScoredPersonCandidate],
    *,
    shared_name_token: str | None = None,
) -> DisambiguationOutcome:
    if not candidates:
        return DisambiguationOutcome(
            PersonResolutionStatus.UNKNOWN,
            [],
            reason="Insufficient public professional evidence",
        )

    ordered = sorted(candidates, key=lambda c: c.score, reverse=True)

    by_canonical: dict[str, list[ScoredPersonCandidate]] = {}
    for cand in ordered:
        key = normalize_free_text(cand.canonical_name)
        by_canonical.setdefault(key, []).append(cand)
    for group in by_canonical.values():
        if len(group) >= 2:
            return DisambiguationOutcome(
                PersonResolutionStatus.AMBIGUOUS,
                ordered,
                reason="Multiple credible candidates remain",
            )

    if shared_name_token:
        token = normalize_free_text(shared_name_token)
        peers = [
            c
            for c in ordered
            if token in normalize_free_text(c.canonical_name) or token in normalize_free_text(c.professional_context)
        ]
        if len(peers) >= 2:
            return DisambiguationOutcome(
                PersonResolutionStatus.AMBIGUOUS,
                ordered,
                reason="Multiple credible candidates remain",
            )

    top = ordered[0]
    second_score = ordered[1].score if len(ordered) > 1 else 0.0

    strong = [c for c in ordered if c.score >= _AMBIGUOUS_MIN_SCORE]
    if len(strong) == 1 and top.score >= _RESOLVE_MIN_SCORE:
        return DisambiguationOutcome(PersonResolutionStatus.RESOLVED, ordered)

    if top.score >= _RESOLVE_MIN_SCORE and (top.score - second_score) >= _RESOLVE_MIN_GAP:
        return DisambiguationOutcome(PersonResolutionStatus.RESOLVED, ordered)

    if len(strong) >= 2:
        return DisambiguationOutcome(
            PersonResolutionStatus.AMBIGUOUS,
            ordered,
            reason="Multiple credible candidates remain",
        )

    if top.score < _AMBIGUOUS_MIN_SCORE:
        return DisambiguationOutcome(
            PersonResolutionStatus.UNKNOWN,
            ordered,
            reason="Insufficient public professional evidence",
        )

    return DisambiguationOutcome(PersonResolutionStatus.AMBIGUOUS, ordered, reason="Weak multi-match")
