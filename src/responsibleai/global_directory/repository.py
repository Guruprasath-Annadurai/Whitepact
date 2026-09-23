# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select

from responsibleai.db.engine import (
    DatabaseEngine,
    global_directory_aliases,
    global_directory_claims,
    global_directory_entities,
    global_directory_identifiers,
    global_directory_relationships,
    global_directory_sources,
)
from responsibleai.global_directory.enums import (
    DataScope,
    EntityType,
    EvidenceState,
    FreshnessState,
)
from responsibleai.global_directory.models import (
    DirectoryClaim,
    DirectoryEntity,
    DirectoryRelationship,
    DirectorySource,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _entity_from_row(row: Any, aliases: list[str]) -> DirectoryEntity:
    return DirectoryEntity(
        entity_id=row.entity_id,
        canonical_name=row.canonical_name,
        entity_type=EntityType(row.entity_type),
        aliases=aliases,
        canonical_urls=json.loads(row.canonical_urls_json or "[]"),
        description=row.description,
        confidence=float(row.confidence or 0),
        evidence_state=EvidenceState(row.evidence_state),
        freshness_state=FreshnessState(row.freshness_state),
        created_at=row.created_at,
        first_observed_at=row.first_observed_at,
        last_observed_at=row.last_observed_at,
        last_verified_at=row.last_verified_at,
        metadata=json.loads(row.metadata_json or "{}"),
    )


class GlobalDirectoryRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def save_entity_bundle(
        self,
        entity: DirectoryEntity,
        *,
        identifiers: list[tuple[str, str]],
        aliases: list[str],
        sources: list[DirectorySource],
        claims: list[DirectoryClaim],
        relationships: list[DirectoryRelationship],
    ) -> None:
        now = _now()
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                global_directory_entities.delete().where(
                    global_directory_entities.c.entity_id == entity.entity_id
                )
            )
            await conn.execute(
                global_directory_entities.insert().values(
                    entity_id=entity.entity_id,
                    entity_type=entity.entity_type.value,
                    canonical_name=entity.canonical_name,
                    description=entity.description,
                    canonical_urls_json=json.dumps(entity.canonical_urls),
                    confidence=entity.confidence,
                    evidence_state=entity.evidence_state.value,
                    freshness_state=entity.freshness_state.value,
                    data_scope=DataScope.GLOBAL_PUBLIC_EVIDENCE.value,
                    metadata_json=json.dumps(entity.metadata),
                    created_at=entity.created_at or now,
                    first_observed_at=entity.first_observed_at or now,
                    last_observed_at=entity.last_observed_at or now,
                    last_verified_at=entity.last_verified_at,
                )
            )
            await conn.execute(
                global_directory_aliases.delete().where(
                    global_directory_aliases.c.entity_id == entity.entity_id
                )
            )
            for alias in aliases:
                await conn.execute(
                    global_directory_aliases.insert().values(
                        alias_id=f"alias_{uuid.uuid4().hex[:16]}",
                        entity_id=entity.entity_id,
                        alias_normalized=alias,
                    )
                )
            await conn.execute(
                global_directory_identifiers.delete().where(
                    global_directory_identifiers.c.entity_id == entity.entity_id
                )
            )
            for id_type, value in identifiers:
                await conn.execute(
                    global_directory_identifiers.insert().values(
                        identifier_id=f"id_{uuid.uuid4().hex[:16]}",
                        entity_id=entity.entity_id,
                        identifier_type=id_type,
                        normalized_value=value,
                    )
                )
            for source in sources:
                await conn.execute(
                    global_directory_sources.insert().values(
                        source_id=source.source_id,
                        canonical_url=source.canonical_url,
                        source_type=source.source_type,
                        publisher=source.publisher,
                        retrieved_at=source.retrieved_at,
                        published_at=source.published_at,
                        content_hash=source.content_hash,
                        quality_tier=source.quality_tier.value,
                        parser_version=source.parser_version,
                        retrieval_status=source.retrieval_status,
                    )
                )
            await conn.execute(
                global_directory_claims.delete().where(
                    global_directory_claims.c.subject_entity_id == entity.entity_id
                )
            )
            for claim in claims:
                await conn.execute(
                    global_directory_claims.insert().values(
                        claim_id=claim.claim_id,
                        subject_entity_id=claim.subject_entity_id,
                        predicate=claim.predicate,
                        object_entity_id=claim.object_entity_id,
                        normalized_value=claim.normalized_value,
                        evidence_state=claim.evidence_state.value,
                        confidence=claim.confidence,
                        first_seen_at=claim.first_seen_at,
                        last_seen_at=claim.last_seen_at,
                        last_verified_at=claim.last_verified_at,
                        valid_from=claim.valid_from,
                        valid_until=claim.valid_until,
                        source_refs_json=json.dumps(claim.source_refs),
                    )
                )
            await conn.execute(
                global_directory_relationships.delete().where(
                    global_directory_relationships.c.subject_entity_id == entity.entity_id
                )
            )
            for rel in relationships:
                await conn.execute(
                    global_directory_relationships.insert().values(
                        relationship_id=rel.relationship_id,
                        subject_entity_id=rel.subject_entity_id,
                        predicate=rel.predicate.value,
                        object_entity_id=rel.object_entity_id,
                        evidence_state=rel.evidence_state.value,
                        confidence=rel.confidence,
                        first_seen_at=rel.first_seen_at,
                        last_seen_at=rel.last_seen_at,
                        valid_from=rel.valid_from,
                        valid_until=rel.valid_until,
                    )
                )

    async def get_entity(self, entity_id: str) -> DirectoryEntity | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(global_directory_entities).where(
                        global_directory_entities.c.entity_id == entity_id
                    )
                )
            ).first()
            if not row:
                return None
            aliases = [
                r.alias_normalized
                for r in (
                    await conn.execute(
                        select(global_directory_aliases).where(
                            global_directory_aliases.c.entity_id == entity_id
                        )
                    )
                ).fetchall()
            ]
            return _entity_from_row(row, aliases)

    async def find_by_identifier(self, id_type: str, value: str) -> DirectoryEntity | None:
        async with self._engine.raw.connect() as conn:
            ident = (
                await conn.execute(
                    select(global_directory_identifiers).where(
                        global_directory_identifiers.c.identifier_type == id_type,
                        global_directory_identifiers.c.normalized_value == value,
                    )
                )
            ).first()
            if not ident:
                return None
            return await self.get_entity(ident.entity_id)

    async def search_by_name(self, normalized_name: str, limit: int = 10) -> list[DirectoryEntity]:
        async with self._engine.raw.connect() as conn:
            entity_rows = (
                await conn.execute(
                    select(global_directory_entities).where(
                        global_directory_entities.c.canonical_name.ilike(f"%{normalized_name}%")
                    ).limit(limit)
                )
            ).fetchall()
            alias_rows = (
                await conn.execute(
                    select(global_directory_aliases).where(
                        global_directory_aliases.c.alias_normalized == normalized_name
                    ).limit(limit)
                )
            ).fetchall()
            entity_ids = {r.entity_id for r in entity_rows} | {r.entity_id for r in alias_rows}
            results: list[DirectoryEntity] = []
            for eid in entity_ids:
                entity = await self.get_entity(eid)
                if entity:
                    results.append(entity)
            return results

    async def list_claims(self, entity_id: str) -> list[DirectoryClaim]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(global_directory_claims).where(
                        global_directory_claims.c.subject_entity_id == entity_id
                    )
                )
            ).fetchall()
            return [
                DirectoryClaim(
                    claim_id=r.claim_id,
                    subject_entity_id=r.subject_entity_id,
                    predicate=r.predicate,
                    object_entity_id=r.object_entity_id,
                    normalized_value=r.normalized_value,
                    evidence_state=EvidenceState(r.evidence_state),
                    confidence=float(r.confidence),
                    first_seen_at=r.first_seen_at,
                    last_seen_at=r.last_seen_at,
                    last_verified_at=r.last_verified_at,
                    valid_from=r.valid_from,
                    valid_until=r.valid_until,
                    source_refs=json.loads(r.source_refs_json or "[]"),
                )
                for r in rows
            ]

    async def list_relationships(self, entity_id: str) -> list[DirectoryRelationship]:
        from responsibleai.global_directory.enums import RelationshipPredicate

        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(global_directory_relationships).where(
                        global_directory_relationships.c.subject_entity_id == entity_id
                    )
                )
            ).fetchall()
            return [
                DirectoryRelationship(
                    relationship_id=r.relationship_id,
                    subject_entity_id=r.subject_entity_id,
                    predicate=RelationshipPredicate(r.predicate),
                    object_entity_id=r.object_entity_id,
                    evidence_state=EvidenceState(r.evidence_state),
                    confidence=float(r.confidence),
                    first_seen_at=r.first_seen_at,
                    last_seen_at=r.last_seen_at,
                    valid_from=r.valid_from,
                    valid_until=r.valid_until,
                )
                for r in rows
            ]

    async def list_sources_for_entity(self, entity_id: str) -> list[DirectorySource]:
        from responsibleai.global_directory.enums import SourceQualityTier

        claims = await self.list_claims(entity_id)
        source_ids = {sid for c in claims for sid in c.source_refs}
        if not source_ids:
            return []
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(global_directory_sources).where(
                        global_directory_sources.c.source_id.in_(source_ids)
                    )
                )
            ).fetchall()
            return [
                DirectorySource(
                    source_id=r.source_id,
                    canonical_url=r.canonical_url,
                    source_type=r.source_type,
                    publisher=r.publisher,
                    retrieved_at=r.retrieved_at,
                    published_at=r.published_at,
                    content_hash=r.content_hash,
                    quality_tier=SourceQualityTier(r.quality_tier),
                    parser_version=r.parser_version,
                    retrieval_status=r.retrieval_status,
                )
                for r in rows
            ]
