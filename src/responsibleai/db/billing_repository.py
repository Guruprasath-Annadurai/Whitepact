# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable, idempotent Stripe webhook event ledger."""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import DatabaseEngine, stripe_webhook_events


def _now() -> str:
    return datetime.now(UTC).isoformat()


class BillingEventRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def begin(self, event_id: str, event_type: str, org_id: str | None) -> bool:
        try:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    insert(stripe_webhook_events).values(
                        event_id=event_id,
                        event_type=event_type,
                        org_id=org_id,
                        status="processing",
                        received_at=_now(),
                    )
                )
            return True
        except IntegrityError:
            return False

    async def complete(self, event_id: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(stripe_webhook_events)
                .where(stripe_webhook_events.c.event_id == event_id)
                .values(status="processed", processed_at=_now(), last_error=None)
            )

    async def fail(self, event_id: str, error: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(stripe_webhook_events)
                .where(stripe_webhook_events.c.event_id == event_id)
                .values(status="failed", last_error=error[:2000])
            )

    async def get(self, event_id: str) -> dict[str, str | None] | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(stripe_webhook_events).where(
                        stripe_webhook_events.c.event_id == event_id
                    )
                )
            ).fetchone()
        return dict(row._mapping) if row else None
