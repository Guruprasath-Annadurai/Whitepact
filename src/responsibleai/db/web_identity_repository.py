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

from sqlalchemy import delete, insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import (
    DatabaseEngine,
    organizations,
    web_memberships,
    web_sessions,
    web_users,
    web_verification_tokens,
)
from responsibleai.rbac.models import Plan, Role

_SCRYPT_N = 1 << 14
_SCRYPT_R = 8
_SCRYPT_P = 1
_DUMMY_PASSWORD_HASH = (
    "scrypt$16384$8$1$V2hpdGVQYWN0LXRpbWluZw==$0FZjlHPZgU2LP8T2sKbbDHUlmJ2O8U6e2CvJE5lPo2k="
)


class DuplicateWebUserError(Exception):
    """Raised when registration uses an existing normalized email."""


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
                org = (
                    await conn.execute(
                        select(organizations).where(organizations.c.id == session.org_id)
                    )
                ).fetchone()
                if org is None:
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
            role=Role(membership.role) if membership else None,
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
                )
            )
            await conn.execute(
                insert(web_memberships).values(
                    id=str(uuid.uuid4()),
                    user_id=user_id,
                    org_id=org_id,
                    role=role.value,
                    created_at=_iso(now),
                )
            )
            await conn.execute(
                update(web_sessions)
                .where(web_sessions.c.user_id == user_id, web_sessions.c.revoked == 0)
                .values(org_id=org_id)
            )
        return org_id

    async def delete_expired_state(self) -> None:
        now = _iso(_now())
        async with self._engine.raw.begin() as conn:
            await conn.execute(delete(web_sessions).where(web_sessions.c.expires_at <= now))
            await conn.execute(
                delete(web_verification_tokens).where(
                    web_verification_tokens.c.expires_at <= now,
                )
            )
