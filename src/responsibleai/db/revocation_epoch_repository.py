# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Database-serialized revocation counters shared by all execution replicas."""

from datetime import UTC, datetime

from sqlalchemy import select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.ext.asyncio import AsyncConnection

from responsibleai.db.engine import DatabaseEngine
from responsibleai.db.engine import governance_revocation_epochs as epochs
from responsibleai.governance.revocation_kernel import RevocationEpoch


async def lock_epoch(conn: AsyncConnection, organization_id: str, scope: str = "governance") -> int:
    """Lock the tenant counter until the caller's transaction ends.

    The no-op UPDATE takes a PostgreSQL row lock or SQLite writer lock. All
    authority mutations must use this same transaction boundary, not a later
    best-effort bump. Unsupported databases fail closed.
    """
    if not organization_id or not scope:
        raise ValueError("An explicit organization and scope are required")
    dialect = conn.dialect.name
    if dialect not in {"postgresql", "sqlite"}:
        raise ValueError("Unsupported revocation database")
    insert = pg_insert if dialect == "postgresql" else sqlite_insert
    await conn.execute(
        insert(epochs)
        .values(
            organization_id=organization_id,
            scope=scope,
            epoch=0,
            updated_at=datetime.now(UTC).isoformat(),
        )
        .on_conflict_do_nothing(index_elements=["organization_id", "scope"])
    )
    result = await conn.execute(
        update(epochs)
        .where(
            epochs.c.organization_id == organization_id,
            epochs.c.scope == scope,
        )
        .values(epoch=epochs.c.epoch)
        .returning(epochs.c.epoch)
    )
    return int(result.scalar_one())


async def bump_epoch_on_connection(
    conn: AsyncConnection, organization_id: str, scope: str = "governance"
) -> int:
    """Advance a counter atomically inside the authority mutation transaction."""
    await lock_epoch(conn, organization_id, scope)
    result = await conn.execute(
        update(epochs)
        .where(
            epochs.c.organization_id == organization_id,
            epochs.c.scope == scope,
        )
        .values(epoch=epochs.c.epoch + 1, updated_at=datetime.now(UTC).isoformat())
        .returning(epochs.c.epoch)
    )
    return int(result.scalar_one())


class RevocationEpochRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def current(self, organization_id: str, scope: str = "governance") -> RevocationEpoch:
        if not organization_id or not scope:
            raise ValueError("An explicit organization and scope are required")
        async with self._engine.raw.connect() as conn:
            value = await conn.scalar(
                select(epochs.c.epoch).where(
                    epochs.c.organization_id == organization_id,
                    epochs.c.scope == scope,
                )
            )
        return RevocationEpoch(organization_id, scope, int(value or 0))

    async def bump(self, organization_id: str, scope: str = "governance") -> RevocationEpoch:
        async with self._engine.raw.begin() as conn:
            value = await bump_epoch_on_connection(conn, organization_id, scope)
        return RevocationEpoch(organization_id, scope, value)
