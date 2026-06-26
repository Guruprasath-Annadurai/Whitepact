"""SDK response models."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class TrustScore:
    overall: float
    grade: str
    fairness: float
    privacy: float
    security: float
    robustness: float
    compliance: float
    authenticity: float
    model_name: str = ""
    provider: str = ""
    passport_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> TrustScore:
        dims = d.get("dimensions", {})
        return cls(
            overall=d.get("overall", 0.0),
            grade=d.get("grade", "F"),
            fairness=dims.get("fairness", 0.0),
            privacy=dims.get("privacy", 0.0),
            security=dims.get("security", 0.0),
            robustness=dims.get("robustness", 0.0),
            compliance=dims.get("compliance", 0.0),
            authenticity=dims.get("authenticity", 0.0),
            model_name=d.get("model_name", ""),
            provider=d.get("provider", ""),
            passport_id=d.get("passport_id"),
            raw=d,
        )


@dataclass(frozen=True)
class PIIFinding:
    category: str
    value: str
    start: int
    end: int

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> PIIFinding:
        return cls(
            category=d.get("category", ""),
            value=d.get("value", ""),
            start=d.get("start", 0),
            end=d.get("end", 0),
        )


@dataclass(frozen=True)
class GuardrailScan:
    is_blocked: bool
    pii_findings: list[PIIFinding]
    toxicity_score: float
    redacted_text: str
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> GuardrailScan:
        return cls(
            is_blocked=d.get("is_blocked", False),
            pii_findings=[PIIFinding.from_dict(f) for f in d.get("pii_findings", [])],
            toxicity_score=d.get("toxicity_score", 0.0),
            redacted_text=d.get("redacted_text", ""),
            raw=d,
        )


@dataclass(frozen=True)
class HallucinationAnalysis:
    hallucination_risk: float
    risk_level: str
    hedging_score: float
    consistency_score: float
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> HallucinationAnalysis:
        return cls(
            hallucination_risk=d.get("hallucination_risk", 0.0),
            risk_level=d.get("risk_level", "low"),
            hedging_score=d.get("hedging_score", 0.0),
            consistency_score=d.get("consistency_score", 1.0),
            raw=d,
        )


@dataclass(frozen=True)
class ComplianceReport:
    overall_status: str
    score: float
    frameworks: list[dict[str, Any]]
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> ComplianceReport:
        return cls(
            overall_status=d.get("overall_status", "unknown"),
            score=d.get("score", 0.0),
            frameworks=d.get("frameworks", []),
            raw=d,
        )


@dataclass(frozen=True)
class CostRecord:
    request_id: str
    provider: str
    model: str
    input_cost: float
    output_cost: float
    total_cost: float
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> CostRecord:
        return cls(
            request_id=d.get("request_id", ""),
            provider=d.get("provider", ""),
            model=d.get("model", ""),
            input_cost=d.get("input_cost_usd", 0.0),
            output_cost=d.get("output_cost_usd", 0.0),
            total_cost=d.get("total_cost_usd", 0.0),
            raw=d,
        )


@dataclass(frozen=True)
class EvalCompareResult:
    winner: str | None
    score_a: float
    score_b: float
    model_a: str
    model_b: str
    prompts_evaluated: int
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> EvalCompareResult:
        return cls(
            winner=d.get("winner"),
            score_a=d.get("score_a", 0.0),
            score_b=d.get("score_b", 0.0),
            model_a=d.get("model_a", ""),
            model_b=d.get("model_b", ""),
            prompts_evaluated=d.get("prompts_evaluated", 0),
            raw=d,
        )
