# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from responsibleai.global_directory.enums import (
    EntityType,
    EvidenceState,
    FreshnessState,
    RelationshipPredicate,
    SourceQualityTier,
)


class DirectoryEntity(BaseModel):
    entity_id: str
    canonical_name: str
    entity_type: EntityType
    aliases: list[str] = Field(default_factory=list)
    normalized_identifiers: list[dict[str, str]] = Field(default_factory=list)
    canonical_urls: list[str] = Field(default_factory=list)
    description: str | None = None
    confidence: float = 0.0
    evidence_state: EvidenceState = EvidenceState.UNKNOWN
    freshness_state: FreshnessState = FreshnessState.REFRESH_REQUIRED
    created_at: str
    first_observed_at: str | None = None
    last_observed_at: str | None = None
    last_verified_at: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class DirectorySource(BaseModel):
    source_id: str
    canonical_url: str
    source_type: str
    publisher: str | None = None
    retrieved_at: str
    published_at: str | None = None
    content_hash: str
    quality_tier: SourceQualityTier
    parser_version: str
    retrieval_status: str


class DirectoryClaim(BaseModel):
    claim_id: str
    subject_entity_id: str
    predicate: str
    object_entity_id: str | None = None
    normalized_value: str | None = None
    evidence_state: EvidenceState
    confidence: float
    first_seen_at: str
    last_seen_at: str
    last_verified_at: str | None = None
    valid_from: str | None = None
    valid_until: str | None = None
    source_refs: list[str] = Field(default_factory=list)
    supporting_evidence: list[str] = Field(default_factory=list)
    contradicting_evidence: list[str] = Field(default_factory=list)


class DirectoryRelationship(BaseModel):
    relationship_id: str
    subject_entity_id: str
    predicate: RelationshipPredicate
    object_entity_id: str
    evidence_state: EvidenceState
    confidence: float
    first_seen_at: str
    last_seen_at: str
    valid_from: str | None = None
    valid_until: str | None = None


class ResolutionCandidate(BaseModel):
    entity: DirectoryEntity
    match_reason: str
    confidence: float


class ResolutionResult(BaseModel):
    query: str
    status: str
    confidence: float = 0.0
    entity: DirectoryEntity | None = None
    candidates: list[ResolutionCandidate] = Field(default_factory=list)
    message: str | None = None


class TrustContextSignal(BaseModel):
    code: str
    label: str
    evidence_state: EvidenceState
    detail: str | None = None


class TrustContext(BaseModel):
    entity_id: str
    signals: list[TrustContextSignal] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    freshness_state: FreshnessState = FreshnessState.REFRESH_REQUIRED
    note: str = (
        "Structured trust signals derived from evidence. "
        "This is not execution authority."
    )


class MachineDirectoryResponse(BaseModel):
    entity: DirectoryEntity | None = None
    claims: list[DirectoryClaim] = Field(default_factory=list)
    relationships: list[DirectoryRelationship] = Field(default_factory=list)
    conflicts: list[dict[str, Any]] = Field(default_factory=list)
    sources: list[DirectorySource] = Field(default_factory=list)
    trust_context: TrustContext | None = None
    last_verified_at: str | None = None
    summary: str = ""
