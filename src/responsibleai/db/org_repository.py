"""Async repository for multi-tenant org, API key, and RBAC data.

Key security decisions:
- Raw API keys are never stored — only SHA-256 hashes.
- Key generation uses `secrets.token_urlsafe(32)` with "rai_" prefix.
- `authenticate()` re-hashes the presented key and compares against stored hash.
- Revoked keys are kept in DB for audit purposes (revoked=1 flag).
"""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import DatabaseEngine, org_api_keys, organizations
from responsibleai.rbac.models import Organization, OrgApiKey, OrgContext, Role
from responsibleai.rbac.permissions import role_from_str


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_raw_key() -> str:
    return "rai_" + secrets.token_urlsafe(32)


class OrgRepository:
    """CRUD operations for organizations and their API keys."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    # ── Organizations ─────────────────────────────────────────────────────────

    async def create_org(
        self,
        name: str,
        slug: str,
        monthly_budget_usd: float = 10_000.0,
    ) -> Organization:
        org = Organization(
            name=name,
            slug=slug,
            monthly_budget_usd=monthly_budget_usd,
            created_at=_now(),
        )
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(organizations).values(
                id=org.id,
                name=org.name,
                slug=org.slug,
                monthly_budget_usd=org.monthly_budget_usd,
                created_at=org.created_at,
            ))
        return org

    async def get_org(self, org_id: str) -> Organization | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(organizations).where(organizations.c.id == org_id)
            )).fetchone()
        return self._row_to_org(row) if row else None

    async def get_org_by_slug(self, slug: str) -> Organization | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(organizations).where(organizations.c.slug == slug)
            )).fetchone()
        return self._row_to_org(row) if row else None

    async def list_orgs(self) -> list[Organization]:
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(select(organizations))).fetchall()
        return [self._row_to_org(r) for r in rows]

    async def delete_org(self, org_id: str) -> bool:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                delete(organizations).where(organizations.c.id == org_id)
            )
        return result.rowcount > 0

    # ── API Keys ──────────────────────────────────────────────────────────────

    async def create_key(
        self,
        org_id: str,
        name: str,
        role: Role = Role.ANALYST,
    ) -> tuple[OrgApiKey, str]:
        """Create a new API key. Returns (OrgApiKey, raw_key).
        The raw_key is shown ONCE and never stored. Store it now."""
        raw = _generate_raw_key()
        key_rec = OrgApiKey(
            org_id=org_id,
            name=name,
            role=role,
            created_at=_now(),
        )
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(org_api_keys).values(
                id=key_rec.id,
                org_id=org_id,
                key_hash=_hash_key(raw),
                name=name,
                role=role.value,
                created_at=key_rec.created_at,
                revoked=0,
            ))
        return key_rec, raw

    async def revoke_key(self, key_id: str) -> bool:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.id == key_id)
                .values(revoked=1)
            )
        return result.rowcount > 0

    async def list_keys(self, org_id: str) -> list[OrgApiKey]:
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(
                select(org_api_keys)
                .where(org_api_keys.c.org_id == org_id)
                .where(org_api_keys.c.revoked == 0)
            )).fetchall()
        return [self._row_to_key(r) for r in rows]

    async def authenticate(self, raw_key: str) -> OrgContext | None:
        """Verify a raw key, update last_used_at, return OrgContext or None."""
        key_hash = _hash_key(raw_key)
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(org_api_keys)
                .where(org_api_keys.c.key_hash == key_hash)
                .where(org_api_keys.c.revoked == 0)
            )).fetchone()

        if row is None:
            return None

        # Update last_used_at (best-effort, fire & forget)
        try:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    update(org_api_keys)
                    .where(org_api_keys.c.id == row.id)
                    .values(last_used_at=_now())
                )
        except Exception:
            pass

        org = await self.get_org(row.org_id)
        return OrgContext(
            key_id=row.id,
            role=role_from_str(row.role),
            org_id=row.org_id,
            org_name=org.name if org else None,
            is_legacy=False,
        )

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _row_to_org(self, row: object) -> Organization:
        return Organization(
            id=row.id,
            name=row.name,
            slug=row.slug,
            monthly_budget_usd=row.monthly_budget_usd,
            created_at=row.created_at,
        )

    def _row_to_key(self, row: object) -> OrgApiKey:
        return OrgApiKey(
            id=row.id,
            org_id=row.org_id,
            name=row.name,
            role=role_from_str(row.role),
            created_at=row.created_at,
            last_used_at=getattr(row, "last_used_at", None),
            revoked=bool(row.revoked),
        )
