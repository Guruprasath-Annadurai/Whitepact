"""Regression detector — track benchmark baselines and flag score drops."""

from __future__ import annotations

from responsibleai.eval.models import BenchmarkResult, RegressionAlert, RegressionSeverity

_SEVERITY_THRESHOLDS = [
    (RegressionSeverity.SEVERE,   0.15),
    (RegressionSeverity.MODERATE, 0.05),
    (RegressionSeverity.MINOR,    0.01),
]


class RegressionDetector:
    """Persist per-model benchmark baselines and detect regressions.

    A regression is any drop in ``accuracy`` or ``overall_score``, or any
    rise in ``bias_rate``.  Once a baseline is set with ``set_baseline()``,
    subsequent calls to ``check()`` return ``RegressionAlert`` objects for
    every metric that crossed a severity threshold.
    """

    def __init__(self) -> None:
        # model → suite:metric → float
        self._baselines: dict[str, dict[str, float]] = {}

    # ── Baseline management ───────────────────────────────────────────────────

    def set_baseline(self, model: str, result: BenchmarkResult) -> None:
        """Record a benchmark result as the baseline for a model+suite pair."""
        prefix = result.suite.value
        if model not in self._baselines:
            self._baselines[model] = {}
        self._baselines[model][f"{prefix}:accuracy"]     = result.accuracy
        self._baselines[model][f"{prefix}:bias_rate"]    = result.bias_rate
        self._baselines[model][f"{prefix}:overall_score"] = result.overall_score

    def get_baselines(self, model: str) -> dict[str, float]:
        """Return all stored baseline metrics for a model."""
        return dict(self._baselines.get(model, {}))

    def list_models(self) -> list[str]:
        """Return all models with stored baselines."""
        return list(self._baselines.keys())

    def clear_baseline(self, model: str) -> bool:
        if model in self._baselines:
            del self._baselines[model]
            return True
        return False

    # ── Regression check ──────────────────────────────────────────────────────

    def check(self, model: str, result: BenchmarkResult) -> list[RegressionAlert]:
        """Compare *result* against the stored baseline; return any alerts."""
        if model not in self._baselines:
            return []

        prefix = result.suite.value
        checks = [
            (f"{prefix}:accuracy",      result.accuracy,      False),
            (f"{prefix}:bias_rate",     result.bias_rate,     True),
            (f"{prefix}:overall_score", result.overall_score, False),
        ]

        alerts: list[RegressionAlert] = []
        for metric, current, higher_is_worse in checks:
            baseline = self._baselines[model].get(metric)
            if baseline is None:
                continue
            delta = (current - baseline) if higher_is_worse else (baseline - current)
            if delta <= 0:
                continue
            severity = self._classify(delta)
            if severity is None:
                continue
            alerts.append(
                RegressionAlert(
                    model=model,
                    metric=metric,
                    baseline_score=round(baseline, 4),
                    current_score=round(current, 4),
                    delta=round(delta, 4),
                    severity=severity,
                    suite=prefix,
                )
            )
        return alerts

    @staticmethod
    def _classify(delta: float) -> RegressionSeverity | None:
        for severity, threshold in _SEVERITY_THRESHOLDS:
            if delta >= threshold:
                return severity
        return None
