# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Principal Directory and Global Identifier Management.

Enforces:
- Normalized identifier canonicalization (email, domain, phone, registration numbers).
- Multi-tenant boundary isolation: cross-tenant reads/writes strictly rejected.
- Anti-collision: duplicate active identifiers in the same organization are rejected.
- Identifier resurrection prevention: deleting a principal revokes active bindings,
  and subsequent registrations with the same identifier create a new, distinct principal
  with zero transferred authority.
- Anti-enumeration: searches are strictly scoped to the authorized organization.
"""

from __future__ import annotations

import re
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import and_, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import (
    DatabaseEngine,
    trust_fabric_identifiers,
    trust_fabric_principals,
)
from responsibleai.trust_fabric.enums import (
    IdentifierType,
    IdentifierVerificationState,
    PrincipalState,
    PrincipalType,
)
from responsibleai.trust_fabric.errors import (
    CrossTenantAccessError,
    IdentifierCollisionError,
    PrincipalInactiveError,
    PrincipalNotFoundError,
)
from responsibleai.trust_fabric.models import (
    Principal,
    PrincipalIdentifier,
)


def normalize_identifier(identifier_type: IdentifierType, value: str) -> str:
    """Canonicalize an identifier value based on its type."""
    val = value.strip()
    if identifier_type == IdentifierType.EMAIL:
        val = val.lower()
        if "@" not in val or val.startswith("@") or val.endswith("@"):
            raise ValueError(f"Invalid email address: {value!r}")
        local_part, domain_part = val.split("@", 1)
        domain_part = domain_part.encode("idna").decode("ascii")
        return f"{local_part}@{domain_part}"
    elif identifier_type == IdentifierType.DOMAIN:
        val = val.lower().rstrip(".")
        if "://" in val:
            val = val.split("://", 1)[1]
        if "/" in val:
            val = val.split("/", 1)[0]
        return val.encode("idna").decode("ascii")
    elif identifier_type == IdentifierType.PHONE:
        # Normalize to E.164 digits with leading +
        digits = re.sub(r"[^\d+]", "", val)
        if not digits.startswith("+"):
            digits = f"+{digits}"
        return digits
    elif identifier_type == IdentifierType.REGISTRATION_NUMBER:
        return val.upper()
    else:
        return val


class PrincipalDirectory:
    """Enterprise repository managing canonical principals and global identifiers."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def create_principal(
        self,
        *,
        org_id: str,
        principal_type: PrincipalType,
        display_name: str,
        lifecycle_state: PrincipalState = PrincipalState.PENDING_VERIFICATION,
        metadata: dict[str, Any] | None = None,
    ) -> Principal:
        """Create a new canonical principal within an organization."""
        principal = Principal.create(
            org_id=org_id,
            principal_type=principal_type,
            display_name=display_name,
            lifecycle_state=lifecycle_state,
            metadata=metadata,
        )

        async with self.db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_principals.insert().values(
                    id=principal.id,
                    org_id=principal.org_id,
                    principal_type=principal.principal_type.value,
                    display_name=principal.display_name,
                    lifecycle_state=principal.lifecycle_state.value,
                    created_at=principal.created_at,
                    updated_at=principal.updated_at,
                    metadata_json=str(principal.metadata),
                )
            )

        return principal

    async def get_principal(self, principal_id: str, *, org_id: str) -> Principal:
        """Retrieve a principal with strict multi-tenant boundary verification."""
        async with self.db.raw.connect() as conn:
            stmt = select(trust_fabric_principals).where(
                trust_fabric_principals.c.id == principal_id
            )
            res = (await conn.execute(stmt)).first()
            if not res:
                raise PrincipalNotFoundError(f"Principal {principal_id!r} does not exist.")

            row = dict(res._mapping)
            if row["org_id"] != org_id:
                raise CrossTenantAccessError(
                    f"Principal {principal_id!r} belongs to organization {row['org_id']!r}, "
                    f"access denied for tenant {org_id!r}."
                )

            return Principal(
                id=row["id"],
                org_id=row["org_id"],
                principal_type=PrincipalType(row["principal_type"]),
                display_name=row["display_name"],
                lifecycle_state=PrincipalState(row["lifecycle_state"]),
                created_at=row["created_at"],
                updated_at=row["updated_at"],
                metadata={},
            )

    async def attach_identifier(
        self,
        *,
        principal_id: str,
        org_id: str,
        identifier_type: IdentifierType,
        value: str,
        is_primary: bool = False,
        verification_state: IdentifierVerificationState = IdentifierVerificationState.UNVERIFIED,
        source_id: str | None = None,
    ) -> PrincipalIdentifier:
        """Attach a normalized identifier to an active principal."""
        principal = await self.get_principal(principal_id, org_id=org_id)
        if principal.lifecycle_state in (PrincipalState.DELETED, PrincipalState.REVOKED):
            raise PrincipalInactiveError(
                f"Cannot attach identifier to inactive principal {principal_id!r} "
                f"(state: {principal.lifecycle_state.value})."
            )

        norm_val = normalize_identifier(identifier_type, value)

        try:
            async with self.db.raw.begin() as conn:
                # Check for existing active identifier in this organization
                chk_stmt = select(trust_fabric_identifiers).where(
                    and_(
                        trust_fabric_identifiers.c.org_id == org_id,
                        trust_fabric_identifiers.c.identifier_type == identifier_type.value,
                        trust_fabric_identifiers.c.normalized_value == norm_val,
                        trust_fabric_identifiers.c.revoked_at.is_(None),
                    )
                )
                existing = (await conn.execute(chk_stmt)).first()
                if existing:
                    row = dict(existing._mapping)
                    if row["principal_id"] != principal_id:
                        raise IdentifierCollisionError(
                            f"Identifier {identifier_type.value}:{norm_val!r} is already claimed "
                            f"by principal {row['principal_id']!r} in organization {org_id!r}."
                        )
                    # If already attached to same principal, return existing record
                    return PrincipalIdentifier(
                        id=row["id"],
                        principal_id=row["principal_id"],
                        org_id=row["org_id"],
                        identifier_type=IdentifierType(row["identifier_type"]),
                        raw_value=row["raw_value"],
                        normalized_value=row["normalized_value"],
                        is_primary=bool(row["is_primary"]),
                        verification_state=IdentifierVerificationState(row["verification_state"]),
                        verified_at=row["verified_at"],
                        expires_at=row["expires_at"],
                        revoked_at=row["revoked_at"],
                        source_id=row["source_id"],
                        created_at=row["created_at"],
                    )

                now_iso = datetime.now(UTC).isoformat()
                ident_id = f"wp_ident_{uuid.uuid4().hex}"
                verified_at = now_iso if verification_state == IdentifierVerificationState.VERIFIED else None

                await conn.execute(
                    trust_fabric_identifiers.insert().values(
                        id=ident_id,
                        principal_id=principal_id,
                        org_id=org_id,
                        identifier_type=identifier_type.value,
                        raw_value=value,
                        normalized_value=norm_val,
                        is_primary=1 if is_primary else 0,
                        verification_state=verification_state.value,
                        verified_at=verified_at,
                        expires_at=None,
                        revoked_at=None,
                        source_id=source_id,
                        created_at=now_iso,
                    )
                )
        except IntegrityError as exc:
            raise IdentifierCollisionError(
                f"Identifier {identifier_type.value}:{norm_val!r} is already claimed in organization {org_id!r}."
            ) from exc

        return PrincipalIdentifier(
            id=ident_id,
            principal_id=principal_id,
            org_id=org_id,
            identifier_type=identifier_type,
            raw_value=value,
            normalized_value=norm_val,
            is_primary=is_primary,
            verification_state=verification_state,
            verified_at=verified_at,
            expires_at=None,
            revoked_at=None,
            source_id=source_id,
            created_at=now_iso,
        )

    async def resolve_by_identifier(
        self,
        *,
        org_id: str,
        identifier_type: IdentifierType,
        value: str,
    ) -> Principal | None:
        """Resolve a principal by its normalized identifier within an organization."""
        norm_val = normalize_identifier(identifier_type, value)
        async with self.db.raw.connect() as conn:
            stmt = (
                select(trust_fabric_principals)
                .select_from(
                    trust_fabric_principals.join(
                        trust_fabric_identifiers,
                        trust_fabric_principals.c.id == trust_fabric_identifiers.c.principal_id,
                    )
                )
                .where(
                    and_(
                        trust_fabric_identifiers.c.org_id == org_id,
                        trust_fabric_identifiers.c.identifier_type == identifier_type.value,
                        trust_fabric_identifiers.c.normalized_value == norm_val,
                        trust_fabric_identifiers.c.revoked_at.is_(None),
                        trust_fabric_principals.c.lifecycle_state != PrincipalState.DELETED.value,
                    )
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                return None

            data = dict(row._mapping)
            return Principal(
                id=data["id"],
                org_id=data["org_id"],
                principal_type=PrincipalType(data["principal_type"]),
                display_name=data["display_name"],
                lifecycle_state=PrincipalState(data["lifecycle_state"]),
                created_at=data["created_at"],
                updated_at=data["updated_at"],
                metadata={},
            )

    async def delete_principal(self, principal_id: str, *, org_id: str) -> None:
        """Delete/tombstone a principal and revoke active identifiers (prevents resurrection)."""
        await self.get_principal(principal_id, org_id=org_id)
        now_iso = datetime.now(UTC).isoformat()

        async with self.db.raw.begin() as conn:
            # 1. Update lifecycle state to DELETED
            await conn.execute(
                update(trust_fabric_principals)
                .where(
                    and_(
                        trust_fabric_principals.c.id == principal_id,
                        trust_fabric_principals.c.org_id == org_id,
                    )
                )
                .values(
                    lifecycle_state=PrincipalState.DELETED.value,
                    updated_at=now_iso,
                )
            )
            # 2. Revoke active identifiers so they can be re-bound to new entities
            # without resurrecting old authority
            await conn.execute(
                update(trust_fabric_identifiers)
                .where(
                    and_(
                        trust_fabric_identifiers.c.principal_id == principal_id,
                        trust_fabric_identifiers.c.org_id == org_id,
                        trust_fabric_identifiers.c.revoked_at.is_(None),
                    )
                )
                .values(
                    revoked_at=now_iso,
                    verification_state=IdentifierVerificationState.REVOKED.value,
                )
            )

    async def search_principals(
        self,
        *,
        org_id: str,
        query: str,
        limit: int = 50,
    ) -> list[Principal]:
        """Tenant-isolated search preventing cross-tenant enumeration."""
        q = f"%{query.strip()}%"
        async with self.db.raw.connect() as conn:
            stmt = (
                select(trust_fabric_principals)
                .where(
                    and_(
                        trust_fabric_principals.c.org_id == org_id,
                        trust_fabric_principals.c.lifecycle_state != PrincipalState.DELETED.value,
                        trust_fabric_principals.c.display_name.ilike(q),
                    )
                )
                .limit(limit)
            )
            rows = (await conn.execute(stmt)).fetchall()
            return [
                Principal(
                    id=r["id"],
                    org_id=r["org_id"],
                    principal_type=PrincipalType(r["principal_type"]),
                    display_name=r["display_name"],
                    lifecycle_state=PrincipalState(r["lifecycle_state"]),
                    created_at=r["created_at"],
                    updated_at=r["updated_at"],
                    metadata={},
                )
                for r in [dict(r._mapping) for r in rows]
            ]
