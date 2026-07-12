"""Async repository for the governance audit log.

Every API request is recorded here by the AuditLogMiddleware.
Supports filtered queries and auto-cleanup of old entries.

Tamper-evidence: entries form a single hash chain across the whole log
(entry_hash = sha256(prev_hash + entry fields)). This detects post-hoc
row edits/deletes made directly against the database — it does not defend
against an attacker with DB write access recomputing the whole chain from
scratch. Treat it as SOC2/audit evidence of integrity monitoring, not a
cryptographic guarantee against a fully compromised database.

The chain is process-local: writes are serialized with an in-process lock,
so it is only strictly ordered within one server process. Multi-replica
deployments get one independent chain per replica, not one global chain —
`verify_chain()` reports on whichever replica's DB it's pointed at.
"""

from __future__ import annotations

import asyncio
import hashlib
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, func, insert, select

from responsibleai.db.engine import DatabaseEngine, audit_log
from responsibleai.rbac.models import AuditEntry

_GENESIS_HASH = "0" * 64


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _days_ago(days: int) -> str:
    return (datetime.now(UTC) - timedelta(days=days)).isoformat()


def _compute_entry_hash(prev_hash: str, entry: AuditEntry) -> str:
    material = "|".join([
        prev_hash,
        entry.id,
        entry.timestamp,
        entry.org_id or "",
        entry.key_id or "",
        entry.endpoint,
        entry.method,
        str(entry.status_code or ""),
    ])
    return hashlib.sha256(material.encode()).hexdigest()


class AuditRepository:
    """Write and query the audit log table."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self._chain_lock = asyncio.Lock()
        self._last_hash: str | None = None
        self._hydrated = False

    async def _hydrate_chain(self) -> None:
        """Load the tail hash of the existing chain on first write after startup."""
        if self._hydrated:
            return
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(audit_log.c.entry_hash)
                .where(audit_log.c.entry_hash.is_not(None))
                .order_by(audit_log.c.timestamp.desc())
                .limit(1)
            )).fetchone()
        self._last_hash = row.entry_hash if row else None
        self._hydrated = True

    async def write(self, entry: AuditEntry) -> None:
        """Persist one audit entry, chained to the previous entry's hash."""
        if not entry.timestamp:
            entry.timestamp = _now()

        async with self._chain_lock:
            await self._hydrate_chain()
            prev_hash = self._last_hash or _GENESIS_HASH
            entry.prev_hash = prev_hash
            entry.entry_hash = _compute_entry_hash(prev_hash, entry)

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
                    entry_hash=entry.entry_hash,
                    prev_hash=entry.prev_hash,
                ))
            self._last_hash = entry.entry_hash

    async def verify_chain(self, days: int = 90) -> dict[str, Any]:
        """Recompute the hash chain over the last *days* and report tampering.

        Returns intact=True only if every entry's stored hash matches a
        fresh recomputation from its fields and the previous entry's hash.
        """
        cutoff = _days_ago(days)
        stmt = (
            select(audit_log)
            .where(audit_log.c.timestamp >= cutoff)
            .order_by(audit_log.c.timestamp.asc())
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()

        broken_at: list[dict[str, Any]] = []
        expected_prev = _GENESIS_HASH
        checked = 0
        for r in rows:
            if r.entry_hash is None:
                # Pre-integrity-migration entries have no hash — skip, don't flag.
                continue
            checked += 1
            entry = AuditEntry(
                id=r.id, timestamp=r.timestamp, org_id=r.org_id, key_id=r.key_id,
                endpoint=r.endpoint, method=r.method, status_code=r.status_code,
            )
            recomputed = _compute_entry_hash(expected_prev, entry)
            if r.prev_hash != expected_prev or recomputed != r.entry_hash:
                broken_at.append({
                    "id": r.id,
                    "timestamp": r.timestamp,
                    "expected_prev_hash": expected_prev,
                    "stored_prev_hash": r.prev_hash,
                })
            expected_prev = r.entry_hash

        return {
            "intact": len(broken_at) == 0,
            "entries_checked": checked,
            "entries_scanned": len(rows),
            "broken_links": broken_at,
            "days": days,
        }

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
                "entry_hash": r.entry_hash,
                "prev_hash": r.prev_hash,
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
