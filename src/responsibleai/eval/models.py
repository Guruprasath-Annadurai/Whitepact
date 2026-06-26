"""Data models for the Model Evaluation Framework."""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class BenchmarkSuite(StrEnum):
    TRUTHFULQA = "truthfulqa"
    BBQ = "bbq"
    HELLASWAG = "hellaswag"
    CUSTOM = "custom"


class RegressionSeverity(StrEnum):
    MINOR = "minor"       # 1–5 point drop
    MODERATE = "moderate" # 5–15 point drop
    SEVERE = "severe"     # > 15 point drop


@dataclass
class EvalPrompt:
    """A single evaluation prompt with optional expected answer and category."""
    prompt: str
    expected: str = ""
    category: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ModelResponse:
    """A model's response to an EvalPrompt."""
    prompt_id: str
    model: str
    provider: str
    response: str
    latency_ms: float = 0.0
    tokens: int = 0
    cost_usd: float = 0.0
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class PromptComparisonResult:
    """Per-prompt comparison between two models."""
    prompt_id: str
    prompt: str
    response_a: str
    response_b: str
    model_a: str
    model_b: str
    trust_score_a: float
    trust_score_b: float
    winner: str  # "model_a" | "model_b" | "tie"
    pii_detected_a: bool = False
    pii_detected_b: bool = False
    hallucination_risk_a: float = 0.0
    hallucination_risk_b: float = 0.0


@dataclass
class ComparisonResult:
    """Full A/B comparison of two models across a prompt set."""
    model_a: str
    model_b: str
    provider_a: str
    provider_b: str
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    prompt_results: list[PromptComparisonResult] = field(default_factory=list)

    @property
    def avg_trust_a(self) -> float:
        if not self.prompt_results:
            return 0.0
        return round(sum(r.trust_score_a for r in self.prompt_results) / len(self.prompt_results), 2)

    @property
    def avg_trust_b(self) -> float:
        if not self.prompt_results:
            return 0.0
        return round(sum(r.trust_score_b for r in self.prompt_results) / len(self.prompt_results), 2)

    @property
    def winner(self) -> str:
        if self.avg_trust_a > self.avg_trust_b + 0.5:
            return self.model_a
        if self.avg_trust_b > self.avg_trust_a + 0.5:
            return self.model_b
        return "tie"

    @property
    def wins_a(self) -> int:
        return sum(1 for r in self.prompt_results if r.winner == "model_a")

    @property
    def wins_b(self) -> int:
        return sum(1 for r in self.prompt_results if r.winner == "model_b")

    @property
    def ties(self) -> int:
        return sum(1 for r in self.prompt_results if r.winner == "tie")

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "created_at": self.created_at,
            "model_a": self.model_a,
            "model_b": self.model_b,
            "provider_a": self.provider_a,
            "provider_b": self.provider_b,
            "avg_trust_a": self.avg_trust_a,
            "avg_trust_b": self.avg_trust_b,
            "winner": self.winner,
            "wins_a": self.wins_a,
            "wins_b": self.wins_b,
            "ties": self.ties,
            "total_prompts": len(self.prompt_results),
            "prompt_results": [
                {
                    "prompt_id": r.prompt_id,
                    "prompt": r.prompt[:300],
                    "model_a": r.model_a,
                    "model_b": r.model_b,
                    "trust_a": r.trust_score_a,
                    "trust_b": r.trust_score_b,
                    "winner": r.winner,
                    "pii_a": r.pii_detected_a,
                    "pii_b": r.pii_detected_b,
                    "hallucination_risk_a": r.hallucination_risk_a,
                    "hallucination_risk_b": r.hallucination_risk_b,
                }
                for r in self.prompt_results
            ],
        }


@dataclass
class BenchmarkSampleResult:
    """Result for a single benchmark sample."""
    sample_id: str
    prompt: str
    expected: str
    model_response: str
    model: str
    correct: bool
    category: str = ""
    bias_detected: bool = False
    bias_flags: list[str] = field(default_factory=list)
    score: float = 0.0


@dataclass
class BenchmarkResult:
    """Full benchmark run for a model on a named suite."""
    model: str
    provider: str
    suite: BenchmarkSuite
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    sample_results: list[BenchmarkSampleResult] = field(default_factory=list)

    @property
    def accuracy(self) -> float:
        if not self.sample_results:
            return 0.0
        return round(sum(1 for r in self.sample_results if r.correct) / len(self.sample_results), 4)

    @property
    def bias_rate(self) -> float:
        if not self.sample_results:
            return 0.0
        return round(sum(1 for r in self.sample_results if r.bias_detected) / len(self.sample_results), 4)

    @property
    def overall_score(self) -> float:
        """Weighted combination: 70% accuracy + 30% safety (1 − bias_rate)."""
        return round(self.accuracy * 0.7 + (1.0 - self.bias_rate) * 0.3, 4)

    def to_dict(self) -> dict[str, Any]:
        cats: dict[str, dict[str, int]] = {}
        for r in self.sample_results:
            cat = r.category or "general"
            if cat not in cats:
                cats[cat] = {"total": 0, "correct": 0}
            cats[cat]["total"] += 1
            if r.correct:
                cats[cat]["correct"] += 1

        return {
            "id": self.id,
            "created_at": self.created_at,
            "model": self.model,
            "provider": self.provider,
            "suite": self.suite.value,
            "total_samples": len(self.sample_results),
            "accuracy": self.accuracy,
            "bias_rate": self.bias_rate,
            "overall_score": self.overall_score,
            "category_breakdown": {
                c: {
                    "total": v["total"],
                    "correct": v["correct"],
                    "accuracy": round(v["correct"] / v["total"], 4) if v["total"] else 0.0,
                }
                for c, v in cats.items()
            },
        }


@dataclass
class RegressionAlert:
    """Flags a significant score drop vs a recorded baseline."""
    model: str
    metric: str
    baseline_score: float
    current_score: float
    delta: float
    severity: RegressionSeverity
    suite: str = ""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    detected_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "detected_at": self.detected_at,
            "model": self.model,
            "metric": self.metric,
            "baseline_score": self.baseline_score,
            "current_score": self.current_score,
            "delta": round(self.delta, 4),
            "severity": self.severity.value,
            "suite": self.suite,
        }


@dataclass
class DatasetRowResult:
    """Analysis result for a single dataset row."""
    row_index: int
    text: str
    bias_categories: list[str]
    pii_detected: bool
    toxicity_detected: bool
    flags: list[str]
    score: float  # 0 = clean, 1 = heavily flagged


@dataclass
class DatasetScanResult:
    """Aggregated result of a full dataset bias scan."""
    filename: str
    total_rows: int
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())
    row_results: list[DatasetRowResult] = field(default_factory=list)

    @property
    def flagged_rows(self) -> int:
        return sum(1 for r in self.row_results if r.flags)

    @property
    def pii_rows(self) -> int:
        return sum(1 for r in self.row_results if r.pii_detected)

    @property
    def bias_rows(self) -> int:
        return sum(1 for r in self.row_results if r.bias_categories)

    @property
    def flag_rate(self) -> float:
        if not self.total_rows:
            return 0.0
        return round(self.flagged_rows / self.total_rows, 4)

    def to_dict(self) -> dict[str, Any]:
        cat_counts: dict[str, int] = {}
        for r in self.row_results:
            for c in r.bias_categories:
                cat_counts[c] = cat_counts.get(c, 0) + 1

        return {
            "id": self.id,
            "created_at": self.created_at,
            "filename": self.filename,
            "total_rows": self.total_rows,
            "flagged_rows": self.flagged_rows,
            "pii_rows": self.pii_rows,
            "bias_rows": self.bias_rows,
            "flag_rate": self.flag_rate,
            "bias_category_counts": cat_counts,
            "flagged_samples": [
                {
                    "row": r.row_index,
                    "text_preview": r.text[:200],
                    "flags": r.flags,
                    "bias_categories": r.bias_categories,
                    "pii": r.pii_detected,
                    "toxicity": r.toxicity_detected,
                    "score": round(r.score, 4),
                }
                for r in self.row_results
                if r.flags
            ][:100],
        }
