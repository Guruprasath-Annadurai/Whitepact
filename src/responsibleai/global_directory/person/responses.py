# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from responsibleai.global_directory.enums import EntityType, EvidenceState, PersonResolutionStatus
from responsibleai.global_directory.models import (
    DirectoryClaim,
    DirectoryEntity,
    DirectoryRelationship,
    DirectorySource,
    PersonResolutionPayload,
)
from responsibleai.global_directory.person.signals import ScoredPersonCandidate
from responsibleai.global_directory.synthesis import grounded_summary


def person_candidate_summary(candidate: ScoredPersonCandidate) -> dict[str, Any]:
    return {
        "entity_id": candidate.entity_id,
        "name": candidate.canonical_name,
        "professional_context": candidate.professional_context,
        "confidence": round(candidate.score, 3),
        "distinguishing_signals": [
            {"kind": s.kind.value, "detail": s.detail, "polarity": s.polarity.value} for s in candidate.signals[:8]
        ],
    }


def build_person_payload(
    *,
    resolution: PersonResolutionStatus,
    query: str,
    hints_display: str,
    entity: DirectoryEntity | None,
    claims: list[DirectoryClaim],
    relationships: list[DirectoryRelationship],
    sources: list[DirectorySource],
    candidates: list[ScoredPersonCandidate],
    reason: str | None = None,
    refinement_token: str | None = None,
) -> PersonResolutionPayload:
    conflicts = [
        {"claim_id": c.claim_id, "predicate": c.predicate, "state": c.evidence_state.value}
        for c in claims
        if c.evidence_state == EvidenceState.CONFLICTING_EVIDENCE
    ]
    payload: dict[str, Any] = {
        "resolution": resolution.value,
        "query": query,
    }
    if resolution == PersonResolutionStatus.RESOLVED and entity:
        payload["entity"] = {
            "id": entity.entity_id,
            "canonical_name": entity.canonical_name,
            "type": EntityType.PERSON.value,
            "confidence": entity.confidence,
            "last_verified_at": entity.last_verified_at,
        }
        payload["professional_summary"] = grounded_summary(entity, claims)
        payload["roles"] = _roles_from_claims(claims)
        payload["organizations"] = _orgs_from_claims(claims)
        payload["projects"] = []
        payload["repositories"] = []
        payload["publications"] = []
        payload["relationships"] = [r.model_dump() for r in relationships]
        payload["claims"] = [c.model_dump() for c in claims]
        payload["sources"] = [s.model_dump() for s in sources]
        payload["conflicts"] = conflicts
    elif resolution == PersonResolutionStatus.AMBIGUOUS:
        payload["candidates"] = [person_candidate_summary(c) for c in candidates if c.score > 0]
        payload["recommended_disambiguation_fields"] = [
            "organization",
            "profession",
            "project",
            "location",
        ]
        if refinement_token:
            payload["refinement_token"] = refinement_token
    else:
        payload["reason"] = reason or "Insufficient public professional evidence"

    return PersonResolutionPayload(**payload)


def _roles_from_claims(claims: list[DirectoryClaim]) -> list[dict[str, Any]]:
    roles: list[dict[str, Any]] = []
    for c in claims:
        if c.predicate in {"ROLE", "TITLE", "EMPLOYED_AS"}:
            roles.append(
                {
                    "title": c.normalized_value,
                    "evidence_state": c.evidence_state.value,
                    "valid_from": c.valid_from,
                    "valid_until": c.valid_until,
                    "last_verified_at": c.last_verified_at,
                }
            )
    return roles


def _orgs_from_claims(claims: list[DirectoryClaim]) -> list[dict[str, Any]]:
    orgs: list[dict[str, Any]] = []
    for c in claims:
        if c.predicate == "ASSOCIATED_WITH":
            orgs.append(
                {
                    "name": c.normalized_value,
                    "evidence_state": c.evidence_state.value,
                    "valid_from": c.valid_from,
                    "valid_until": c.valid_until,
                }
            )
    return orgs
