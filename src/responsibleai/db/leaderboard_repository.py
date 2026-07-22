"""Async repository for the public cross-model trust leaderboard.

Two tables: `leaderboard_models` (the registry of which models are tracked)
and `leaderboard_runs` (one row per completed evaluation pass, written by
`LeaderboardRunner` via scripts/run_leaderboard_eval.py or the admin
POST /api/leaderboard/run endpoint). Neither table carries an org_id — this
data is global and public by design, not tenant-scoped.
"""

from __future__ import annotations

import json
import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import insert, select, update

from responsibleai.db.engine import DatabaseEngine, leaderboard_models, leaderboard_runs
from responsibleai.leaderboard.models import LeaderboardRunResult


def _now() -> str:
    return datetime.now(UTC).isoformat()


class LeaderboardRepository:
    """Write and query the leaderboard model registry and run history."""

    def __init__(self, engine: DatabaseEngine) -> None:
        self._engine = engine

    # ── Model registry ──────────────────────────────────────────────────────

    async def register_model(
        self,
        model: str,
        provider: str,
        display_name: str | None = None,
        adapter: str = "mock",
        active: bool = True,
    ) -> dict[str, Any]:
        """Insert a new tracked model, or update it in place if the
        (model, provider) pair already exists — idempotent by design so a
        deploy script can re-register the full model list every run."""
        async with self._engine.raw.connect() as conn:
            existing = (await conn.execute(
                select(leaderboard_models).where(
                    leaderboard_models.c.model == model,
                    leaderboard_models.c.provider == provider,
                )
            )).fetchone()

        if existing:
            async with self._engine.raw.begin() as conn:
                await conn.execute(
                    update(leaderboard_models)
                    .where(leaderboard_models.c.id == existing.id)
                    .values(display_name=display_name, adapter=adapter, active=int(active))
                )
            return await self.get_model(model, provider)  # type: ignore[return-value]

        row_id = str(uuid.uuid4())
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(leaderboard_models).values(
                id=row_id, model=model, provider=provider, display_name=display_name,
                adapter=adapter, active=int(active), added_at=_now(),
            ))
        return await self.get_model(model, provider)  # type: ignore[return-value]

    async def get_model(self, model: str, provider: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(leaderboard_models).where(
                    leaderboard_models.c.model == model,
                    leaderboard_models.c.provider == provider,
                )
            )).fetchone()
        return self._model_to_dict(row) if row else None

    async def list_models(self, active_only: bool = False) -> list[dict[str, Any]]:
        stmt = select(leaderboard_models).order_by(leaderboard_models.c.added_at.asc())
        if active_only:
            stmt = stmt.where(leaderboard_models.c.active == 1)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [self._model_to_dict(r) for r in rows]

    async def set_model_active(self, model: str, provider: str, active: bool) -> bool:
        async with self._engine.raw.begin() as conn:
            result = await conn.execute(
                update(leaderboard_models)
                .where(leaderboard_models.c.model == model, leaderboard_models.c.provider == provider)
                .values(active=int(active))
            )
        return result.rowcount > 0

    @staticmethod
    def _model_to_dict(r: Any) -> dict[str, Any]:
        return {
            "id": r.id, "model": r.model, "provider": r.provider,
            "display_name": r.display_name, "adapter": r.adapter,
            "active": bool(r.active), "added_at": r.added_at,
        }

    # ── Runs ─────────────────────────────────────────────────────────────────

    async def create_run(self, result: LeaderboardRunResult) -> dict[str, Any]:
        async with self._engine.raw.begin() as conn:
            await conn.execute(insert(leaderboard_runs).values(
                id=result.id, model=result.model, provider=result.provider,
                created_at=result.created_at, methodology_version=result.methodology_version,
                overall_score=result.trust_score.overall, grade=result.trust_score.grade,
                risk_level=result.trust_score.risk_level,
                fairness=result.trust_score.fairness, privacy=result.trust_score.privacy,
                security=result.trust_score.security, robustness=result.trust_score.robustness,
                compliance=result.trust_score.compliance, authenticity=result.trust_score.authenticity,
                dimensions_live=json.dumps(result.dimensions_live),
                truthfulqa_accuracy=result.truthfulqa_accuracy, bbq_bias_rate=result.bbq_bias_rate,
                hellaswag_accuracy=result.hellaswag_accuracy, security_score=result.security_score,
                privacy_pii_leak_rate=result.privacy_pii_leak_rate,
                avg_hallucination_risk=result.avg_hallucination_risk,
                sample_size=result.sample_size,
                findings=json.dumps([f.to_dict() for f in result.findings]),
            ))
        return await self.get_run(result.id)  # type: ignore[return-value]

    async def get_run(self, run_id: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(leaderboard_runs).where(leaderboard_runs.c.id == run_id)
            )).fetchone()
        return self._run_to_dict(row) if row else None

    async def latest_run(self, model: str, provider: str) -> dict[str, Any] | None:
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(
                select(leaderboard_runs)
                .where(leaderboard_runs.c.model == model, leaderboard_runs.c.provider == provider)
                .order_by(leaderboard_runs.c.created_at.desc())
                .limit(1)
            )).fetchone()
        return self._run_to_dict(row) if row else None

    async def history(self, model: str, provider: str, limit: int = 30) -> list[dict[str, Any]]:
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(
                select(leaderboard_runs)
                .where(leaderboard_runs.c.model == model, leaderboard_runs.c.provider == provider)
                .order_by(leaderboard_runs.c.created_at.desc())
                .limit(limit)
            )).fetchall()
        return [self._run_to_dict(r) for r in rows]

    async def ranked_leaderboard(self) -> list[dict[str, Any]]:
        """One row per active model — its most recent run, ranked by overall_score desc."""
        active_models = await self.list_models(active_only=True)
        rows = []
        for m in active_models:
            latest = await self.latest_run(m["model"], m["provider"])
            if latest is not None:
                rows.append({**latest, "display_name": m["display_name"]})
        rows.sort(key=lambda r: r["overall_score"], reverse=True)
        for i, r in enumerate(rows, start=1):
            r["rank"] = i
        return rows

    @staticmethod
    def _run_to_dict(r: Any) -> dict[str, Any]:
        return {
            "id": r.id, "model": r.model, "provider": r.provider, "created_at": r.created_at,
            "methodology_version": r.methodology_version,
            "overall_score": r.overall_score, "grade": r.grade, "risk_level": r.risk_level,
            "dimensions": {
                "fairness": round(r.fairness * 100, 2), "privacy": round(r.privacy * 100, 2),
                "security": round(r.security * 100, 2), "robustness": round(r.robustness * 100, 2),
                "compliance": round(r.compliance * 100, 2), "authenticity": round(r.authenticity * 100, 2),
            },
            "dimensions_live": json.loads(r.dimensions_live),
            "raw_metrics": {
                "truthfulqa_accuracy": r.truthfulqa_accuracy, "bbq_bias_rate": r.bbq_bias_rate,
                "hellaswag_accuracy": r.hellaswag_accuracy, "security_score": r.security_score,
                "privacy_pii_leak_rate": r.privacy_pii_leak_rate,
                "avg_hallucination_risk": r.avg_hallucination_risk,
            },
            "sample_size": r.sample_size,
            "findings": (findings := json.loads(r.findings)),
            "findings_count": len(findings),
        }
