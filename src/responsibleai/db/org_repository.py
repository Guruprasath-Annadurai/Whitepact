# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Async repository for multi-tenant org, API key, and RBAC data.

Key security decisions:
- Raw API keys are never stored — only SHA-256 hashes.
- Dashboard keys use environment-specific ``wp_test_``/``wp_live_``
  prefixes; the legacy default remains ``rai_`` for compatibility.
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

from responsibleai.db.engine import (
    DatabaseEngine,
    org_api_key_metadata,
    org_api_keys,
    organizations,
    tenant_tombstones,
)
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection
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


def _generate_raw_key(environment: str | None = None) -> str:
    if environment is None:
        prefix = "rai_"
    elif environment in {"test", "live"}:
        prefix = f"wp_{environment}_"
    else:
        raise ValueError("environment must be 'test' or 'live'")
    return prefix + secrets.token_urlsafe(32)


class SSORequiredError(Exception):
    """Raised by authenticate() when the org has enforced SSO-only login."""

    def __init__(self, org_id: str) -> None:
        self.org_id = org_id
        super().__init__(
            f"Organization {org_id} requires SSO login — static API keys are disabled."
        )


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
        provisioner_key_id: str | None = None,
    ) -> Organization:
        org = Organization(
            name=name,
            slug=slug,
            monthly_budget_usd=monthly_budget_usd,
            created_at=_now(),
            plan=plan,
            provisioner_key_id=provisioner_key_id,
        )
        async with self._engine.raw.begin() as conn:
            # Check tombstone ledger
            ts = (
                await conn.execute(
                    select(tenant_tombstones).where(
                        (tenant_tombstones.c.org_id == org.id)
                        | (tenant_tombstones.c.original_name == name)
                    )
                )
            ).fetchone()
            if ts:
                from responsibleai.data_governance.deletion_orchestrator import TenantDeletionError

                raise TenantDeletionError(
                    f"Cannot create tenant: identifier '{org.id}' or name '{name}' is tombstoned ({ts.org_id})"
                )

            await conn.execute(
                insert(organizations).values(
                    id=org.id,
                    name=org.name,
                    slug=org.slug,
                    monthly_budget_usd=org.monthly_budget_usd,
                    created_at=org.created_at,
                    plan=org.plan.value,
                    provisioner_key_id=provisioner_key_id,
                )
            )
        return org

    async def set_plan(
        self,
        org_id: str,
        plan: Plan,
        stripe_customer_id: str | None = None,
        stripe_subscription_id: str | None = None,
        plan_renews_at: str | None = None,
        subscription_status: str | None = None,
    ) -> bool:
        """Update an org's billing plan — called from Stripe webhook handlers."""
        values: dict[str, object] = {"plan": plan.value}
        if stripe_customer_id is not None:
            values["stripe_customer_id"] = stripe_customer_id
        if stripe_subscription_id is not None:
            values["stripe_subscription_id"] = stripe_subscription_id
        if plan_renews_at is not None:
            values["plan_renews_at"] = plan_renews_at
        if subscription_status is not None:
            values["subscription_status"] = subscription_status
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(organizations).where(organizations.c.id == org_id).values(**values)
            )
        return result.rowcount > 0

    async def update_org_name(self, org_id: str, name: str) -> bool:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(organizations).where(organizations.c.id == org_id).values(name=name)
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
            row = (
                await conn.execute(
                    select(organizations).where(
                        organizations.c.stripe_customer_id == stripe_customer_id
                    )
                )
            ).fetchone()
        return self._row_to_org(row) if row else None

    async def get_org(self, org_id: str) -> Organization | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(select(organizations).where(organizations.c.id == org_id))
            ).fetchone()
        return self._row_to_org(row) if row else None

    async def get_org_by_slug(self, slug: str) -> Organization | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(select(organizations).where(organizations.c.slug == slug))
            ).fetchone()
        return self._row_to_org(row) if row else None

    async def list_orgs(self) -> list[Organization]:
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(select(organizations))).fetchall()
        return [self._row_to_org(r) for r in rows]

    async def delete_org(self, org_id: str) -> bool:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(delete(organizations).where(organizations.c.id == org_id))
        return result.rowcount > 0

    # ── API Keys ──────────────────────────────────────────────────────────────

    async def create_key(
        self,
        org_id: str,
        name: str,
        role: Role = Role.ANALYST,
        *,
        environment: str | None = None,
        scopes: tuple[str, ...] = (),
        expires_at: str | None = None,
        rotated_from_id: str | None = None,
    ) -> tuple[OrgApiKey, str]:
        """Create a new API key. Returns (OrgApiKey, raw_key).
        The raw_key is shown ONCE and never stored. Store it now."""
        raw = _generate_raw_key(environment)
        prefix = "rai_" if environment is None else f"wp_{environment}_"
        key_rec = OrgApiKey(
            org_id=org_id,
            name=name,
            role=role,
            created_at=_now(),
            prefix=prefix,
            environment=environment or "legacy",
            scopes=tuple(sorted(set(scopes))),
            expires_at=expires_at,
            rotated_from_id=rotated_from_id,
        )
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(org_api_keys).values(
                    id=key_rec.id,
                    org_id=org_id,
                    key_hash=_hash_key(raw),
                    name=name,
                    role=role.value,
                    created_at=key_rec.created_at,
                    revoked=0,
                )
            )
            await conn.execute(
                insert(org_api_key_metadata).values(
                    key_id=key_rec.id,
                    prefix=prefix,
                    environment=environment or "legacy",
                    scopes=json.dumps(list(key_rec.scopes)),
                    expires_at=expires_at,
                    rotated_from_id=rotated_from_id,
                )
            )
        return key_rec, raw

    async def revoke_key(self, key_id: str, org_id: str | None = None) -> bool:
        where = org_api_keys.c.id == key_id
        if org_id is not None:
            where = where & (org_api_keys.c.org_id == org_id)
        async with self._engine.raw.begin() as conn:
            resolved_org = await conn.scalar(
                select(org_api_keys.c.org_id).where(where)
            )
            if resolved_org is not None:
                await bump_epoch_on_connection(conn, resolved_org)
            result = await conn.execute(update(org_api_keys).where(where).values(revoked=1))
        return result.rowcount > 0

    async def rotate_key(self, org_id: str, key_id: str) -> tuple[OrgApiKey, str] | None:
        """Atomically revoke an active key and create its unique replacement."""
        async with self._engine.raw.begin() as conn:
            old = (
                await conn.execute(
                    select(org_api_keys, org_api_key_metadata)
                    .outerjoin(
                        org_api_key_metadata,
                        org_api_key_metadata.c.key_id == org_api_keys.c.id,
                    )
                    .where(
                        org_api_keys.c.id == key_id,
                        org_api_keys.c.org_id == org_id,
                        org_api_keys.c.revoked == 0,
                    )
                )
            ).fetchone()
            if old is None:
                return None
            await bump_epoch_on_connection(conn, org_id)
            environment = getattr(old, "environment", None)
            environment = environment if environment in {"test", "live"} else "live"
            replacement = OrgApiKey(
                org_id=org_id,
                name=old.name,
                role=role_from_str(old.role),
                created_at=_now(),
                prefix=f"wp_{environment}_",
                environment=environment,
                scopes=tuple(json.loads(getattr(old, "scopes", "[]") or "[]")),
                expires_at=getattr(old, "expires_at", None),
                rotated_from_id=old.id,
            )
            raw = _generate_raw_key(environment)
            await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.id == old.id, org_api_keys.c.org_id == org_id)
                .values(revoked=1)
            )
            await conn.execute(
                insert(org_api_keys).values(
                    id=replacement.id,
                    org_id=org_id,
                    key_hash=_hash_key(raw),
                    name=replacement.name,
                    role=replacement.role.value,
                    created_at=replacement.created_at,
                    revoked=0,
                )
            )
            await conn.execute(
                insert(org_api_key_metadata).values(
                    key_id=replacement.id,
                    prefix=replacement.prefix,
                    environment=replacement.environment,
                    scopes=json.dumps(list(replacement.scopes)),
                    expires_at=replacement.expires_at,
                    rotated_from_id=old.id,
                )
            )
        return replacement, raw

    async def list_keys(self, org_id: str) -> list[OrgApiKey]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(org_api_keys, org_api_key_metadata)
                    .outerjoin(
                        org_api_key_metadata,
                        org_api_key_metadata.c.key_id == org_api_keys.c.id,
                    )
                    .where(org_api_keys.c.org_id == org_id)
                    .where(org_api_keys.c.revoked == 0)
                )
            ).fetchall()
        return [self._row_to_key(r) for r in rows]

    async def authenticate(self, raw_key: str) -> OrgContext | None:
        """Verify a raw key, update last_used_at, return OrgContext or None."""
        key_hash = _hash_key(raw_key)
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(org_api_keys, org_api_key_metadata)
                    .outerjoin(
                        org_api_key_metadata,
                        org_api_key_metadata.c.key_id == org_api_keys.c.id,
                    )
                    .where(org_api_keys.c.key_hash == key_hash)
                    .where(org_api_keys.c.revoked == 0)
                )
            ).fetchone()

        if row is None:
            return None

        expires_at = getattr(row, "expires_at", None)
        if expires_at and expires_at <= _now():
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
            scopes=frozenset(json.loads(getattr(row, "scopes", "[]") or "[]")),
        )

    # ── MFA (TOTP) ────────────────────────────────────────────────────────────

    async def get_key(self, key_id: str) -> OrgApiKey | None:
        """Fetch a key by ID, including its MFA secret/backup codes.
        Server-side use only (login/enroll flows) — never returned to a
        client as-is; OrgApiKey.to_dict() already omits those fields."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(org_api_keys, org_api_key_metadata)
                    .outerjoin(
                        org_api_key_metadata,
                        org_api_key_metadata.c.key_id == org_api_keys.c.id,
                    )
                    .where(org_api_keys.c.id == key_id)
                )
            ).fetchone()
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
            subscription_status=getattr(row, "subscription_status", "inactive") or "inactive",
            sso_required=bool(getattr(row, "sso_required", 0)),
            mfa_required=bool(getattr(row, "mfa_required", 0)),
            provisioner_key_id=getattr(row, "provisioner_key_id", None),
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
            prefix=getattr(row, "prefix", "rai_") or "rai_",
            environment=getattr(row, "environment", "legacy") or "legacy",
            scopes=tuple(json.loads(getattr(row, "scopes", "[]") or "[]")),
            expires_at=getattr(row, "expires_at", None),
            rotated_from_id=getattr(row, "rotated_from_id", None),
        )
