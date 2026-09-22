# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise IAM Session Lifecycle & Revocation Management."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, insert, select, update

from responsibleai.db.engine import DatabaseEngine, iam_sessions
from responsibleai.db.revocation_epoch_repository import bump_epoch_on_connection


class SessionService:
    """Manages privileged sessions, session freshness, and instant cascading revocation."""

    def __init__(self, db: DatabaseEngine) -> None:
        self.db = db

    async def create_session(
        self,
        *,
        org_id: str,
        principal_id: str,
        session_type: str = "INTERACTIVE",
        ttl_seconds: int = 43200,  # 12 hours
    ) -> tuple[str, str]:
        """Create a new session, returning (session_id, session_token)."""
        session_id = f"sess_{uuid.uuid4().hex}"
        token = f"wp_sess_{secrets.token_urlsafe(32)}"
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()

        now = datetime.now(UTC)
        expires_at = (now + timedelta(seconds=ttl_seconds)).isoformat()

        async with self.db.raw.begin() as conn:
            await conn.execute(
                insert(iam_sessions).values(
                    id=session_id,
                    org_id=org_id,
                    principal_id=principal_id,
                    token_hash=token_hash,
                    session_type=session_type,
                    status="ACTIVE",
                    created_at=now.isoformat(),
                    expires_at=expires_at,
                    last_seen_at=now.isoformat(),
                    revoked_at=None,
                )
            )

        return session_id, token

    async def validate_session(self, *, org_id: str, session_id: str, token: str) -> bool:
        """Validate an active session token."""
        token_hash = hashlib.sha256(token.encode("utf-8")).hexdigest()
        now = datetime.now(UTC).isoformat()

        async with self.db.raw.connect() as conn:
            stmt = select(iam_sessions).where(
                and_(
                    iam_sessions.c.id == session_id,
                    iam_sessions.c.org_id == org_id,
                )
            )
            row = (await conn.execute(stmt)).first()
            if not row:
                return False

            sess = dict(row._mapping)
            if sess["status"] != "ACTIVE":
                return False
            if sess["revoked_at"] is not None:
                return False
            if now >= sess["expires_at"]:
                return False
            if not secrets.compare_digest(sess["token_hash"], token_hash):
                return False

        return True

    async def revoke_session(self, *, org_id: str, session_id: str) -> bool:
        """Revoke a specific session."""
        now = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            res = await conn.execute(
                update(iam_sessions)
                .where(
                    and_(
                        iam_sessions.c.id == session_id,
                        iam_sessions.c.org_id == org_id,
                    )
                )
                .values(status="REVOKED", revoked_at=now)
            )
            return (res.rowcount or 0) > 0

    async def revoke_all_principal_sessions(self, *, org_id: str, principal_id: str) -> int:
        """Revoke all active sessions for a given principal (e.g. on deprovisioning)."""
        now = datetime.now(UTC).isoformat()
        async with self.db.raw.begin() as conn:
            res = await conn.execute(
                update(iam_sessions)
                .where(
                    and_(
                        iam_sessions.c.org_id == org_id,
                        iam_sessions.c.principal_id == principal_id,
                        iam_sessions.c.status == "ACTIVE",
                    )
                )
                .values(status="REVOKED", revoked_at=now)
            )
            return res.rowcount or 0

    async def advance_security_epoch(self, *, org_id: str) -> int:
        """Advance the tenant security epoch, instantly invalidating all prior sessions."""
        async with self.db.raw.begin() as conn:
            new_epoch = await bump_epoch_on_connection(conn, org_id, scope="iam_session")
            # Mark all existing active sessions as revoked
            now = datetime.now(UTC).isoformat()
            await conn.execute(
                update(iam_sessions)
                .where(
                    and_(
                        iam_sessions.c.org_id == org_id,
                        iam_sessions.c.status == "ACTIVE",
                    )
                )
                .values(status="EPOCH_REVOKED", revoked_at=now)
            )
        return new_epoch
