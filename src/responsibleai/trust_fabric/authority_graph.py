# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Principal Relationships and Authority Graph Engine.

Core Invariants:
- Multi-tenant boundary isolation: authority grants and relationships are
  strictly scoped to the organization.
- Explicit authority edges: grantor, grantee, action_type, resource_pattern,
  ceiling_limit_usd, currency, delegation depth, and validity window.
- Revocation and expiration are strictly honored: revoked or expired edges
  never authorize an action.
- Financial & volumetric ceilings: transactions exceeding limits are rejected.
"""

from __future__ import annotations

import fnmatch
import uuid
from datetime import UTC, datetime

from sqlalchemy import and_, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_authority_edges,
    trust_fabric_principals,
    trust_fabric_relationships,
)
from responsibleai.trust_fabric.enums import (
    IdentifierVerificationState,
    PrincipalState,
    RelationshipType,
)
from responsibleai.trust_fabric.errors import (
    CrossTenantAccessError,
    PrincipalInactiveError,
    PrincipalNotFoundError,
)
from responsibleai.trust_fabric.models import (
    AuthorityEdge,
    PrincipalRelationship,
    compute_digest,
)


class AuthorityGraph:
    """Manages organizational relationships and delegated authority edges."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def create_relationship(
        self,
        *,
        subject_principal_id: str,
        target_principal_id: str,
        org_id: str,
        relationship_type: RelationshipType,
        source_id: str,
        role_title: str | None = None,
        valid_from: str | None = None,
        expires_at: str | None = None,
        verification_state: IdentifierVerificationState = IdentifierVerificationState.VERIFIED,
    ) -> PrincipalRelationship:
        """Establish a verified relationship between two principals within an organization."""
        # Verify both principals exist and belong to org_id
        async with self.db.raw.connect() as conn:
            for pid in (subject_principal_id, target_principal_id):
                stmt = select(trust_fabric_principals).where(trust_fabric_principals.c.id == pid)
                row = (await conn.execute(stmt)).first()
                if not row:
                    raise PrincipalNotFoundError(f"Principal {pid!r} not found.")
                if row._mapping["org_id"] != org_id:
                    raise CrossTenantAccessError(
                        f"Principal {pid!r} does not belong to organization {org_id!r}."
                    )
                if row._mapping["lifecycle_state"] in (
                    PrincipalState.DELETED.value,
                    PrincipalState.REVOKED.value,
                ):
                    raise PrincipalInactiveError(f"Principal {pid!r} is inactive.")

        rel_id = f"wp_rel_{uuid.uuid4().hex}"
        v_from = valid_from or datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_relationships.insert().values(
                    id=rel_id,
                    subject_principal_id=subject_principal_id,
                    target_principal_id=target_principal_id,
                    org_id=org_id,
                    relationship_type=relationship_type.value,
                    role_title=role_title,
                    verification_state=verification_state.value,
                    valid_from=v_from,
                    expires_at=expires_at,
                    revoked_at=None,
                    source_id=source_id,
                )
            )

        return PrincipalRelationship(
            id=rel_id,
            subject_principal_id=subject_principal_id,
            target_principal_id=target_principal_id,
            org_id=org_id,
            relationship_type=relationship_type,
            role_title=role_title,
            valid_from=v_from,
            expires_at=expires_at,
            revoked_at=None,
            source_id=source_id,
            verification_state=verification_state,
        )

    async def revoke_relationship(self, relationship_id: str, *, org_id: str) -> None:
        """Revoke an active relationship."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            stmt = select(trust_fabric_relationships).where(
                and_(
                    trust_fabric_relationships.c.id == relationship_id,
                    trust_fabric_relationships.c.org_id == org_id,
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                raise CrossTenantAccessError(
                    f"Relationship {relationship_id!r} not found for organization {org_id!r}."
                )

            await conn.execute(
                update(trust_fabric_relationships)
                .where(trust_fabric_relationships.c.id == relationship_id)
                .values(
                    revoked_at=now_iso,
                    verification_state=IdentifierVerificationState.REVOKED.value,
                )
            )

    async def grant_authority(
        self,
        *,
        grantor_principal_id: str,
        grantee_principal_id: str,
        org_id: str,
        action_type: str,
        resource_pattern: str = "*",
        ceiling_limit_usd: float | None = None,
        currency: str = "USD",
        delegation_depth: int = 0,
        valid_from: str | None = None,
        expires_at: str | None = None,
    ) -> AuthorityEdge:
        """Grant bounded, explicit authority from a grantor to a grantee."""
        async with self.db.raw.connect() as conn:
            for pid in (grantor_principal_id, grantee_principal_id):
                stmt = select(trust_fabric_principals).where(trust_fabric_principals.c.id == pid)
                row = (await conn.execute(stmt)).first()
                if not row:
                    raise PrincipalNotFoundError(f"Principal {pid!r} not found.")
                if row._mapping["org_id"] != org_id:
                    raise CrossTenantAccessError(
                        f"Principal {pid!r} does not belong to organization {org_id!r}."
                    )

        edge_id = f"wp_edge_{uuid.uuid4().hex}"
        v_from = valid_from or datetime.now(UTC).isoformat()

        payload = {
            "id": edge_id,
            "grantor": grantor_principal_id,
            "grantee": grantee_principal_id,
            "org_id": org_id,
            "action_type": action_type,
            "resource": resource_pattern,
            "ceiling": ceiling_limit_usd,
            "valid_from": v_from,
            "expires_at": expires_at,
        }
        canonical_digest = compute_digest(payload)

        async with self.db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_authority_edges.insert().values(
                    id=edge_id,
                    grantor_principal_id=grantor_principal_id,
                    grantee_principal_id=grantee_principal_id,
                    org_id=org_id,
                    action_type=action_type,
                    resource_pattern=resource_pattern,
                    ceiling_limit_usd=ceiling_limit_usd,
                    currency=currency,
                    delegation_depth=delegation_depth,
                    valid_from=v_from,
                    expires_at=expires_at,
                    revoked_at=None,
                    revoked_by=None,
                    canonical_digest=canonical_digest,
                )
            )

        return AuthorityEdge(
            id=edge_id,
            grantor_principal_id=grantor_principal_id,
            grantee_principal_id=grantee_principal_id,
            org_id=org_id,
            action_type=action_type,
            resource_pattern=resource_pattern,
            ceiling_limit_usd=ceiling_limit_usd,
            currency=currency,
            delegation_depth=delegation_depth,
            valid_from=v_from,
            expires_at=expires_at,
            revoked_at=None,
            canonical_digest=canonical_digest,
        )

    async def revoke_authority(
        self,
        edge_id: str,
        *,
        org_id: str,
        revoked_by_principal_id: str,
    ) -> None:
        """Explicitly revoke an authority grant."""
        now_iso = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            stmt = select(trust_fabric_authority_edges).where(
                and_(
                    trust_fabric_authority_edges.c.id == edge_id,
                    trust_fabric_authority_edges.c.org_id == org_id,
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                raise CrossTenantAccessError(
                    f"Authority edge {edge_id!r} not found for organization {org_id!r}."
                )

            await conn.execute(
                update(trust_fabric_authority_edges)
                .where(trust_fabric_authority_edges.c.id == edge_id)
                .values(
                    revoked_at=now_iso,
                    revoked_by=revoked_by_principal_id,
                )
            )

    async def check_authority(
        self,
        *,
        grantee_principal_id: str,
        org_id: str,
        action_type: str,
        resource: str = "*",
        amount_usd: float | None = None,
    ) -> tuple[bool, str, AuthorityEdge | None]:
        """Check if a principal holds active authority for an action, resource, and amount."""
        now_iso = datetime.now(UTC).isoformat()

        async with self.db.raw.connect() as conn:
            stmt = select(trust_fabric_authority_edges).where(
                and_(
                    trust_fabric_authority_edges.c.grantee_principal_id == grantee_principal_id,
                    trust_fabric_authority_edges.c.org_id == org_id,
                    trust_fabric_authority_edges.c.action_type == action_type,
                )
            )
            rows = (await conn.execute(stmt)).fetchall()

            for r in [dict(row._mapping) for row in rows]:
                edge = AuthorityEdge(
                    id=r["id"],
                    grantor_principal_id=r["grantor_principal_id"],
                    grantee_principal_id=r["grantee_principal_id"],
                    org_id=r["org_id"],
                    action_type=r["action_type"],
                    resource_pattern=r["resource_pattern"],
                    ceiling_limit_usd=r["ceiling_limit_usd"],
                    currency=r["currency"],
                    delegation_depth=r["delegation_depth"],
                    valid_from=r["valid_from"],
                    expires_at=r["expires_at"],
                    revoked_at=r["revoked_at"],
                    canonical_digest=r["canonical_digest"],
                )

                if edge.revoked_at is not None:
                    continue
                if edge.valid_from > now_iso:
                    continue
                if edge.expires_at is not None and edge.expires_at <= now_iso:
                    continue
                if not fnmatch.fnmatch(resource, edge.resource_pattern):
                    continue

                if amount_usd is not None and edge.ceiling_limit_usd is not None:
                    amt = float(amount_usd)
                    if amt > edge.ceiling_limit_usd:
                        return (
                            False,
                            f"Delegated authority ceiling of ${edge.ceiling_limit_usd:,.2f} USD exceeded (requested: ${amt:,.2f} USD).",
                            edge,
                        )

                return True, "AUTHORIZED", edge

            return False, "NO_MATCHING_AUTHORITY_GRANT", None
