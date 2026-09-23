# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Trust Source Provider Abstraction & Query Protocol (Section 13).

Defines the pluggable interface for authoritative external identity and credential
sources (e.g. Statutory Registries, HRIS IdP, Cryptographic Notaries, Sanction Lists).

Core Invariants:
- Distinct failure taxonomy: SOURCE_NOT_FOUND, SOURCE_UNAVAILABLE, SOURCE_UNAUTHORIZED,
  ASSERTION_NOT_VERIFIED, ASSERTION_VERIFIED, ASSERTION_CONFLICTED.
- Fail-closed: Provider outages or authentication failures NEVER cause UNKNOWN -> VERIFIED
  or REVOKED -> VERIFIED.
- Global coverage reality: All authoritative coverage is classified as NOT_ESTABLISHED
  unless an active, verified provider integration is configured.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from responsibleai.trust_fabric.enums import SourceTier


class ProviderQueryResultStatus(StrEnum):
    """Detailed taxonomy for trust source query results."""

    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    SOURCE_UNAVAILABLE = "SOURCE_UNAVAILABLE"
    SOURCE_UNAUTHORIZED = "SOURCE_UNAUTHORIZED"
    ASSERTION_NOT_VERIFIED = "ASSERTION_NOT_VERIFIED"
    ASSERTION_VERIFIED = "ASSERTION_VERIFIED"
    ASSERTION_CONFLICTED = "ASSERTION_CONFLICTED"


@dataclass(frozen=True)
class SourceQueryResult:
    """Result of querying an authoritative trust source provider."""

    status: ProviderQueryResultStatus
    source_id: str
    source_tier: SourceTier
    claim_type: str
    payload: dict[str, Any] = field(default_factory=dict)
    evidence_digest: str | None = None
    error_detail: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    @property
    def is_verified(self) -> bool:
        """True strictly if the assertion was positively verified by the source."""
        return self.status == ProviderQueryResultStatus.ASSERTION_VERIFIED


class TrustSourceProvider(ABC):
    """Abstract interface for an authoritative trust source provider."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Unique identifier for this provider integration."""
        ...

    @property
    @abstractmethod
    def source_tier(self) -> SourceTier:
        """Authoritative tier according to WhitePact 6-tier hierarchy."""
        ...

    @abstractmethod
    async def query_claim(
        self,
        *,
        principal_id: str,
        identifier_value: str,
        claim_type: str,
    ) -> SourceQueryResult:
        """Query the authoritative source for a given claim.

        Must explicitly distinguish SOURCE_NOT_FOUND, SOURCE_UNAVAILABLE,
        SOURCE_UNAUTHORIZED, ASSERTION_NOT_VERIFIED, ASSERTION_VERIFIED,
        and ASSERTION_CONFLICTED.
        """
        ...


class TrustSourceRegistry:
    """Manages active trust source providers with fail-closed query dispatch."""

    def __init__(self) -> None:
        self._providers: dict[str, TrustSourceProvider] = {}

    def register_provider(self, provider: TrustSourceProvider) -> None:
        """Register an active provider instance."""
        self._providers[provider.provider_id] = provider

    def get_provider(self, provider_id: str) -> TrustSourceProvider | None:
        """Get provider by ID."""
        return self._providers.get(provider_id)

    async def query_provider(
        self,
        provider_id: str,
        *,
        principal_id: str,
        identifier_value: str,
        claim_type: str,
    ) -> SourceQueryResult:
        """Query a registered provider with fail-closed error handling."""
        provider = self.get_provider(provider_id)
        if not provider:
            return SourceQueryResult(
                status=ProviderQueryResultStatus.SOURCE_NOT_FOUND,
                source_id=provider_id,
                source_tier=SourceTier.TIER_F,
                claim_type=claim_type,
                error_detail=f"Provider {provider_id!r} is not registered.",
            )

        try:
            result = await provider.query_claim(
                principal_id=principal_id,
                identifier_value=identifier_value,
                claim_type=claim_type,
            )
            # Invariant: Never allow an outage or failure to report VERIFIED
            if result.status not in (
                ProviderQueryResultStatus.ASSERTION_VERIFIED,
                ProviderQueryResultStatus.ASSERTION_NOT_VERIFIED,
                ProviderQueryResultStatus.ASSERTION_CONFLICTED,
                ProviderQueryResultStatus.SOURCE_NOT_FOUND,
                ProviderQueryResultStatus.SOURCE_UNAVAILABLE,
                ProviderQueryResultStatus.SOURCE_UNAUTHORIZED,
            ):
                return SourceQueryResult(
                    status=ProviderQueryResultStatus.SOURCE_UNAVAILABLE,
                    source_id=provider_id,
                    source_tier=provider.source_tier,
                    claim_type=claim_type,
                    error_detail="Unknown provider response status.",
                )
            return result
        except Exception as exc:
            # Outage / network / auth error fails closed to SOURCE_UNAVAILABLE
            return SourceQueryResult(
                status=ProviderQueryResultStatus.SOURCE_UNAVAILABLE,
                source_id=provider_id,
                source_tier=provider.source_tier,
                claim_type=claim_type,
                error_detail=f"Provider raised unexpected error: {exc}",
            )
