"""Async repository classes — thin async wrappers over the schema tables."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import func, select, text

from responsibleai.cost.models import (
    BudgetPolicy,
    BudgetStatus,
    CostRecord,
    TokenUsage,
    get_pricing,
)
from responsibleai.db.engine import DatabaseEngine, token_usage, trust_scores
from responsibleai.trust.score import TrustScore


class CostRepository:
    """
    Async replacement for the synchronous CostTracker DB operations.

    Backed by any SQLAlchemy-supported database (SQLite, PostgreSQL, etc.).
    Use CostTracker directly for in-process synchronous SQLite access.
    """

    def __init__(self, engine: DatabaseEngine, policy: BudgetPolicy | None = None) -> None:
        self._engine = engine
        self._policy = policy or BudgetPolicy()

    async def record(self, usage: TokenUsage) -> CostRecord:
        pricing = get_pricing(usage.provider, usage.model)
        input_cost  = pricing.cost_for(usage.input_tokens, 0)
        output_cost = pricing.cost_for(0, usage.output_tokens)
        total_cost  = input_cost + output_cost

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                token_usage.insert().prefix_with("OR IGNORE").values(
                    request_id    = usage.request_id,
                    org_id        = usage.org_id,
                    provider      = usage.provider,
                    model         = usage.model,
                    team          = usage.team,
                    application   = usage.application,
                    input_tokens  = usage.input_tokens,
                    output_tokens = usage.output_tokens,
                    cached_tokens = usage.cached_tokens,
                    input_cost    = input_cost,
                    output_cost   = output_cost,
                    total_cost    = total_cost,
                    prompt_hash   = usage.prompt_hash,
                    metadata      = json.dumps(usage.metadata),
                    recorded_at   = usage.timestamp.isoformat(),
                )
            )

        return CostRecord(
            usage=usage, pricing=pricing,
            input_cost=input_cost, output_cost=output_cost, total_cost=total_cost,
        )

    async def total_cost(self, days: int | None = None, org_id: str | None = None) -> float:
        stmt = select(func.coalesce(func.sum(token_usage.c.total_cost), 0.0))
        if days is not None:
            stmt = stmt.where(token_usage.c.recorded_at >= _days_ago_iso(days))
        if org_id is not None:
            stmt = stmt.where(token_usage.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            result = await conn.execute(stmt)
            return float(result.scalar() or 0.0)

    async def total_tokens(self, days: int | None = None, org_id: str | None = None) -> dict[str, int]:
        stmt = select(
            func.coalesce(func.sum(token_usage.c.input_tokens), 0),
            func.coalesce(func.sum(token_usage.c.output_tokens), 0),
        )
        if days is not None:
            stmt = stmt.where(token_usage.c.recorded_at >= _days_ago_iso(days))
        if org_id is not None:
            stmt = stmt.where(token_usage.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(stmt)).one()
        inp, out = int(row[0]), int(row[1])
        return {"input": inp, "output": out, "total": inp + out}

    async def request_count(self, days: int | None = None, org_id: str | None = None) -> int:
        stmt = select(func.count()).select_from(token_usage)
        if days is not None:
            stmt = stmt.where(token_usage.c.recorded_at >= _days_ago_iso(days))
        if org_id is not None:
            stmt = stmt.where(token_usage.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            return int((await conn.execute(stmt)).scalar() or 0)

    async def get_model_breakdown(self, days: int | None = None, org_id: str | None = None) -> dict[str, float]:
        model_col = (token_usage.c.provider + text("'/'") + token_usage.c.model).label("key")
        stmt = (
            select(model_col, func.coalesce(func.sum(token_usage.c.total_cost), 0.0).label("cost"))
            .group_by(token_usage.c.provider, token_usage.c.model)
            .order_by(text("cost DESC"))
        )
        if days is not None:
            stmt = stmt.where(token_usage.c.recorded_at >= _days_ago_iso(days))
        if org_id is not None:
            stmt = stmt.where(token_usage.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return {r[0]: round(float(r[1]), 6) for r in rows}

    async def get_team_breakdown(self, days: int | None = None, org_id: str | None = None) -> dict[str, float]:
        stmt = (
            select(token_usage.c.team, func.coalesce(func.sum(token_usage.c.total_cost), 0.0).label("cost"))
            .group_by(token_usage.c.team)
            .order_by(text("cost DESC"))
        )
        if days is not None:
            stmt = stmt.where(token_usage.c.recorded_at >= _days_ago_iso(days))
        if org_id is not None:
            stmt = stmt.where(token_usage.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return {r[0]: round(float(r[1]), 6) for r in rows}

    async def check_budget(self, org_id: str | None = None) -> BudgetStatus:
        spent = await self.total_cost(30, org_id=org_id)
        limit = self._policy.monthly_limit_usd
        pct = (spent / limit * 100) if limit > 0 else 0.0
        return BudgetStatus(
            total_spent_usd=spent,
            monthly_limit_usd=limit,
            percentage_used=round(pct, 2),
            is_exceeded=spent > limit,
            alert_triggered=pct >= self._policy.alert_threshold_pct * 100,
            team_breakdown=await self.get_team_breakdown(30, org_id=org_id),
            model_breakdown=await self.get_model_breakdown(30, org_id=org_id),
        )

    async def get_daily_costs(self, days: int = 30, org_id: str | None = None) -> list[dict[str, Any]]:
        cutoff = _days_ago_iso(days)
        stmt = (
            select(
                func.date(token_usage.c.recorded_at).label("day"),
                func.sum(token_usage.c.total_cost).label("cost"),
                func.sum(token_usage.c.input_tokens + token_usage.c.output_tokens).label("tokens"),
                func.count().label("requests"),
            )
            .where(token_usage.c.recorded_at >= cutoff)
            .group_by(text("day"))
            .order_by(text("day"))
        )
        if org_id is not None:
            stmt = stmt.where(token_usage.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [
            {"date": r[0], "cost_usd": round(float(r[1]), 4),
             "tokens": int(r[2]), "requests": int(r[3])}
            for r in rows
        ]


class TrustRepository:
    """
    Async repository for trust score history and drift detection.

    Mirrors the DB operations of TrustDriftMonitor with async/await.
    """

    def __init__(self, engine: DatabaseEngine, alert_threshold: float = 5.0) -> None:
        self._engine = engine
        self._alert_threshold = alert_threshold

    async def record(
        self,
        model_name: str,
        provider: str,
        score: TrustScore,
        org_id: str | None = None,
    ) -> dict[str, Any] | None:
        """Persist a score snapshot; return drift info if threshold exceeded."""
        now = datetime.now(UTC).isoformat()

        async with self._engine.raw.begin() as conn:
            await conn.execute(
                trust_scores.insert().values(
                    org_id       = org_id,
                    model_name   = model_name,
                    provider     = provider,
                    overall      = score.overall,
                    grade        = score.grade,
                    risk_level   = score.risk_level,
                    fairness     = score.fairness,
                    privacy      = score.privacy,
                    security     = score.security,
                    robustness   = score.robustness,
                    compliance   = score.compliance,
                    authenticity = score.authenticity,
                    recorded_at  = now,
                )
            )

        prev = await self._previous_score(model_name, provider, org_id=org_id)
        if prev is not None:
            delta = prev - score.overall
            if abs(delta) >= self._alert_threshold:
                return {
                    "model_name": model_name,
                    "provider": provider,
                    "previous_score": round(prev, 2),
                    "current_score": round(score.overall, 2),
                    "delta": round(delta, 2),
                    "severity": "HIGH" if abs(delta) >= self._alert_threshold * 2 else "MEDIUM",
                    "timestamp": now,
                }
        return None

    async def history(
        self,
        model_name: str,
        provider: str,
        limit: int = 30,
        org_id: str | None = None,
    ) -> list[dict[str, Any]]:
        stmt = (
            select(trust_scores)
            .where(
                (trust_scores.c.model_name == model_name) &
                (trust_scores.c.provider == provider)
            )
            .order_by(trust_scores.c.recorded_at.desc())
            .limit(limit)
        )
        if org_id is not None:
            stmt = stmt.where(trust_scores.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [
            {
                "overall": r.overall, "grade": r.grade, "risk_level": r.risk_level,
                "fairness": r.fairness, "privacy": r.privacy, "security": r.security,
                "robustness": r.robustness, "compliance": r.compliance,
                "authenticity": r.authenticity, "recorded_at": r.recorded_at,
            }
            for r in reversed(rows)
        ]

    async def trend(self, model_name: str, provider: str, org_id: str | None = None) -> dict[str, Any]:
        history = await self.history(model_name, provider, limit=30, org_id=org_id)
        if len(history) < 2:
            return {"error": "insufficient_data", "points": len(history)}
        scores = [h["overall"] for h in history]
        recent = scores[-7:] if len(scores) >= 7 else scores
        direction = "stable"
        if len(recent) >= 2:
            slope = (recent[-1] - recent[0]) / max(len(recent) - 1, 1)
            if slope > 0.5:
                direction = "improving"
            elif slope < -0.5:
                direction = "degrading"
        return {
            "direction": direction,
            "latest": round(scores[-1], 2),
            "7d_avg": round(sum(recent) / len(recent), 2),
            "30d_avg": round(sum(scores) / len(scores), 2),
            "30d_min": round(min(scores), 2),
            "30d_max": round(max(scores), 2),
            "data_points": len(scores),
        }

    async def all_models(self, org_id: str | None = None) -> list[dict[str, str]]:
        stmt = select(trust_scores.c.model_name, trust_scores.c.provider).distinct()
        if org_id is not None:
            stmt = stmt.where(trust_scores.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            rows = (await conn.execute(stmt)).fetchall()
        return [{"model_name": r[0], "provider": r[1]} for r in rows]

    async def _previous_score(
        self,
        model_name: str,
        provider: str,
        org_id: str | None = None,
    ) -> float | None:
        stmt = (
            select(trust_scores.c.overall)
            .where(
                (trust_scores.c.model_name == model_name) &
                (trust_scores.c.provider == provider)
            )
            .order_by(trust_scores.c.recorded_at.desc())
            .offset(1)
            .limit(1)
        )
        if org_id is not None:
            stmt = stmt.where(trust_scores.c.org_id == org_id)
        async with self._engine.raw.connect() as conn:
            row = (await conn.execute(stmt)).fetchone()
        return float(row[0]) if row else None


def _days_ago_iso(days: int) -> str:
    from datetime import timedelta
    dt = datetime.now(UTC) - timedelta(days=days)
    return dt.isoformat()
