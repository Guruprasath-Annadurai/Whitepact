"""Trust Drift Monitor — detect governance score degradation over time."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Generator
from contextlib import contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from responsibleai.trust.score import TrustScore

_CREATE_SCORES_TABLE = """
CREATE TABLE IF NOT EXISTS trust_scores (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    model_name  TEXT NOT NULL,
    provider    TEXT NOT NULL,
    overall     REAL NOT NULL,
    grade       TEXT NOT NULL,
    risk_level  TEXT NOT NULL,
    fairness    REAL NOT NULL,
    privacy     REAL NOT NULL,
    security    REAL NOT NULL,
    robustness  REAL NOT NULL,
    compliance  REAL NOT NULL,
    authenticity REAL NOT NULL,
    metadata    TEXT,
    recorded_at TEXT NOT NULL
)
"""

_CREATE_IDX = [
    "CREATE INDEX IF NOT EXISTS idx_model ON trust_scores(model_name)",
    "CREATE INDEX IF NOT EXISTS idx_provider ON trust_scores(provider)",
    "CREATE INDEX IF NOT EXISTS idx_recorded ON trust_scores(recorded_at)",
]


class DriftAlert:
    """Describes a detected drift event."""

    def __init__(
        self,
        model_name: str,
        provider: str,
        previous_score: float,
        current_score: float,
        delta: float,
        severity: str,
        affected_dimensions: list[str],
        timestamp: datetime,
    ) -> None:
        self.model_name = model_name
        self.provider = provider
        self.previous_score = previous_score
        self.current_score = current_score
        self.delta = delta
        self.severity = severity
        self.affected_dimensions = affected_dimensions
        self.timestamp = timestamp

    def to_dict(self) -> dict[str, Any]:
        return {
            "model": self.model_name,
            "provider": self.provider,
            "previous_score": round(self.previous_score, 2),
            "current_score": round(self.current_score, 2),
            "delta": round(self.delta, 2),
            "severity": self.severity,
            "affected_dimensions": self.affected_dimensions,
            "timestamp": self.timestamp.isoformat(),
        }


def _drift_severity(delta: float) -> str:
    delta = abs(delta)
    if delta >= 15:
        return "critical"
    if delta >= 10:
        return "high"
    if delta >= 5:
        return "medium"
    return "low"


class TrustDriftMonitor:
    """
    Record trust scores over time and detect degradation.

    Design intent: run after each evaluation cycle (daily, per-release, per-deploy)
    and alert when the overall trust score drops by a configurable threshold.

    Backed by SQLite — use ``':memory:'`` for stateless testing.
    """

    def __init__(
        self,
        db_path: str | Path = ":memory:",
        alert_threshold: float = 5.0,
    ) -> None:
        self._db_path = str(db_path)
        self._alert_threshold = alert_threshold
        self._conn = sqlite3.connect(self._db_path, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        with self._conn:
            self._conn.execute(_CREATE_SCORES_TABLE)
            for idx in _CREATE_IDX:
                self._conn.execute(idx)

    @contextmanager
    def _tx(self) -> Generator[sqlite3.Connection, None, None]:
        try:
            yield self._conn
            self._conn.commit()
        except Exception:
            self._conn.rollback()
            raise

    def record(
        self,
        model_name: str,
        provider: str,
        score: TrustScore,
        metadata: dict[str, Any] | None = None,
    ) -> DriftAlert | None:
        """
        Persist *score* and return a DriftAlert if degradation exceeds the threshold.

        Parameters
        ----------
        model_name : str
            Name of the model that was evaluated.
        provider : str
            Provider name.
        score : TrustScore
            Result from TrustScoreEngine.
        metadata : dict | None
            Optional context (e.g., git commit hash, deployment version).

        Returns
        -------
        DriftAlert | None
            Alert if the score dropped by more than ``alert_threshold`` points,
            otherwise None.
        """
        previous = self._latest_score(model_name, provider)

        with self._tx():
            self._conn.execute(
                """
                INSERT INTO trust_scores
                (model_name, provider, overall, grade, risk_level,
                 fairness, privacy, security, robustness, compliance, authenticity,
                 metadata, recorded_at)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)
                """,
                (
                    model_name, provider, score.overall, score.grade, score.risk_level,
                    score.fairness, score.privacy, score.security,
                    score.robustness, score.compliance, score.authenticity,
                    json.dumps(metadata or {}),
                    datetime.now(UTC).isoformat(),
                ),
            )

        if previous is None:
            return None

        delta = score.overall - previous["overall"]
        if delta >= -self._alert_threshold:
            return None

        # Identify which dimensions degraded most
        dims = ["fairness", "privacy", "security", "robustness", "compliance", "authenticity"]
        current_vals = {
            "fairness": score.fairness, "privacy": score.privacy,
            "security": score.security, "robustness": score.robustness,
            "compliance": score.compliance, "authenticity": score.authenticity,
        }
        degraded = [
            d for d in dims
            if current_vals[d] < previous[d] - 0.05  # >5% drop
        ]

        return DriftAlert(
            model_name=model_name,
            provider=provider,
            previous_score=previous["overall"],
            current_score=score.overall,
            delta=delta,
            severity=_drift_severity(delta),
            affected_dimensions=degraded,
            timestamp=datetime.now(UTC),
        )

    def history(
        self,
        model_name: str,
        provider: str,
        limit: int = 30,
    ) -> list[dict[str, Any]]:
        """Return the last *limit* trust score records for a model."""
        rows = self._conn.execute(
            """
            SELECT overall, grade, risk_level,
                   fairness, privacy, security, robustness, compliance, authenticity,
                   recorded_at
            FROM trust_scores
            WHERE model_name = ? AND provider = ?
            ORDER BY recorded_at DESC
            LIMIT ?
            """,
            (model_name, provider, limit),
        ).fetchall()
        return [dict(r) for r in reversed(rows)]

    def trend(self, model_name: str, provider: str) -> dict[str, Any]:
        """
        Return a trend summary: current score, 7-day average, 30-day average,
        and the direction (improving / stable / degrading).
        """
        rows = self._conn.execute(
            """
            SELECT overall, recorded_at FROM trust_scores
            WHERE model_name = ? AND provider = ?
            ORDER BY recorded_at DESC LIMIT 30
            """,
            (model_name, provider),
        ).fetchall()

        if not rows:
            return {"error": "No history found"}

        current = float(rows[0]["overall"])
        all_scores = [float(r["overall"]) for r in rows]
        avg_30 = sum(all_scores) / len(all_scores)
        avg_7 = sum(all_scores[:7]) / min(7, len(all_scores))

        if len(all_scores) >= 2:
            delta = current - float(rows[-1]["overall"])
            if delta > 2:
                direction = "improving"
            elif delta < -2:
                direction = "degrading"
            else:
                direction = "stable"
        else:
            direction = "stable"

        return {
            "model": model_name,
            "provider": provider,
            "current_score": round(current, 2),
            "avg_7_day": round(avg_7, 2),
            "avg_30_day": round(avg_30, 2),
            "direction": direction,
            "data_points": len(all_scores),
        }

    def all_models(self) -> list[dict[str, Any]]:
        """Return latest trust score for every tracked model."""
        rows = self._conn.execute(
            """
            SELECT model_name, provider, overall, grade, risk_level, recorded_at
            FROM trust_scores
            WHERE id IN (
                SELECT MAX(id) FROM trust_scores GROUP BY model_name, provider
            )
            ORDER BY overall DESC
            """
        ).fetchall()
        return [dict(r) for r in rows]

    def _latest_score(self, model_name: str, provider: str) -> dict | None:
        row = self._conn.execute(
            """
            SELECT overall, fairness, privacy, security,
                   robustness, compliance, authenticity
            FROM trust_scores
            WHERE model_name = ? AND provider = ?
            ORDER BY recorded_at DESC LIMIT 1
            """,
            (model_name, provider),
        ).fetchone()
        return dict(row) if row else None

    def close(self) -> None:
        self._conn.close()
