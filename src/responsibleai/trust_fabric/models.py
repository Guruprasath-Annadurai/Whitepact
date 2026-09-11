# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Data models for WhitePact Global Trust Fabric & Principal Intelligence."""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from responsibleai.trust_fabric.enums import (
    AssuranceLevel,
    ChallengeStatus,
    ChallengeType,
    ConflictStatus,
    ConflictType,
    DecisionOutcome,
    DisclosureClass,
    IdentifierType,
    IdentifierVerificationState,
    PrincipalState,
    PrincipalType,
    RelationshipType,
    SourceTier,
)


def _canonical_json(payload: dict[str, Any]) -> str:
    """Deterministic canonical JSON serialization for cryptographic integrity."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_digest(payload: dict[str, Any]) -> str:
    """Compute SHA-256 digest of canonical JSON payload."""
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Principal:
    """Canonical entity in the Global Trust Fabric."""

    id: str
    org_id: str
    principal_type: PrincipalType
    display_name: str
    lifecycle_state: PrincipalState = PrincipalState.PENDING_VERIFICATION
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    metadata: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def create(
        cls,
        org_id: str,
        principal_type: PrincipalType,
        display_name: str,
        lifecycle_state: PrincipalState = PrincipalState.PENDING_VERIFICATION,
        metadata: dict[str, Any] | None = None,
    ) -> Principal:
        pid = f"wp_prin_{uuid.uuid4().hex}"
        now = datetime.now(UTC).isoformat()
        return cls(
            id=pid,
            org_id=org_id,
            principal_type=principal_type,
            display_name=display_name,
            lifecycle_state=lifecycle_state,
            created_at=now,
            updated_at=now,
            metadata=metadata or {},
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "principal_type": self.principal_type.value,
            "display_name": self.display_name,
            "lifecycle_state": self.lifecycle_state.value,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "metadata": self.metadata,
        }


@dataclass(frozen=True)
class PrincipalIdentifier:
    """Normalized, verifiable identifier bound to a principal."""

    id: str
    principal_id: str
    org_id: str
    identifier_type: IdentifierType
    raw_value: str
    normalized_value: str
    is_primary: bool = False
    verification_state: IdentifierVerificationState = IdentifierVerificationState.UNVERIFIED
    verified_at: str | None = None
    expires_at: str | None = None
    revoked_at: str | None = None
    source_id: str | None = None
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "principal_id": self.principal_id,
            "org_id": self.org_id,
            "identifier_type": self.identifier_type.value,
            "raw_value": self.raw_value,
            "normalized_value": self.normalized_value,
            "is_primary": self.is_primary,
            "verification_state": self.verification_state.value,
            "verified_at": self.verified_at,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "source_id": self.source_id,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class TrustSource:
    """Registered source of trust evidence."""

    id: str
    name: str
    source_tier: SourceTier
    provider_type: str
    endpoint_or_uri: str | None = None
    org_id: str | None = None
    is_active: bool = True
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "source_tier": self.source_tier.value,
            "provider_type": self.provider_type,
            "endpoint_or_uri": self.endpoint_or_uri,
            "org_id": self.org_id,
            "is_active": self.is_active,
            "created_at": self.created_at,
        }


@dataclass(frozen=True)
class FieldProvenance:
    """Field-level verified assertion with full provenance tracking."""

    id: str
    principal_id: str
    org_id: str
    field_name: str
    field_value: str
    source_id: str
    source_tier: SourceTier
    verification_method: str
    assurance_level: AssuranceLevel
    disclosure_class: DisclosureClass
    verified_at: str
    last_checked_at: str
    evidence_digest: str
    expires_at: str | None = None
    revoked_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "principal_id": self.principal_id,
            "org_id": self.org_id,
            "field_name": self.field_name,
            "field_value": self.field_value,
            "source_id": self.source_id,
            "source_tier": self.source_tier.value,
            "verification_method": self.verification_method,
            "assurance_level": self.assurance_level.value,
            "disclosure_class": self.disclosure_class.value,
            "verified_at": self.verified_at,
            "last_checked_at": self.last_checked_at,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "evidence_digest": self.evidence_digest,
        }


@dataclass(frozen=True)
class PrincipalRelationship:
    """Directional relationship between two principals within an organization."""

    id: str
    subject_principal_id: str
    target_principal_id: str
    org_id: str
    relationship_type: RelationshipType
    role_title: str | None
    valid_from: str
    source_id: str
    verification_state: IdentifierVerificationState = IdentifierVerificationState.UNVERIFIED
    expires_at: str | None = None
    revoked_at: str | None = None

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        if self.expires_at is not None:
            return datetime.now(UTC).isoformat() < self.expires_at
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject_principal_id": self.subject_principal_id,
            "target_principal_id": self.target_principal_id,
            "org_id": self.org_id,
            "relationship_type": self.relationship_type.value,
            "role_title": self.role_title,
            "verification_state": self.verification_state.value,
            "valid_from": self.valid_from,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "source_id": self.source_id,
            "is_active": self.is_active,
        }


@dataclass(frozen=True)
class AuthorityEdge:
    """Explicit grant of bounded authority from a grantor to a grantee."""

    id: str
    grantor_principal_id: str
    grantee_principal_id: str
    org_id: str
    action_type: str
    resource_pattern: str
    valid_from: str
    canonical_digest: str
    ceiling_limit_usd: float | None = None
    currency: str = "USD"
    delegation_depth: int = 0
    expires_at: str | None = None
    revoked_at: str | None = None
    revoked_by: str | None = None

    @property
    def is_active(self) -> bool:
        if self.revoked_at is not None:
            return False
        now_iso = datetime.now(UTC).isoformat()
        if self.valid_from > now_iso:
            return False
        if self.expires_at is not None and self.expires_at <= now_iso:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "grantor_principal_id": self.grantor_principal_id,
            "grantee_principal_id": self.grantee_principal_id,
            "org_id": self.org_id,
            "action_type": self.action_type,
            "resource_pattern": self.resource_pattern,
            "ceiling_limit_usd": self.ceiling_limit_usd,
            "currency": self.currency,
            "delegation_depth": self.delegation_depth,
            "valid_from": self.valid_from,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "is_active": self.is_active,
            "canonical_digest": self.canonical_digest,
        }


@dataclass(frozen=True)
class OrganizationTrustRoot:
    """Cryptographic anchor representing customer organizational sovereignty."""

    id: str
    org_id: str
    root_principal_id: str
    root_public_key: str
    established_at: str
    canonical_digest: str
    key_algorithm: str = "Ed25519"
    status: str = "ACTIVE"

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "root_principal_id": self.root_principal_id,
            "root_public_key": self.root_public_key,
            "key_algorithm": self.key_algorithm,
            "established_at": self.established_at,
            "status": self.status,
            "canonical_digest": self.canonical_digest,
        }


@dataclass(frozen=True)
class BootstrapRecord:
    """Ephemeral record for atomic single-winner trust bootstrap ceremony."""

    id: str
    org_id: str
    token_hash: str
    expires_at: str
    nonce: str
    created_at: str
    consumed_at: str | None = None
    claimed_by_principal_id: str | None = None

    @property
    def is_consumed(self) -> bool:
        return self.consumed_at is not None

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC).isoformat() >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "expires_at": self.expires_at,
            "nonce": self.nonce,
            "consumed_at": self.consumed_at,
            "claimed_by_principal_id": self.claimed_by_principal_id,
            "is_consumed": self.is_consumed,
            "is_expired": self.is_expired,
        }


@dataclass(frozen=True)
class AssuranceVector:
    """Multi-dimensional confidence vector."""

    identity_assurance: AssuranceLevel
    affiliation_assurance: AssuranceLevel
    authority_assurance: AssuranceLevel
    source_freshness: str  # "CURRENT", "STALE", "EXPIRED"
    credential_state: str  # "VALID", "REVOKED", "EXPIRED", "UNKNOWN"
    conflict_state: str  # "NONE", "CONFLICTED"

    def to_dict(self) -> dict[str, str]:
        return {
            "identity_assurance": self.identity_assurance.value,
            "affiliation_assurance": self.affiliation_assurance.value,
            "authority_assurance": self.authority_assurance.value,
            "source_freshness": self.source_freshness,
            "credential_state": self.credential_state,
            "conflict_state": self.conflict_state,
        }


@dataclass(frozen=True)
class TrustPassport:
    """Verifiable, tamper-evident cryptographic passport for a principal."""

    id: str
    principal_id: str
    org_id: str
    passport_type: PrincipalType
    claims: dict[str, Any]
    assurance: AssuranceVector
    generated_at: str
    expires_at: str
    verification_hash: str
    version: str = "3.0"
    signature: str | None = None
    signing_key_id: str | None = None
    revoked_at: str | None = None

    @property
    def is_valid(self) -> bool:
        if self.revoked_at is not None:
            return False
        return datetime.now(UTC).isoformat() < self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "version": self.version,
            "principal_id": self.principal_id,
            "org_id": self.org_id,
            "passport_type": self.passport_type.value,
            "claims": self.claims,
            "assurance": self.assurance.to_dict(),
            "generated_at": self.generated_at,
            "expires_at": self.expires_at,
            "verification_hash": self.verification_hash,
            "signature": self.signature,
            "signing_key_id": self.signing_key_id,
            "revoked_at": self.revoked_at,
            "is_valid": self.is_valid,
        }


@dataclass(frozen=True)
class TrustConflict:
    """Record of a contradiction detected between independent sources."""

    id: str
    principal_id: str
    org_id: str
    field_or_claim: str
    assertion_id_a: str
    assertion_id_b: str
    conflict_type: ConflictType
    detected_at: str
    status: ConflictStatus = ConflictStatus.UNRESOLVED
    resolution_reason: str | None = None
    resolved_at: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "principal_id": self.principal_id,
            "org_id": self.org_id,
            "field_or_claim": self.field_or_claim,
            "assertion_id_a": self.assertion_id_a,
            "assertion_id_b": self.assertion_id_b,
            "conflict_type": self.conflict_type.value,
            "detected_at": self.detected_at,
            "status": self.status.value,
            "resolution_reason": self.resolution_reason,
            "resolved_at": self.resolved_at,
        }


@dataclass(frozen=True)
class TrustChallenge:
    """Cryptographic or control challenge issued to verify an unknown or pending claim."""

    id: str
    org_id: str
    challenge_type: ChallengeType
    target_identifier: str
    nonce: str
    expected_response_hash: str
    issued_at: str
    expires_at: str
    principal_id: str | None = None
    status: ChallengeStatus = ChallengeStatus.PENDING
    completed_at: str | None = None

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC).isoformat() >= self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "org_id": self.org_id,
            "principal_id": self.principal_id,
            "challenge_type": self.challenge_type.value,
            "target_identifier": self.target_identifier,
            "nonce": self.nonce,
            "status": self.status.value,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "completed_at": self.completed_at,
            "is_expired": self.is_expired,
        }


@dataclass(frozen=True)
class FederatedAssertion:
    """Signed cross-organizational trust assertion."""

    id: str
    issuer_org_id: str
    audience_org_id: str
    subject_principal_id: str
    claim_type: str
    claim_payload: dict[str, Any]
    nonce: str
    signature: str
    key_id: str
    issued_at: str
    expires_at: str
    revoked_at: str | None = None

    @property
    def is_valid(self) -> bool:
        if self.revoked_at is not None:
            return False
        return datetime.now(UTC).isoformat() < self.expires_at

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "issuer_org_id": self.issuer_org_id,
            "audience_org_id": self.audience_org_id,
            "subject_principal_id": self.subject_principal_id,
            "claim_type": self.claim_type,
            "claim_payload": self.claim_payload,
            "nonce": self.nonce,
            "signature": self.signature,
            "key_id": self.key_id,
            "issued_at": self.issued_at,
            "expires_at": self.expires_at,
            "revoked_at": self.revoked_at,
            "is_valid": self.is_valid,
        }


@dataclass(frozen=True)
class TrustDecisionRequest:
    """Request to the Trust Decision API."""

    requesting_org_id: str
    subject_principal_id: str
    target_org_id: str
    requested_action: str
    context: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class TrustDecisionResponse:
    """Structured response from the Trust Decision API."""

    decision: DecisionOutcome
    reason_code: str
    explanation: str
    assurance: AssuranceVector
    evidence_references: tuple[str, ...] = ()
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "reason_code": self.reason_code,
            "explanation": self.explanation,
            "assurance": self.assurance.to_dict(),
            "evidence_references": list(self.evidence_references),
            "timestamp": self.timestamp,
        }
