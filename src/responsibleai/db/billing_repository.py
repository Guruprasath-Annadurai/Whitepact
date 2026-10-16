# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable, idempotent Stripe webhook event ledger."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import DatabaseEngine, stripe_webhook_events


def _now() -> str:
    return datetime.now(UTC).isoformat()


# A delivery that crashed between begin() and complete() leaves the row "processing". After this
# long the provider's retry may take it over; before it, a concurrent delivery is a real duplicate.
STALE_PROCESSING_AFTER = timedelta(minutes=10)


def is_reclaimable(
    status: str | None, received_at: str | None, *, now: datetime | None = None
) -> bool:
    """A failed event, or one stuck in 'processing' past the stale window, may be retried."""
    if status == "failed":
        return True
    if status != "processing" or not received_at:
        return False
    try:
        started = datetime.fromisoformat(received_at)
    except ValueError:
        return True  # an unreadable timestamp must not block a customer's plan change forever
    if started.tzinfo is None:
        started = started.replace(tzinfo=UTC)
    return (now or datetime.now(UTC)) - started >= STALE_PROCESSING_AFTER


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
            record = await self.get(event_id)
            if record is None and org_id is not None:
                # Foreign key violation on unknown or uncommitted org_id.
                # Record the event with org_id=None so it is durably audited and can be classified.
                try:
                    async with self._engine.raw.begin() as conn:
                        await conn.execute(
                            insert(stripe_webhook_events).values(
                                event_id=event_id,
                                event_type=event_type,
                                org_id=None,
                                status="processing",
                                received_at=_now(),
                            )
                        )
                    return True
                except IntegrityError:
                    return await self._reclaim(event_id)
            return await self._reclaim(event_id)

    async def _reclaim(self, event_id: str) -> bool:
        """Take over a failed or abandoned event, atomically (compare-and-swap on the observed
        status and received_at), so two concurrent retries cannot both process it. Returns True
        only to the single caller that won. A processed or in-flight event stays a duplicate.

        Without this a provider retry after a failed ``set_plan`` was answered "duplicate" and the
        customer's plan change was lost for good."""
        record = await self.get(event_id)
        if record is None or not is_reclaimable(record["status"], record["received_at"]):
            return False
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(stripe_webhook_events)
                .where(
                    stripe_webhook_events.c.event_id == event_id,
                    stripe_webhook_events.c.status == record["status"],
                    stripe_webhook_events.c.received_at == record["received_at"],
                )
                .values(status="processing", received_at=_now())
            )
        return bool(result.rowcount == 1)

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
