# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Human identity and browser-session persistence for the WhitePact web app.

Human sessions never reuse machine API keys. Passwords use scrypt with a
per-password random salt; session, CSRF, and verification tokens are random
opaque values whose SHA-256 digests are the only values persisted.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import secrets
import unicodedata
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, insert, or_, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.data_governance.legal_hold import LegalHoldActiveError, LegalHoldManager
from responsibleai.db.engine import (
    DatabaseEngine,
    iam_sessions,
    oauth_flow_states,
    org_api_keys,
    organizations,
    web_identity_providers,
    web_invitations,
    web_memberships,
    web_sessions,
    web_users,
    web_verification_tokens,
)
from responsibleai.rbac.models import Plan, Role
from responsibleai.rbac.permissions import role_from_str

_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DUMMY_PASSWORD_HASH = (
    "scrypt$16384$8$1$V2hpdGVQYWN0LXRpbWluZw==$0FZjlHPZgU2LP8T2sKbbDHUlmJ2O8U6e2CvJE5lPo2k="
)


class DuplicateWebUserError(Exception):
    """Raised when registration uses an existing normalized email."""


class InvitationError(Exception):
    """Raised when an invitation token is invalid, expired, or mismatch."""


class SoleOwnerError(Exception):
    """Raised when an owner attempts account deletion without transferring ownership."""


@dataclass(frozen=True)
class WebPrincipal:
    user_id: str
    email: str
    full_name: str
    org_id: str | None
    org_name: str | None
    org_plan: Plan | None
    role: Role | None
    csrf_hash: str


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _normalize_email(value: str) -> str:
    return unicodedata.normalize("NFKC", value).strip().casefold()


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_SCRYPT_N, r=_SCRYPT_R, p=_SCRYPT_P, dklen=32
    )
    return "$".join(
        [
            "scrypt",
            str(_SCRYPT_N),
            str(_SCRYPT_R),
            str(_SCRYPT_P),
            base64.urlsafe_b64encode(salt).decode(),
            base64.urlsafe_b64encode(digest).decode(),
        ]
    )


def verify_password(password: str, encoded: str) -> bool:
    try:
        algorithm, n, r, p, salt_b64, digest_b64 = encoded.split("$")
        if algorithm != "scrypt":
            return False
        expected = base64.urlsafe_b64decode(digest_b64)
        actual = hashlib.scrypt(
            password.encode("utf-8"),
            salt=base64.urlsafe_b64decode(salt_b64),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
        return hmac.compare_digest(actual, expected)
    except (ValueError, TypeError):
        return False


class WebIdentityRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def register(self, full_name: str, email: str, password: str) -> tuple[str, str]:
        now = _now()
        user_id = str(uuid.uuid4())
        verification_token = secrets.token_urlsafe(32)
        try:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    insert(web_users).values(
                        id=user_id,
                        email=_normalize_email(email),
                        full_name=unicodedata.normalize("NFKC", full_name).strip(),
                        password_hash=hash_password(password),
                        email_verified_at=None,
                        disabled=0,
                        created_at=_iso(now),
                        updated_at=_iso(now),
                    )
                )
                await conn.execute(
                    insert(web_verification_tokens).values(
                        token_hash=_hash(verification_token),
                        user_id=user_id,
                        purpose="verify_email",
                        created_at=_iso(now),
                        expires_at=_iso(now + timedelta(hours=24)),
                        consumed_at=None,
                    )
                )
        except IntegrityError as exc:
            raise DuplicateWebUserError from exc
        return user_id, verification_token

    async def verify_email(self, token: str) -> bool:
        now = _now()
        async with self._engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(web_verification_tokens).where(
                        web_verification_tokens.c.token_hash == _hash(token),
                        web_verification_tokens.c.purpose == "verify_email",
                        web_verification_tokens.c.consumed_at.is_(None),
                        web_verification_tokens.c.expires_at > _iso(now),
                    )
                )
            ).fetchone()
            if row is None:
                return False
            await conn.execute(
                update(web_verification_tokens)
                .where(web_verification_tokens.c.token_hash == row.token_hash)
                .values(consumed_at=_iso(now))
            )
            await conn.execute(
                update(web_users)
                .where(web_users.c.id == row.user_id)
                .values(email_verified_at=_iso(now), updated_at=_iso(now))
            )
        return True

    async def create_password_reset(self, email: str) -> tuple[str, str, str] | None:
        """Create a one-hour reset token without exposing whether an account exists."""
        now = _now()
        async with self._engine.raw.begin() as conn:
            user = (
                await conn.execute(
                    select(web_users).where(
                        web_users.c.email == _normalize_email(email),
                        web_users.c.disabled == 0,
                        web_users.c.email_verified_at.is_not(None),
                    )
                )
            ).fetchone()
            if user is None:
                # Keep token generation and hashing on the unknown-account path so
                # response timing is less useful for email enumeration.
                _hash(secrets.token_urlsafe(32))
                return None
            token = secrets.token_urlsafe(32)
            await conn.execute(
                update(web_verification_tokens)
                .where(
                    web_verification_tokens.c.user_id == user.id,
                    web_verification_tokens.c.purpose == "password_reset",
                    web_verification_tokens.c.consumed_at.is_(None),
                )
                .values(consumed_at=_iso(now))
            )
            await conn.execute(
                insert(web_verification_tokens).values(
                    token_hash=_hash(token),
                    user_id=user.id,
                    purpose="password_reset",
                    created_at=_iso(now),
                    expires_at=_iso(now + timedelta(hours=1)),
                    consumed_at=None,
                )
            )
        return user.email, user.full_name, token

    async def reset_password(self, token: str, new_password: str) -> bool:
        """Consume a valid reset token, change the password, and revoke all sessions."""
        now = _now()
        new_hash = hash_password(new_password)
        async with self._engine.raw.begin() as conn:
            reset = (
                await conn.execute(
                    select(web_verification_tokens).where(
                        web_verification_tokens.c.token_hash == _hash(token),
                        web_verification_tokens.c.purpose == "password_reset",
                        web_verification_tokens.c.consumed_at.is_(None),
                        web_verification_tokens.c.expires_at > _iso(now),
                    )
                )
            ).fetchone()
            if reset is None:
                return False
            await conn.execute(
                update(web_verification_tokens)
                .where(web_verification_tokens.c.token_hash == reset.token_hash)
                .values(consumed_at=_iso(now))
            )
            await conn.execute(
                update(web_users)
                .where(web_users.c.id == reset.user_id)
                .values(password_hash=new_hash, updated_at=_iso(now))
            )
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.user_id == reset.user_id, web_sessions.c.revoked == 0)
                .values(revoked=1)
            )
        return True

    async def authenticate(self, email: str, password: str) -> tuple[str, str, str] | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(web_users).where(web_users.c.email == _normalize_email(email))
                )
            ).fetchone()
        if row is None or row.disabled or row.email_verified_at is None:
            # Do equivalent password work for unknown/unverified accounts to reduce
            # timing disclosure without revealing which condition failed.
            verify_password(password, _DUMMY_PASSWORD_HASH)
            return None
        if not verify_password(password, row.password_hash):
            return None
        return row.id, row.email, row.full_name

    async def primary_org_id(self, user_id: str) -> str | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(web_memberships.c.org_id)
                    .where(web_memberships.c.user_id == user_id)
                    .order_by(web_memberships.c.created_at)
                    .limit(1)
                )
            ).fetchone()
        return str(row.org_id) if row else None

    async def list_members(self, org_id: str) -> list[dict[str, str]]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(
                        web_users.c.id,
                        web_users.c.full_name,
                        web_users.c.email,
                        web_memberships.c.role,
                        web_memberships.c.created_at,
                    )
                    .join(web_memberships, web_memberships.c.user_id == web_users.c.id)
                    .where(web_memberships.c.org_id == org_id)
                    .order_by(web_memberships.c.created_at)
                )
            ).fetchall()
        return [
            {
                "id": row.id,
                "full_name": row.full_name,
                "email": row.email,
                "role": row.role,
                "joined_at": row.created_at,
            }
            for row in rows
        ]

    async def create_session(
        self, user_id: str, *, org_id: str | None = None, ttl_hours: int = 12
    ) -> tuple[str, str]:
        token = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        now = _now()
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(web_sessions).values(
                    token_hash=_hash(token),
                    session_id=str(uuid.uuid4()),
                    user_id=user_id,
                    org_id=org_id,
                    csrf_hash=_hash(csrf),
                    created_at=_iso(now),
                    expires_at=_iso(now + timedelta(hours=ttl_hours)),
                    last_seen_at=_iso(now),
                    revoked=0,
                )
            )
        return token, csrf

    async def get_principal(self, token: str) -> WebPrincipal | None:
        now = _now()
        async with self._engine.raw.begin() as conn:
            session = (
                await conn.execute(
                    select(web_sessions).where(
                        web_sessions.c.token_hash == _hash(token),
                        web_sessions.c.revoked == 0,
                        web_sessions.c.expires_at > _iso(now),
                    )
                )
            ).fetchone()
            if session is None:
                return None
            user = (
                await conn.execute(
                    select(web_users).where(
                        web_users.c.id == session.user_id,
                        web_users.c.disabled == 0,
                        web_users.c.email_verified_at.is_not(None),
                    )
                )
            ).fetchone()
            if user is None:
                return None
            membership = None
            org = None
            if session.org_id:
                membership = (
                    await conn.execute(
                        select(web_memberships).where(
                            web_memberships.c.user_id == user.id,
                            web_memberships.c.org_id == session.org_id,
                        )
                    )
                ).fetchone()
                if membership is None:
                    return None
                membership_status = getattr(membership, "status", "ACTIVE") or "ACTIVE"
                if membership_status != "ACTIVE":
                    return None
                org = (
                    await conn.execute(
                        select(organizations).where(organizations.c.id == session.org_id)
                    )
                ).fetchone()
                if org is None:
                    return None
                gov = getattr(org, "governance_status", "ACTIVE") or "ACTIVE"
                if gov == "DISABLED":
                    return None
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.token_hash == session.token_hash)
                .values(last_seen_at=_iso(now))
            )
        return WebPrincipal(
            user_id=user.id,
            email=user.email,
            full_name=user.full_name,
            org_id=org.id if org else None,
            org_name=org.name if org else None,
            org_plan=Plan(org.plan) if org else None,
            role=role_from_str(membership.role) if membership else None,
            csrf_hash=session.csrf_hash,
        )

    async def revoke_session(self, token: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.token_hash == _hash(token))
                .values(revoked=1)
            )

    async def attach_organization(
        self, user_id: str, *, name: str, slug: str, role: Role = Role.OWNER
    ) -> str:
        now = _now()
        org_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(organizations).values(
                    id=org_id,
                    name=name,
                    slug=slug,
                    monthly_budget_usd=10_000.0,
                    created_at=_iso(now),
                    plan=Plan.FREE.value,
                    sso_required=0,
                    mfa_required=0,
                    workspace_kind="ORGANIZATION",
                    owner_user_id=user_id,
                    settings_json="{}",
                )
            )
            await conn.execute(
                insert(web_memberships).values(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    org_id=org_id,
                    role=role.value,
                    status="ACTIVE",
                    invited_by_user_id=None,
                    accepted_at=_iso(now),
                    created_at=_iso(now),
                    updated_at=_iso(now),
                )
            )
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.user_id == user_id, web_sessions.c.revoked == 0)
                .values(org_id=org_id)
            )
        return org_id

    async def list_organizations(self, user_id: str) -> list[dict[str, str]]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(
                        organizations.c.id,
                        organizations.c.name,
                        organizations.c.slug,
                        organizations.c.plan,
                        web_memberships.c.role,
                    )
                    .join(web_memberships, web_memberships.c.org_id == organizations.c.id)
                    .where(
                        web_memberships.c.user_id == user_id,
                        web_memberships.c.status == "ACTIVE",
                    )
                    .order_by(organizations.c.name)
                )
            ).fetchall()
        return [dict(row._mapping) for row in rows]

    async def revoke_all_sessions(self, user_id: str) -> int:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.user_id == user_id, web_sessions.c.revoked == 0)
                .values(revoked=1)
            )
        return result.rowcount or 0

    async def switch_organization(
        self, token: str, user_id: str, org_id: str, *, ttl_hours: int = 12
    ) -> tuple[str, str] | None:
        """Rotate the browser session after validating durable membership."""
        now = _now()
        replacement = secrets.token_urlsafe(32)
        csrf = secrets.token_urlsafe(32)
        async with self._engine.raw.begin() as conn:
            membership = (
                await conn.execute(
                    select(web_memberships.c.id).where(
                        web_memberships.c.user_id == user_id,
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.status == "ACTIVE",
                    )
                )
            ).fetchone()
            if membership is None:
                return None
            current = (
                await conn.execute(
                    select(web_sessions.c.token_hash).where(
                        web_sessions.c.token_hash == _hash(token),
                        web_sessions.c.user_id == user_id,
                        web_sessions.c.revoked == 0,
                        web_sessions.c.expires_at > _iso(now),
                    )
                )
            ).fetchone()
            if current is None:
                return None
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.token_hash == current.token_hash)
                .values(revoked=1)
            )
            await conn.execute(
                insert(web_sessions).values(
                    token_hash=_hash(replacement),
                    session_id=str(uuid.uuid4()),
                    user_id=user_id,
                    org_id=org_id,
                    csrf_hash=_hash(csrf),
                    created_at=_iso(now),
                    expires_at=_iso(now + timedelta(hours=ttl_hours)),
                    last_seen_at=_iso(now),
                    revoked=0,
                )
            )
        return replacement, csrf

    async def create_invitation(
        self,
        *,
        org_id: str,
        email: str,
        role: Role,
        invited_by_user_id: str,
        ttl_hours: int = 168,
    ) -> tuple[str, str]:
        if role == Role.OWNER:
            raise InvitationError("Cannot invite a direct owner; use ownership transfer.")
        normalized = _normalize_email(email)
        token = secrets.token_urlsafe(32)
        invitation_id = str(uuid.uuid4())
        now = _now()
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(web_invitations)
                .where(
                    web_invitations.c.org_id == org_id,
                    web_invitations.c.email == normalized,
                    web_invitations.c.status == "PENDING",
                )
                .values(status="REVOKED")
            )
            await conn.execute(
                insert(web_invitations).values(
                    id=invitation_id,
                    token_hash=_hash(token),
                    org_id=org_id,
                    email=normalized,
                    role=role.value,
                    invited_by_user_id=invited_by_user_id,
                    accepted_by_user_id=None,
                    status="PENDING",
                    created_at=_iso(now),
                    expires_at=_iso(now + timedelta(hours=ttl_hours)),
                    consumed_at=None,
                )
            )
        return invitation_id, token

    async def accept_invitation(self, token: str, user_id: str) -> str:
        now = _now()
        async with self._engine.raw.begin() as conn:
            user = (
                await conn.execute(
                    select(web_users.c.email).where(
                        web_users.c.id == user_id,
                        web_users.c.disabled == 0,
                        web_users.c.email_verified_at.is_not(None),
                    )
                )
            ).fetchone()
            invitation = (
                await conn.execute(
                    select(web_invitations).where(
                        web_invitations.c.token_hash == _hash(token),
                        web_invitations.c.status.in_(("PENDING", "INVITED")),
                        web_invitations.c.consumed_at.is_(None),
                        web_invitations.c.expires_at > _iso(now),
                    )
                )
            ).fetchone()
            if user is None or invitation is None or user.email != invitation.email:
                raise InvitationError("This invitation is invalid, expired, or belongs to another account.")
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
                raise InvitationError("This invitation cannot be accepted.") from exc
            await conn.execute(
                update(web_invitations)
                .where(
                    web_invitations.c.id == invitation.id,
                    web_invitations.c.status.in_(("PENDING", "INVITED")),
                )
                .values(status="ACCEPTED", accepted_by_user_id=user_id, consumed_at=_iso(now))
            )
        return str(invitation.org_id)

    async def revoke_invitation(self, invitation_id: str, org_id: str) -> bool:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(web_invitations)
                .where(
                    web_invitations.c.id == invitation_id,
                    web_invitations.c.org_id == org_id,
                    web_invitations.c.status == "PENDING",
                )
                .values(status="REVOKED")
            )
        return (result.rowcount or 0) > 0

    async def list_invitations(self, org_id: str) -> list[dict[str, Any]]:
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(web_invitations).where(web_invitations.c.org_id == org_id)
                )
            ).fetchall()
        return [
            {
                "id": r.id,
                "email": r.email,
                "role": r.role,
                "status": r.status,
                "invited_by_user_id": r.invited_by_user_id,
                "created_at": r.created_at,
                "expires_at": r.expires_at,
                "consumed_at": r.consumed_at,
            }
            for r in rows
        ]

    async def update_membership_role(self, org_id: str, user_id: str, role: Role) -> bool:
        if role == Role.OWNER:
            raise InvitationError("Ownership transfer requires the canonical privileged workflow.")
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(web_memberships)
                .where(
                    web_memberships.c.org_id == org_id,
                    web_memberships.c.user_id == user_id,
                    web_memberships.c.role != Role.OWNER.value,
                )
                .values(role=role.value)
            )
            if result.rowcount:
                await conn.execute(
                    update(web_sessions)
                    .where(web_sessions.c.user_id == user_id, web_sessions.c.org_id == org_id)
                    .values(revoked=1)
                )
        return (result.rowcount or 0) > 0

    async def remove_membership(self, org_id: str, user_id: str) -> bool:
        async with self._engine.raw.begin() as conn:
            membership = (
                await conn.execute(
                    select(web_memberships.c.role).where(
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.user_id == user_id,
                    )
                )
            ).fetchone()
            if membership is None or membership.role == Role.OWNER.value:
                return False
            result = await conn.execute(
                delete(web_memberships).where(
                    web_memberships.c.org_id == org_id,
                    web_memberships.c.user_id == user_id,
                )
            )
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.user_id == user_id, web_sessions.c.org_id == org_id)
                .values(revoked=1)
            )
        return (result.rowcount or 0) > 0

    async def transfer_organization_ownership(
        self, *, org_id: str, current_owner_id: str, new_owner_id: str
    ) -> bool:
        if current_owner_id == new_owner_id:
            return True
        async with self._engine.raw.begin() as conn:
            current_m = (
                await conn.execute(
                    select(web_memberships.c.role).where(
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.user_id == current_owner_id,
                        web_memberships.c.role == Role.OWNER.value,
                    )
                )
            ).fetchone()
            if not current_m:
                return False
            target_m = (
                await conn.execute(
                    select(web_memberships.c.role).where(
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.user_id == new_owner_id,
                    )
                )
            ).fetchone()
            if not target_m:
                return False
            await conn.execute(
                update(web_memberships)
                .where(
                    web_memberships.c.org_id == org_id,
                    web_memberships.c.user_id == current_owner_id,
                )
                .values(role=Role.ADMIN.value)
            )
            await conn.execute(
                update(web_memberships)
                .where(
                    web_memberships.c.org_id == org_id,
                    web_memberships.c.user_id == new_owner_id,
                )
                .values(role=Role.OWNER.value)
            )
            await conn.execute(
                update(web_sessions)
                .where(
                    web_sessions.c.user_id.in_([current_owner_id, new_owner_id]),
                    web_sessions.c.org_id == org_id,
                )
                .values(revoked=1)
            )
        return True

    async def is_sole_owner_of_any_org(self, user_id: str) -> bool:
        async with self._engine.raw.connect() as conn:
            owned_org_ids = (
                await conn.execute(
                    select(web_memberships.c.org_id).where(
                        web_memberships.c.user_id == user_id,
                        web_memberships.c.role == Role.OWNER.value,
                    )
                )
            ).scalars().all()
            for org_id in owned_org_ids:
                count = await conn.scalar(
                    select(func.count()).select_from(web_memberships).where(
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.role == Role.OWNER.value,
                    )
                )
                if (count or 0) <= 1:
                    return True
        return False

    async def disable_account(self, user_id: str) -> bool:
        """Disable and pseudonymize a human account while retaining security evidence.

        Refuses deletion if user is the sole owner of an active organization
        or if any associated organization is under active legal hold.
        """
        if await self.is_sole_owner_of_any_org(user_id):
            raise SoleOwnerError(
                "Cannot delete account while being the sole owner of an organization. "
                "Transfer ownership or delete the organization first."
            )

        org_list = await self.list_organizations(user_id)
        legal_hold_mgr = LegalHoldManager(self._engine)
        for org in org_list:
            if await legal_hold_mgr.is_held(org["id"]):
                raise LegalHoldActiveError(
                    f"Cannot delete account: Organization '{org['name']}' ({org['id']}) is under an active legal hold."
                )

        now = _now()
        async with self._engine.raw.begin() as conn:
            # Find user's original email and session token hashes
            user_row = (await conn.execute(
                select(web_users.c.email).where(web_users.c.id == user_id)
            )).first()
            old_email = user_row[0] if user_row else ""

            sess_rows = (await conn.execute(
                select(web_sessions.c.token_hash).where(web_sessions.c.user_id == user_id)
            )).scalars().all()

            result = await conn.execute(
                update(web_users)
                .where(web_users.c.id == user_id, web_users.c.disabled == 0)
                .values(
                    email=f"deleted+{uuid.uuid4().hex}@invalid.whitepact",
                    full_name="Deleted WhitePact user",
                    password_hash=hash_password(secrets.token_urlsafe(48)),
                    disabled=1,
                    updated_at=_iso(now),
                )
            )
            if not result.rowcount:
                return False

            # 1. Revoke all web sessions
            await conn.execute(update(web_sessions).where(web_sessions.c.user_id == user_id).values(revoked=1))

            # 2. Invalidate OAuth flow states associated with user's sessions
            if sess_rows:
                await conn.execute(
                    delete(oauth_flow_states).where(oauth_flow_states.c.session_id.in_(sess_rows))
                )

            # 3. Revoke IAM sessions
            await conn.execute(
                update(iam_sessions)
                .where(iam_sessions.c.principal_id == user_id)
                .values(status="REVOKED", revoked_at=_iso(now))
            )

            # 4. Revoke user's API keys
            await conn.execute(
                update(org_api_keys)
                .where(or_(org_api_keys.c.id == user_id, org_api_keys.c.name.like(f"%{user_id}%")))
                .values(revoked=1)
            )

            # 5. Invalidate verification and password reset tokens
            await conn.execute(delete(web_verification_tokens).where(web_verification_tokens.c.user_id == user_id))

            # 6. Invalidate pending invitations (sent to user or created by user)
            if old_email:
                await conn.execute(
                    update(web_invitations)
                    .where(or_(web_invitations.c.invited_by_user_id == user_id, web_invitations.c.email == old_email))
                    .values(status="REVOKED")
                )
            else:
                await conn.execute(
                    update(web_invitations)
                    .where(web_invitations.c.invited_by_user_id == user_id)
                    .values(status="REVOKED")
                )

            # 7. Delete provider linkages and memberships
            await conn.execute(delete(web_identity_providers).where(web_identity_providers.c.user_id == user_id))
            await conn.execute(delete(web_memberships).where(web_memberships.c.user_id == user_id))
        return True

    async def link_provider_identity(
        self,
        *,
        user_id: str,
        issuer: str,
        subject: str,
        email: str | None,
        email_verified: bool = True,
        tenant_id: str | None = None,
    ) -> None:
        if not issuer or not subject:
            raise ValueError("OIDC issuer and subject are required")
        if not email_verified:
            raise ValueError("Cannot link provider identity with unverified email")

        async with self._engine.raw.begin() as conn:
            # 1. Target user must exist and not be disabled
            u_row = (await conn.execute(
                select(web_users.c.id, web_users.c.disabled).where(web_users.c.id == user_id)
            )).first()
            if not u_row or u_row.disabled:
                raise ValueError("Target user does not exist or is disabled")

            # 2. Check if (issuer, subject) is already linked
            existing = (await conn.execute(
                select(web_identity_providers.c.user_id).where(
                    web_identity_providers.c.issuer == issuer,
                    web_identity_providers.c.subject == subject,
                )
            )).first()
            if existing is not None:
                if existing.user_id != user_id:
                    raise ValueError("Provider identity is already linked to a different account")
                return  # Idempotent re-link for same user

            # 3. Cross-tenant check: if tenant_id given, verify membership
            if tenant_id:
                m_row = (await conn.execute(
                    select(web_memberships.c.id).where(
                        web_memberships.c.user_id == user_id,
                        web_memberships.c.org_id == tenant_id,
                    )
                )).first()
                if not m_row:
                    raise ValueError(f"User is not a member of organization {tenant_id}")

            await conn.execute(
                insert(web_identity_providers).values(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    issuer=issuer,
                    subject=subject,
                    email_at_link=_normalize_email(email) if email else None,
                    created_at=_iso(_now()),
                )
            )

    async def resolve_provider_identity(self, issuer: str, subject: str) -> str | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(web_identity_providers.c.user_id).where(
                        web_identity_providers.c.issuer == issuer,
                        web_identity_providers.c.subject == subject,
                    )
                )
            ).fetchone()
        return str(row.user_id) if row else None

    async def create_oauth_flow_state(
        self,
        *,
        state: str,
        provider: str,
        nonce: str,
        redirect_uri: str,
        tenant_id: str | None = None,
        session_id: str | None = None,
        pkce_verifier: str | None = None,
        ttl_seconds: int = 600,
    ) -> None:
        state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
        now = _now()
        expires_at = _iso(now + timedelta(seconds=ttl_seconds))
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(oauth_flow_states).values(
                    state_hash=state_hash,
                    provider=provider,
                    tenant_id=tenant_id,
                    session_id=session_id,
                    nonce=nonce,
                    pkce_verifier=pkce_verifier,
                    redirect_uri=redirect_uri,
                    created_at=_iso(now),
                    expires_at=expires_at,
                    consumed_at=None,
                )
            )

    async def consume_oauth_flow_state(
        self,
        state: str,
        expected_provider: str | None = None,
        expected_session_id: str | None = None,
        expected_tenant_id: str | None = None,
    ) -> dict[str, Any] | None:
        state_hash = hashlib.sha256(state.encode("utf-8")).hexdigest()
        now = _now()
        now_iso = _iso(now)
        async with self._engine.raw.begin() as conn:
            stmt = select(oauth_flow_states).where(
                oauth_flow_states.c.state_hash == state_hash,
                oauth_flow_states.c.consumed_at.is_(None),
                oauth_flow_states.c.expires_at > now_iso,
            )
            if self._engine.raw.dialect.name == "postgresql":
                stmt = stmt.with_for_update()
            row = (await conn.execute(stmt)).fetchone()
            if row is None:
                return None
            if expected_provider and row.provider != expected_provider:
                return None
            if expected_tenant_id and row.tenant_id and row.tenant_id != expected_tenant_id:
                return None
            if row.session_id and expected_session_id != row.session_id:
                return None
            res = await conn.execute(
                update(oauth_flow_states)
                .where(
                    oauth_flow_states.c.state_hash == state_hash,
                    oauth_flow_states.c.consumed_at.is_(None),
                )
                .values(consumed_at=now_iso)
            )
            if not res.rowcount:
                return None
            return {
                "provider": row.provider,
                "tenant_id": row.tenant_id,
                "session_id": row.session_id,
                "nonce": row.nonce,
                "pkce_verifier": row.pkce_verifier,
                "redirect_uri": row.redirect_uri,
                "created_at": row.created_at,
                "expires_at": row.expires_at,
            }

    async def delete_expired_state(self) -> None:
        now = _iso(_now())
        async with self._engine.raw.begin() as conn:
            await conn.execute(delete(web_sessions).where(web_sessions.c.expires_at <= now))
            await conn.execute(
                delete(web_verification_tokens).where(
                    web_verification_tokens.c.expires_at <= now,
                )
            )
            await conn.execute(
                delete(oauth_flow_states).where(
                    oauth_flow_states.c.expires_at <= now,
                )
            )

