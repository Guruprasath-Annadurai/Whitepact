# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable identity abuse counters.

Redis is defensive infrastructure, not identity authority. PostgreSQL (or the
active DatabaseEngine backend) holds the counter. Storage failure fails closed
for high-risk flows and never silently falls back to a per-process dict.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, insert, select, update
from sqlalchemy.exc import SQLAlchemyError

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


class DurableIdentityRateLimiter:
    """Shared counters across replicas. No in-memory production fallback."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    async def check(self, key: str, *, limit: int, window_seconds: float) -> None:
        window_start = _iso(_now() - timedelta(seconds=window_seconds))
        now = _iso()
        try:
            async with self.engine.raw.begin() as conn:
                row = (
                    await conn.execute(
                        select(identity_rate_counters).where(
                            identity_rate_counters.c.bucket_key == key
                        )
                    )
                ).fetchone()
                if row is None:
                    await conn.execute(
                        insert(identity_rate_counters).values(
                            bucket_key=key,
                            window_start=now,
                            count=1,
                            updated_at=now,
                        )
                    )
                    return
                if str(row.window_start) < window_start:
                    await conn.execute(
                        update(identity_rate_counters)
                        .where(identity_rate_counters.c.bucket_key == key)
                        .values(window_start=now, count=1, updated_at=now)
                    )
                    return
                current = int(row._mapping["count"])
                if current >= limit:
                    raise EnterpriseError("RATE_LIMITED", "Try again later.", 429)
                result = await conn.execute(
                    update(identity_rate_counters)
                    .where(
                        and_(
                            identity_rate_counters.c.bucket_key == key,
                            identity_rate_counters.c.count < limit,
                            identity_rate_counters.c.window_start == row.window_start,
                        )
                    )
                    .values(count=current + 1, updated_at=now)
                )
                if (result.rowcount or 0) != 1:
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
