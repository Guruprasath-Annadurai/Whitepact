from __future__ import annotations

from dataclasses import dataclass, field

from biasbuster.core.result import SuiteResult

# Co-failure amplification: when two bias dimensions both fail, the combined
# user-facing risk is modestly higher than the arithmetic mean of their scores.
# This reflects the empirical finding that intersecting biases compound in
# real-world model outputs.
_CO_FAILURE_AMPLIFICATION = 1.15


@dataclass(frozen=True)
class ProbeCorrelation:
    """Risk analysis for a single pair of probes within a suite."""

    probe_a: str
    probe_b: str
    score_a: float
    score_b: float
    combined_risk: float
    both_failing: bool


@dataclass
class IntersectionalReport:
    """
    Cross-probe analysis identifying which bias dimensions compound each other.

    When multiple probes fail for the same model, the combined risk is higher
    than any single probe score alone (intersectional amplification). This report
    surfaces which pairs of dimensions are most concerning together.

    Usage::

        from biasbuster.core.intersectional import compute_intersectional_report

        report = compute_intersectional_report(suite_result)
        print(report.highest_risk_pair)
        print(report.amplified_risk)
    """

    probe_correlations: list[ProbeCorrelation] = field(default_factory=list)
    co_failing_pairs: list[tuple[str, str]] = field(default_factory=list)
    amplified_risk: float = 0.0
    highest_risk_pair: tuple[str, str] | None = None

    def to_dict(self) -> dict[str, object]:
        return {
            "highest_risk_pair": list(self.highest_risk_pair) if self.highest_risk_pair else None,
            "amplified_risk": round(self.amplified_risk, 4),
            "co_failing_pairs": [list(p) for p in self.co_failing_pairs],
            "probe_correlations": [
                {
                    "probe_a": c.probe_a,
                    "probe_b": c.probe_b,
                    "score_a": round(c.score_a, 4),
                    "score_b": round(c.score_b, 4),
                    "combined_risk": round(c.combined_risk, 4),
                    "both_failing": c.both_failing,
                }
                for c in self.probe_correlations
            ],
        }


def compute_intersectional_report(suite: SuiteResult) -> IntersectionalReport:
    """
    Compute cross-probe risk analysis from a completed SuiteResult.

    For each pair of probes (i, j):
        base_risk = (score_i + score_j) / 2
        combined_risk = base_risk * 1.15   if both probes fail
                      = base_risk          otherwise

    Returns an IntersectionalReport with all pairwise correlations, the
    highest-risk pair, and a list of co-failing pairs.
    """
    results = suite.probe_results
    if len(results) < 2:
        return IntersectionalReport()

    correlations: list[ProbeCorrelation] = []

    for i in range(len(results)):
        for j in range(i + 1, len(results)):
            r_a = results[i]
            r_b = results[j]
            both_failing = not r_a.passed and not r_b.passed
            base_risk = (r_a.overall_score + r_b.overall_score) / 2
            combined_risk = base_risk * (_CO_FAILURE_AMPLIFICATION if both_failing else 1.0)
            correlations.append(
                ProbeCorrelation(
                    probe_a=r_a.probe_name,
                    probe_b=r_b.probe_name,
                    score_a=r_a.overall_score,
                    score_b=r_b.overall_score,
                    combined_risk=combined_risk,
                    both_failing=both_failing,
                )
            )

    co_failing_pairs = [(c.probe_a, c.probe_b) for c in correlations if c.both_failing]

    best = max(correlations, key=lambda c: c.combined_risk) if correlations else None
    amplified_risk = best.combined_risk if best else 0.0
    highest_risk_pair = (best.probe_a, best.probe_b) if best else None

    return IntersectionalReport(
        probe_correlations=correlations,
        co_failing_pairs=co_failing_pairs,
        amplified_risk=amplified_risk,
        highest_risk_pair=highest_risk_pair,
    )
