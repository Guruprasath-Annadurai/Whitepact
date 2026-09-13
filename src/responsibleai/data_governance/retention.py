# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Data Retention Policy Evaluation and Automated Pruning Engine."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import delete, insert, select, update

from responsibleai.data_governance.backup_defense import assert_restore_readiness_admitted
from responsibleai.data_governance.legal_hold import LegalHoldManager
from responsibleai.db.engine import (
    DatabaseEngine,
    data_retention_policies,
    eval_runs,
    mcp_tool_calls,
    token_usage,
    tool_trust_scores,
)


def _now() -> str:
    return datetime.now(UTC).isoformat()


@dataclass(frozen=True)
class RetentionPolicy:
    id: str
    org_id: str
    data_category: str
    retention_period_seconds: int
    created_at: str
    updated_at: str


@dataclass(frozen=True)
class RetentionExecutionReport:
    org_id: str | None
    evaluated_policies: int
    pruned_records: dict[str, int]
    held_categories: list[str]
    executed_at: str


class RetentionManager:
    """Configures and executes automated retention policies."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine
        self._legal_hold_manager = LegalHoldManager(engine)

    async def set_retention_policy(
        self,
        org_id: str,
        data_category: str,
        retention_period_seconds: int,
    ) -> RetentionPolicy:
        """Create or update a retention policy for an org and category."""
        now = _now()
        async with self._engine.raw.begin() as conn:
            existing = (
                await conn.execute(
                    select(data_retention_policies)
                    .where(data_retention_policies.c.org_id == org_id)
                    .where(data_retention_policies.c.data_category == data_category)
                )
            ).fetchone()

            if existing:
                await conn.execute(
                    update(data_retention_policies)
                    .where(data_retention_policies.c.id == existing.id)
                    .values(
                        retention_period_seconds=retention_period_seconds,
                        updated_at=now,
                    )
                )
                pol_id = existing.id
                created_at = existing.created_at
            else:
                pol_id = str(uuid.uuid4())
                created_at = now
                await conn.execute(
                    insert(data_retention_policies).values(
                        id=pol_id,
                        org_id=org_id,
                        data_category=data_category,
                        retention_period_seconds=retention_period_seconds,
                        created_at=created_at,
                        updated_at=now,
                    )
                )

        return RetentionPolicy(
            id=pol_id,
            org_id=org_id,
            data_category=data_category,
            retention_period_seconds=retention_period_seconds,
            created_at=created_at,
            updated_at=now,
        )

    async def get_retention_policies(self, org_id: str) -> list[RetentionPolicy]:
        """Retrieve all retention policies configured for an organization."""
        async with self._engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    select(data_retention_policies).where(data_retention_policies.c.org_id == org_id)
                )
            ).fetchall()
            return [
                RetentionPolicy(
                    id=r.id,
                    org_id=r.org_id,
                    data_category=r.data_category,
                    retention_period_seconds=r.retention_period_seconds,
                    created_at=r.created_at,
                    updated_at=r.updated_at,
                )
                for r in rows
            ]

    async def run_retention_cleanup(self, org_id: str | None = None) -> RetentionExecutionReport:
        """Evaluates retention policies and prunes eligible expired records.

        Skips any category currently protected by an active legal hold.
        """
        assert_restore_readiness_admitted()

        now = _now()
        pruned_counts: dict[str, int] = {}
        held_cats: list[str] = []

        async with self._engine.raw.begin() as conn:
            query = select(data_retention_policies)
            if org_id:
                query = query.where(data_retention_policies.c.org_id == org_id)
            policies = (await conn.execute(query)).fetchall()

            for pol in policies:
                # Check legal hold
                if await self._legal_hold_manager.is_held(pol.org_id, pol.data_category, conn=conn):
                    held_cats.append(f"{pol.org_id}:{pol.data_category}")
                    continue

                # Clean up category
                if pol.data_category == "TENANT_OPERATIONAL":
                    # Prune tool_trust_scores
                    res1 = await conn.execute(
                        delete(tool_trust_scores).where(tool_trust_scores.c.org_id == pol.org_id)
                    )
                    pruned_counts["tool_trust_scores"] = pruned_counts.get("tool_trust_scores", 0) + (res1.rowcount or 0)

                    # Prune eval_runs
                    res2 = await conn.execute(
                        delete(eval_runs).where(eval_runs.c.org_id == pol.org_id)
                    )
                    pruned_counts["eval_runs"] = pruned_counts.get("eval_runs", 0) + (res2.rowcount or 0)

                    # Prune token_usage
                    res3 = await conn.execute(
                        delete(token_usage).where(token_usage.c.org_id == pol.org_id)
                    )
                    pruned_counts["token_usage"] = pruned_counts.get("token_usage", 0) + (res3.rowcount or 0)

                    # Prune mcp_tool_calls
                    res4 = await conn.execute(
                        delete(mcp_tool_calls).where(mcp_tool_calls.c.org_id == pol.org_id)
                    )
                    pruned_counts["mcp_tool_calls"] = pruned_counts.get("mcp_tool_calls", 0) + (res4.rowcount or 0)

        return RetentionExecutionReport(
            org_id=org_id,
            evaluated_policies=len(policies),
            pruned_records=pruned_counts,
            held_categories=held_cats,
            executed_at=now,
        )
