# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Deterministic synthetic mutating tool state for V1 exactly-once proofs.

``test.counter.increment`` is not a customer product feature. It exists so
governed execution can be observed without calling an opaque downstream.
The table is not authority. Incrementing it is a consequential effect only
after canonical admission. Production refuses the tool.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from responsibleai.dashboard.config import is_production_environment
from responsibleai.db.engine import DatabaseEngine, test_consequential_counters

SYNTHETIC_COUNTER_TOOL = "test.counter.increment"


class SyntheticAcknowledgementLostError(RuntimeError):
    """Mutation applied; caller acknowledgement was lost."""


_engine: DatabaseEngine | None = None


def bind_counter_engine(engine: DatabaseEngine | None) -> None:
    global _engine
    _engine = engine


def _now() -> str:
    return datetime.now(UTC).isoformat()


async def snapshot(organization_id: str) -> dict[str, int]:
    if _engine is None:
        raise RuntimeError("Synthetic counter repository is not bound")
    async with _engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(test_consequential_counters).where(
                    test_consequential_counters.c.organization_id == organization_id
                )
            )
        ).fetchone()
    if row is None:
        return {"counter": 0, "downstream_call_count": 0}
    return {"counter": int(row.counter), "downstream_call_count": int(row.downstream_call_count)}


async def increment(
    organization_id: str,
    *,
    fail_after_effect: bool = False,
) -> dict[str, Any]:
    """Apply one downstream mutation. Must only be called after admission."""
    import os

    from responsibleai.sovereign.zero_effect import record_consequential_invocation

    record_consequential_invocation()

    environment = os.environ.get("WHITEPACT_ENV") or os.environ.get("RAI_ENVIRONMENT") or ""
    if is_production_environment(environment):
        raise RuntimeError("Synthetic counter tool is forbidden in production")
    if not organization_id:
        raise ValueError("organization_id is required")
    if _engine is None:
        raise RuntimeError("Synthetic counter repository is not bound")

    async with _engine.raw.begin() as conn:
        updated = await conn.execute(
            test_consequential_counters.update()
            .where(test_consequential_counters.c.organization_id == organization_id)
            .values(
                counter=test_consequential_counters.c.counter + 1,
                downstream_call_count=test_consequential_counters.c.downstream_call_count + 1,
                updated_at=_now(),
            )
        )
        if updated.rowcount == 0:
            try:
                await conn.execute(
                    test_consequential_counters.insert().values(
                        organization_id=organization_id,
                        counter=1,
                        downstream_call_count=1,
                        updated_at=_now(),
                    )
                )
            except IntegrityError:
                await conn.execute(
                    test_consequential_counters.update()
                    .where(test_consequential_counters.c.organization_id == organization_id)
                    .values(
                        counter=test_consequential_counters.c.counter + 1,
                        downstream_call_count=test_consequential_counters.c.downstream_call_count
                        + 1,
                        updated_at=_now(),
                    )
                )
    state = await snapshot(organization_id)
    if fail_after_effect:
        raise SyntheticAcknowledgementLostError("synthetic_ack_lost")
    return {"ok": True, "organization_id": organization_id, **state}
