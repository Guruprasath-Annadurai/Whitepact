"""Async repository for the governance audit log.

Every API request is recorded here by the AuditLogMiddleware.
Supports filtered queries and auto-cleanup of old entries.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, insert, select

from responsibleai.db.engine import DatabaseEngine, audit_log
from responsibleai.rbac.models import AuditEntry


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


class AuditRepository:
    """Write and query the audit log table."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def write(self, entry: AuditEntry) -> None:
        """Persist one audit entry. Fast — single INSERT."""
        if not entry.timestamp:
            entry.timestamp = _now()
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(audit_log).values(
                id=entry.id,
                timestamp=entry.timestamp,
                org_id=entry.org_id,
                key_id=entry.key_id,
                endpoint=entry.endpoint,
                method=entry.method,
                status_code=entry.status_code,
                ip_address=entry.ip_address,
                request_id=entry.request_id,
                duration_ms=entry.duration_ms,
                user_agent=entry.user_agent,
            ))

    async def query(
        self,
        org_id: str | None = None,
        endpoint: str | None = None,
        days: int = 30,
        limit: int = 100,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        cutoff = _days_ago(days)
        stmt = (
            select(audit_log)
            .where(audit_log.c.timestamp >= cutoff)
            .order_by(audit_log.c.timestamp.desc())
            .limit(limit)
            .offset(offset)
        )
        if org_id:
            stmt = stmt.where(audit_log.c.org_id == org_id)
        if endpoint:
            stmt = stmt.where(audit_log.c.endpoint == endpoint)

        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()

        return [
            {
                "id": r.id,
                "timestamp": r.timestamp,
                "org_id": r.org_id,
                "key_id": r.key_id,
                "endpoint": r.endpoint,
                "method": r.method,
                "status_code": r.status_code,
                "ip_address": r.ip_address,
                "request_id": r.request_id,
                "duration_ms": r.duration_ms,
            }
            for r in rows
        ]

    async def count(self, days: int = 30, org_id: str | None = None) -> int:
        cutoff = _days_ago(days)
        stmt = (
            select(func.count())
            .select_from(audit_log)
            .where(audit_log.c.timestamp >= cutoff)
        )
        if org_id:
            stmt = stmt.where(audit_log.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            result = (await conn.execute(stmt)).scalar()
        return result or 0

    async def cleanup(self, retention_days: int = 90) -> int:
        """Delete entries older than *retention_days*. Returns deleted count."""
        cutoff = _days_ago(retention_days)
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                delete(audit_log).where(audit_log.c.timestamp < cutoff)
            )
        return result.rowcount

    async def endpoint_summary(self, days: int = 7) -> list[dict[str, Any]]:
        """Top endpoints by request count for the last N days."""
        cutoff = _days_ago(days)
        stmt = (
            select(
                audit_log.c.endpoint,
                func.count().label("count"),
                func.avg(audit_log.c.duration_ms).label("avg_ms"),
            )
            .where(audit_log.c.timestamp >= cutoff)
            .group_by(audit_log.c.endpoint)
            .order_by(func.count().desc())
            .limit(20)
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [
            {"endpoint": r.endpoint, "count": r.count, "avg_ms": round(r.avg_ms or 0, 2)}
            for r in rows
        ]
