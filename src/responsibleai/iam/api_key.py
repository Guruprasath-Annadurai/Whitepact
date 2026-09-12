# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise API Key Lineage & Rotation Service."""

from __future__ import annotations

import hashlib
import json
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, insert, select, update

from responsibleai.db.engine import DatabaseEngine, iam_api_key_lineage, org_api_keys
from responsibleai.rbac.models import Role


class ApiKeyService:
    """Enterprise API key lifecycle: creation, rotation lineage, SHA-256 fingerprinting, revocation."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    def generate_raw_key(self, environment: str = "live") -> str:
        """Generate a cryptographically random prefixed key."""
        return f"wp_{environment}_{secrets.token_urlsafe(32)}"

    def compute_fingerprint(self, raw_key: str) -> str:
        """Compute public SHA-256 fingerprint (never logs raw keys)."""
        return hashlib.sha256(raw_key.encode("utf-8")).hexdigest()

    async def create_key(
        self,
        *,
        org_id: str,
        name: str,
        role: Role,
        environment: str = "live",
        scopes: list[str] | None = None,
        ttl_days: int = 90,
    ) -> tuple[str, str, str]:
        """Create an enterprise API key, returning (key_id, raw_key, fingerprint)."""
        raw_key = self.generate_raw_key(environment)
        fingerprint = self.compute_fingerprint(raw_key)
        key_id = f"wpk_{uuid.uuid4().hex}"
        now = datetime.now(UTC)
        expires_at = (now + timedelta(days=ttl_days)).isoformat()

        async with self.db.raw.begin() as conn:
            # Insert into org_api_keys for compatibility
            await conn.execute(
                insert(org_api_keys).values(
                    id=key_id,
                    org_id=org_id,
                    name=name,
                    role=role.value,
                    key_hash=fingerprint,
                    created_at=now.isoformat(),
                    revoked=0,
                    mfa_enrolled=0,
                )
            )

            # Insert lineage tracking
            await conn.execute(
                insert(iam_api_key_lineage).values(
                    id=key_id,
                    org_id=org_id,
                    name=name,
                    fingerprint=fingerprint,
                    parent_key_id=None,
                    status="ACTIVE",
                    scopes_json=json.dumps(scopes or []),
                    created_at=now.isoformat(),
                    expires_at=expires_at,
                    revoked_at=None,
                )
            )

        return key_id, raw_key, fingerprint

    async def rotate_key(
        self,
        *,
        org_id: str,
        old_key_id: str,
        grace_period_seconds: int = 300,
    ) -> tuple[str, str, str]:
        """Rotate an API key, linking lineage and scheduling old key deprecation."""
        now = datetime.now(UTC)
        new_raw_key = self.generate_raw_key("live")
        new_fingerprint = self.compute_fingerprint(new_raw_key)
        new_key_id = f"wpk_{uuid.uuid4().hex}"

        async with self.db.raw.begin() as conn:
            # Fetch old key
            stmt = select(iam_api_key_lineage).where(
                and_(
                    iam_api_key_lineage.c.id == old_key_id,
                    iam_api_key_lineage.c.org_id == org_id,
                )
            )
            old_row = (await conn.execute(stmt)).first()
            if not old_row:
                raise ValueError("Old API key not found in tenant lineage.")

            old_data = dict(old_row._mapping)

            # Insert new key
            await conn.execute(
                insert(iam_api_key_lineage).values(
                    id=new_key_id,
                    org_id=org_id,
                    name=old_data["name"],
                    fingerprint=new_fingerprint,
                    parent_key_id=old_key_id,
                    status="ACTIVE",
                    scopes_json=old_data["scopes_json"],
                    created_at=now.isoformat(),
                    expires_at=(now + timedelta(days=90)).isoformat(),
                    revoked_at=None,
                )
            )

            # Mark old key as ROTATED
            await conn.execute(
                update(iam_api_key_lineage)
                .where(iam_api_key_lineage.c.id == old_key_id)
                .values(status="ROTATED", revoked_at=now.isoformat())
            )
            # Revoke in org_api_keys
            await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.id == old_key_id)
                .values(revoked=1)
            )

        return new_key_id, new_raw_key, new_fingerprint

    async def revoke_key(self, *, org_id: str, key_id: str) -> bool:
        """Immediately revoke an API key."""
        now = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            await conn.execute(
                update(iam_api_key_lineage)
                .where(
                    and_(
                        iam_api_key_lineage.c.id == key_id,
                        iam_api_key_lineage.c.org_id == org_id,
                    )
                )
                .values(status="REVOKED", revoked_at=now)
            )
            res = await conn.execute(
                update(org_api_keys)
                .where(
                    and_(
                        org_api_keys.c.id == key_id,
                        org_api_keys.c.org_id == org_id,
                    )
                )
                .values(revoked=1)
            )
            return (res.rowcount or 0) > 0
