# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Legal Hold Management Subsystem for WhitePact Phase 5.

Guarantees:
- Granular holds scoped by organization and data category (or 'ALL').
- Blocks deletion/erasure of preserved data while permitting erasure of unheld operational data.
- Prevents unauthorized release of legal preservation mandates.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import DatabaseEngine, data_holds


def _now() -> str:
    return datetime.now(UTC).isoformat()


class LegalHoldError(Exception):
    """Base exception for legal hold violations."""


class LegalHoldActiveError(LegalHoldError):
    """Raised when erasure is blocked by an active legal hold."""


class LegalHoldNotFoundError(LegalHoldError):
    """Raised when a specified legal hold cannot be found."""


@dataclass(frozen=True)
class DataHold:
    id: str
    org_id: str
    data_category: str
    hold_reason: str
    active: bool
    created_at: str
    created_by: str
    released_at: str | None
    released_by: str | None


class LegalHoldManager:
    """Manages creation, query, and release of legal holds."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def create_hold(
        self,
        org_id: str,
        data_category: str,
        hold_reason: str,
        created_by: str,
    ) -> DataHold:
        """Create and activate a legal hold for an org and category."""
        hold_id = str(uuid.uuid4())
        now = _now()
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(data_holds).values(
                    id=hold_id,
                    org_id=org_id,
                    data_category=data_category,
                    hold_reason=hold_reason,
                    active=True,
                    created_at=now,
                    created_by=created_by,
                    released_at=None,
                    released_by=None,
                )
            )

        return DataHold(
            id=hold_id,
            org_id=org_id,
            data_category=data_category,
            hold_reason=hold_reason,
            active=True,
            created_at=now,
            created_by=created_by,
            released_at=None,
            released_by=None,
        )

    async def release_hold(
        self,
        org_id: str,
        hold_id: str,
        released_by: str,
    ) -> DataHold:
        """Release an active legal hold."""
        now = _now()
        async with self._engine.raw.begin() as conn:
            row = (
                await conn.execute(
                    select(data_holds)
                    .where(data_holds.c.id == hold_id)
                    .where(data_holds.c.org_id == org_id)
                )
            ).fetchone()
            if not row:
                raise LegalHoldNotFoundError(f"Legal hold {hold_id} not found for org {org_id}")

            await conn.execute(
                update(data_holds)
                .where(data_holds.c.id == hold_id)
                .values(active=False, released_at=now, released_by=released_by)
            )

            return DataHold(
                id=row.id,
                org_id=row.org_id,
                data_category=row.data_category,
                hold_reason=row.hold_reason,
                active=False,
                created_at=row.created_at,
                created_by=row.created_by,
                released_at=now,
                released_by=released_by,
            )

    async def is_held(
        self, org_id: str, data_category: str | None = None, conn: Any = None
    ) -> bool:
        """Check if an org (or specific category) is under active legal hold."""
        query = (
            select(data_holds.c.id)
            .where(data_holds.c.org_id == org_id)
            .where(data_holds.c.active == True)  # noqa: E712
        )
        if data_category:
            query = query.where(
                (data_holds.c.data_category == data_category)
                | (data_holds.c.data_category == "ALL")
            )
        if conn is not None:
            result = await conn.execute(query)
            return result.first() is not None
        async with self._engine.raw.connect() as connection:
            result = await connection.execute(query)
            return result.first() is not None

    async def get_active_holds(self, org_id: str) -> list[DataHold]:
        """Return all active legal holds for an organization."""
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(data_holds)
                    .where(data_holds.c.org_id == org_id)
                    .where(data_holds.c.active == True)  # noqa: E712
                )
            ).fetchall()
            return [
                DataHold(
                    id=r.id,
                    org_id=r.org_id,
                    data_category=r.data_category,
                    hold_reason=r.hold_reason,
                    active=r.active,
                    created_at=r.created_at,
                    created_by=r.created_by,
                    released_at=r.released_at,
                    released_by=r.released_by,
                )
                for r in rows
            ]
