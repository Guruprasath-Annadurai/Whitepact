"""SQLite-backed token usage and cost tracker."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from responsibleai.cost.models import (
    BudgetPolicy,
    BudgetStatus,
    CostRecord,
    TokenUsage,
    get_pricing,
)

_CREATE_USAGE_TABLE = """
CREATE TABLE IF NOT EXISTS token_usage (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    request_id    TEXT NOT NULL UNIQUE,
    provider      TEXT NOT NULL,
    model         TEXT NOT NULL,
    team          TEXT NOT NULL DEFAULT 'default',
    application   TEXT NOT NULL DEFAULT 'default',
    input_tokens  INTEGER NOT NULL,
    output_tokens INTEGER NOT NULL,
    cached_tokens INTEGER NOT NULL DEFAULT 0,
    input_cost    REAL NOT NULL DEFAULT 0.0,
    output_cost   REAL NOT NULL DEFAULT 0.0,
    total_cost    REAL NOT NULL DEFAULT 0.0,
    prompt_hash   TEXT,
    metadata      TEXT,
    recorded_at   TEXT NOT NULL
)
"""

_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_provider  ON token_usage(provider)",
    "CREATE INDEX IF NOT EXISTS idx_model     ON token_usage(model)",
    "CREATE INDEX IF NOT EXISTS idx_team      ON token_usage(team)",
    "CREATE INDEX IF NOT EXISTS idx_recorded  ON token_usage(recorded_at)",
]


class CostTracker:
    """
    Track AI token usage and compute costs against a configurable budget.

    Backed by SQLite — pass ``db_path=':memory:'`` for ephemeral tracking
    (tests, demos) or a file path for persistent storage.
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        policy: BudgetPolicy | None = None,
    ) -> None:
        self._db_path = str(db_path)
        self._policy = policy or BudgetPolicy()
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(_CREATE_USAGE_TABLE)
            for idx in _CREATE_INDEXES:
                self._conn.execute(idx)

    @contextmanager
    def _tx(self) -> Generator[sqlite3.Connection, None, None]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    # ------------------------------------------------------------------
    # Write
    # ------------------------------------------------------------------

    def record(self, usage: TokenUsage) -> CostRecord:
        """Record a single API call and return the computed CostRecord."""
        pricing = get_pricing(usage.provider, usage.model)
        input_cost = pricing.cost_for(usage.input_tokens, 0)
        output_cost = pricing.cost_for(0, usage.output_tokens)
        total_cost = input_cost + output_cost

        with self._tx():
            self._conn.execute(
                """
                INSERT OR IGNORE INTO token_usage
                (request_id, provider, model, team, application,
                 input_tokens, output_tokens, cached_tokens,
                 input_cost, output_cost, total_cost,
                 prompt_hash, metadata, recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    usage.request_id, usage.provider, usage.model,
                    usage.team, usage.application,
                    usage.input_tokens, usage.output_tokens, usage.cached_tokens,
                    input_cost, output_cost, total_cost,
                    usage.prompt_hash,
                    json.dumps(usage.metadata),
                    usage.timestamp.isoformat(),
                ),
            )

        return CostRecord(
            usage=usage,
            pricing=pricing,
            input_cost=input_cost,
            output_cost=output_cost,
            total_cost=total_cost,
        )

    # ------------------------------------------------------------------
    # Read
    # ------------------------------------------------------------------

    def total_cost(self, days: int | None = None) -> float:
        """Total cost (USD) over the last *days* days, or all time if None."""
        if days is None:
            row = self._conn.execute("SELECT COALESCE(SUM(total_cost),0) FROM token_usage").fetchone()
        else:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(total_cost),0) FROM token_usage "
                "WHERE recorded_at >= datetime('now', ?)",
                (f"-{days} days",),
            ).fetchone()
        return float(row[0])

    def total_tokens(self, days: int | None = None) -> dict[str, int]:
        if days is None:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) FROM token_usage"
            ).fetchone()
        else:
            row = self._conn.execute(
                "SELECT COALESCE(SUM(input_tokens),0), COALESCE(SUM(output_tokens),0) "
                "FROM token_usage WHERE recorded_at >= datetime('now', ?)",
                (f"-{days} days",),
            ).fetchone()
        return {"input": int(row[0]), "output": int(row[1]), "total": int(row[0]) + int(row[1])}

    def get_model_breakdown(self, days: int | None = None) -> dict[str, float]:
        """Cost per model, sorted descending."""
        if days:
            rows = self._conn.execute(
                "SELECT provider||'/'||model, COALESCE(SUM(total_cost),0) "
                "FROM token_usage WHERE recorded_at >= datetime('now', ?) "
                "GROUP BY provider, model ORDER BY 2 DESC",
                (f"-{int(days)} days",),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT provider||'/'||model, COALESCE(SUM(total_cost),0) "
                "FROM token_usage GROUP BY provider, model ORDER BY 2 DESC"
            ).fetchall()
        return {r[0]: round(float(r[1]), 6) for r in rows}

    def get_team_breakdown(self, days: int | None = None) -> dict[str, float]:
        if days:
            rows = self._conn.execute(
                "SELECT team, COALESCE(SUM(total_cost),0) "
                "FROM token_usage WHERE recorded_at >= datetime('now', ?) "
                "GROUP BY team ORDER BY 2 DESC",
                (f"-{int(days)} days",),
            ).fetchall()
        else:
            rows = self._conn.execute(
                "SELECT team, COALESCE(SUM(total_cost),0) "
                "FROM token_usage GROUP BY team ORDER BY 2 DESC"
            ).fetchall()
        return {r[0]: round(float(r[1]), 6) for r in rows}

    def get_daily_costs(self, days: int = 30) -> list[dict[str, Any]]:
        rows = self._conn.execute(
            """
            SELECT DATE(recorded_at) as day,
                   SUM(total_cost)   as cost,
                   SUM(input_tokens + output_tokens) as tokens,
                   COUNT(*)          as requests
            FROM token_usage
            WHERE recorded_at >= datetime('now', ?)
            GROUP BY day
            ORDER BY day
            """,
            (f"-{days} days",),
        ).fetchall()
        return [
            {"date": r["day"], "cost_usd": round(r["cost"], 4),
             "tokens": r["tokens"], "requests": r["requests"]}
            for r in rows
        ]

    def monthly_summary(self, year: int | None = None, month: int | None = None) -> dict[str, Any]:
        now = datetime.now(UTC)
        year = year or now.year
        month = month or now.month
        rows = self._conn.execute(
            """
            SELECT
                COALESCE(SUM(total_cost),0)           as total_cost,
                COALESCE(SUM(input_tokens),0)          as input_tokens,
                COALESCE(SUM(output_tokens),0)         as output_tokens,
                COUNT(*)                               as requests,
                COUNT(DISTINCT provider||'/'||model)   as distinct_models
            FROM token_usage
            WHERE strftime('%Y-%m', recorded_at) = ?
            """,
            (f"{year:04d}-{month:02d}",),
        ).fetchone()
        return {
            "year": year,
            "month": month,
            "total_cost_usd": round(float(rows["total_cost"]), 4),
            "input_tokens": int(rows["input_tokens"]),
            "output_tokens": int(rows["output_tokens"]),
            "total_tokens": int(rows["input_tokens"]) + int(rows["output_tokens"]),
            "total_requests": int(rows["requests"]),
            "distinct_models": int(rows["distinct_models"]),
            "model_breakdown": self.get_model_breakdown(30),
            "team_breakdown": self.get_team_breakdown(30),
        }

    def check_budget(self) -> BudgetStatus:
        """Check current spend against the configured budget policy."""
        spent = self.total_cost(30)  # last 30 days
        pct = (spent / self._policy.monthly_limit_usd * 100) if self._policy.monthly_limit_usd > 0 else 0.0
        return BudgetStatus(
            total_spent_usd=spent,
            monthly_limit_usd=self._policy.monthly_limit_usd,
            percentage_used=round(pct, 2),
            is_exceeded=spent > self._policy.monthly_limit_usd,
            alert_triggered=pct >= self._policy.alert_threshold_pct * 100,
            team_breakdown=self.get_team_breakdown(30),
            model_breakdown=self.get_model_breakdown(30),
        )

    def request_count(self, days: int | None = None) -> int:
        if days:
            row = self._conn.execute(
                "SELECT COUNT(*) FROM token_usage WHERE recorded_at >= datetime('now', ?)",
                (f"-{int(days)} days",),
            ).fetchone()
        else:
            row = self._conn.execute("SELECT COUNT(*) FROM token_usage").fetchone()
        return int(row[0])

    def close(self) -> None:
        self._conn.close()
