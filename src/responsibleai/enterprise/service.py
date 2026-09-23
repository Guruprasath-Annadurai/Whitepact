# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise IAM service: orgs, membership, environments, keys, service accounts.

Fail closed. Database errors deny. Redis is never consulted for authorization.
API-key possession never equals execution authority.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import secrets
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from responsibleai.db.engine import (
    DatabaseEngine,
    api_key_issuance_decisions,
    enterprise_environments,
    enterprise_service_account_environments,
    enterprise_service_accounts,
    org_api_key_metadata,
    org_api_keys,
    organizations,
    web_invitations,
    web_memberships,
    web_sessions,
    web_users,
)
from responsibleai.enterprise.audit import EnterpriseAuditLog
from responsibleai.enterprise.errors import (
    API_KEY_ISSUANCE_NOT_ALLOWED,
    ENVIRONMENT_DISABLED,
    FORBIDDEN,
    INSUFFICIENT_SCOPE,
    INVITE_EXPIRED,
    INVITE_REPLAY,
    INVITE_REVOKED,
    KEY_EXPIRED,
    KEY_REVOKED,
    LAST_OWNER,
    MEMBERSHIP_REVOKED,
    ORG_DISABLED,
    ORG_SUSPENDED,
    SERVICE_ACCOUNT_FORBIDDEN,
    VERIFICATION_SUSPENDED,
    WRONG_ENVIRONMENT,
    WRONG_TENANT,
    EnterpriseError,
    forbidden,
)
from responsibleai.enterprise.roles import (
    CANONICAL_SCOPES,
    Permission,
    has_rbac_permission,
    role_privilege,
)
from responsibleai.rbac.models import GovernanceStatus, Role
from responsibleai.rbac.permissions import role_from_str
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN

logger = logging.getLogger(__name__)

_INVITE_TTL_HOURS = 168
_KEY_PREFIX = {
    "DEVELOPMENT": "wp_test_",
    "STAGING": "wp_staging_",
    "PRODUCTION": "wp_live_",
}


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _hash_secret(raw: str) -> str:
    # codeql[py/weak-sensitive-data-hashing]: one-way digest of API secrets at rest, not password storage.
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _hash_token(raw: str) -> str:
    # codeql[py/weak-sensitive-data-hashing]: one-way digest of opaque session tokens, not password storage.
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class Actor:
    actor_type: str  # human | service_account | api_key | system
    actor_id: str
    user_id: str | None
    org_id: str
    role: Role
    membership_status: str
    environment_id: str | None = None
    scopes: frozenset[str] = frozenset()
    request_id: str | None = None


class EnterpriseIAM:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self.audit = EnterpriseAuditLog(engine)

    async def _deny_if_db_fails(self, fn, *, action: str) -> Any:
        try:
            return await fn()
        except EnterpriseError:
            raise
        except SQLAlchemyError:
            logger.exception("enterprise_authz_db_failure", extra={"action": action})
            raise forbidden(FORBIDDEN, "Authorization backend unavailable.") from None

    # ── Authorization ────────────────────────────────────────────────────────

    async def authorize(
        self,
        actor: Actor,
        permission: Permission,
        *,
        org_id: str,
        environment_id: str | None = None,
        required_scope: str | None = None,
    ) -> None:
        async def _inner() -> None:
            if actor.org_id != org_id:
                raise forbidden(WRONG_TENANT, "Cross-tenant access is denied.")
            if actor.membership_status != "ACTIVE" and actor.actor_type == "human":
                raise forbidden(MEMBERSHIP_REVOKED, "Membership is not active.")
            org = await self._load_org(org_id)
            if org is None:
                raise forbidden(WRONG_TENANT, "Organization not found.")
            gov = org["governance_status"]
            if gov == GovernanceStatus.DISABLED.value or org.get("deactivated_at"):
                raise forbidden(ORG_DISABLED, "Organization is disabled.")
            if gov == GovernanceStatus.SUSPENDED.value and permission not in {
                Permission.ORG_VIEW,
                Permission.AUDIT_READ,
                Permission.SESSIONS_REVOKE,
                Permission.CREDENTIALS_EMERGENCY_REVOKE,
            }:
                raise forbidden(ORG_SUSPENDED, "Organization is suspended.")
            if not has_rbac_permission(actor.role, permission):
                raise forbidden(FORBIDDEN, "Insufficient administrative permission.")
            if required_scope:
                if required_scope not in actor.scopes and actor.actor_type == "api_key":
                    raise forbidden(INSUFFICIENT_SCOPE, "API key lacks required scope.")
            if environment_id:
                env = await self.get_environment(org_id, environment_id)
                if env is None:
                    raise forbidden(
                        WRONG_ENVIRONMENT, "Environment not found in this organization."
                    )
                if env["status"] != "ACTIVE":
                    raise forbidden(ENVIRONMENT_DISABLED, "Environment is not active.")
                if actor.environment_id and actor.environment_id != environment_id:
                    raise forbidden(
                        WRONG_ENVIRONMENT, "Credential is bound to a different environment."
                    )
            # Compiled-in reminder: this function never opens Gate B.
            if PRODUCTION_GATE_B_OPEN:
                raise forbidden(FORBIDDEN, "Unexpected production gate state.")

        await self._deny_if_db_fails(_inner, action=f"authorize:{permission.value}")

    async def _load_org(self, org_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(select(organizations).where(organizations.c.id == org_id))
            ).fetchone()
        return dict(row._mapping) if row else None

    # ── Organizations / workspaces ───────────────────────────────────────────

    async def create_workspace(
        self,
        *,
        actor_user_id: str,
        name: str,
        slug: str,
        kind: str,
        request_id: str | None = None,
    ) -> dict[str, Any]:
        kind = kind.upper()
        if kind not in {"ORGANIZATION", "INDIVIDUAL"}:
            raise forbidden(FORBIDDEN, "Workspace kind must be ORGANIZATION or INDIVIDUAL.")
        now = _iso()
        org_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
            user = (
                await conn.execute(
                    select(web_users).where(
                        web_users.c.id == actor_user_id, web_users.c.disabled == 0
                    )
                )
            ).fetchone()
            if user is None:
                raise forbidden(FORBIDDEN, "Account is not eligible to create a workspace.")
            await conn.execute(
                insert(organizations).values(
                    id=org_id,
                    name=name.strip(),
                    slug=slug.strip(),
                    monthly_budget_usd=10_000.0,
                    created_at=now,
                    plan="FREE",
                    sso_required=0,
                    mfa_required=0,
                    governance_status=GovernanceStatus.ACTIVE.value,
                    workspace_kind=kind,
                    owner_user_id=actor_user_id,
                    settings_json="{}",
                )
            )
            await conn.execute(
                insert(web_memberships).values(
                    id=str(uuid.uuid4()),
                    user_id=actor_user_id,
                    org_id=org_id,
                    role=Role.OWNER.value,
                    status="ACTIVE",
                    invited_by_user_id=None,
                    accepted_at=now,
                    created_at=now,
                    updated_at=now,
                )
            )
            for env_type, env_name in (
                ("DEVELOPMENT", "Development"),
                ("STAGING", "Staging"),
                ("PRODUCTION", "Production"),
            ):
                await conn.execute(
                    insert(enterprise_environments).values(
                        id=str(uuid.uuid4()),
                        org_id=org_id,
                        type=env_type,
                        name=env_name,
                        status="ACTIVE",
                        created_at=now,
                        metadata_json=json.dumps({"stricter_defaults": env_type == "PRODUCTION"}),
                    )
                )
        await self.audit.record(
            org_id=org_id,
            actor_type="human",
            actor_id=actor_user_id,
            action="org.created",
            target_type="organization",
            target_id=org_id,
            result="ALLOWED",
            request_id=request_id,
            metadata={"kind": kind},
        )
        org = await self._load_org(org_id)
        assert org is not None
        return org

    async def list_visible_workspaces(self, user_id: str) -> list[dict[str, Any]]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(
                        organizations.c.id,
                        organizations.c.name,
                        organizations.c.slug,
                        organizations.c.workspace_kind,
                        organizations.c.governance_status,
                        organizations.c.owner_user_id,
                        web_memberships.c.role,
                        web_memberships.c.status,
                    )
                    .join(web_memberships, web_memberships.c.org_id == organizations.c.id)
                    .where(
                        web_memberships.c.user_id == user_id,
                        web_memberships.c.status == "ACTIVE",
                    )
                    .order_by(organizations.c.name)
                )
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    async def update_settings(
        self,
        actor: Actor,
        org_id: str,
        *,
        display_name: str | None,
        settings: dict[str, Any] | None,
    ) -> dict[str, Any]:
        await self.authorize(actor, Permission.ORG_UPDATE_SETTINGS, org_id=org_id)
        values: dict[str, Any] = {}
        if display_name is not None:
            values["name"] = display_name.strip()
        if settings is not None:
            blocked = {"governance_status", "plan", "stripe_customer_id", "paddle_customer_id"}
            safe = {k: v for k, v in settings.items() if k not in blocked}
            values["settings_json"] = json.dumps(safe)
        if not values:
            org = await self._load_org(org_id)
            assert org is not None
            return org
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(organizations).where(organizations.c.id == org_id).values(**values)
            )
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="org.settings_changed",
            target_type="organization",
            target_id=org_id,
            result="ALLOWED",
            request_id=actor.request_id,
        )
        org = await self._load_org(org_id)
        assert org is not None
        return org

    async def deactivate_organization(self, actor: Actor, org_id: str) -> None:
        await self.authorize(actor, Permission.ORG_DEACTIVATE, org_id=org_id)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(
                    governance_status=GovernanceStatus.DISABLED.value,
                    deactivated_at=_iso(),
                )
            )
            await conn.execute(
                update(org_api_keys)
                .where(org_api_keys.c.org_id == org_id, org_api_keys.c.revoked == 0)
                .values(revoked=1, revoked_at=_iso())
            )
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.org_id == org_id, web_sessions.c.revoked == 0)
                .values(revoked=1)
            )
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="org.deactivated",
            target_type="organization",
            target_id=org_id,
            result="ALLOWED",
            request_id=actor.request_id,
        )

    async def transfer_ownership(
        self,
        actor: Actor,
        org_id: str,
        *,
        new_owner_user_id: str,
        confirmation: str,
    ) -> None:
        await self.authorize(actor, Permission.ORG_TRANSFER_OWNERSHIP, org_id=org_id)
        if confirmation != "TRANSFER_OWNERSHIP":
            raise forbidden(FORBIDDEN, "Ownership transfer requires explicit confirmation.")
        if actor.role != Role.OWNER:
            raise forbidden(FORBIDDEN, "Only the current owner may transfer ownership.")
        async with self._engine.raw.begin() as conn:
            dialect = conn.engine.dialect.name
            lock = select(web_memberships).where(web_memberships.c.org_id == org_id)
            if dialect != "sqlite":
                lock = lock.with_for_update()
            rows = (await conn.execute(lock)).fetchall()
            current_owners = [
                r for r in rows if r.role == Role.OWNER.value and r.status == "ACTIVE"
            ]
            target = next(
                (r for r in rows if r.user_id == new_owner_user_id and r.status == "ACTIVE"), None
            )
            if target is None:
                raise forbidden(FORBIDDEN, "New owner must be an active member.")
            if not current_owners or actor.user_id not in {r.user_id for r in current_owners}:
                raise forbidden(FORBIDDEN, "Caller is not the current owner.")
            await conn.execute(
                update(web_memberships)
                .where(
                    web_memberships.c.org_id == org_id,
                    web_memberships.c.user_id == actor.user_id,
                    web_memberships.c.role == Role.OWNER.value,
                    web_memberships.c.status == "ACTIVE",
                )
                .values(role=Role.ADMIN.value, updated_at=_iso())
            )
            await conn.execute(
                update(web_memberships)
                .where(
                    web_memberships.c.org_id == org_id,
                    web_memberships.c.user_id == new_owner_user_id,
                    web_memberships.c.status == "ACTIVE",
                )
                .values(role=Role.OWNER.value, updated_at=_iso())
            )
            await conn.execute(
                update(organizations)
                .where(organizations.c.id == org_id)
                .values(owner_user_id=new_owner_user_id)
            )
            await conn.execute(
                update(web_sessions)
                .where(
                    web_sessions.c.org_id == org_id,
                    web_sessions.c.user_id.in_([actor.user_id, new_owner_user_id]),
                )
                .values(revoked=1)
            )
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="org.ownership_transferred",
            target_type="user",
            target_id=new_owner_user_id,
            result="ALLOWED",
            request_id=actor.request_id,
        )

    # ── Membership / invitations ─────────────────────────────────────────────

    async def invite_member(
        self, actor: Actor, org_id: str, *, email: str, role: Role
    ) -> tuple[str, str]:
        await self.authorize(actor, Permission.MEMBERS_INVITE, org_id=org_id)
        if role == Role.OWNER:
            raise forbidden(FORBIDDEN, "Cannot invite an owner; transfer ownership instead.")
        if role_privilege(role) >= role_privilege(actor.role) and actor.role != Role.OWNER:
            raise forbidden(FORBIDDEN, "Cannot assign a role at or above your own.")
        token = secrets.token_urlsafe(32)
        invitation_id = str(uuid.uuid4())
        now = _now()
        normalized = email.strip().casefold()
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(web_invitations)
                .where(
                    web_invitations.c.org_id == org_id,
                    web_invitations.c.email == normalized,
                    web_invitations.c.status.in_(("PENDING", "INVITED")),
                )
                .values(status="REVOKED")
            )
            await conn.execute(
                insert(web_invitations).values(
                    id=invitation_id,
                    token_hash=_hash_token(token),
                    org_id=org_id,
                    email=normalized,
                    role=role.value,
                    invited_by_user_id=actor.user_id,
                    accepted_by_user_id=None,
                    status="INVITED",
                    created_at=_iso(now),
                    expires_at=_iso(now + timedelta(hours=_INVITE_TTL_HOURS)),
                    consumed_at=None,
                )
            )
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="membership.invited",
            target_type="invitation",
            target_id=invitation_id,
            result="ALLOWED",
            request_id=actor.request_id,
            metadata={"role": role.value, "email_domain": normalized.split("@")[-1]},
        )
        return invitation_id, token

    async def accept_invitation(
        self, *, token: str, user_id: str, request_id: str | None = None
    ) -> str:
        now = _now()
        token_hash = _hash_token(token)
        async with self._engine.raw.begin() as conn:
            dialect = conn.engine.dialect.name
            user = (
                await conn.execute(
                    select(web_users).where(
                        web_users.c.id == user_id,
                        web_users.c.disabled == 0,
                    )
                )
            ).fetchone()
            stmt = select(web_invitations).where(web_invitations.c.token_hash == token_hash)
            if dialect != "sqlite":
                stmt = stmt.with_for_update()
            invitation = (await conn.execute(stmt)).fetchone()
            if invitation is None:
                raise forbidden(FORBIDDEN, "Invitation not found.")
            if invitation.status == "REVOKED":
                raise forbidden(INVITE_REVOKED, "Invitation has been revoked.")
            if invitation.status == "ACCEPTED":
                raise forbidden(INVITE_REPLAY, "Invitation has already been used.")
            if invitation.status not in {"PENDING", "INVITED"}:
                raise forbidden(FORBIDDEN, "Invitation is not acceptable.")
            if invitation.expires_at <= _iso(now):
                raise forbidden(INVITE_EXPIRED, "Invitation has expired.")
            if user is None or user.email != invitation.email:
                raise forbidden(FORBIDDEN, "Invitation belongs to a different account.")
            claimed = await conn.execute(
                update(web_invitations)
                .where(
                    web_invitations.c.id == invitation.id,
                    web_invitations.c.status.in_(("PENDING", "INVITED")),
                    web_invitations.c.consumed_at.is_(None),
                )
                .values(status="ACCEPTED", accepted_by_user_id=user_id, consumed_at=_iso(now))
            )
            if (claimed.rowcount or 0) != 1:
                raise forbidden(INVITE_REPLAY, "Invitation has already been used.")
            existing = (
                await conn.execute(
                    select(web_memberships).where(
                        web_memberships.c.user_id == user_id,
                        web_memberships.c.org_id == invitation.org_id,
                    )
                )
            ).fetchone()
            if existing is not None:
                if existing.status == "ACTIVE":
                    raise forbidden(FORBIDDEN, "Active membership already exists.")
                await conn.execute(
                    update(web_memberships)
                    .where(web_memberships.c.id == existing.id)
                    .values(
                        role=invitation.role,
                        status="ACTIVE",
                        invited_by_user_id=invitation.invited_by_user_id,
                        accepted_at=_iso(now),
                        revoked_at=None,
                        updated_at=_iso(now),
                    )
                )
            else:
                try:
                    await conn.execute(
                        insert(web_memberships).values(
                            id=str(uuid.uuid4()),
                            user_id=user_id,
                            org_id=invitation.org_id,
                            role=invitation.role,
                            status="ACTIVE",
                            invited_by_user_id=invitation.invited_by_user_id,
                            accepted_at=_iso(now),
                            created_at=_iso(now),
                            updated_at=_iso(now),
                        )
                    )
                except IntegrityError as exc:
                    raise forbidden(FORBIDDEN, "Active membership already exists.") from exc
        await self.audit.record(
            org_id=str(invitation.org_id),
            actor_type="human",
            actor_id=user_id,
            action="membership.accepted",
            target_type="invitation",
            target_id=str(invitation.id),
            result="ALLOWED",
            request_id=request_id,
        )
        return str(invitation.org_id)

    async def change_role(self, actor: Actor, org_id: str, *, user_id: str, role: Role) -> None:
        await self.authorize(actor, Permission.MEMBERS_UPDATE_ROLE, org_id=org_id)
        if role == Role.OWNER:
            raise forbidden(FORBIDDEN, "Use ownership transfer to grant OWNER.")
        if role_privilege(role) >= role_privilege(actor.role) and actor.role != Role.OWNER:
            raise forbidden(FORBIDDEN, "Cannot escalate a member to your role or above.")
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(web_memberships)
                .where(
                    web_memberships.c.org_id == org_id,
                    web_memberships.c.user_id == user_id,
                    web_memberships.c.status == "ACTIVE",
                    web_memberships.c.role != Role.OWNER.value,
                )
                .values(role=role.value, updated_at=_iso())
            )
            if (result.rowcount or 0) != 1:
                raise forbidden(FORBIDDEN, "Membership role was not changed.")
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="membership.role_changed",
            target_type="user",
            target_id=user_id,
            result="ALLOWED",
            request_id=actor.request_id,
            metadata={"role": role.value},
        )

    async def revoke_member(self, actor: Actor, org_id: str, *, user_id: str) -> None:
        await self.authorize(actor, Permission.MEMBERS_REVOKE, org_id=org_id)
        async with self._engine.raw.begin() as conn:
            dialect = conn.engine.dialect.name
            stmt = select(web_memberships).where(
                web_memberships.c.org_id == org_id,
                web_memberships.c.user_id == user_id,
            )
            if dialect != "sqlite":
                stmt = stmt.with_for_update()
            membership = (await conn.execute(stmt)).fetchone()
            if membership is None or membership.status != "ACTIVE":
                raise forbidden(FORBIDDEN, "Active membership not found.")
            if membership.role == Role.OWNER.value:
                owners = await conn.scalar(
                    select(func.count())
                    .select_from(web_memberships)
                    .where(
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.role == Role.OWNER.value,
                        web_memberships.c.status == "ACTIVE",
                    )
                )
                if (owners or 0) <= 1:
                    raise EnterpriseError(LAST_OWNER, "Cannot remove the last owner.", 409)
                if actor.user_id != user_id and actor.role != Role.OWNER:
                    raise forbidden(FORBIDDEN, "Only an owner may remove another owner.")
            await conn.execute(
                update(web_memberships)
                .where(web_memberships.c.id == membership.id)
                .values(status="REVOKED", revoked_at=_iso(), updated_at=_iso())
            )
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.user_id == user_id, web_sessions.c.org_id == org_id)
                .values(revoked=1)
            )
            await conn.execute(
                update(org_api_keys)
                .where(
                    org_api_keys.c.org_id == org_id,
                    org_api_keys.c.revoked == 0,
                    or_(
                        org_api_keys.c.created_by_user_id == user_id,
                        org_api_keys.c.accountable_human_user_id == user_id,
                    ),
                )
                .values(revoked=1, revoked_at=_iso())
            )
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="membership.revoked",
            target_type="user",
            target_id=user_id,
            result="ALLOWED",
            request_id=actor.request_id,
        )

    async def list_members(self, actor: Actor, org_id: str) -> list[dict[str, Any]]:
        await self.authorize(actor, Permission.ORG_VIEW, org_id=org_id)
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(
                        web_memberships.c.id,
                        web_memberships.c.user_id,
                        web_memberships.c.role,
                        web_memberships.c.status,
                        web_memberships.c.invited_by_user_id,
                        web_memberships.c.created_at,
                        web_memberships.c.accepted_at,
                        web_memberships.c.revoked_at,
                        web_users.c.email,
                        web_users.c.full_name,
                        web_users.c.verification_status,
                    )
                    .join(web_users, web_users.c.id == web_memberships.c.user_id)
                    .where(web_memberships.c.org_id == org_id)
                )
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    # ── Environments ─────────────────────────────────────────────────────────

    async def ensure_default_environments(self, org_id: str) -> None:
        async with self._engine.raw.begin() as conn:
            existing = (
                await conn.execute(
                    select(enterprise_environments.c.id).where(
                        enterprise_environments.c.org_id == org_id
                    )
                )
            ).fetchall()
            if existing:
                return
            now = _iso()
            for env_type, env_name in (
                ("DEVELOPMENT", "Development"),
                ("STAGING", "Staging"),
                ("PRODUCTION", "Production"),
            ):
                await conn.execute(
                    insert(enterprise_environments).values(
                        id=str(uuid.uuid4()),
                        org_id=org_id,
                        type=env_type,
                        name=env_name,
                        status="ACTIVE",
                        created_at=now,
                        metadata_json=json.dumps({"stricter_defaults": env_type == "PRODUCTION"}),
                    )
                )

    async def list_environments(self, actor: Actor, org_id: str) -> list[dict[str, Any]]:
        await self.authorize(actor, Permission.ENV_READ, org_id=org_id)
        await self.ensure_default_environments(org_id)
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(enterprise_environments).where(
                        enterprise_environments.c.org_id == org_id,
                        enterprise_environments.c.status != "DELETED",
                    )
                )
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    async def create_environment(
        self, actor: Actor, org_id: str, *, env_type: str, name: str
    ) -> dict[str, Any]:
        await self.authorize(actor, Permission.ENV_WRITE, org_id=org_id)
        env_type = env_type.upper()
        if env_type not in {"DEVELOPMENT", "STAGING", "PRODUCTION"}:
            raise forbidden(FORBIDDEN, "Invalid environment type.")
        env_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(enterprise_environments).values(
                    id=env_id,
                    org_id=org_id,
                    type=env_type,
                    name=name.strip(),
                    status="ACTIVE",
                    created_at=_iso(),
                    metadata_json=json.dumps({"stricter_defaults": env_type == "PRODUCTION"}),
                )
            )
        await self.audit.record(
            org_id=org_id,
            environment_id=env_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="environment.created",
            target_type="environment",
            target_id=env_id,
            result="ALLOWED",
            request_id=actor.request_id,
        )
        env = await self.get_environment(org_id, env_id)
        assert env is not None
        return env

    async def get_environment(self, org_id: str, environment_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(enterprise_environments).where(
                        enterprise_environments.c.id == environment_id,
                        enterprise_environments.c.org_id == org_id,
                    )
                )
            ).fetchone()
        return dict(row._mapping) if row else None

    async def set_environment_status(
        self, actor: Actor, org_id: str, environment_id: str, status: str
    ) -> None:
        await self.authorize(
            actor, Permission.ENV_WRITE, org_id=org_id, environment_id=environment_id
        )
        if status not in {"ACTIVE", "DISABLED", "DELETED"}:
            raise forbidden(FORBIDDEN, "Invalid environment status.")
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(enterprise_environments)
                .where(
                    enterprise_environments.c.id == environment_id,
                    enterprise_environments.c.org_id == org_id,
                )
                .values(status=status)
            )
            if (result.rowcount or 0) != 1:
                raise forbidden(WRONG_ENVIRONMENT, "Environment not found.")
        await self.audit.record(
            org_id=org_id,
            environment_id=environment_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="environment.changed",
            target_type="environment",
            target_id=environment_id,
            result="ALLOWED",
            request_id=actor.request_id,
            metadata={"status": status},
        )

    # ── API keys ─────────────────────────────────────────────────────────────

    def _generate_raw_key(self, env_type: str) -> tuple[str, str]:
        prefix = _KEY_PREFIX.get(env_type, "wp_test_")
        return prefix, prefix + secrets.token_urlsafe(32)

    async def create_api_key(
        self,
        actor: Actor,
        org_id: str,
        *,
        name: str,
        environment_id: str,
        scopes: tuple[str, ...],
        expires_at: str | None,
        service_account_id: str | None = None,
        overlap_not_used: None = None,
    ) -> tuple[dict[str, Any], str]:
        await self.authorize(
            actor, Permission.API_KEYS_CREATE, org_id=org_id, environment_id=environment_id
        )
        from responsibleai.enterprise.eligibility import EligibilityGate
        from responsibleai.enterprise.preflight import identity_webhook_secret_from_env
        from responsibleai.enterprise.verification import (
            HmacVerificationProvider,
            VerificationService,
        )

        if not actor.user_id:
            raise forbidden(
                API_KEY_ISSUANCE_NOT_ALLOWED, "Credential provenance cannot be established."
            )
        if actor.actor_type != "human":
            raise forbidden(
                API_KEY_ISSUANCE_NOT_ALLOWED,
                "Only an authenticated IDENTITY_VERIFIED human may issue reusable credentials.",
            )
        secret = identity_webhook_secret_from_env()
        gate = EligibilityGate(
            self._engine,
            VerificationService(self._engine, HmacVerificationProvider(secret)),
        )
        decision = await gate.may_issue_api_key(
            principal_user_id=actor.user_id,
            organization_id=org_id,
            environment_id=environment_id,
            requested_scopes=scopes,
            role=actor.role,
            request_id=actor.request_id,
        )
        await self.record_issuance_decision(
            org_id=org_id,
            principal_user_id=actor.user_id,
            environment_id=environment_id,
            allowed=decision.allowed,
            reason_code=decision.reason_code,
            requested_scopes=scopes,
        )
        if not decision.allowed:
            raise EnterpriseError(decision.reason_code, decision.message, 403)
        unknown = set(scopes) - CANONICAL_SCOPES
        if unknown:
            raise forbidden(INSUFFICIENT_SCOPE, "Unknown API scopes requested.")
        env = await self.get_environment(org_id, environment_id)
        if env is None or env["status"] != "ACTIVE":
            raise forbidden(WRONG_ENVIRONMENT, "Environment is not usable.")
        holder_kind = "service_account" if service_account_id else "human_key"
        accountable = decision.accountable_human_user_id or actor.user_id
        if not accountable:
            raise forbidden(
                API_KEY_ISSUANCE_NOT_ALLOWED, "Credential provenance cannot be established."
            )
        prefix, raw = self._generate_raw_key(str(env["type"]))
        key_id = str(uuid.uuid4())
        key_hash = _hash_secret(raw)
        now = _iso()
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(org_api_keys).values(
                    id=key_id,
                    org_id=org_id,
                    key_hash=key_hash,
                    name=name,
                    role=Role.DEVELOPER.value
                    if holder_kind == "human_key"
                    else Role.DEVELOPER.value,
                    created_at=now,
                    revoked=0,
                    created_by_user_id=actor.user_id,
                    accountable_human_user_id=accountable,
                    service_account_id=service_account_id,
                    environment_id=environment_id,
                    holder_kind=holder_kind,
                )
            )
            await conn.execute(
                insert(org_api_key_metadata).values(
                    key_id=key_id,
                    prefix=prefix,
                    environment=str(env["type"]),
                    scopes=json.dumps(sorted(set(scopes))),
                    expires_at=expires_at,
                    rotated_from_id=None,
                )
            )
        await self.audit.record(
            org_id=org_id,
            environment_id=environment_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="api_key.created",
            target_type="api_key",
            target_id=key_id,
            result="ALLOWED",
            request_id=actor.request_id,
            metadata={"prefix": prefix, "scopes": sorted(set(scopes)), "holder_kind": holder_kind},
        )
        record = {
            "id": key_id,
            "org_id": org_id,
            "name": name,
            "prefix": prefix,
            "environment_id": environment_id,
            "environment_type": env["type"],
            "scopes": sorted(set(scopes)),
            "created_at": now,
            "expires_at": expires_at,
            "holder_kind": holder_kind,
            "accountable_human_user_id": accountable,
        }
        return record, raw

    async def issue_api_key(self, *args: Any, **kwargs: Any) -> tuple[dict[str, Any], str]:
        """Canonical hosted issuance alias. Never skip CredentialIssuancePolicy."""
        return await self.create_api_key(*args, **kwargs)

    async def rotate_api_key(
        self, actor: Actor, org_id: str, key_id: str, *, overlap_seconds: int = 0
    ) -> tuple[dict[str, Any], str]:
        await self.authorize(actor, Permission.API_KEYS_ROTATE, org_id=org_id)
        if actor.actor_type != "human" or not actor.user_id:
            raise forbidden(
                API_KEY_ISSUANCE_NOT_ALLOWED,
                "Only an authenticated IDENTITY_VERIFIED human may rotate credentials.",
            )
        async with self._engine.raw.connect() as conn:
            peek = (
                await conn.execute(
                    select(org_api_keys, org_api_key_metadata)
                    .outerjoin(
                        org_api_key_metadata, org_api_key_metadata.c.key_id == org_api_keys.c.id
                    )
                    .where(org_api_keys.c.id == key_id, org_api_keys.c.org_id == org_id)
                )
            ).fetchone()
        if peek is None:
            raise forbidden(WRONG_TENANT, "API key not found.")
        env_id = getattr(peek, "environment_id", None)
        if not env_id:
            raise forbidden(
                API_KEY_ISSUANCE_NOT_ALLOWED,
                "Keys without an environment binding cannot be rotated on the hosted path.",
            )
        from responsibleai.enterprise.eligibility import EligibilityGate
        from responsibleai.enterprise.preflight import identity_webhook_secret_from_env
        from responsibleai.enterprise.verification import (
            HmacVerificationProvider,
            VerificationService,
        )

        scopes = tuple(json.loads(getattr(peek, "scopes", "[]") or "[]"))
        gate = EligibilityGate(
            self._engine,
            VerificationService(
                self._engine, HmacVerificationProvider(identity_webhook_secret_from_env())
            ),
        )
        decision = await gate.may_issue_api_key(
            principal_user_id=actor.user_id,
            organization_id=org_id,
            environment_id=env_id,
            requested_scopes=scopes or ("usage:read",),
            role=actor.role,
            request_id=actor.request_id,
        )
        if not decision.allowed:
            raise EnterpriseError(decision.reason_code, decision.message, 403)
        now = _now()
        async with self._engine.raw.begin() as conn:
            dialect = conn.engine.dialect.name
            lock_stmt = select(org_api_keys).where(
                org_api_keys.c.id == key_id, org_api_keys.c.org_id == org_id
            )
            if dialect != "sqlite":
                lock_stmt = lock_stmt.with_for_update()
            locked = (await conn.execute(lock_stmt)).fetchone()
            if locked is None:
                raise forbidden(WRONG_TENANT, "API key not found.")
            if locked.revoked:
                raise forbidden(KEY_REVOKED, "Revoked keys cannot be rotated or resurrected.")
            old = (
                await conn.execute(
                    select(org_api_keys, org_api_key_metadata)
                    .outerjoin(
                        org_api_key_metadata,
                        org_api_key_metadata.c.key_id == org_api_keys.c.id,
                    )
                    .where(org_api_keys.c.id == key_id, org_api_keys.c.org_id == org_id)
                )
            ).fetchone()
            if old is None:
                raise forbidden(WRONG_TENANT, "API key not found.")
            env_id = getattr(old, "environment_id", None)
            env_type = getattr(old, "environment", None) or "DEVELOPMENT"
            prefix, raw = self._generate_raw_key(str(env_type))
            new_id = str(uuid.uuid4())
            scopes = json.loads(getattr(old, "scopes", "[]") or "[]")
            await conn.execute(
                insert(org_api_keys).values(
                    id=new_id,
                    org_id=org_id,
                    key_hash=_hash_secret(raw),
                    name=old.name,
                    role=old.role,
                    created_at=_iso(now),
                    revoked=0,
                    created_by_user_id=actor.user_id,
                    accountable_human_user_id=getattr(old, "accountable_human_user_id", None)
                    or actor.user_id,
                    service_account_id=getattr(old, "service_account_id", None),
                    environment_id=env_id,
                    holder_kind=getattr(old, "holder_kind", None) or "human_key",
                )
            )
            await conn.execute(
                insert(org_api_key_metadata).values(
                    key_id=new_id,
                    prefix=prefix,
                    environment=str(env_type),
                    scopes=json.dumps(scopes),
                    expires_at=getattr(old, "expires_at", None),
                    rotated_from_id=old.id,
                )
            )
            if overlap_seconds > 0:
                await conn.execute(
                    update(org_api_keys)
                    .where(
                        org_api_keys.c.id == old.id,
                        org_api_keys.c.org_id == org_id,
                        org_api_keys.c.revoked == 0,
                    )
                    .values(overlap_expires_at=_iso(now + timedelta(seconds=overlap_seconds)))
                )
            else:
                await conn.execute(
                    update(org_api_keys)
                    .where(org_api_keys.c.id == old.id, org_api_keys.c.org_id == org_id)
                    .values(revoked=1, revoked_at=_iso(now))
                )
        await self.audit.record(
            org_id=org_id,
            environment_id=env_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="api_key.rotated",
            target_type="api_key",
            target_id=new_id,
            result="ALLOWED",
            request_id=actor.request_id,
            metadata={
                "rotated_from_id": key_id,
                "overlap_seconds": overlap_seconds,
                "prefix": prefix,
            },
        )
        return (
            {
                "id": new_id,
                "org_id": org_id,
                "name": old.name,
                "prefix": prefix,
                "environment_id": env_id,
                "scopes": scopes,
                "rotated_from_id": key_id,
            },
            raw,
        )

    async def revoke_api_key(
        self, actor: Actor, org_id: str, key_id: str, *, emergency: bool = False
    ) -> None:
        perm = Permission.CREDENTIALS_EMERGENCY_REVOKE if emergency else Permission.API_KEYS_REVOKE
        await self.authorize(actor, perm, org_id=org_id)
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(org_api_keys)
                .where(
                    org_api_keys.c.id == key_id,
                    org_api_keys.c.org_id == org_id,
                    org_api_keys.c.revoked == 0,
                )
                .values(revoked=1, revoked_at=_iso(), overlap_expires_at=None)
            )
            if (result.rowcount or 0) != 1:
                raise forbidden(KEY_REVOKED, "API key is missing or already revoked.")
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="api_key.revoked",
            target_type="api_key",
            target_id=key_id,
            result="ALLOWED",
            request_id=actor.request_id,
        )

    async def authenticate_api_key(
        self,
        raw_key: str,
        *,
        expected_org_id: str | None = None,
        expected_environment_id: str | None = None,
        required_scope: str | None = None,
    ) -> dict[str, Any]:
        presented_hash = _hash_secret(raw_key)
        try:
            async with self._engine.raw.connect() as conn:
                row = (
                    await conn.execute(
                        select(org_api_keys, org_api_key_metadata)
                        .outerjoin(
                            org_api_key_metadata,
                            org_api_key_metadata.c.key_id == org_api_keys.c.id,
                        )
                        .where(org_api_keys.c.key_hash == presented_hash)
                    )
                ).fetchone()
        except SQLAlchemyError:
            raise forbidden(FORBIDDEN, "Authorization backend unavailable.") from None
        if row is None or not hmac.compare_digest(str(row.key_hash), presented_hash):
            raise forbidden(FORBIDDEN, "Invalid API key.")
        if row.revoked:
            raise forbidden(KEY_REVOKED, "API key has been revoked.")
        overlap = getattr(row, "overlap_expires_at", None)
        if overlap and overlap <= _iso():
            raise forbidden(KEY_REVOKED, "Rotated API key overlap has ended.")
        expires_at = getattr(row, "expires_at", None)
        if expires_at and expires_at <= _iso():
            raise forbidden(KEY_EXPIRED, "API key has expired.")
        if expected_org_id and row.org_id != expected_org_id:
            raise forbidden(WRONG_TENANT, "API key belongs to another organization.")
        env_id = getattr(row, "environment_id", None)
        if expected_environment_id:
            if env_id != expected_environment_id:
                raise forbidden(WRONG_ENVIRONMENT, "API key is not valid for this environment.")
            env = await self.get_environment(row.org_id, expected_environment_id)
            if env is None:
                raise forbidden(WRONG_ENVIRONMENT, "Environment does not belong to this tenant.")
            if env["status"] != "ACTIVE":
                raise forbidden(ENVIRONMENT_DISABLED, "Environment is not active.")
            key_env_type = getattr(row, "environment", None)
            if key_env_type in {"DEVELOPMENT", "STAGING", "test"} and env["type"] == "PRODUCTION":
                raise forbidden(
                    WRONG_ENVIRONMENT, "Non-production credentials cannot operate on production."
                )
            if key_env_type == "STAGING" and env["type"] == "PRODUCTION":
                raise forbidden(
                    WRONG_ENVIRONMENT, "Staging credentials cannot operate on production."
                )
        scopes = frozenset(json.loads(getattr(row, "scopes", "[]") or "[]"))
        if required_scope and required_scope not in scopes:
            raise forbidden(INSUFFICIENT_SCOPE, "API key lacks required scope.")
        org = await self._load_org(row.org_id)
        if org is None or org["governance_status"] == GovernanceStatus.DISABLED.value:
            raise forbidden(ORG_DISABLED, "Organization is disabled.")
        if org["governance_status"] == GovernanceStatus.SUSPENDED.value:
            raise forbidden(ORG_SUSPENDED, "Organization is suspended.")
        accountable = getattr(row, "accountable_human_user_id", None)
        if accountable:
            async with self._engine.raw.connect() as conn:
                human = (
                    await conn.execute(select(web_users).where(web_users.c.id == accountable))
                ).fetchone()
                membership = (
                    await conn.execute(
                        select(web_memberships).where(
                            web_memberships.c.user_id == accountable,
                            web_memberships.c.org_id == row.org_id,
                        )
                    )
                ).fetchone()
            if human is None or human.disabled:
                raise forbidden(KEY_REVOKED, "Accountable human is no longer active.")
            status = getattr(human, "verification_status", None) or "UNVERIFIED"
            if status in {"SUSPENDED", "REJECTED"}:
                raise forbidden(VERIFICATION_SUSPENDED, "Accountable human identity is suspended.")
            if membership is None or membership.status != "ACTIVE":
                raise forbidden(MEMBERSHIP_REVOKED, "Accountable human membership is not active.")
        try:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    update(org_api_keys)
                    .where(org_api_keys.c.id == row.id)
                    .values(last_used_at=_iso())
                )
        except SQLAlchemyError:
            pass
        return {
            "key_id": row.id,
            "org_id": row.org_id,
            "environment_id": env_id,
            "scopes": scopes,
            "holder_kind": getattr(row, "holder_kind", None) or "human_key",
            "accountable_human_user_id": getattr(row, "accountable_human_user_id", None),
            "service_account_id": getattr(row, "service_account_id", None),
            "role": role_from_str(row.role),
        }

    async def list_api_keys(self, actor: Actor, org_id: str) -> list[dict[str, Any]]:
        await self.authorize(actor, Permission.API_KEYS_READ, org_id=org_id)
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(org_api_keys, org_api_key_metadata)
                    .outerjoin(
                        org_api_key_metadata, org_api_key_metadata.c.key_id == org_api_keys.c.id
                    )
                    .where(org_api_keys.c.org_id == org_id)
                )
            ).fetchall()
        out = []
        for r in rows:
            out.append(
                {
                    "id": r.id,
                    "name": r.name,
                    "prefix": getattr(r, "prefix", None),
                    "environment": getattr(r, "environment", None),
                    "environment_id": getattr(r, "environment_id", None),
                    "scopes": json.loads(getattr(r, "scopes", "[]") or "[]"),
                    "revoked": bool(r.revoked),
                    "created_at": r.created_at,
                    "last_used_at": r.last_used_at,
                    "expires_at": getattr(r, "expires_at", None),
                    "holder_kind": getattr(r, "holder_kind", None),
                    "accountable_human_user_id": getattr(r, "accountable_human_user_id", None),
                    "service_account_id": getattr(r, "service_account_id", None),
                }
            )
        return out

    async def record_issuance_decision(
        self,
        *,
        org_id: str | None,
        principal_user_id: str | None,
        environment_id: str | None,
        allowed: bool,
        reason_code: str,
        requested_scopes: tuple[str, ...],
    ) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(api_key_issuance_decisions).values(
                    id=str(uuid.uuid4()),
                    org_id=org_id,
                    principal_user_id=principal_user_id,
                    environment_id=environment_id,
                    allowed=1 if allowed else 0,
                    reason_code=reason_code,
                    requested_scopes=json.dumps(list(requested_scopes)),
                    created_at=_iso(),
                )
            )

    # ── Service accounts ─────────────────────────────────────────────────────

    async def create_service_account(
        self,
        actor: Actor,
        org_id: str,
        *,
        display_name: str,
        role: Role,
        environment_ids: tuple[str, ...],
    ) -> dict[str, Any]:
        await self.authorize(actor, Permission.SA_CREATE, org_id=org_id)
        if actor.actor_type != "human":
            raise forbidden(
                SERVICE_ACCOUNT_FORBIDDEN,
                "A service account cannot be its own accountability root.",
            )
        if role == Role.OWNER:
            raise forbidden(SERVICE_ACCOUNT_FORBIDDEN, "Service accounts cannot receive OWNER.")
        if actor.actor_type == "service_account":
            if role_privilege(role) >= role_privilege(actor.role):
                raise forbidden(SERVICE_ACCOUNT_FORBIDDEN, "Service accounts cannot self-promote.")
            if not has_rbac_permission(actor.role, Permission.SA_CREATE):
                raise forbidden(
                    SERVICE_ACCOUNT_FORBIDDEN,
                    "Service account cannot create a more privileged identity.",
                )
        if role_privilege(role) >= role_privilege(actor.role) and actor.role != Role.OWNER:
            raise forbidden(
                SERVICE_ACCOUNT_FORBIDDEN,
                "Cannot assign a service-account role at or above your own.",
            )
        if not actor.user_id:
            raise forbidden(
                SERVICE_ACCOUNT_FORBIDDEN, "Service account requires accountable human provenance."
            )
        from responsibleai.enterprise.eligibility import EligibilityGate
        from responsibleai.enterprise.issuance import CredentialIssuancePolicy
        from responsibleai.enterprise.preflight import identity_webhook_secret_from_env
        from responsibleai.enterprise.verification import (
            HmacVerificationProvider,
            VerificationService,
        )

        secret = identity_webhook_secret_from_env()
        verification = VerificationService(self._engine, HmacVerificationProvider(secret))
        sponsor = await CredentialIssuancePolicy(
            self._engine, verification
        ).assert_sponsor_eligible(
            principal_user_id=actor.user_id,
            organization_id=org_id,
            role=actor.role,
        )
        await EligibilityGate(self._engine, verification).audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="service_account.sponsor_checked",
            target_type="user",
            target_id=actor.user_id,
            result="ALLOWED" if sponsor.allowed else "DENIED",
            request_id=actor.request_id,
            metadata={"reason_code": sponsor.reason_code},
        )
        if not sponsor.allowed:
            raise EnterpriseError(sponsor.reason_code, sponsor.message, 403)
        sa_id = str(uuid.uuid4())
        now = _iso()
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(enterprise_service_accounts).values(
                    id=sa_id,
                    org_id=org_id,
                    display_name=display_name.strip(),
                    status="ACTIVE",
                    role=role.value,
                    created_by_user_id=actor.user_id,
                    created_at=now,
                )
            )
            for env_id in environment_ids:
                env = (
                    await conn.execute(
                        select(enterprise_environments.c.id).where(
                            enterprise_environments.c.id == env_id,
                            enterprise_environments.c.org_id == org_id,
                        )
                    )
                ).fetchone()
                if env is None:
                    raise forbidden(WRONG_ENVIRONMENT, "Environment is not in this organization.")
                await conn.execute(
                    insert(enterprise_service_account_environments).values(
                        service_account_id=sa_id,
                        environment_id=env_id,
                        org_id=org_id,
                    )
                )
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="service_account.created",
            target_type="service_account",
            target_id=sa_id,
            result="ALLOWED",
            request_id=actor.request_id,
            metadata={"role": role.value},
        )
        return {
            "id": sa_id,
            "org_id": org_id,
            "display_name": display_name.strip(),
            "status": "ACTIVE",
            "role": role.value,
            "created_by_user_id": actor.user_id,
            "created_at": now,
            "environment_ids": list(environment_ids),
        }

    async def revoke_service_account(
        self, actor: Actor, org_id: str, service_account_id: str
    ) -> None:
        await self.authorize(actor, Permission.SA_REVOKE, org_id=org_id)
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(enterprise_service_accounts)
                .where(
                    enterprise_service_accounts.c.id == service_account_id,
                    enterprise_service_accounts.c.org_id == org_id,
                    enterprise_service_accounts.c.status == "ACTIVE",
                )
                .values(status="REVOKED", revoked_at=_iso())
            )
            if (result.rowcount or 0) != 1:
                raise forbidden(
                    SERVICE_ACCOUNT_FORBIDDEN, "Service account not found or already revoked."
                )
            await conn.execute(
                update(org_api_keys)
                .where(
                    org_api_keys.c.service_account_id == service_account_id,
                    org_api_keys.c.org_id == org_id,
                    org_api_keys.c.revoked == 0,
                )
                .values(revoked=1, revoked_at=_iso())
            )
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="service_account.revoked",
            target_type="service_account",
            target_id=service_account_id,
            result="ALLOWED",
            request_id=actor.request_id,
        )

    async def list_service_accounts(self, actor: Actor, org_id: str) -> list[dict[str, Any]]:
        await self.authorize(actor, Permission.SA_READ, org_id=org_id)
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(enterprise_service_accounts).where(
                        enterprise_service_accounts.c.org_id == org_id
                    )
                )
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    # ── Sessions ─────────────────────────────────────────────────────────────

    async def list_sessions(self, actor: Actor, org_id: str, user_id: str) -> list[dict[str, Any]]:
        await self.authorize(actor, Permission.SESSIONS_READ, org_id=org_id)
        if actor.user_id != user_id and actor.role not in {
            Role.OWNER,
            Role.ADMIN,
            Role.SECURITY_ADMIN,
        }:
            raise forbidden(FORBIDDEN, "Cannot list another user's sessions.")
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(
                        web_sessions.c.session_id,
                        web_sessions.c.created_at,
                        web_sessions.c.last_seen_at,
                        web_sessions.c.expires_at,
                        web_sessions.c.revoked,
                        web_sessions.c.org_id,
                    ).where(web_sessions.c.user_id == user_id)
                )
            ).fetchall()
        return [dict(r._mapping) for r in rows]

    async def revoke_session(self, actor: Actor, org_id: str, session_id: str) -> None:
        await self.authorize(actor, Permission.SESSIONS_REVOKE, org_id=org_id)
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.session_id == session_id, web_sessions.c.org_id == org_id)
                .values(revoked=1)
            )
        await self.audit.record(
            org_id=org_id,
            actor_type=actor.actor_type,
            actor_id=actor.actor_id,
            action="session.revoked",
            target_type="session",
            target_id=session_id,
            result="ALLOWED",
            request_id=actor.request_id,
        )

    async def logout_all(self, user_id: str, *, request_id: str | None = None) -> int:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.user_id == user_id, web_sessions.c.revoked == 0)
                .values(revoked=1)
            )
        await self.audit.record(
            actor_type="human",
            actor_id=user_id,
            action="session.logout_all",
            target_type="user",
            target_id=user_id,
            result="ALLOWED",
            request_id=request_id,
        )
        return result.rowcount or 0
