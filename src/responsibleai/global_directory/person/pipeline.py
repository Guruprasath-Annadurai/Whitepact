# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""
A name is a query, not an identity.

WhitePact establishes person identity from corroborated public professional evidence.
"""

from __future__ import annotations

import logging

from responsibleai.global_directory.discovery.registry import build_discovery_providers
from responsibleai.global_directory.enums import EntityType, PersonResolutionStatus
from responsibleai.global_directory.identifiers import normalize_free_text
from responsibleai.global_directory.models import (
    DirectoryEntity,
    PersonResolutionPayload,
    ResolutionResult,
)
from responsibleai.global_directory.person.disambiguation import disambiguate_candidates
from responsibleai.global_directory.person.hints import PersonQueryHints, extract_person_hints
from responsibleai.global_directory.person.refinement import RefinementSession, RefinementStore
from responsibleai.global_directory.person.responses import build_person_payload
from responsibleai.global_directory.person.signals import (
    ScoredPersonCandidate,
    build_signals_for_catalog_entry,
)
from responsibleai.global_directory.repository import GlobalDirectoryRepository

logger = logging.getLogger(__name__)

_PRIVACY_BLOCKED_FIELDS = frozenset(
    {
        "home_address",
        "private_email",
        "private_phone",
        "family_members",
        "ssn",
        "financial",
    }
)


class PersonResolutionPipeline:
    def __init__(self, repo: GlobalDirectoryRepository) -> None:
        self._repo = repo
        self._refinements = RefinementStore()
        self._materializer = None

    def _fixture_materializer(self):
        if self._materializer is None:
            from responsibleai.global_directory.discovery.providers.fixture_catalog import (
                FixtureCatalogProvider,
            )

            self._materializer = FixtureCatalogProvider()
        return self._materializer

    @property
    def refinement_store(self) -> RefinementStore:
        return self._refinements

    async def resolve(
        self,
        query: str,
        *,
        allow_discovery: bool = True,
        extra_hints: PersonQueryHints | None = None,
        refinement_session: RefinementSession | None = None,
    ) -> tuple[ResolutionResult, PersonResolutionPayload]:
        hints = extra_hints or extract_person_hints(query)
        local_candidates = await self._local_person_candidates(hints)
        catalog_entries: dict[str, dict] = {}

        if refinement_session and refinement_session.discovery_completed:
            catalog_entries = dict(refinement_session.catalog_entries)
        elif allow_discovery:
            for provider in build_discovery_providers():
                for entry in provider.discover(query, hints):
                    if entry.get("entity_type") != EntityType.PERSON.value:
                        continue
                    key = str(entry.get("entity_key", ""))
                    if key:
                        catalog_entries[key] = entry

        scored = self._score_entries(catalog_entries, hints, local_candidates)

        if refinement_session:
            allowed = set(refinement_session.candidate_keys)
            scored = [c for c in scored if c.entity_key in allowed or c.entity_id in allowed]

        shared_token = None
        if len(hints.name_tokens) == 1 and not hints.organization_hint and not hints.profession_hint:
            shared_token = hints.name_tokens[0]
        outcome = disambiguate_candidates(scored, shared_name_token=shared_token)
        session = refinement_session
        if outcome.resolution == PersonResolutionStatus.AMBIGUOUS and session is None:
            session = self._refinements.create(query)
            session.candidate_keys = [c.entity_key for c in outcome.ordered[:10]]
            session.catalog_entries = catalog_entries
            session.scored = outcome.ordered
            session.discovery_completed = True

        entity: DirectoryEntity | None = None
        claims = []
        relationships = []
        sources = []

        if outcome.resolution == PersonResolutionStatus.RESOLVED and outcome.ordered:
            top = outcome.ordered[0]
            entry = catalog_entries.get(top.entity_key)
            if entry:
                bundle = self._fixture_materializer().materialize(entry)
                entity = bundle[0]
                await self._repo.save_entity_bundle(
                    bundle[0],
                    identifiers=bundle[1],
                    aliases=bundle[2],
                    sources=bundle[3],
                    claims=bundle[4],
                    relationships=bundle[5],
                )
                claims, relationships, sources = bundle[4], bundle[5], bundle[3]
            elif local_candidates:
                entity = local_candidates[0]
                claims = await self._repo.list_claims(entity.entity_id)
                relationships = await self._repo.list_relationships(entity.entity_id)
                sources = await self._repo.list_sources_for_entity(entity.entity_id)

        person_payload = build_person_payload(
            resolution=outcome.resolution,
            query=query,
            hints_display=hints.display_name,
            entity=entity,
            claims=claims,
            relationships=relationships,
            sources=sources,
            candidates=outcome.ordered,
            reason=outcome.reason,
            refinement_token=session.session_id if session else None,
        )
        self._strip_private_fields(person_payload)

        resolution = ResolutionResult(
            query=query,
            status=outcome.resolution.value,
            confidence=outcome.ordered[0].score if outcome.ordered else 0.0,
            entity=entity,
            candidates=[],
            message=outcome.reason,
            person=person_payload,
        )
        return resolution, person_payload

    async def refine(
        self,
        refinement_token: str,
        *,
        organization_hint: str | None = None,
        profession_hint: str | None = None,
    ) -> tuple[ResolutionResult, PersonResolutionPayload]:
        session = self._refinements.get(refinement_token)
        if not session:
            payload = build_person_payload(
                resolution=PersonResolutionStatus.UNKNOWN,
                query="",
                hints_display="",
                entity=None,
                claims=[],
                relationships=[],
                sources=[],
                candidates=[],
                reason="Unknown refinement session",
            )
            return (
                ResolutionResult(
                    query="",
                    status=PersonResolutionStatus.UNKNOWN.value,
                    confidence=0.0,
                    message="Unknown refinement session",
                    person=payload,
                ),
                payload,
            )

        hints = extract_person_hints(session.query)
        if organization_hint:
            hints.organization_hint = organization_hint
        if profession_hint:
            hints.profession_hint = profession_hint

        return await self.resolve(
            session.query,
            allow_discovery=False,
            extra_hints=hints,
            refinement_session=session,
        )

    async def _local_person_candidates(self, hints: PersonQueryHints) -> list[DirectoryEntity]:
        name = normalize_free_text(" ".join(hints.name_tokens)) if hints.name_tokens else hints.normalized_query
        entities = await self._repo.search_by_name(name, limit=20)
        return [e for e in entities if e.entity_type == EntityType.PERSON]

    def _score_entries(
        self,
        catalog_entries: dict[str, dict],
        hints: PersonQueryHints,
        local_entities: list[DirectoryEntity],
    ) -> list[ScoredPersonCandidate]:
        scored: list[ScoredPersonCandidate] = []
        for key, entry in catalog_entries.items():
            signals = build_signals_for_catalog_entry(entry, hints)
            if not signals and hints.name_tokens:
                continue
            ctx = entry.get("description") or entry.get("professional_context") or ""
            scored.append(
                ScoredPersonCandidate(
                    entity_key=key,
                    entity_id=f"gd_{key}",
                    canonical_name=entry.get("canonical_name", ""),
                    professional_context=str(ctx),
                    signals=signals,
                )
            )
        for ent in local_entities:
            if any(c.entity_id == ent.entity_id for c in scored):
                continue
            scored.append(
                ScoredPersonCandidate(
                    entity_key=ent.entity_id.removeprefix("gd_"),
                    entity_id=ent.entity_id,
                    canonical_name=ent.canonical_name,
                    professional_context=ent.description or "",
                    signals=[],
                )
            )
        return scored

    def _strip_private_fields(self, payload: PersonResolutionPayload) -> None:
        data = payload.model_dump()
        for key in list(data.keys()):
            if key in _PRIVACY_BLOCKED_FIELDS:
                data.pop(key, None)
        # model is frozen-ish via pydantic — payload object already excludes these keys at build time
