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

from sqlalchemy import delete, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import (
    DatabaseEngine,
    org_api_key_metadata,
    org_api_keys,
    organizations,
    tenant_tombstones,
)
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection
from responsibleai.rbac.models import (
    GovernanceStatus,
    Organization,
    OrgApiKey,
    OrgContext,
    Plan,
    Role,
    is_equal_timestamp_transition_allowed,
)
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


_BASE_ORG_COLUMNS = (
    organizations.c.id,
    organizations.c.name,
    organizations.c.slug,
    organizations.c.monthly_budget_usd,
    organizations.c.created_at,
    organizations.c.plan,
    organizations.c.stripe_customer_id,
    organizations.c.stripe_subscription_id,
    organizations.c.plan_renews_at,
    organizations.c.subscription_status,
    organizations.c.sso_required,
    organizations.c.mfa_required,
    organizations.c.provisioner_key_id,
)


class OrgRepository:
    """CRUD operations for organizations and their API keys."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def _execute_org_select(self, conn: Any, where_clause: Any = None) -> Any:
        stmt = select(organizations)
        if where_clause is not None:
            stmt = stmt.where(where_clause)
        try:
            return await conn.execute(stmt)
        except Exception:
            await conn.rollback()
            fallback_stmt = select(*_BASE_ORG_COLUMNS).select_from(organizations)
            if where_clause is not None:
                fallback_stmt = fallback_stmt.where(where_clause)
            return await conn.execute(fallback_stmt)

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

    async def set_governance_status(self, org_id: str, status: str | GovernanceStatus) -> bool:
        """Human/admin organization lifecycle. Never called from billing webhooks.

        Atomically updates ``organizations.governance_status`` and bumps the
        governance revocation epoch in the same transaction.
        """
        normalized = status.value if isinstance(status, GovernanceStatus) else str(status).upper()
        if normalized not in {item.value for item in GovernanceStatus}:
            raise ValueError(f"invalid governance_status: {status!r}")
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(governance_status=normalized)
            )
            if result.rowcount == 0:
                return False
            await bump_epoch_on_connection(conn, org_id)
        return True

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
            res = await self._execute_org_select(
                conn, organizations.c.stripe_customer_id == stripe_customer_id
            )
            row = res.fetchone()
        return self._row_to_org(row) if row else None

    async def get_org_by_paddle_customer(self, paddle_customer_id: str) -> Organization | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(organizations).where(
                        organizations.c.paddle_customer_id == paddle_customer_id
                    )
                )
            ).fetchone()
        return self._row_to_org(row) if row else None

    async def get_org_by_paddle_subscription(self, paddle_subscription_id: str) -> Organization | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(organizations).where(
                        organizations.c.paddle_subscription_id == paddle_subscription_id
                    )
                )
            ).fetchone()
        return self._row_to_org(row) if row else None

    async def apply_paddle_entitlement(
        self,
        *,
        org_id: str,
        customer_id: str,
        subscription_id: str | None,
        plan: Plan,
        subscription_status: str = "active",
        occurred_at: str | None = None,
        event_version: int = 0,
        updated_at: str | None = None,
    ) -> bool:
        """Apply one already signature-verified Paddle event in chronological order.

        Uses real Paddle occurred_at timestamp comparison for monotonic ordering.
        Synthetic event_version is deprecated and non-operative.
        Database-level row locking (FOR UPDATE) and unique index constraints
        guarantee strict concurrency isolation and zero cross-tenant binding.
        This repository method controls commercial features only. It is never
        consulted by Trust, authority, policy, or ExecutionAuthorization.
        """
        if not customer_id.startswith("ctm_"):
            raise ValueError("Paddle customer identity must use a ctm_ identifier")
        if subscription_id is not None and not subscription_id.startswith("sub_"):
            raise ValueError("Paddle subscription identity must use a sub_ identifier")
        effective_occurred = occurred_at or updated_at
        if not effective_occurred:
            raise ValueError("Paddle occurred_at timestamp is required for entitlement updates")

        normalized_status = subscription_status.casefold()
        effective_plan = plan if normalized_status in {"active", "trialing"} else Plan.FREE

        try:
            async with self._engine.raw.begin() as conn:
                # 1. Lock the organization row for update to ensure atomic chronology evaluation
                org_row = (await conn.execute(
                    select(organizations).where(organizations.c.id == org_id).with_for_update()
                )).first()
                if org_row is None:
                    raise ValueError(f"Organization '{org_id}' not found")

                # Check tombstone ledger
                ts = await conn.scalar(
                    select(tenant_tombstones.c.id).where(tenant_tombstones.c.org_id == org_id)
                )
                if ts is not None:
                    raise ValueError(f"Cannot apply entitlement: organization '{org_id}' is tombstoned")

                # 2. Prevent commercial identity reassignment across tenants
                existing_customer_org = await conn.scalar(
                    select(organizations.c.id).where(
                        organizations.c.paddle_customer_id == customer_id,
                        organizations.c.id != org_id,
                    )
                )
                if existing_customer_org is not None:
                    raise ValueError("Paddle customer is already bound to another tenant")

                if subscription_id is not None:
                    existing_sub_org = await conn.scalar(
                        select(organizations.c.id).where(
                            organizations.c.paddle_subscription_id == subscription_id,
                            organizations.c.id != org_id,
                        )
                    )
                    if existing_sub_org is not None:
                        raise ValueError("Paddle subscription is already bound to another tenant")

                # 3. Chronological admission check using occurred_at
                org_map = dict(org_row._mapping)
                current_occurred_at = org_map.get("paddle_last_occurred_at") or org_map.get("entitlement_updated_at")
                current_status = org_map.get("subscription_status") or "inactive"
                current_plan_str = str(org_map.get("plan") or "FREE").upper()

                if current_occurred_at:
                    if effective_occurred < current_occurred_at:
                        # Out-of-order stale event: safely ignored
                        return False
                    if effective_occurred == current_occurred_at:
                        # Equal timestamp fail-safe: never widen commercial entitlement on ambiguous equal timestamp
                        if not is_equal_timestamp_transition_allowed(
                            current_plan=current_plan_str,
                            current_status=current_status,
                            incoming_plan=plan,
                            incoming_status=normalized_status,
                        ):
                            return False

                values: dict[str, Any] = {
                    "paddle_customer_id": customer_id,
                    "paddle_subscription_id": subscription_id,
                    "plan": effective_plan.value,
                    "subscription_status": normalized_status,
                    "entitlement_updated_at": effective_occurred,
                    "entitlement_version": 0,
                }
                if "paddle_last_occurred_at" in organizations.c:
                    values["paddle_last_occurred_at"] = effective_occurred

                res = await conn.execute(
                    update(organizations)
                    .where(
                        organizations.c.id == org_id,
                        or_(
                            organizations.c.paddle_last_occurred_at.is_(None),
                            organizations.c.paddle_last_occurred_at <= effective_occurred,
                        ),
                    )
                    .values(**values)
                )
                return res.rowcount > 0
        except IntegrityError as exc:
            err_str = str(exc).lower()
            if "idx_org_paddle_subscription" in err_str or "paddle_subscription_id" in err_str:
                raise ValueError("Paddle subscription is already bound to another tenant") from exc
            if "idx_org_paddle_customer" in err_str or "paddle_customer_id" in err_str:
                raise ValueError("Paddle customer is already bound to another tenant") from exc
            raise

    async def get_org(self, org_id: str) -> Organization | None:
        async with self._engine.raw.connect() as conn:
            res = await self._execute_org_select(conn, organizations.c.id == org_id)
            row = res.fetchone()
        return self._row_to_org(row) if row else None

    async def get_org_by_slug(self, slug: str) -> Organization | None:
        async with self._engine.raw.connect() as conn:
            res = await self._execute_org_select(conn, organizations.c.slug == slug)
            row = res.fetchone()
        return self._row_to_org(row) if row else None

    async def list_orgs(self) -> list[Organization]:
        async with self._engine.raw.connect() as conn:
            res = await self._execute_org_select(conn)
            rows = res.fetchall()
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
            paddle_customer_id=getattr(row, "paddle_customer_id", None),
            paddle_subscription_id=getattr(row, "paddle_subscription_id", None),
            entitlement_version=getattr(row, "entitlement_version", 0) or 0,
            entitlement_updated_at=getattr(row, "entitlement_updated_at", None),
            paddle_last_occurred_at=getattr(row, "paddle_last_occurred_at", None),
            plan_renews_at=getattr(row, "plan_renews_at", None),
            subscription_status=getattr(row, "subscription_status", "inactive") or "inactive",
            governance_status=getattr(row, "governance_status", GovernanceStatus.ACTIVE.value)
            or GovernanceStatus.ACTIVE.value,
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
