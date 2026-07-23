"""Async repository for multi-tenant org, API key, and RBAC data.

Key security decisions:
- Raw API keys are never stored — only SHA-256 hashes.
- Key generation uses `secrets.token_urlsafe(32)` with "rai_" prefix.
- `authenticate()` re-hashes the presented key and compares against stored hash.
- Revoked keys are kept in DB for audit purposes (revoked=1 flag).
"""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import DatabaseEngine, org_api_keys, organizations
from responsibleai.rbac.models import Organization, OrgApiKey, OrgContext, Plan, Role
from responsibleai.rbac.permissions import role_from_str


def _plan_from_str(s: str | None) -> Plan:
    try:
        return Plan(str(s).upper()) if s else Plan.FREE
    except ValueError:
        return Plan.FREE


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _hash_key(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def _generate_raw_key() -> str:
    return "rai_" + secrets.token_urlsafe(32)


class SSORequiredError(Exception):
    """Raised by authenticate() when the org has enforced SSO-only login."""

    def __init__(self, org_id: str) -> None:
        self.org_id = org_id
        super().__init__(f"Organization {org_id} requires SSO login — static API keys are disabled.")


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
        plan: Plan = Plan.FREE,
    ) -> Organization:
        org = Organization(
            name=name,
            slug=slug,
            monthly_budget_usd=monthly_budget_usd,
            created_at=_now(),
            plan=plan,
        )
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(organizations).values(
                id=org.id,
                name=org.name,
                slug=org.slug,
                monthly_budget_usd=org.monthly_budget_usd,
                created_at=org.created_at,
                plan=org.plan.value,
            ))
        return org

    async def set_plan(
        self,
        org_id: str,
        plan: Plan,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        plan_renews_at: str | None = None,
    ) -> bool:
        """Update an org's billing plan — called from Stripe webhook handlers."""
        values: dict[str, object] = {"plan": plan.value}
        if stripe_customer_id is not None:
            values["stripe_customer_id"] = stripe_customer_id
        if stripe_subscription_id is not None:
            values["stripe_subscription_id"] = stripe_subscription_id
        if plan_renews_at is not None:
            values["plan_renews_at"] = plan_renews_at
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(organizations).where(organizations.c.id == org_id).values(**values)
            )
        return result.rowcount > 0

    async def set_sso_required(self, org_id: str, required: bool) -> bool:
        """Enable/disable SSO-only enforcement. When enabled, static API keys
        scoped to this org are rejected by authenticate() — SSO becomes the
        only login path, closing the static-key backdoor for departed staff."""
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(sso_required=1 if required else 0)
            )
        return result.rowcount > 0

    async def get_org_by_stripe_customer(self, stripe_customer_id: str) -> Organization | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(organizations).where(organizations.c.stripe_customer_id == stripe_customer_id)
            )).fetchone()
        return self._row_to_org(row) if row else None

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

        org = await self.get_org(row.org_id)
        if org is not None and org.sso_required:
            raise SSORequiredError(org.id)

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

        return OrgContext(
            key_id=row.id,
            role=role_from_str(row.role),
            org_id=row.org_id,
            org_name=org.name if org else None,
            key_name=row.name,
            mfa_enrolled=bool(getattr(row, "mfa_enrolled", 0)),
            is_legacy=False,
            plan=org.plan if org else Plan.FREE,
        )

    # ── MFA (TOTP) ────────────────────────────────────────────────────────────

    async def get_key(self, key_id: str) -> OrgApiKey | None:
        """Fetch a key by ID, including its MFA secret/backup codes.
        Server-side use only (login/enroll flows) — never returned to a
        client as-is; OrgApiKey.to_dict() already omits those fields."""
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(org_api_keys).where(org_api_keys.c.id == key_id)
            )).fetchone()
        return self._row_to_key(row) if row else None

    async def set_mfa_secret(self, key_id: str, secret: str) -> bool:
        """Store a freshly generated, not-yet-confirmed TOTP secret.
        enrolled stays 0 until confirm_mfa() succeeds."""
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.id == key_id)
                .values(mfa_secret=secret, mfa_enrolled=0, mfa_backup_codes=None)
            )
        return result.rowcount > 0

    async def confirm_mfa(self, key_id: str, backup_codes_hashed: list[str]) -> bool:
        """Mark MFA enrolled after the first correct code is verified,
        storing the hashed one-time backup codes."""
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.id == key_id)
                .values(mfa_enrolled=1, mfa_backup_codes=json.dumps(backup_codes_hashed))
            )
        return result.rowcount > 0

    async def disable_mfa(self, key_id: str) -> bool:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.id == key_id)
                .values(mfa_secret=None, mfa_enrolled=0, mfa_backup_codes=None)
            )
        return result.rowcount > 0

    async def consume_backup_code(self, key_id: str, remaining_hashed: list[str]) -> bool:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.id == key_id)
                .values(mfa_backup_codes=json.dumps(remaining_hashed))
            )
        return result.rowcount > 0

    async def set_org_mfa_required(self, org_id: str, required: bool) -> bool:
        """Force every key under this org through MFA enrollment + TOTP
        verification at /login — same enforcement pattern as set_sso_required."""
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(mfa_required=1 if required else 0)
            )
        return result.rowcount > 0

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _row_to_org(self, row: Any) -> Organization:
        return Organization(
            id=row.id,
            name=row.name,
            slug=row.slug,
            monthly_budget_usd=row.monthly_budget_usd,
            created_at=row.created_at,
            plan=_plan_from_str(getattr(row, "plan", None)),
            stripe_customer_id=getattr(row, "stripe_customer_id", None),
            stripe_subscription_id=getattr(row, "stripe_subscription_id", None),
            plan_renews_at=getattr(row, "plan_renews_at", None),
            sso_required=bool(getattr(row, "sso_required", 0)),
            mfa_required=bool(getattr(row, "mfa_required", 0)),
        )

    def _row_to_key(self, row: Any) -> OrgApiKey:
        backup_codes_raw = getattr(row, "mfa_backup_codes", None)
        return OrgApiKey(
            id=row.id,
            org_id=row.org_id,
            name=row.name,
            role=role_from_str(row.role),
            created_at=row.created_at,
            last_used_at=getattr(row, "last_used_at", None),
            revoked=bool(row.revoked),
            mfa_enrolled=bool(getattr(row, "mfa_enrolled", 0)),
            mfa_secret=getattr(row, "mfa_secret", None),
            mfa_backup_codes=json.loads(backup_codes_raw) if backup_codes_raw else None,
        )
