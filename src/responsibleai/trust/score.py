"""
Trust Score Engine — composite AI trustworthiness metric.

Aggregates six governance dimensions (fairness, privacy, security, robustness,
compliance, authenticity) into a single 0-100 score with letter grade and risk tier.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

_DEFAULT_WEIGHTS: dict[str, float] = {
    "fairness": 0.20,
    "privacy": 0.15,
    "security": 0.20,
    "robustness": 0.15,
    "compliance": 0.20,
    "authenticity": 0.10,
}

_DIMENSIONS = tuple(_DEFAULT_WEIGHTS.keys())


def _score_to_grade(score: float) -> str:
    if score >= 90:
        return "A"
    if score >= 80:
        return "B"
    if score >= 70:
        return "C"
    if score >= 60:
        return "D"
    return "F"


def _score_to_risk(score: float) -> str:
    if score >= 80:
        return "LOW"
    if score >= 60:
        return "MEDIUM"
    if score >= 40:
        return "HIGH"
    return "CRITICAL"


@dataclass(frozen=True)
class TrustScore:
    """Immutable result of a Trust Score computation."""

    overall: float
    grade: str
    risk_level: str
    fairness: float
    privacy: float
    security: float
    robustness: float
    compliance: float
    authenticity: float
    weights: dict[str, float]
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    @property
    def passed(self) -> bool:
        return self.overall >= 70.0

    def to_dict(self) -> dict[str, Any]:
        return {
            "trust_score": round(self.overall, 2),
            "grade": self.grade,
            "risk": self.risk_level,
            "passed": self.passed,
            "dimensions": {
                "fairness": round(self.fairness * 100, 2),
                "privacy": round(self.privacy * 100, 2),
                "security": round(self.security * 100, 2),
                "robustness": round(self.robustness * 100, 2),
                "compliance": round(self.compliance * 100, 2),
                "authenticity": round(self.authenticity * 100, 2),
            },
            "timestamp": self.timestamp.isoformat(),
        }


class TrustScoreEngine:
    """
    Compute a composite AI Trust Score from six governance dimensions.

    Each dimension is normalised to [0, 1] where 1 is fully trustworthy.
    The weighted mean is scaled to [0, 100].

    Default weights (must sum to 1.0):
        fairness      0.20
        privacy       0.15
        security      0.20
        robustness    0.15
        compliance    0.20
        authenticity  0.10
    """

    def __init__(self, weights: dict[str, float] | None = None) -> None:
        self._weights = weights or dict(_DEFAULT_WEIGHTS)
        total = sum(self._weights.values())
        if not (0.999 < total < 1.001):
            raise ValueError(
                f"Weights must sum to 1.0; got {total:.4f}. "
                "Adjust weights so they total exactly 1."
            )
        missing = set(_DIMENSIONS) - set(self._weights)
        if missing:
            raise ValueError(f"Missing weights for dimensions: {missing}")

    def compute(
        self,
        fairness: float = 0.5,
        privacy: float = 0.5,
        security: float = 0.5,
        robustness: float = 0.5,
        compliance: float = 0.5,
        authenticity: float = 0.5,
    ) -> TrustScore:
        """
        Compute a TrustScore from six dimension values.

        Parameters
        ----------
        fairness : float
            Bias / fairness score, 0-1 where 1 = no detected bias.
        privacy : float
            Privacy protection level, 0-1.
        security : float
            Security posture, 0-1.
        robustness : float
            Factual reliability / anti-hallucination score, 0-1.
        compliance : float
            Regulatory compliance maturity, 0-1.
        authenticity : float
            Media authenticity (anti-deepfake), 0-1.

        Returns
        -------
        TrustScore
        """
        dims = {
            "fairness": fairness,
            "privacy": privacy,
            "security": security,
            "robustness": robustness,
            "compliance": compliance,
            "authenticity": authenticity,
        }
        for name, val in dims.items():
            if not (0.0 <= val <= 1.0):
                raise ValueError(
                    f"Dimension '{name}' must be in [0, 1]; got {val}"
                )

        overall = sum(self._weights[k] * v for k, v in dims.items()) * 100.0
        return TrustScore(
            overall=round(overall, 2),
            grade=_score_to_grade(overall),
            risk_level=_score_to_risk(overall),
            fairness=fairness,
            privacy=privacy,
            security=security,
            robustness=robustness,
            compliance=compliance,
            authenticity=authenticity,
            weights=dict(self._weights),
        )

    def from_module_results(
        self,
        *,
        bias_divergence: float | None = None,
        privacy_budget_fraction: float | None = None,
        hallucination_risk: float | None = None,
        security_pass_rate: float | None = None,
        compliance_score: float | None = None,
        deepfake_fake_probability: float | None = None,
    ) -> TrustScore:
        """
        Build a TrustScore directly from module outputs.

        Missing values default to 0.5 (unknown / not assessed).

        Parameters
        ----------
        bias_divergence : float | None
            BiasBuster overall divergence score (0=no bias → higher fairness).
        privacy_budget_fraction : float | None
            Fraction of privacy budget remaining (0-1).
        hallucination_risk : float | None
            HallucinationDetector risk score (0=reliable → higher robustness).
        security_pass_rate : float | None
            RedTeamSimulator fraction of attacks resisted (0-1).
        compliance_score : float | None
            ComplianceEngine compliance fraction (0-1).
        deepfake_fake_probability : float | None
            DeepfakeDetector ensemble fake probability (0=authentic → higher authenticity).
        """
        fairness = (1.0 - min(bias_divergence, 1.0)) if bias_divergence is not None else 0.5
        privacy = privacy_budget_fraction if privacy_budget_fraction is not None else 0.5
        robustness = (1.0 - min(hallucination_risk, 1.0)) if hallucination_risk is not None else 0.5
        security = security_pass_rate if security_pass_rate is not None else 0.5
        compliance = compliance_score if compliance_score is not None else 0.5
        authenticity = (1.0 - deepfake_fake_probability) if deepfake_fake_probability is not None else 0.5

        return self.compute(
            fairness=fairness,
            privacy=privacy,
            security=security,
            robustness=robustness,
            compliance=compliance,
            authenticity=authenticity,
        )
