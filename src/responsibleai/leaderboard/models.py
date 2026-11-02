"""Data models for the public cross-model trust leaderboard.

A LeaderboardRunResult is the output of one full evaluation pass against one
model (see `leaderboard/runner.py`). It carries both the public summary (the
free leaderboard row) and the diagnostic findings (the paid deep-dive) in one
object — the API layer decides what to redact for the free tier, not the
runner.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any

from responsibleai.trust.score import TrustScore

# Bump this whenever the prompt corpus, scoring formula, or dimension mapping
# changes in a way that makes runs before/after not directly comparable.
# Published alongside compliance/LEADERBOARD_METHODOLOGY.md.
METHODOLOGY_VERSION = "1.0.0"


@dataclass(frozen=True)
class DiagnosticFinding:
    """One notable (usually failing) prompt from a leaderboard run.

    This is the paid diagnostic content: which specific prompts caused the
    score to drop, and why. The free leaderboard never exposes these.
    """

    suite: str  # "truthfulqa" | "bbq" | "hellaswag" | "redteam" | "privacy_scan"
    sample_id: str
    category: str
    failure_reason: str
    severity: str  # "low" | "medium" | "high" | "critical" | "n/a"
    prompt_excerpt: str  # truncated — see runner.py's _EXCERPT_MAX_CHARS

    def to_dict(self) -> dict[str, Any]:
        return {
            "suite": self.suite,
            "sample_id": self.sample_id,
            "category": self.category,
            "failure_reason": self.failure_reason,
            "severity": self.severity,
            "prompt_excerpt": self.prompt_excerpt,
        }


@dataclass
class LeaderboardRunResult:
    """Full result of one LeaderboardRunner.run_model() call."""

    model: str
    provider: str
    trust_score: TrustScore
    truthfulqa_accuracy: float
    bbq_bias_rate: float
    hellaswag_accuracy: float
    security_score: float
    privacy_pii_leak_rate: float
    avg_hallucination_risk: float
    sample_size: int
    dimensions_live: dict[str, bool]
    findings: list[DiagnosticFinding] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    methodology_version: str = METHODOLOGY_VERSION
    created_at: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def to_public_dict(self) -> dict[str, Any]:
        """Free-tier view: score + grade + raw diagnostic metrics, no
        per-prompt findings (that's the paid diagnostic)."""
        return {
            "id": self.id,
            "model": self.model,
            "provider": self.provider,
            "created_at": self.created_at,
            "methodology_version": self.methodology_version,
            "overall_score": self.trust_score.overall,
            "grade": self.trust_score.grade,
            "risk_level": self.trust_score.risk_level,
            "dimensions": self.trust_score.to_dict()["dimensions"],
            "dimensions_live": self.dimensions_live,
            "raw_metrics": {
                "truthfulqa_accuracy": round(self.truthfulqa_accuracy, 4),
                "bbq_bias_rate": round(self.bbq_bias_rate, 4),
                "hellaswag_accuracy": round(self.hellaswag_accuracy, 4),
                "security_score": round(self.security_score, 4),
                "privacy_pii_leak_rate": round(self.privacy_pii_leak_rate, 4),
                "avg_hallucination_risk": round(self.avg_hallucination_risk, 4),
            },
            "sample_size": self.sample_size,
        }

    def to_diagnostic_dict(self) -> dict[str, Any]:
        """Paid-tier view: public summary plus every finding."""
        d = self.to_public_dict()
        d["findings"] = [f.to_dict() for f in self.findings]
        d["findings_count"] = len(self.findings)
        return d
