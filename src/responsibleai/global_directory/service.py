# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import uuid

from responsibleai.global_directory.discovery.providers.fixture_catalog import (
    FixtureCatalogProvider,
)
from responsibleai.global_directory.discovery.registry import (
    _fixture_enabled,
    build_discovery_providers,
)
from responsibleai.global_directory.enums import EntityType, EvidenceState, PersonResolutionStatus
from responsibleai.global_directory.governance_bridge import build_governance_context
from responsibleai.global_directory.identifiers import extract_identifiers, normalize_free_text
from responsibleai.global_directory.models import (
    MachineDirectoryResponse,
    PersonResolutionPayload,
    ResolutionCandidate,
    ResolutionResult,
)
from responsibleai.global_directory.person.hints import (
    extract_person_hints,
    is_person_primary_query,
)
from responsibleai.global_directory.person.pipeline import PersonResolutionPipeline
from responsibleai.global_directory.repository import GlobalDirectoryRepository
from responsibleai.global_directory.synthesis import grounded_summary

logger = logging.getLogger(__name__)


class GlobalDirectoryService:
    def __init__(self, repo: GlobalDirectoryRepository) -> None:
        self._repo = repo
        self._fixture = FixtureCatalogProvider()
        self._person = PersonResolutionPipeline(repo)

    async def resolve_person(
        self,
        query: str,
        *,
        allow_discovery: bool = True,
    ) -> PersonResolutionPayload:
        result, payload = await self._person.resolve(query, allow_discovery=allow_discovery)
        return payload

    async def refine_resolution(
        self,
        refinement_token: str,
        *,
        organization_hint: str | None = None,
        profession_hint: str | None = None,
    ) -> PersonResolutionPayload:
        _, payload = await self._person.refine(
            refinement_token,
            organization_hint=organization_hint,
            profession_hint=profession_hint,
        )
        return payload

    async def resolve_entity(self, query: str, *, allow_discovery: bool = True) -> ResolutionResult:
        parsed_identifiers = extract_identifiers(query)
        for ident in parsed_identifiers:
            if ident.implied_entity_type and ident.implied_entity_type != EntityType.PERSON:
                entity = await self._repo.find_by_identifier(ident.identifier_type, ident.normalized_value)
                if entity:
                    return ResolutionResult(
                        query=query,
                        status=PersonResolutionStatus.RESOLVED.value,
                        confidence=entity.confidence,
                        entity=entity,
                    )

        if is_person_primary_query(query):
            result, _ = await self._person.resolve(query, allow_discovery=allow_discovery)
            if result.status == PersonResolutionStatus.AMBIGUOUS.value and result.person:
                from datetime import UTC, datetime

                from responsibleai.global_directory.models import DirectoryEntity

                now = datetime.now(UTC).isoformat()
                result.candidates = [
                    ResolutionCandidate(
                        entity=DirectoryEntity(
                            entity_id=str(c.get("entity_id", "")),
                            canonical_name=str(c.get("name", "")),
                            entity_type=EntityType.PERSON,
                            description=str(c.get("professional_context", "")),
                            confidence=float(c.get("confidence", 0)),
                            created_at=now,
                            last_observed_at=now,
                        ),
                        match_reason="person_disambiguation",
                        confidence=float(c.get("confidence", 0)),
                    )
                    for c in result.person.candidates
                ]
            return result

        normalized = normalize_free_text(query)
        candidates_entities = await self._repo.search_by_name(normalized)
        if len(candidates_entities) == 1:
            ent = candidates_entities[0]
            return ResolutionResult(
                query=query,
                status=PersonResolutionStatus.RESOLVED.value,
                confidence=ent.confidence,
                entity=ent,
            )
        if len(candidates_entities) > 1:
            return ResolutionResult(
                query=query,
                status=PersonResolutionStatus.AMBIGUOUS.value,
                confidence=max(e.confidence for e in candidates_entities),
                candidates=[
                    ResolutionCandidate(entity=e, match_reason="name_or_alias", confidence=e.confidence)
                    for e in candidates_entities
                ],
                message="Multiple entities match; disambiguation required.",
            )

        if allow_discovery:
            hints = extract_person_hints(query)
            for provider in build_discovery_providers():
                matches = provider.discover(query, hints) if hasattr(provider, "discover") else []
                if not matches and hasattr(provider, "match_entities"):
                    matches = provider.match_entities(query, hints)
                non_person = [m for m in matches if m.get("entity_type") != EntityType.PERSON.value]
                if len(non_person) == 1:
                    bundle = self._fixture.materialize(non_person[0])
                    await self._repo.save_entity_bundle(
                        bundle[0],
                        identifiers=bundle[1],
                        aliases=bundle[2],
                        sources=bundle[3],
                        claims=bundle[4],
                        relationships=bundle[5],
                    )
                    return ResolutionResult(
                        query=query,
                        status=PersonResolutionStatus.RESOLVED.value,
                        confidence=bundle[0].confidence,
                        entity=bundle[0],
                    )

        return ResolutionResult(
            query=query,
            status=PersonResolutionStatus.UNKNOWN.value,
            confidence=0.0,
            message="No entity matched.",
        )

    async def search_entities(self, query: str, limit: int = 10) -> list[ResolutionCandidate]:
        resolution = await self.resolve_entity(query, allow_discovery=True)
        if resolution.entity:
            return [
                ResolutionCandidate(
                    entity=resolution.entity,
                    match_reason="resolve",
                    confidence=resolution.confidence,
                )
            ]
        return resolution.candidates[:limit]

    async def get_machine_response(self, entity_id: str) -> MachineDirectoryResponse:
        entity = await self._repo.get_entity(entity_id)
        if not entity:
            return MachineDirectoryResponse(summary="Entity not found.")
        claims = await self._repo.list_claims(entity_id)
        relationships = await self._repo.list_relationships(entity_id)
        sources = await self._repo.list_sources_for_entity(entity_id)
        conflicts = [
            {"claim_id": c.claim_id, "predicate": c.predicate, "state": c.evidence_state.value}
            for c in claims
            if c.evidence_state == EvidenceState.CONFLICTING_EVIDENCE
        ]
        gov = build_governance_context(entity, claims)
        return MachineDirectoryResponse(
            entity=entity,
            claims=claims,
            relationships=relationships,
            conflicts=conflicts,
            sources=sources,
            trust_context=gov.trust_context,
            last_verified_at=entity.last_verified_at,
            summary=grounded_summary(entity, claims),
        )

    async def verify_claim(self, claim_id: str) -> dict[str, str]:
        return {
            "claim_id": claim_id,
            "status": "lookup_requires_repository_scope",
            "note": "Claim verification re-evaluates evidence_state; does not grant authority.",
        }

    async def check_identity_conflict(self, query: str) -> dict[str, object]:
        result = await self.resolve_entity(query, allow_discovery=True)
        return {
            "status": result.status,
            "ambiguous": result.status == PersonResolutionStatus.AMBIGUOUS.value,
            "candidate_count": len(result.candidates),
            "message": result.message,
        }

    async def record_discovery_run(self, query: str, status: str, org_id: str | None = None) -> str:
        run_id = f"run_{uuid.uuid4().hex[:16]}"
        logger.info(
            "global_directory_discovery_run run_id=%s status=%s org_id=%s query=%s fixture=%s",
            run_id,
            status,
            org_id,
            query[:120],
            _fixture_enabled(),
        )
        return run_id
