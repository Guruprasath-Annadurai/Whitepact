"""Async repository for `RevocationEpoch` (Heart Phase H9,
governance/revocation_kernel.py) -- Heart Production Closure Gap B.

`database/shared durable state = authority; cache = optimization
only`: this repository IS the authority. There is no in-process cache
in front of it anywhere in this module -- every `current()` call reads
the row fresh. `bump()` is the only mutation, and is written to be
correct under concurrent callers (two instances bumping the same
scope at once) without relying on any particular DB's isolation level
beyond what a single `UPDATE`/`INSERT` statement already guarantees.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import DatabaseEngine, governance_revocation_epochs
from responsibleai.governance.revocation_kernel import RevocationEpoch

_MAX_BUMP_RACE_RETRIES = 5


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_epoch(row: Any) -> RevocationEpoch:
    return RevocationEpoch(organization_id=row.organization_id, scope=row.scope, epoch=row.epoch)


class RevocationEpochRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def current(self, organization_id: str, scope: str) -> RevocationEpoch:
        """The scope's current epoch, or `epoch=0` (matching
        `RevocationEpoch`'s own in-memory default) if the scope has
        never been bumped and so has no row yet -- a scope that has
        never had anything revoked is not an error condition."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(governance_revocation_epochs).where(
                        governance_revocation_epochs.c.organization_id == organization_id,
                        governance_revocation_epochs.c.scope == scope,
                    )
                )
            ).fetchone()
        if row is None:
            return RevocationEpoch(organization_id=organization_id, scope=scope, epoch=0)
        return _row_to_epoch(row)

    async def bump(self, organization_id: str, scope: str) -> RevocationEpoch:
        """Atomically advances `(organization_id, scope)`'s epoch by
        exactly one and returns the new value.

        Two-step, race-safe against concurrent bumpers on any SQL
        backend without depending on dialect-specific upsert syntax:

        1. Try an `UPDATE ... SET epoch = epoch + 1` (a single atomic
           statement on every backend -- the new value is computed by
           the database from whatever the current row holds at the
           instant it is written, not from a value read earlier in
           this process). If a row was affected, done.
        2. If no row existed yet (`rowcount == 0`), try `INSERT` with
           `epoch=1` (the first bump from the implicit epoch-0
           baseline). If a concurrent bumper's INSERT wins the race
           for the same primary key, this INSERT raises
           `IntegrityError` -- caught, and the loop retries the UPDATE
           (which will now find the concurrently-inserted row and
           advance it), bounded by `_MAX_BUMP_RACE_RETRIES`.
        """
        for _ in range(_MAX_BUMP_RACE_RETRIES):
            async with self._engine.raw.begin() as conn:
                result = await conn.execute(
                    update(governance_revocation_epochs)
                    .where(
                        governance_revocation_epochs.c.organization_id == organization_id,
                        governance_revocation_epochs.c.scope == scope,
                    )
                    .values(epoch=governance_revocation_epochs.c.epoch + 1, updated_at=_now())
                )
                if result.rowcount and result.rowcount > 0:
                    # Read the new value back on this SAME connection/
                    # transaction, not via current() -- that would try
                    # to check out a second connection from the pool
                    # while this one is still held open by this `async
                    # with` block, deadlocking any pool with no spare
                    # connections (e.g. the ":memory:" engine's
                    # pool_size=1, max_overflow=0).
                    row = (
                        await conn.execute(
                            select(governance_revocation_epochs).where(
                                governance_revocation_epochs.c.organization_id == organization_id,
                                governance_revocation_epochs.c.scope == scope,
                            )
                        )
                    ).fetchone()
                    assert row is not None
                    return _row_to_epoch(row)

            try:
                async with self._engine.raw.begin() as conn:
                    await conn.execute(
                        insert(governance_revocation_epochs).values(
                            organization_id=organization_id,
                            scope=scope,
                            epoch=1,
                            updated_at=_now(),
                        )
                    )
                return RevocationEpoch(organization_id=organization_id, scope=scope, epoch=1)
            except IntegrityError:
                continue  # lost the insert race -- retry the UPDATE branch

        raise RuntimeError(
            f"RevocationEpochRepository.bump() could not complete for "
            f"({organization_id!r}, {scope!r}) after {_MAX_BUMP_RACE_RETRIES} "
            "retries -- unexpectedly high contention."
        )
