"""Persist and query Model Evaluation Framework results."""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import delete, insert, select

from responsibleai.db.engine import DatabaseEngine, eval_baselines, eval_runs


class EvalRepository:
    """Read/write eval run results and model baselines."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    # ── Eval runs ─────────────────────────────────────────────────────────────

    async def save_run(
        self,
        run_type: str,
        model: str,
        payload: dict[str, Any],
        provider: str = "",
        suite: str | None = None,
        org_id: str | None = None,
    ) -> str:
        run_id = payload.get("id") or str(uuid.uuid4())
        created_at = payload.get("created_at") or datetime.now(UTC).isoformat()
        async with self._engine.raw.begin() as conn:
            await conn.execute(
                insert(eval_runs).values(
                    id=run_id,
                    run_type=run_type,
                    model=model,
                    provider=provider,
                    suite=suite,
                    org_id=org_id,
                    created_at=created_at,
                    payload=json.dumps(payload),
                )
            )
        return run_id

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(eval_runs).where(eval_runs.c.id == run_id)
            )).fetchone()
        if row is None:
            return None
        return {**dict(row._mapping), "payload": json.loads(row.payload)}

    async def list_runs(
        self,
        run_type: str | None = None,
        model: str | None = None,
        org_id: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[dict[str, Any]]:
        q = select(
            eval_runs.c.id,
            eval_runs.c.run_type,
            eval_runs.c.model,
            eval_runs.c.provider,
            eval_runs.c.suite,
            eval_runs.c.org_id,
            eval_runs.c.created_at,
        ).order_by(eval_runs.c.created_at.desc()).limit(limit).offset(offset)
        if run_type:
            q = q.where(eval_runs.c.run_type == run_type)
        if model:
            q = q.where(eval_runs.c.model == model)
        if org_id:
            q = q.where(eval_runs.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(q)).fetchall()
        return [dict(r._mapping) for r in rows]

    async def delete_run(self, run_id: str) -> bool:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                delete(eval_runs).where(eval_runs.c.id == run_id)
            )
        return result.rowcount > 0

    # ── Baselines ─────────────────────────────────────────────────────────────

    async def set_baseline(
        self,
        model: str,
        suite: str,
        metric: str,
        score: float,
        org_id: str | None = None,
    ) -> None:
        updated_at = datetime.now(UTC).isoformat()
        async with self._engine.raw.begin() as conn:
            existing = (await conn.execute(
                select(eval_baselines.c.id).where(
                    eval_baselines.c.model == model,
                    eval_baselines.c.suite == suite,
                    eval_baselines.c.metric == metric,
                )
            )).fetchone()
            if existing:
                await conn.execute(
                    eval_baselines.update()
                    .where(eval_baselines.c.id == existing.id)
                    .values(score=score, updated_at=updated_at, org_id=org_id)
                )
            else:
                await conn.execute(
                    insert(eval_baselines).values(
                        id=str(uuid.uuid4()),
                        model=model,
                        suite=suite,
                        metric=metric,
                        score=score,
                        org_id=org_id,
                        updated_at=updated_at,
                    )
                )

    async def get_baselines(self, model: str) -> dict[str, float]:
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(
                select(eval_baselines).where(eval_baselines.c.model == model)
            )).fetchall()
        return {f"{r.suite}:{r.metric}": r.score for r in rows}

    async def delete_baselines(self, model: str) -> int:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                delete(eval_baselines).where(eval_baselines.c.model == model)
            )
        return result.rowcount
