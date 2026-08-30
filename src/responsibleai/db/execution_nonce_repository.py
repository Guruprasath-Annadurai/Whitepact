"""Async repository for durable execution-nonce consumption
(Enterprise Readiness Phase 4, `governance/execution.py`'s
`ExecutionAuthorization.nonce`).

Pure additive durability: the in-memory `consumed: bool` flag on
`ExecutionAuthorization` already stops same-process replay
unconditionally, at zero setup cost -- this repository is the OPT-IN
layer that also stops it across a process restart or a second
instance, matching this codebase's established "cache/in-memory state
is an optimization, the durable store is authority" discipline
(`RevocationEpochRepository`'s own docstring states the identical
principle).

`nonce` as the table's primary key IS the atomicity guarantee -- a
concurrent second `consume()` for the same nonce fails on the
database's own UNIQUE constraint, not on any locking this module
writes itself.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlalchemy import insert
from sqlalchemy.exc import IntegrityError

from responsibleai.db.engine import DatabaseEngine, governance_execution_nonces


def _now() -> str:
    return datetime.now(UTC).isoformat()


class NonceAlreadyConsumedError(Exception):
    """Raised when `consume()` is called with a nonce that already has
    a durable row -- either a genuine replay (the same authorization
    presented twice) or a concurrent racer that won. Both are the
    correct case to refuse; this repository does not try to distinguish
    "attacker replay" from "your own retry after a lost response,"
    matching `RevocationEpochRepository`'s own precedent of not
    over-interpreting a UNIQUE-constraint hit."""

    def __init__(self, nonce: str) -> None:
        self.nonce = nonce
        super().__init__(f"Execution nonce {nonce!r} has already been consumed.")


class ExecutionNonceRepository:
    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def consume(self, nonce: str, *, authorization_id: str, organization_id: str) -> None:
        """Atomically records *nonce* as spent. Raises
        `NonceAlreadyConsumedError` if it already was -- by this exact
        process, a different process, or a concurrent racer in this
        same process. A single `INSERT` is the entire atomicity
        mechanism; there is no read-then-write race window to reason
        about, unlike `RevocationEpochRepository.bump()`'s
        update-or-insert shape (that primitive needs to handle "no row
        yet" as a normal case; this one's normal case is always "insert
        a brand new row," so a plain `INSERT` is already correct and
        simpler)."""
        try:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    insert(governance_execution_nonces).values(
                        nonce=nonce,
                        authorization_id=authorization_id,
                        organization_id=organization_id,
                        consumed_at=_now(),
                    )
                )
        except IntegrityError as exc:
            raise NonceAlreadyConsumedError(nonce) from exc
