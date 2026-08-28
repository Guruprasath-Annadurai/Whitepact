# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Async repository for ``AutonomyBudgetPolicy`` (v3 authority-layer
work) -- one row per org, fetched by ``mcp/governance_integration.py``
on every hosted MCP tool call and passed to
``WhitePactRuntimeGateway.evaluate()`` as ``autonomy_budget``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select, update

from responsibleai.db.engine import DatabaseEngine, org_autonomy_budgets
from responsibleai.governance.autonomy_budget import AutonomyBudgetPolicy


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _row_to_policy(row: Any) -> AutonomyBudgetPolicy:
    return AutonomyBudgetPolicy(
        max_autonomous_actions=row.max_autonomous_actions,
        window_minutes=row.window_minutes,
    )


class OrgAutonomyBudgetRepository:
    """CRUD over one autonomy-budget row per organization. Unlike
    ``OrgAuthorityCeilingRepository``, there's no "all-null means
    unrestricted" row shape here -- both fields are required (a budget
    row that existed but capped nothing would be a contradiction), so
    "no budget configured" is represented purely by row absence."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    async def get(self, org_id: str) -> AutonomyBudgetPolicy | None:
        """``None`` for an org with no autonomy budget configured --
        the caller treats that as "no ``autonomy_budget`` to pass,"
        identical to pre-feature behavior."""
        async with self._engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(org_autonomy_budgets).where(org_autonomy_budgets.c.org_id == org_id)
                )
            ).fetchone()
        return _row_to_policy(row) if row is not None else None

    async def set(self, org_id: str, policy: AutonomyBudgetPolicy) -> None:
        """Upserts the org's autonomy budget wholesale."""
        now = _now()
        values = {
            "max_autonomous_actions": policy.max_autonomous_actions,
            "window_minutes": policy.window_minutes,
            "updated_at": now,
        }
        async with self._engine.raw.begin() as conn:
            existing = (
                await conn.execute(
                    select(org_autonomy_budgets.c.org_id).where(
                        org_autonomy_budgets.c.org_id == org_id
                    )
                )
            ).scalar()
            if existing is None:
                await conn.execute(insert(org_autonomy_budgets).values(org_id=org_id, **values))
            else:
                await conn.execute(
                    update(org_autonomy_budgets)
                    .where(org_autonomy_budgets.c.org_id == org_id)
                    .values(**values)
                )

    async def delete(self, org_id: str) -> None:
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                delete(org_autonomy_budgets).where(org_autonomy_budgets.c.org_id == org_id)
            )
