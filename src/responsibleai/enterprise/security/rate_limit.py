# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable identity abuse counters.

Redis is defensive infrastructure, not identity authority. PostgreSQL (or the
active DatabaseEngine backend) holds the counter. Storage failure fails closed
for high-risk flows and never silently falls back to a per-process dict.

Increment, first-bucket insert, and window rollover are decided atomically in
SQL so concurrent workers cannot lose updates under READ COMMITTED.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncConnection

from responsibleai.db.engine import DatabaseEngine, identity_rate_counters
from responsibleai.enterprise.errors import EnterpriseError

logger = logging.getLogger(__name__)

HIGH_RISK_PREFIXES = (
    "recovery",
    "recovery-code",
    "recovery-token",
    "totp",
    "passkey",
    "step-up",
    "sso",
    "oauth",
    "four-eyes",
    "privileged",
    "login",
)


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def is_high_risk(bucket_key: str) -> bool:
    head = bucket_key.split(":", 1)[0]
    return head in HIGH_RISK_PREFIXES or bucket_key.startswith(HIGH_RISK_PREFIXES)


def _rowcount(result: object) -> int:
    return int(getattr(result, "rowcount", 0) or 0)


class DurableIdentityRateLimiter:
    """Shared counters across replicas. No in-memory production fallback."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    async def check(self, key: str, *, limit: int, window_seconds: float) -> None:
        if limit < 1:
            raise EnterpriseError("RATE_LIMITED", "Try again later.", 429)
        cutoff = _iso(_now() - timedelta(seconds=window_seconds))
        now = _iso()
        try:
            async with self.engine.raw.begin() as conn:
                if await self._claim_new_bucket(conn, key, now):
                    return
                if await self._try_increment(conn, key, limit, cutoff, now):
                    return
                if await self._try_rollover(conn, key, cutoff, now):
                    return
                if await self._try_increment(conn, key, limit, cutoff, now):
                    return
                raise EnterpriseError("RATE_LIMITED", "Try again later.", 429)
        except EnterpriseError:
            raise
        except SQLAlchemyError:
            logger.warning("identity_rate_limit_storage_unavailable")
            raise EnterpriseError(
                "IDENTITY_PROTECTION_UNAVAILABLE",
                "Abuse protection is unavailable. Try again later.",
                503,
            ) from None

    async def current_count(self, key: str, *, window_seconds: float) -> int:
        """Read the live window count without incrementing.

        Used by dashboard REST failed-auth gating so valid credentials are
        not charged. Storage failure fails closed.
        """
        cutoff = _iso(_now() - timedelta(seconds=window_seconds))
        try:
            async with self.engine.raw.begin() as conn:
                row = (
                    await conn.execute(
                        select(
                            identity_rate_counters.c.count,
                            identity_rate_counters.c.window_start,
                        ).where(identity_rate_counters.c.bucket_key == key)
                    )
                ).fetchone()
                if row is None:
                    return 0
                stored_count, window_start = row[0], row[1]
                if str(window_start) < cutoff:
                    return 0
                return int(stored_count)
        except SQLAlchemyError:
            logger.warning("identity_rate_limit_storage_unavailable")
            raise EnterpriseError(
                "IDENTITY_PROTECTION_UNAVAILABLE",
                "Abuse protection is unavailable. Try again later.",
                503,
            ) from None

    async def _claim_new_bucket(self, conn: AsyncConnection, key: str, now: str) -> bool:
        """Insert the first slot without aborting the transaction on conflict."""
        values = {
            "bucket_key": key,
            "window_start": now,
            "count": 1,
            "updated_at": now,
        }
        if conn.dialect.name == "sqlite":
            from sqlalchemy.dialects.sqlite import insert as sqlite_insert

            result = await conn.execute(
                sqlite_insert(identity_rate_counters)
                .values(**values)
                .on_conflict_do_nothing(index_elements=["bucket_key"])
            )
            return _rowcount(result) == 1
        from sqlalchemy.dialects.postgresql import insert as postgres_insert

        result = await conn.execute(
            postgres_insert(identity_rate_counters)
            .values(**values)
            .on_conflict_do_nothing(index_elements=["bucket_key"])
        )
        return _rowcount(result) == 1

    async def _try_increment(
        self,
        conn: AsyncConnection,
        key: str,
        limit: int,
        cutoff: str,
        now: str,
    ) -> bool:
        result = await conn.execute(
            update(identity_rate_counters)
            .where(
                identity_rate_counters.c.bucket_key == key,
                identity_rate_counters.c.count < limit,
                identity_rate_counters.c.window_start >= cutoff,
            )
            .values(
                count=identity_rate_counters.c.count + 1,
                updated_at=now,
            )
        )
        return _rowcount(result) == 1

    async def _try_rollover(self, conn: AsyncConnection, key: str, cutoff: str, now: str) -> bool:
        result = await conn.execute(
            update(identity_rate_counters)
            .where(
                identity_rate_counters.c.bucket_key == key,
                identity_rate_counters.c.window_start < cutoff,
            )
            .values(window_start=now, count=1, updated_at=now)
        )
        return _rowcount(result) == 1
