"""DB-backed webhook delivery log — persists delivery attempts so retries survive restarts."""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import select, update

from responsibleai.db.engine import DatabaseEngine, webhook_deliveries


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _at(seconds_from_now: float) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds_from_now)).isoformat()


class WebhookDeliveryRepository:
    """Persist webhook delivery attempts and manage the persistent retry queue."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create(
        self,
        delivery_id: str,
        webhook_id: str,
        event: str,
        payload: dict[str, Any],
        max_retries: int = 3,
    ) -> None:
        """Record a new delivery attempt (status=pending)."""
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                webhook_deliveries.insert().values(
                    id=delivery_id,
                    webhook_id=webhook_id,
                    event=event,
                    payload=json.dumps(payload),
                    status="pending",
                    attempts=0,
                    max_retries=max_retries,
                    created_at=_now(),
                )
            )

    async def record_attempt(
        self,
        delivery_id: str,
        attempt: int,
        status_code: int | None,
        error: str | None,
        success: bool,
    ) -> None:
        """Update a delivery after an attempt. Calculates next_retry_at on failure."""
        retry_delays = [1.0, 5.0, 30.0, 120.0, 600.0]

        if success:
            status = "delivered"
            next_retry_at = None
            delivered_at = _now()
        else:
            row = await self._get(delivery_id)
            max_retries = row["max_retries"] if row else 3
            if attempt < max_retries:
                status = "retrying"
                delay = retry_delays[min(attempt - 1, len(retry_delays) - 1)]
                next_retry_at = _at(delay)
            else:
                status = "failed"
                next_retry_at = None
            delivered_at = None

        stmt = (
            update(webhook_deliveries)
            .where(webhook_deliveries.c.id == delivery_id)
            .values(
                attempts=attempt,
                status=status,
                status_code=status_code,
                last_error=error,
                next_retry_at=next_retry_at,
                delivered_at=delivered_at,
            )
        )
        async with self._engine.raw.begin() as conn:
            await conn.execute(stmt)

    async def pending_retries(self) -> list[dict[str, Any]]:
        """Return deliveries due for retry (status=retrying, next_retry_at <= now)."""
        now = _now()
        stmt = (
            select(webhook_deliveries)
            .where(webhook_deliveries.c.status == "retrying")
            .where(webhook_deliveries.c.next_retry_at <= now)
            .order_by(webhook_deliveries.c.next_retry_at)
            .limit(50)
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def list(self, limit: int = 100) -> list[dict[str, Any]]:
        """Most-recent delivery log entries."""
        stmt = (
            select(webhook_deliveries)
            .order_by(webhook_deliveries.c.created_at.desc())
            .limit(limit)
        )
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [self._row_to_dict(r) for r in rows]

    async def stats(self) -> dict[str, int]:
        """Summary counts by status."""
        rows = await self.list(limit=10000)
        counts: dict[str, int] = {}
        for row in rows:
            counts[row["status"]] = counts.get(row["status"], 0) + 1
        return counts

    async def _get(self, delivery_id: str) -> dict[str, Any] | None:
        stmt = select(webhook_deliveries).where(webhook_deliveries.c.id == delivery_id)
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(stmt)).fetchone()
        return self._row_to_dict(row) if row else None

    @staticmethod
    def _row_to_dict(row: Any) -> dict[str, Any]:
        return {
            "id":            row.id,
            "webhook_id":    row.webhook_id,
            "event":         row.event,
            "payload":       json.loads(row.payload),
            "status":        row.status,
            "attempts":      row.attempts,
            "max_retries":   row.max_retries,
            "status_code":   row.status_code,
            "last_error":    row.last_error,
            "created_at":    row.created_at,
            "next_retry_at": row.next_retry_at,
            "delivered_at":  row.delivered_at,
        }
