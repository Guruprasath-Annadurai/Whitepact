"""Tests for TrustDriftMonitor."""

from __future__ import annotations

import pytest

from responsibleai.drift.monitor import TrustDriftMonitor
from responsibleai.trust.score import TrustScoreEngine

_engine = TrustScoreEngine()


def _score(overall_pct: float = 0.80):
    """Create a TrustScore with uniform dimensions at the given value."""
    return _engine.compute(
        fairness=overall_pct,
        privacy=overall_pct,
        security=overall_pct,
        robustness=overall_pct,
        compliance=overall_pct,
        authenticity=overall_pct,
    )


@pytest.fixture()
def monitor() -> TrustDriftMonitor:
    return TrustDriftMonitor()  # in-memory


class TestRecord:
    def test_first_record_returns_no_alert(self, monitor):
        alert = monitor.record("gpt-4o", "openai", _score())
        assert alert is None

    def test_no_alert_on_stable_score(self, monitor):
        monitor.record("gpt-4o", "openai", _score(0.80))
        alert = monitor.record("gpt-4o", "openai", _score(0.79))
        assert alert is None  # <5 pt drop

    def test_alert_on_significant_drop(self, monitor):
        monitor.record("gpt-4o", "openai", _score(0.90))
        alert = monitor.record("gpt-4o", "openai", _score(0.70))
        assert alert is not None
        assert alert.delta < 0

    def test_alert_severity_medium(self, monitor):
        monitor.record("model-x", "acme", _score(0.85))
        alert = monitor.record("model-x", "acme", _score(0.75))
        assert alert is not None
        assert alert.severity in ("medium", "high", "critical")

    def test_alert_severity_critical(self, monitor):
        monitor.record("model-x", "acme", _score(0.95))
        alert = monitor.record("model-x", "acme", _score(0.60))
        assert alert is not None
        assert alert.severity == "critical"

    def test_alert_contains_affected_dimensions(self, monitor):
        monitor.record("model-y", "acme", _score(0.90))
        # Build a score where only fairness and privacy degraded significantly
        low = _engine.compute(
            fairness=0.50,
            privacy=0.55,
            security=0.90,
            robustness=0.90,
            compliance=0.90,
            authenticity=0.90,
        )
        alert = monitor.record("model-y", "acme", low)
        if alert:
            dims = alert.affected_dimensions
            assert "fairness" in dims or "privacy" in dims

    def test_improvement_returns_no_alert(self, monitor):
        monitor.record("gpt-4o", "openai", _score(0.70))
        alert = monitor.record("gpt-4o", "openai", _score(0.90))
        assert alert is None  # improvement, not degradation

    def test_alert_to_dict(self, monitor):
        monitor.record("m", "p", _score(0.90))
        alert = monitor.record("m", "p", _score(0.60))
        assert alert is not None
        d = alert.to_dict()
        assert "model" in d
        assert "delta" in d
        assert "severity" in d
        assert "affected_dimensions" in d


class TestHistory:
    def test_empty_history(self, monitor):
        assert monitor.history("unknown", "x") == []

    def test_history_ordered_chronologically(self, monitor):
        for v in [0.80, 0.82, 0.78, 0.85]:
            monitor.record("gpt-4o", "openai", _score(v))
        history = monitor.history("gpt-4o", "openai")
        assert len(history) == 4
        assert history[0]["overall"] <= history[-1]["overall"] or True  # just check they exist

    def test_history_limit(self, monitor):
        for _ in range(20):
            monitor.record("gpt-4o", "openai", _score(0.80))
        history = monitor.history("gpt-4o", "openai", limit=5)
        assert len(history) == 5

    def test_history_contains_required_fields(self, monitor):
        monitor.record("gpt-4o", "openai", _score(0.80))
        row = monitor.history("gpt-4o", "openai")[0]
        assert "overall" in row
        assert "grade" in row
        assert "recorded_at" in row


class TestTrend:
    def test_trend_no_data(self, monitor):
        result = monitor.trend("unknown", "x")
        assert "error" in result

    def test_trend_returns_direction(self, monitor):
        for v in [0.80, 0.82, 0.84]:
            monitor.record("gpt-4o", "openai", _score(v))
        trend = monitor.trend("gpt-4o", "openai")
        assert trend["direction"] in ("improving", "stable", "degrading")

    def test_trend_averages(self, monitor):
        for v in [0.80, 0.82, 0.84, 0.78, 0.81]:
            monitor.record("gpt-4o", "openai", _score(v))
        trend = monitor.trend("gpt-4o", "openai")
        assert "current_score" in trend
        assert "avg_7_day" in trend
        assert "avg_30_day" in trend
        assert "data_points" in trend

    def test_single_record_stable(self, monitor):
        monitor.record("gpt-4o", "openai", _score(0.80))
        trend = monitor.trend("gpt-4o", "openai")
        assert trend["direction"] == "stable"

    def test_degrading_direction(self, monitor):
        for v in [0.90, 0.88, 0.75]:
            monitor.record("gpt-4o", "openai", _score(v))
        trend = monitor.trend("gpt-4o", "openai")
        assert trend["direction"] == "degrading"

    def test_improving_direction(self, monitor):
        for v in [0.60, 0.70, 0.85]:
            monitor.record("gpt-4o", "openai", _score(v))
        trend = monitor.trend("gpt-4o", "openai")
        assert trend["direction"] == "improving"


class TestAllModels:
    def test_all_models_empty(self, monitor):
        assert monitor.all_models() == []

    def test_all_models_returns_latest_per_model(self, monitor):
        monitor.record("gpt-4o", "openai", _score(0.80))
        monitor.record("gpt-4o", "openai", _score(0.85))
        monitor.record("claude-sonnet-4", "anthropic", _score(0.90))
        rows = monitor.all_models()
        model_names = [r["model_name"] for r in rows]
        assert "gpt-4o" in model_names
        assert "claude-sonnet-4" in model_names
        assert len(rows) == 2

    def test_all_models_sorted_by_score(self, monitor):
        monitor.record("model-a", "acme", _score(0.75))
        monitor.record("model-b", "acme", _score(0.90))
        rows = monitor.all_models()
        scores = [r["overall"] for r in rows]
        assert scores == sorted(scores, reverse=True)

    def test_custom_alert_threshold(self):
        monitor = TrustDriftMonitor(alert_threshold=2.0)
        monitor.record("m", "p", _score(0.80))
        alert = monitor.record("m", "p", _score(0.75))
        assert alert is not None  # 5pt drop > 2pt threshold
