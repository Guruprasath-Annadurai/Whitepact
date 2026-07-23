"""DB-backed webhook delivery log and config storage.

Delivery log persistence lets retries survive restarts (WebhookDeliveryRepository,
original scope of this module). WebhookConfigRepository persists the webhook
*registrations* themselves — added because WebhookManager previously held
those only in an in-memory dict, so every registered webhook silently
vanished on any process restart or redeploy. See migration 0010.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import DatabaseEngine, webhook_configs, webhook_deliveries
from responsibleai.webhooks.models import WebhookConfig, WebhookEvent, WebhookProvider


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
        """Atomically claim up to 50 deliveries due for retry.

        Multi-replica note: this is DB-backed specifically so retries survive
        a restart, which also means every replica's retry worker polls the
        *same* table. A plain SELECT here would let two replicas both pick
        up the same row and double-fire the webhook. Claiming via a single
        UPDATE ... WHERE id IN (SELECT ...) RETURNING statement makes the
        claim atomic under both SQLite (whole-DB write lock) and Postgres
        (the subquery's row selection and the UPDATE happen as one
        statement, so a concurrent claim from another replica either sees
        the rows already flipped to 'claimed' or hasn't started yet — no
        window where both read 'retrying' and both act on it).

        Claiming stamps next_retry_at with the claim time (it has no other
        meaning once status='claimed'), which doubles as this fix's stale-
        claim detector: also reclaims rows stuck in 'claimed' for over 5
        minutes — the safety net for a replica that claimed a delivery and
        then crashed before firing it, which would otherwise orphan that
        retry forever.
        """
        now_dt = datetime.now(UTC)
        now = now_dt.isoformat()
        stale_claim_cutoff = (now_dt - timedelta(minutes=5)).isoformat()
        candidate_ids = (
            select(webhook_deliveries.c.id)
            .where(
                ((webhook_deliveries.c.status == "retrying") & (webhook_deliveries.c.next_retry_at <= now))
                | ((webhook_deliveries.c.status == "claimed") & (webhook_deliveries.c.next_retry_at <= stale_claim_cutoff))
            )
            .order_by(webhook_deliveries.c.next_retry_at)
            .limit(50)
        )
        claim_stmt = (
            update(webhook_deliveries)
            .where(webhook_deliveries.c.id.in_(candidate_ids))
            .values(status="claimed", next_retry_at=now)
            .returning(webhook_deliveries)
        )
        async with self._engine.raw.begin() as conn:
            rows = (await conn.execute(claim_stmt)).fetchall()
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


class WebhookConfigRepository:
    """Persist webhook registrations so they survive process restarts."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create(self, config: WebhookConfig) -> None:
        config.created_at = config.created_at or _now()
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(webhook_configs).values(
                    id=config.id,
                    org_id=config.org_id,
                    url=config.url,
                    provider=config.provider.value,
                    events=json.dumps([e.value for e in config.events]),
                    secret=config.secret or None,
                    description=config.description or None,
                    enabled=1 if config.enabled else 0,
                    max_retries=config.max_retries,
                    created_at=config.created_at,
                )
            )

    async def delete(self, webhook_id: str, org_id: str | None = None) -> bool:
        """Delete a webhook config. If org_id is given, only deletes a config
        owned by that org — callers use this to enforce tenant isolation."""
        stmt = delete(webhook_configs).where(webhook_configs.c.id == webhook_id)
        if org_id is not None:
            stmt = stmt.where(webhook_configs.c.org_id == org_id)
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(stmt)
        return result.rowcount > 0

    async def list_all(self) -> list[WebhookConfig]:
        """Load every persisted config — called once at startup to
        repopulate WebhookManager's in-memory registry."""
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(select(webhook_configs))).fetchall()
        return [self._row_to_config(r) for r in rows]

    @staticmethod
    def _row_to_config(row: Any) -> WebhookConfig:
        events = [WebhookEvent(e) for e in json.loads(row.events)]
        return WebhookConfig(
            id=row.id,
            org_id=row.org_id,
            url=row.url,
            provider=WebhookProvider(row.provider),
            events=events,
            secret=row.secret or "",
            description=row.description or "",
            enabled=bool(row.enabled),
            max_retries=row.max_retries,
            created_at=row.created_at,
        )
