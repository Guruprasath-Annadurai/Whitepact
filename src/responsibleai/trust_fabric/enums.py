# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enumerations for WhitePact Global Trust Fabric & Principal Intelligence."""

from __future__ import annotations

from enum import StrEnum


class PrincipalType(StrEnum):
    """Canonical classification of entities in the trust fabric."""

    HUMAN = "HUMAN"
    ORGANIZATION = "ORGANIZATION"
    AI_AGENT = "AI_AGENT"
    WORKLOAD = "WORKLOAD"
    SERVICE = "SERVICE"
    MACHINE = "MACHINE"


class PrincipalState(StrEnum):
    """Lifecycle state of a principal."""

    PENDING_VERIFICATION = "PENDING_VERIFICATION"
    ACTIVE = "ACTIVE"
    SUSPENDED = "SUSPENDED"
    DISABLED = "DISABLED"
    REVOKED = "REVOKED"
    DELETED = "DELETED"
    CONFLICTED = "CONFLICTED"
    UNKNOWN = "UNKNOWN"


class IdentifierType(StrEnum):
    """Types of global normalized identifiers associated with principals."""

    EMAIL = "EMAIL"
    DOMAIN = "DOMAIN"
    PHONE = "PHONE"
    REGISTRATION_NUMBER = "REGISTRATION_NUMBER"
    PUBLIC_KEY = "PUBLIC_KEY"
    CREDENTIAL_ID = "CREDENTIAL_ID"
    AGENT_DEPLOYMENT_ID = "AGENT_DEPLOYMENT_ID"
    EXTERNAL_DIRECTORY_ID = "EXTERNAL_DIRECTORY_ID"


class IdentifierVerificationState(StrEnum):
    """Verification lifecycle of an identifier."""

    UNVERIFIED = "UNVERIFIED"
    VERIFIED = "VERIFIED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class SourceTier(StrEnum):
    """6-Tier Trust Source Hierarchy.

    TIER_A: Cryptographic / Root Proof (Hardware key, DNSSEC, Org trust root)
    TIER_B: Authoritative Legal / Government Registry (Official national registers)
    TIER_C: Organization-Controlled Authoritative Source (Verified enterprise IdP)
    TIER_D: Verified Third-Party Provider (Regulated financial identity provider)
    TIER_E: Public Professional Source (Official public corporate directory)
    TIER_F: Self-Attestation (Unverified subject claims)
    """

    TIER_A = "TIER_A"
    TIER_B = "TIER_B"
    TIER_C = "TIER_C"
    TIER_D = "TIER_D"
    TIER_E = "TIER_E"
    TIER_F = "TIER_F"


class AssuranceLevel(StrEnum):
    """Multi-dimensional confidence level."""

    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRYPTOGRAPHIC = "CRYPTOGRAPHIC"


class DisclosureClass(StrEnum):
    """Field-level privacy and disclosure boundary."""

    PUBLIC = "PUBLIC"
    BUSINESS_PUBLIC = "BUSINESS_PUBLIC"
    TENANT_INTERNAL = "TENANT_INTERNAL"
    SECURITY_RESTRICTED = "SECURITY_RESTRICTED"
    NEVER_PUBLIC = "NEVER_PUBLIC"


class RelationshipType(StrEnum):
    """Directional, typed relationships between principals."""

    EMPLOYED_BY = "EMPLOYED_BY"
    DIRECTOR_OF = "DIRECTOR_OF"
    OPERATED_BY = "OPERATED_BY"
    OWNED_BY = "OWNED_BY"
    CONTRACTOR_FOR = "CONTRACTOR_FOR"
    SUBSIDIARY_OF = "SUBSIDIARY_OF"


class ProofStatus(StrEnum):
    """Valuation outcome for a factual trust proof query."""

    PROVEN = "PROVEN"
    NOT_PROVEN = "NOT_PROVEN"
    CONFLICTED = "CONFLICTED"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    UNKNOWN = "UNKNOWN"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"


class ConflictType(StrEnum):
    """Classification of contradictions detected across sources."""

    VALUE_CONTRADICTION = "VALUE_CONTRADICTION"
    STATUS_CONTRADICTION = "STATUS_CONTRADICTION"
    AUTHORITY_CONTRADICTION = "AUTHORITY_CONTRADICTION"


class ConflictStatus(StrEnum):
    """Status of an identified trust contradiction."""

    UNRESOLVED = "UNRESOLVED"
    RESOLVED_SUPERSEDED = "RESOLVED_SUPERSEDED"
    RESOLVED_MANUAL_REVIEW = "RESOLVED_MANUAL_REVIEW"


class ChallengeType(StrEnum):
    """Cryptographic or control challenge protocol types."""

    DNS_TXT = "DNS_TXT"
    KEY_POSSESSION = "KEY_POSSESSION"
    EMAIL_OTP = "EMAIL_OTP"
    ORG_ASSERTION = "ORG_ASSERTION"


class ChallengeStatus(StrEnum):
    """Status of an issued trust challenge."""

    PENDING = "PENDING"
    COMPLETED = "COMPLETED"
    EXPIRED = "EXPIRED"
    FAILED = "FAILED"


class DecisionOutcome(StrEnum):
    """Gating judgment from the Trust Decision API."""

    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRES_REVIEW = "REQUIRES_REVIEW"
    UNKNOWN = "UNKNOWN"
