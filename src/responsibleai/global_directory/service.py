# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime

from responsibleai.global_directory.discovery.providers.fixture_catalog import FixtureCatalogProvider
from responsibleai.global_directory.enums import EvidenceState
from responsibleai.global_directory.governance_bridge import build_governance_context
from responsibleai.global_directory.identifiers import extract_identifiers, normalize_free_text
from responsibleai.global_directory.models import (
    MachineDirectoryResponse,
    ResolutionCandidate,
    ResolutionResult,
    TrustContext,
)
from responsibleai.global_directory.repository import GlobalDirectoryRepository
from responsibleai.global_directory.synthesis import grounded_summary

logger = logging.getLogger(__name__)


class GlobalDirectoryService:
    def __init__(self, repo: GlobalDirectoryRepository) -> None:
        self._repo = repo
        self._fixture = FixtureCatalogProvider()

    def _fixture_discovery_enabled(self) -> bool:
        return os.environ.get("WHITEPACT_GLOBAL_DIRECTORY_FIXTURE_DISCOVERY", "1").strip().lower() in (
            "1",
            "true",
            "yes",
        )

    async def resolve_entity(self, query: str, *, allow_discovery: bool = True) -> ResolutionResult:
        normalized = normalize_free_text(query)
        parsed_identifiers = extract_identifiers(query)
        for ident in parsed_identifiers:
            entity = await self._repo.find_by_identifier(ident.identifier_type, ident.normalized_value)
            if entity:
                return ResolutionResult(
                    query=query,
                    status="resolved",
                    confidence=entity.confidence,
                    entity=entity,
                )
        candidates_entities = await self._repo.search_by_name(normalized)
        if len(candidates_entities) == 1:
            ent = candidates_entities[0]
            return ResolutionResult(query=query, status="resolved", confidence=ent.confidence, entity=ent)
        if len(candidates_entities) > 1:
            return ResolutionResult(
                query=query,
                status="ambiguous",
                confidence=max(e.confidence for e in candidates_entities),
                candidates=[
                    ResolutionCandidate(entity=e, match_reason="name_or_alias", confidence=e.confidence)
                    for e in candidates_entities
                ],
                message="Multiple entities match; disambiguation required.",
            )
        if allow_discovery and self._fixture_discovery_enabled():
            matches = self._fixture.match_entities(query)
            preferred_types = {i.identifier_type for i in parsed_identifiers}
            exact_identifier_matches = []
            for entry in matches:
                for ident in entry.get("identifiers", []):
                    id_type = str(ident.get("type", ""))
                    value = str(ident.get("value", "")).casefold()
                    if not value or value not in query.casefold():
                        continue
                    if preferred_types and id_type not in preferred_types:
                        continue
                    exact_identifier_matches.append(entry)
                    break
            if len(exact_identifier_matches) == 1:
                matches = exact_identifier_matches
            if len(matches) > 1 and all(m.get("canonical_name") == matches[0].get("canonical_name") for m in matches):
                candidates = []
                for entry in matches:
                    bundle = self._fixture.materialize(entry)
                    candidates.append(
                        ResolutionCandidate(
                            entity=bundle[0],
                            match_reason="fixture_same_name",
                            confidence=bundle[0].confidence,
                        )
                    )
                return ResolutionResult(
                    query=query,
                    status="ambiguous",
                    confidence=max(c.confidence for c in candidates),
                    candidates=candidates,
                    message="Fixture catalog contains ambiguous same-name entities.",
                )
            if len(matches) > 1:
                candidates = []
                for entry in matches:
                    bundle = self._fixture.materialize(entry)
                    candidates.append(
                        ResolutionCandidate(
                            entity=bundle[0],
                            match_reason="fixture_multi_match",
                            confidence=bundle[0].confidence,
                        )
                    )
                return ResolutionResult(
                    query=query,
                    status="ambiguous",
                    confidence=max(c.confidence for c in candidates),
                    candidates=candidates,
                    message="Multiple fixture catalog entities match; disambiguation required.",
                )
            if len(matches) == 1:
                bundle = self._fixture.materialize(matches[0])
                await self._repo.save_entity_bundle(bundle[0], identifiers=bundle[1], aliases=bundle[2], sources=bundle[3], claims=bundle[4], relationships=bundle[5])
                logger.info("global_directory_fixture_discovery entity_id=%s", bundle[0].entity_id)
                return ResolutionResult(
                    query=query,
                    status="resolved",
                    confidence=bundle[0].confidence,
                    entity=bundle[0],
                )
        return ResolutionResult(
            query=query,
            status="not_found",
            confidence=0.0,
            message="No entity matched. LIVE DISCOVERY EXTERNAL DEPENDENCY for non-fixture public sources.",
        )

    async def search_entities(self, query: str, limit: int = 10) -> list[ResolutionCandidate]:
        resolution = await self.resolve_entity(query, allow_discovery=True)
        if resolution.entity:
            return [ResolutionCandidate(entity=resolution.entity, match_reason="resolve", confidence=resolution.confidence)]
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
            "ambiguous": result.status == "ambiguous",
            "candidate_count": len(result.candidates),
            "message": result.message,
        }

    async def record_discovery_run(self, query: str, status: str, org_id: str | None = None) -> str:
        run_id = f"run_{uuid.uuid4().hex[:16]}"
        logger.info(
            "global_directory_discovery_run run_id=%s status=%s org_id=%s query=%s",
            run_id,
            status,
            org_id,
            query[:120],
        )
        return run_id
