# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Durable, idempotent Paddle webhook event ledger with conflict and replay protection."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import DatabaseEngine, paddle_webhook_events


def _now() -> str:
    return datetime.now(UTC).isoformat()


class PaddleBillingEventRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def begin(
        self,
        event_id: str,
        event_type: str,
        payload_hash: str,
        org_id: str | None = None,
        occurred_at: str | None = None,
        entity_id: str | None = None,
    ) -> bool:
        """Record the receipt of a Paddle webhook event atomically.

        Returns True if this is a new event to process.
        Returns False if this event was already received with the same payload.
        Raises ValueError if an event with the same ID arrives with a different payload hash.
        """
        try:
            async with self._engine.raw.begin() as conn:
                existing = (
                    await conn.execute(
                        select(paddle_webhook_events).where(
                            paddle_webhook_events.c.event_id == event_id
                        )
                    )
                ).fetchone()
                if existing is not None:
                    if existing.payload_hash != payload_hash:
                        raise ValueError(
                            f"Conflicting payload for identical Paddle event ID: {event_id}"
                        )
                    return False

                values: dict[str, Any] = {
                    "event_id": event_id,
                    "event_type": event_type,
                    "org_id": org_id,
                    "payload_hash": payload_hash,
                    "status": "processing",
                    "received_at": _now(),
                }
                if "occurred_at" in paddle_webhook_events.c:
                    values["occurred_at"] = occurred_at
                if "entity_id" in paddle_webhook_events.c:
                    values["entity_id"] = entity_id

                await conn.execute(insert(paddle_webhook_events).values(**values))
                return True
        except IntegrityError:
            existing_rec = await self.get(event_id)
            if existing_rec is not None and existing_rec.get("payload_hash") != payload_hash:
                raise ValueError(
                    f"Conflicting payload for identical Paddle event ID: {event_id}"
                ) from None
            return False

    async def set_org(self, event_id: str, org_id: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(paddle_webhook_events)
                .where(paddle_webhook_events.c.event_id == event_id)
                .values(org_id=org_id)
            )

    async def complete(self, event_id: str, org_id: str | None = None) -> None:
        async with self._engine.raw.begin() as conn:
            values: dict[str, Any] = {
                "status": "processed",
                "processed_at": _now(),
                "last_error": None,
            }
            if org_id is not None:
                values["org_id"] = org_id
            await conn.execute(
                update(paddle_webhook_events)
                .where(paddle_webhook_events.c.event_id == event_id)
                .values(**values)
            )

    async def fail(self, event_id: str, error: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                update(paddle_webhook_events)
                .where(paddle_webhook_events.c.event_id == event_id)
                .values(status="failed", last_error=error[:2000])
            )

    async def get(self, event_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(paddle_webhook_events).where(
                        paddle_webhook_events.c.event_id == event_id
                    )
                )
            ).fetchone()
        return dict(row._mapping) if row else None
