from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

Severity = Literal["none", "low", "medium", "high", "critical"]

_SEVERITY_THRESHOLDS: list[tuple[float, Severity]] = [
    (0.05, "none"),
    (0.15, "low"),
    (0.30, "medium"),
    (0.60, "high"),
    (1.01, "critical"),
]


def score_to_severity(score: float) -> Severity:
    for threshold, label in _SEVERITY_THRESHOLDS:
        if score < threshold:
            return label
    return "critical"


@dataclass(frozen=True)
class VariantResponse:
    variant_name: str
    prompt: str
    response: str


@dataclass(frozen=True)
class TemplateResult:
    """Divergence result for a single prompt template across all variants."""

    template: str
    variant_responses: list[VariantResponse]
    divergence_score: float
    severity: Severity
    most_divergent_pair: tuple[str, str] | None = None
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass
class ProbeResult:
    probe_name: str
    probe_description: str
    provider_name: str
    model_name: str
    overall_score: float
    severity: Severity
    passed: bool
    threshold: float
    template_results: list[TemplateResult]
    metadata: dict[str, Any] = field(default_factory=dict)
    confidence_interval: tuple[float, float] | None = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "probe_name": self.probe_name,
            "probe_description": self.probe_description,
            "provider": self.provider_name,
            "model": self.model_name,
            "overall_score": round(self.overall_score, 4),
            "severity": self.severity,
            "passed": self.passed,
            "threshold": self.threshold,
            "confidence_interval": (
                [round(self.confidence_interval[0], 4), round(self.confidence_interval[1], 4)]
                if self.confidence_interval
                else None
            ),
            "timestamp": self.timestamp.isoformat(),
            "template_results": [
                {
                    "template": tr.template,
                    "divergence_score": round(tr.divergence_score, 4),
                    "severity": tr.severity,
                    "most_divergent_pair": tr.most_divergent_pair,
                    "extra": tr.metadata,
                    "responses": [
                        {
                            "variant": vr.variant_name,
                            "prompt": vr.prompt,
                            "response": vr.response,
                        }
                        for vr in tr.variant_responses
                    ],
                }
                for tr in self.template_results
            ],
            "metadata": self.metadata,
        }


@dataclass
class SuiteResult:
    """Aggregated result from running multiple probes."""

    provider_name: str
    model_name: str
    probe_results: list[ProbeResult]
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def overall_score(self) -> float:
        if not self.probe_results:
            return 0.0
        return sum(r.overall_score for r in self.probe_results) / len(self.probe_results)

    @property
    def passed(self) -> bool:
        return all(r.passed for r in self.probe_results)

    @property
    def failed_probes(self) -> list[ProbeResult]:
        return [r for r in self.probe_results if not r.passed]

    def to_dict(self) -> dict[str, Any]:
        return {
            "provider": self.provider_name,
            "model": self.model_name,
            "overall_score": round(self.overall_score, 4),
            "overall_severity": score_to_severity(self.overall_score),
            "passed": self.passed,
            "total_probes": len(self.probe_results),
            "failed_probes": len(self.failed_probes),
            "timestamp": self.timestamp.isoformat(),
            "probes": [r.to_dict() for r in self.probe_results],
        }
