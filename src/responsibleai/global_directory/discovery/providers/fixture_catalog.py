# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import os
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any

from responsibleai.global_directory.discovery.fetch import content_hash
from responsibleai.global_directory.enums import (
    EntityType,
    EvidenceState,
    FreshnessState,
    RelationshipPredicate,
    SourceQualityTier,
)
from responsibleai.global_directory.identifiers import normalize_free_text
from responsibleai.global_directory.models import (
    DirectoryClaim,
    DirectoryEntity,
    DirectoryRelationship,
    DirectorySource,
)

if TYPE_CHECKING:
    from responsibleai.global_directory.person.hints import PersonQueryHints


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _catalog_path() -> Path:
    override = os.environ.get("WHITEPACT_GLOBAL_DIRECTORY_FIXTURE_CATALOG_PATH", "").strip()
    if override:
        return Path(override)
    return Path(__file__).resolve().parents[2] / "fixtures" / "demo_catalog.json"


def _load_catalog() -> dict[str, Any]:
    catalog_path = _catalog_path()
    if not catalog_path.is_file():
        return {"entities": []}
    raw = catalog_path.read_text(encoding="utf-8")
    return json.loads(raw)


class FixtureCatalogProvider:
    """Deterministic catalog for tests only (WHITEPACT_GLOBAL_DIRECTORY_FIXTURE_DISCOVERY=1)."""

    name = "fixture_catalog"

    def discover(self, query: str, hints: PersonQueryHints | None) -> list[dict[str, Any]]:
        return self.match_entities(query, hints)

    def match_entities(self, query: str, hints: PersonQueryHints | None = None) -> list[dict[str, Any]]:
        normalized = normalize_free_text(query)
        if hints and hints.name_tokens:
            normalized = normalize_free_text(" ".join(hints.name_tokens))
        catalog = _load_catalog()
        matches: list[dict[str, Any]] = []
        seen: set[str] = set()
        for entry in catalog.get("entities", []):
            key = str(entry.get("entity_key", ""))
            names = {normalize_free_text(entry.get("canonical_name", ""))}
            names.update(normalize_free_text(a) for a in entry.get("aliases", []))
            matched = normalized in names
            if not matched and hints and hints.name_tokens:
                first = hints.name_tokens[0]
                matched = first in normalize_free_text(entry.get("canonical_name", ""))
            if matched and key not in seen:
                matches.append(entry)
                seen.add(key)
            for ident in entry.get("identifiers", []):
                if ident.get("value", "").casefold() in query.casefold() and key not in seen:
                    matches.append(entry)
                    seen.add(key)
        return matches

    def materialize(self, entry: dict[str, Any]) -> tuple[
        DirectoryEntity,
        list[tuple[str, str]],
        list[str],
        list[DirectorySource],
        list[DirectoryClaim],
        list[DirectoryRelationship],
    ]:
        now = _now()
        entity_id = f"gd_{entry['entity_key']}"
        entity = DirectoryEntity(
            entity_id=entity_id,
            canonical_name=entry["canonical_name"],
            entity_type=EntityType(entry["entity_type"]),
            aliases=entry.get("aliases", []),
            canonical_urls=entry.get("canonical_urls", []),
            description=entry.get("description"),
            confidence=float(entry.get("confidence", 0.5)),
            evidence_state=EvidenceState(entry.get("evidence_state", "UNKNOWN")),
            freshness_state=FreshnessState.FRESH,
            created_at=now,
            first_observed_at=now,
            last_observed_at=now,
            last_verified_at=now,
        )
        identifiers = [(i["type"], i["value"]) for i in entry.get("identifiers", [])]
        aliases = [normalize_free_text(a) for a in entry.get("aliases", [])]
        sources: list[DirectorySource] = []
        claims: list[DirectoryClaim] = []
        relationships: list[DirectoryRelationship] = []
        for src in entry.get("sources", []):
            sid = f"src_{uuid.uuid4().hex[:12]}"
            body = json.dumps(src, sort_keys=True).encode()
            sources.append(
                DirectorySource(
                    source_id=sid,
                    canonical_url=src["canonical_url"],
                    source_type=src.get("source_type", "fixture"),
                    publisher=src.get("publisher"),
                    retrieved_at=now,
                    published_at=src.get("published_at"),
                    content_hash=content_hash(body),
                    quality_tier=SourceQualityTier(src.get("quality_tier", "UNKNOWN_SOURCE")),
                    parser_version="fixture_catalog_v1",
                    retrieval_status="OK",
                )
            )
        for raw_claim in entry.get("claims", []):
            cid = f"clm_{uuid.uuid4().hex[:12]}"
            sid = sources[0].source_id if sources else f"src_{uuid.uuid4().hex[:12]}"
            claims.append(
                DirectoryClaim(
                    claim_id=cid,
                    subject_entity_id=entity_id,
                    predicate=raw_claim["predicate"],
                    object_entity_id=raw_claim.get("object_entity_id"),
                    normalized_value=raw_claim.get("normalized_value"),
                    evidence_state=EvidenceState(raw_claim.get("evidence_state", "INFERRED_SIGNAL")),
                    confidence=float(raw_claim.get("confidence", 0.5)),
                    first_seen_at=now,
                    last_seen_at=now,
                    last_verified_at=now,
                    valid_from=raw_claim.get("valid_from"),
                    valid_until=raw_claim.get("valid_until"),
                    source_refs=[sid],
                )
            )
            object_key = raw_claim.get("object_entity_key")
            if object_key:
                relationships.append(
                    DirectoryRelationship(
                        relationship_id=f"rel_{uuid.uuid4().hex[:12]}",
                        subject_entity_id=entity_id,
                        predicate=RelationshipPredicate(raw_claim["predicate"]),
                        object_entity_id=f"gd_{object_key}",
                        evidence_state=EvidenceState(raw_claim.get("evidence_state", "INFERRED_SIGNAL")),
                        confidence=float(raw_claim.get("confidence", 0.5)),
                        first_seen_at=now,
                        last_seen_at=now,
                        valid_from=raw_claim.get("valid_from"),
                        valid_until=raw_claim.get("valid_until"),
                    )
                )
        return entity, identifiers, aliases, sources, claims, relationships
