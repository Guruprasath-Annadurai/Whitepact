# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Continuous Trust Monitor & Freshness Tracking.

Core Invariants:
- Trust is temporal: verified assertions degrade over time without re-verification.
- Revocation cascade: revoking a credential or ending an employment relationship
  immediately invalidates current trust decisions.
- Cache discipline: Cached trust states expire with source TTL. If caching or
  Redis fails, evaluation fails closed to the canonical database.
- A stale cache entry NEVER widens authority or causes an invalid ALLOW.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import and_, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    organizations,
    trust_fabric_authority_edges,
    trust_fabric_identifiers,
    trust_fabric_passports,
    trust_fabric_principals,
    trust_fabric_relationships,
)
from responsibleai.trust_fabric.enums import (
    IdentifierVerificationState,
    PrincipalState,
)


class ContinuousTrustMonitor:
    """Monitors freshness, handles revocation cascades, and enforces cache discipline."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db
        self._local_cache: dict[str, tuple[Any, datetime]] = {}
        self._cache_failing: bool = False

    def invalidate_cache(self) -> None:
        """Clear all cached trust decisions immediately upon any revocation event."""
        self._local_cache.clear()

    def simulate_cache_failure(self, failing: bool = True) -> None:
        """Simulate Redis / external cache service failure for testing fail-closed behavior."""
        self._cache_failing = failing

    async def revoke_credential(
        self,
        identifier_id: str,
        *,
        org_id: str,
    ) -> None:
        """Revoke an identifier credential and invalidate associated cached trust."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_identifiers)
                .where(
                    and_(
                        trust_fabric_identifiers.c.id == identifier_id,
                        trust_fabric_identifiers.c.org_id == org_id,
                    )
                )
                .values(
                    revoked_at=now_iso,
                    verification_state=IdentifierVerificationState.REVOKED.value,
                )
            )
            # Cascade: invalidate active passports for this principal
            ident_stmt = select(trust_fabric_identifiers).where(
                trust_fabric_identifiers.c.id == identifier_id
            )
            row = (await conn.execute(ident_stmt)).first()
            if row:
                principal_id = row._mapping["principal_id"]
                await conn.execute(
                    update(trust_fabric_passports)
                    .where(
                        and_(
                            trust_fabric_passports.c.principal_id == principal_id,
                            trust_fabric_passports.c.org_id == org_id,
                            trust_fabric_passports.c.revoked_at.is_(None),
                        )
                    )
                    .values(revoked_at=now_iso)
                )

        self.invalidate_cache()

    async def terminate_relationship(
        self,
        relationship_id: str,
        *,
        org_id: str,
    ) -> None:
        """Terminate an employment or affiliation relationship and revoke delegated authority."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            # 1. Revoke relationship
            rel_stmt = select(trust_fabric_relationships).where(
                and_(
                    trust_fabric_relationships.c.id == relationship_id,
                    trust_fabric_relationships.c.org_id == org_id,
                )
            )
            rel_row = (await conn.execute(rel_stmt)).first()
            if not rel_row:
                return

            rel = dict(rel_row._mapping)
            await conn.execute(
                update(trust_fabric_relationships)
                .where(trust_fabric_relationships.c.id == relationship_id)
                .values(
                    revoked_at=now_iso,
                    verification_state=IdentifierVerificationState.REVOKED.value,
                )
            )

            # 2. Cascade: Revoke all authority edges granted to this subject principal
            await conn.execute(
                update(trust_fabric_authority_edges)
                .where(
                    and_(
                        trust_fabric_authority_edges.c.grantee_principal_id == rel["subject_principal_id"],
                        trust_fabric_authority_edges.c.org_id == org_id,
                        trust_fabric_authority_edges.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by="SYSTEM_RELATIONSHIP_TERMINATION",
                )
            )

        self.invalidate_cache()

    async def revoke_authority(
        self,
        authority_id: str,
        *,
        org_id: str,
        revoked_by: str = "MANUAL_REVOCATION",
    ) -> None:
        """Revoke a specific delegated authority edge and invalidate cache."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_authority_edges)
                .where(
                    and_(
                        trust_fabric_authority_edges.c.id == authority_id,
                        trust_fabric_authority_edges.c.org_id == org_id,
                        trust_fabric_authority_edges.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by=revoked_by,
                )
            )
        self.invalidate_cache()

    async def expire_authority(
        self,
        authority_id: str,
        *,
        org_id: str,
    ) -> None:
        """Mark an authority edge as expired in the past and invalidate cache."""
        past_iso = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
        async with self.db.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_authority_edges)
                .where(
                    and_(
                        trust_fabric_authority_edges.c.id == authority_id,
                        trust_fabric_authority_edges.c.org_id == org_id,
                    )
                )
                .values(expires_at=past_iso)
            )
        self.invalidate_cache()

    async def dissolve_organization(
        self,
        org_id: str,
    ) -> None:
        """Dissolve/deactivate an organization and cascade revocation to all principals, relationships, and authority."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            # 1. Update organization status
            await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(subscription_status="dissolved")
            )

            # 2. Suspend all principals in the organization
            await conn.execute(
                update(trust_fabric_principals)
                .where(trust_fabric_principals.c.org_id == org_id)
                .values(
                    lifecycle_state=PrincipalState.DISABLED.value,
                    updated_at=now_iso,
                )
            )

            # 3. Revoke all active relationships
            await conn.execute(
                update(trust_fabric_relationships)
                .where(
                    and_(
                        trust_fabric_relationships.c.org_id == org_id,
                        trust_fabric_relationships.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    verification_state=IdentifierVerificationState.REVOKED.value,
                )
            )

            # 4. Revoke all authority edges
            await conn.execute(
                update(trust_fabric_authority_edges)
                .where(
                    and_(
                        trust_fabric_authority_edges.c.org_id == org_id,
                        trust_fabric_authority_edges.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by="SYSTEM_ORGANIZATION_DISSOLVED",
                )
            )

            # 5. Revoke all passports
            await conn.execute(
                update(trust_fabric_passports)
                .where(
                    and_(
                        trust_fabric_passports.c.org_id == org_id,
                        trust_fabric_passports.c.revoked_at.is_(None),
                    )
                )
                .values(revoked_at=now_iso)
            )

        self.invalidate_cache()

    async def reassign_agent_ownership(
        self,
        agent_principal_id: str,
        new_owner_principal_id: str,
        *,
        org_id: str,
    ) -> None:
        """Reassign agent ownership from owner A to owner B and revoke owner A's edges."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            # Find and revoke existing ownership relationships
            await conn.execute(
                update(trust_fabric_relationships)
                .where(
                    and_(
                        trust_fabric_relationships.c.org_id == org_id,
                        trust_fabric_relationships.c.subject_principal_id == agent_principal_id,
                        trust_fabric_relationships.c.relationship_type == "AGENT_OWNER",
                        trust_fabric_relationships.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    verification_state=IdentifierVerificationState.REVOKED.value,
                )
            )

            # Revoke all authority edges where grantor was old owner or grantee is agent under old context
            await conn.execute(
                update(trust_fabric_authority_edges)
                .where(
                    and_(
                        trust_fabric_authority_edges.c.org_id == org_id,
                        trust_fabric_authority_edges.c.grantee_principal_id == agent_principal_id,
                        trust_fabric_authority_edges.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by="SYSTEM_AGENT_OWNER_REASSIGNED",
                )
            )

        self.invalidate_cache()

    async def suspend_principal(
        self,
        principal_id: str,
        *,
        org_id: str,
    ) -> None:
        """Suspend an active principal and revoke all active passports and authorities."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_principals)
                .where(
                    and_(
                        trust_fabric_principals.c.id == principal_id,
                        trust_fabric_principals.c.org_id == org_id,
                    )
                )
                .values(
                    lifecycle_state=PrincipalState.DISABLED.value,
                    updated_at=now_iso,
                )
            )

            # Revoke active passports
            await conn.execute(
                update(trust_fabric_passports)
                .where(
                    and_(
                        trust_fabric_passports.c.principal_id == principal_id,
                        trust_fabric_passports.c.org_id == org_id,
                        trust_fabric_passports.c.revoked_at.is_(None),
                    )
                )
                .values(revoked_at=now_iso)
            )

            # Revoke active authority edges
            await conn.execute(
                update(trust_fabric_authority_edges)
                .where(
                    and_(
                        trust_fabric_authority_edges.c.org_id == org_id,
                        trust_fabric_authority_edges.c.grantee_principal_id == principal_id,
                        trust_fabric_authority_edges.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    revoked_by="SYSTEM_PRINCIPAL_SUSPENSION",
                )
            )

        self.invalidate_cache()

    async def revoke_domain_control(
        self,
        identifier_id: str,
        *,
        org_id: str,
    ) -> None:
        """Revoke domain control identifier and invalidate cache."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            await conn.execute(
                update(trust_fabric_identifiers)
                .where(
                    and_(
                        trust_fabric_identifiers.c.id == identifier_id,
                        trust_fabric_identifiers.c.org_id == org_id,
                        trust_fabric_identifiers.c.identifier_type == "DOMAIN",
                    )
                )
                .values(
                    revoked_at=now_iso,
                    verification_state=IdentifierVerificationState.REVOKED.value,
                )
            )
        self.invalidate_cache()

    def get_cached_decision(self, cache_key: str) -> Any | None:
        """Retrieve a cached decision respecting strict TTL; never widen trust on failure."""
        if self._cache_failing:
            # Cache failure (e.g. Redis connection error) fails closed to authoritative DB
            return None

        if cache_key not in self._local_cache:
            return None
        val, expiry = self._local_cache[cache_key]
        if datetime.now(UTC) >= expiry:
            del self._local_cache[cache_key]
            return None
        return val

    def set_cached_decision(self, cache_key: str, decision: Any, ttl_seconds: int = 60) -> None:
        """Store decision in cache with bounded TTL."""
        if self._cache_failing:
            return
        expiry = datetime.now(UTC) + timedelta(seconds=ttl_seconds)
        self._local_cache[cache_key] = (decision, expiry)
