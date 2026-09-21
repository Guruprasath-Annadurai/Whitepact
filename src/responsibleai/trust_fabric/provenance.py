# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Trust Source Hierarchy, Field-Level Provenance & Multi-Dimensional Assurance Engine.

Core Invariants:
- 6-Tier Source Taxonomy strictly enforced.
- Trust Inflation Defense: Tier F (Self-attestation) can NEVER escalate to HIGH
  or CRYPTOGRAPHIC assurance.
- Multi-dimensional Assurance Vector: outputs explicit dimensions (identity,
  affiliation, authority, freshness, credential, conflict) — NEVER a single moral score.
- Immutable Evidence Digest: every asserted fact binds cryptographically to its provenance.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, select

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_assertions,
    trust_fabric_identifiers,
    trust_fabric_sources,
)
from responsibleai.trust_fabric.enums import (
    AssuranceLevel,
    DisclosureClass,
    IdentifierVerificationState,
    SourceTier,
)
from responsibleai.trust_fabric.errors import (
    TrustFabricError,
)
from responsibleai.trust_fabric.models import (
    AssuranceVector,
    FieldProvenance,
    TrustSource,
    compute_digest,
)


class TrustProvenanceEngine:
    """Manages trust sources, field-level provenance, and multi-dimensional assurance."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def register_source(
        self,
        *,
        name: str,
        source_tier: SourceTier,
        provider_type: str,
        endpoint_or_uri: str | None = None,
        org_id: str | None = None,
    ) -> TrustSource:
        """Register a recognized source of trust evidence."""
        source_id = f"wp_src_{uuid.uuid4().hex}"
        now_iso = datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_sources.insert().values(
                    id=source_id,
                    org_id=org_id,
                    name=name,
                    source_tier=source_tier.value,
                    provider_type=provider_type,
                    endpoint_or_uri=endpoint_or_uri,
                    is_active=1,
                    created_at=now_iso,
                )
            )

        return TrustSource(
            id=source_id,
            name=name,
            source_tier=source_tier,
            provider_type=provider_type,
            endpoint_or_uri=endpoint_or_uri,
            org_id=org_id,
            is_active=True,
            created_at=now_iso,
        )

    async def record_assertion(
        self,
        *,
        principal_id: str,
        org_id: str,
        field_name: str,
        field_value: str,
        source_id: str,
        verification_method: str,
        assurance_level: AssuranceLevel,
        disclosure_class: DisclosureClass,
        expires_at: str | None = None,
    ) -> FieldProvenance:
        """Record a verified field assertion with full provenance tracking."""
        async with self.db.raw.connect() as conn:
            src_stmt = select(trust_fabric_sources).where(trust_fabric_sources.c.id == source_id)
            src_row = (await conn.execute(src_stmt)).first()
            if not src_row:
                raise TrustFabricError(f"Trust source {source_id!r} not registered.")
            source_data = dict(src_row._mapping)
            source_tier = SourceTier(source_data["source_tier"])

        # Trust Inflation Defense: Self-attestation (Tier F) can NEVER escalate
        # to HIGH or CRYPTOGRAPHIC assurance.
        if source_tier == SourceTier.TIER_F and assurance_level in (
            AssuranceLevel.HIGH,
            AssuranceLevel.CRYPTOGRAPHIC,
        ):
            assurance_level = AssuranceLevel.LOW

        assertion_id = f"wp_asst_{uuid.uuid4().hex}"
        now_iso = datetime.now(UTC).isoformat()

        payload = {
            "id": assertion_id,
            "principal_id": principal_id,
            "org_id": org_id,
            "field_name": field_name,
            "field_value": field_value,
            "source_id": source_id,
            "source_tier": source_tier.value,
            "verification_method": verification_method,
            "verified_at": now_iso,
        }
        evidence_digest = compute_digest(payload)

        async with self.db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_assertions.insert().values(
                    id=assertion_id,
                    principal_id=principal_id,
                    org_id=org_id,
                    field_name=field_name,
                    field_value=field_value,
                    source_id=source_id,
                    source_tier=source_tier.value,
                    verification_method=verification_method,
                    assurance_level=assurance_level.value,
                    disclosure_class=disclosure_class.value,
                    verified_at=now_iso,
                    expires_at=expires_at,
                    last_checked_at=now_iso,
                    revoked_at=None,
                    evidence_digest=evidence_digest,
                )
            )

        return FieldProvenance(
            id=assertion_id,
            principal_id=principal_id,
            org_id=org_id,
            field_name=field_name,
            field_value=field_value,
            source_id=source_id,
            source_tier=source_tier,
            verification_method=verification_method,
            assurance_level=assurance_level,
            disclosure_class=disclosure_class,
            verified_at=now_iso,
            last_checked_at=now_iso,
            evidence_digest=evidence_digest,
            expires_at=expires_at,
            revoked_at=None,
        )

    async def get_assertions(
        self,
        principal_id: str,
        *,
        org_id: str,
        disclosure_limit: DisclosureClass | None = None,
    ) -> list[FieldProvenance]:
        """Retrieve active assertions for a principal with selective disclosure filtering."""
        async with self.db.raw.connect() as conn:
            stmt = select(trust_fabric_assertions).where(
                and_(
                    trust_fabric_assertions.c.principal_id == principal_id,
                    trust_fabric_assertions.c.org_id == org_id,
                    trust_fabric_assertions.c.revoked_at.is_(None),
                )
            )
            rows = (await conn.execute(stmt)).fetchall()

            # Define hierarchy of disclosure classes
            hierarchy = {
                DisclosureClass.PUBLIC: 0,
                DisclosureClass.BUSINESS_PUBLIC: 1,
                DisclosureClass.TENANT_INTERNAL: 2,
                DisclosureClass.SECURITY_RESTRICTED: 3,
                DisclosureClass.NEVER_PUBLIC: 4,
            }

            max_level = hierarchy[disclosure_limit] if disclosure_limit else 4

            results: list[FieldProvenance] = []
            for r in [dict(row._mapping) for row in rows]:
                d_class = DisclosureClass(r["disclosure_class"])
                if hierarchy[d_class] <= max_level:
                    results.append(
                        FieldProvenance(
                            id=r["id"],
                            principal_id=r["principal_id"],
                            org_id=r["org_id"],
                            field_name=r["field_name"],
                            field_value=r["field_value"],
                            source_id=r["source_id"],
                            source_tier=SourceTier(r["source_tier"]),
                            verification_method=r["verification_method"],
                            assurance_level=AssuranceLevel(r["assurance_level"]),
                            disclosure_class=d_class,
                            verified_at=r["verified_at"],
                            last_checked_at=r["last_checked_at"],
                            evidence_digest=r["evidence_digest"],
                            expires_at=r["expires_at"],
                            revoked_at=r["revoked_at"],
                        )
                    )

            return results

    async def evaluate_assurance_vector(
        self,
        principal_id: str,
        *,
        org_id: str,
    ) -> AssuranceVector:
        """Compute the multidimensional assurance vector for a principal."""
        assertions = await self.get_assertions(principal_id, org_id=org_id)

        # 1. Identity Assurance
        # Based on verified identifiers & highest tier assertion
        async with self.db.raw.connect() as conn:
            ident_stmt = select(trust_fabric_identifiers).where(
                and_(
                    trust_fabric_identifiers.c.principal_id == principal_id,
                    trust_fabric_identifiers.c.org_id == org_id,
                    trust_fabric_identifiers.c.verification_state
                    == IdentifierVerificationState.VERIFIED.value,
                    trust_fabric_identifiers.c.revoked_at.is_(None),
                )
            )
            idents = (await conn.execute(ident_stmt)).fetchall()

        if not idents and not assertions:
            ident_assurance = AssuranceLevel.LOW
        elif any(a.assurance_level == AssuranceLevel.CRYPTOGRAPHIC for a in assertions):
            ident_assurance = AssuranceLevel.CRYPTOGRAPHIC
        elif any(a.assurance_level == AssuranceLevel.HIGH for a in assertions) or len(idents) >= 2:
            ident_assurance = AssuranceLevel.HIGH
        elif len(idents) >= 1 or any(
            a.assurance_level == AssuranceLevel.MEDIUM for a in assertions
        ):
            ident_assurance = AssuranceLevel.MEDIUM
        else:
            ident_assurance = AssuranceLevel.LOW

        # 2. Affiliation Assurance (Has verified relationship with org)
        from responsibleai.db.engine import trust_fabric_relationships

        async with self.db.raw.connect() as conn:
            rel_stmt = select(trust_fabric_relationships).where(
                and_(
                    trust_fabric_relationships.c.subject_principal_id == principal_id,
                    trust_fabric_relationships.c.org_id == org_id,
                    trust_fabric_relationships.c.verification_state
                    == IdentifierVerificationState.VERIFIED.value,
                    trust_fabric_relationships.c.revoked_at.is_(None),
                )
            )
            rels = (await conn.execute(rel_stmt)).fetchall()
            aff_assurance = AssuranceLevel.HIGH if rels else AssuranceLevel.LOW

        # 3. Authority Assurance
        from responsibleai.db.engine import trust_fabric_authority_edges

        async with self.db.raw.connect() as conn:
            auth_stmt = select(trust_fabric_authority_edges).where(
                and_(
                    trust_fabric_authority_edges.c.grantee_principal_id == principal_id,
                    trust_fabric_authority_edges.c.org_id == org_id,
                    trust_fabric_authority_edges.c.revoked_at.is_(None),
                )
            )
            auths = (await conn.execute(auth_stmt)).fetchall()
            auth_assurance = AssuranceLevel.HIGH if auths else AssuranceLevel.LOW

        # 4. Freshness
        now = datetime.now(UTC)
        freshness = "CURRENT"
        for a in assertions:
            checked = datetime.fromisoformat(a.last_checked_at)
            if now - checked > timedelta(days=7):
                freshness = "STALE"
            if a.expires_at and now.isoformat() >= a.expires_at:
                freshness = "EXPIRED"
                break

        # 5. Credential State
        cred_state = "VALID" if idents or assertions else "UNKNOWN"

        # 6. Conflict State
        from responsibleai.db.engine import trust_fabric_conflicts

        async with self.db.raw.connect() as conn:
            conf_stmt = select(trust_fabric_conflicts).where(
                and_(
                    trust_fabric_conflicts.c.principal_id == principal_id,
                    trust_fabric_conflicts.c.org_id == org_id,
                    trust_fabric_conflicts.c.status == "UNRESOLVED",
                )
            )
            conflicts = (await conn.execute(conf_stmt)).fetchall()
            conflict_state = "CONFLICTED" if conflicts else "NONE"

        return AssuranceVector(
            identity_assurance=ident_assurance,
            affiliation_assurance=aff_assurance,
            authority_assurance=auth_assurance,
            source_freshness=freshness,
            credential_state=cred_state,
            conflict_state=conflict_state,
        )
