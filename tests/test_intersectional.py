from __future__ import annotations

from datetime import UTC, datetime

import pytest

from biasbuster.core.intersectional import (
    IntersectionalReport,
    compute_intersectional_report,
)
from biasbuster.core.result import ProbeResult, SuiteResult


def _make_probe(
    name: str,
    score: float,
    passed: bool,
    threshold: float = 0.20,
) -> ProbeResult:
    return ProbeResult(
        probe_name=name,
        probe_description=f"Tests {name}.",
        provider_name="mock",
        model_name="mock-1.0",
        overall_score=score,
        severity="low",
        passed=passed,
        threshold=threshold,
        template_results=[],
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


def _make_suite(*probes: ProbeResult) -> SuiteResult:
    return SuiteResult(
        provider_name="mock",
        model_name="mock-1.0",
        probe_results=list(probes),
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
    )


class TestComputeIntersectionalReport:
    def test_empty_suite_returns_empty(self) -> None:
        suite = _make_suite()
        report = compute_intersectional_report(suite)
        assert report.probe_correlations == []
        assert report.co_failing_pairs == []
        assert report.amplified_risk == 0.0
        assert report.highest_risk_pair is None

    def test_single_probe_returns_empty(self) -> None:
        suite = _make_suite(_make_probe("gender-bias", 0.15, False))
        report = compute_intersectional_report(suite)
        assert report.probe_correlations == []
        assert report.highest_risk_pair is None

    def test_two_probes_produce_one_pair(self) -> None:
        suite = _make_suite(
            _make_probe("gender-bias", 0.10, True),
            _make_probe("racial-bias", 0.12, True),
        )
        report = compute_intersectional_report(suite)
        assert len(report.probe_correlations) == 1

    def test_three_probes_produce_three_pairs(self) -> None:
        suite = _make_suite(
            _make_probe("gender-bias", 0.10, True),
            _make_probe("racial-bias", 0.12, True),
            _make_probe("age-bias", 0.08, True),
        )
        report = compute_intersectional_report(suite)
        assert len(report.probe_correlations) == 3

    def test_four_probes_produce_six_pairs(self) -> None:
        suite = _make_suite(
            _make_probe("a", 0.1, True),
            _make_probe("b", 0.2, False),
            _make_probe("c", 0.3, False),
            _make_probe("d", 0.05, True),
        )
        report = compute_intersectional_report(suite)
        assert len(report.probe_correlations) == 6

    def test_combined_risk_is_mean_when_both_pass(self) -> None:
        suite = _make_suite(
            _make_probe("a", 0.10, True),
            _make_probe("b", 0.20, True),
        )
        report = compute_intersectional_report(suite)
        corr = report.probe_correlations[0]
        assert corr.combined_risk == pytest.approx(0.15, abs=1e-6)
        assert not corr.both_failing

    def test_co_failure_amplification_applied(self) -> None:
        suite = _make_suite(
            _make_probe("a", 0.10, False),
            _make_probe("b", 0.20, False),
        )
        report = compute_intersectional_report(suite)
        corr = report.probe_correlations[0]
        expected = 0.15 * 1.15
        assert corr.combined_risk == pytest.approx(expected, abs=1e-6)
        assert corr.both_failing

    def test_no_amplification_when_only_one_fails(self) -> None:
        suite = _make_suite(
            _make_probe("a", 0.25, False),
            _make_probe("b", 0.10, True),
        )
        report = compute_intersectional_report(suite)
        corr = report.probe_correlations[0]
        assert corr.combined_risk == pytest.approx(0.175, abs=1e-6)
        assert not corr.both_failing

    def test_highest_risk_pair_identified(self) -> None:
        suite = _make_suite(
            _make_probe("gender-bias", 0.30, False),
            _make_probe("racial-bias", 0.35, False),
            _make_probe("age-bias", 0.05, True),
        )
        report = compute_intersectional_report(suite)
        assert report.highest_risk_pair == ("gender-bias", "racial-bias")

    def test_co_failing_pairs_populated(self) -> None:
        suite = _make_suite(
            _make_probe("gender-bias", 0.30, False),
            _make_probe("racial-bias", 0.35, False),
            _make_probe("age-bias", 0.05, True),
        )
        report = compute_intersectional_report(suite)
        assert ("gender-bias", "racial-bias") in report.co_failing_pairs
        assert len(report.co_failing_pairs) == 1

    def test_co_failing_pairs_empty_when_all_pass(self) -> None:
        suite = _make_suite(
            _make_probe("gender-bias", 0.05, True),
            _make_probe("racial-bias", 0.08, True),
        )
        report = compute_intersectional_report(suite)
        assert report.co_failing_pairs == []

    def test_amplified_risk_uses_best_pair(self) -> None:
        suite = _make_suite(
            _make_probe("a", 0.40, False),
            _make_probe("b", 0.40, False),
            _make_probe("c", 0.05, True),
        )
        report = compute_intersectional_report(suite)
        expected = 0.40 * 1.15
        assert report.amplified_risk == pytest.approx(expected, abs=1e-6)

    def test_probe_names_in_correlation(self) -> None:
        suite = _make_suite(
            _make_probe("alpha", 0.10, True),
            _make_probe("beta", 0.20, True),
        )
        report = compute_intersectional_report(suite)
        corr = report.probe_correlations[0]
        assert corr.probe_a == "alpha"
        assert corr.probe_b == "beta"

    def test_scores_in_correlation(self) -> None:
        suite = _make_suite(
            _make_probe("a", 0.12, True),
            _make_probe("b", 0.18, True),
        )
        report = compute_intersectional_report(suite)
        corr = report.probe_correlations[0]
        assert corr.score_a == pytest.approx(0.12)
        assert corr.score_b == pytest.approx(0.18)


class TestIntersectionalReportToDict:
    def test_to_dict_structure(self) -> None:
        suite = _make_suite(
            _make_probe("gender-bias", 0.25, False),
            _make_probe("racial-bias", 0.30, False),
        )
        report = compute_intersectional_report(suite)
        d = report.to_dict()
        assert "highest_risk_pair" in d
        assert "amplified_risk" in d
        assert "co_failing_pairs" in d
        assert "probe_correlations" in d

    def test_to_dict_highest_risk_pair_is_list(self) -> None:
        suite = _make_suite(
            _make_probe("a", 0.20, False),
            _make_probe("b", 0.30, False),
        )
        report = compute_intersectional_report(suite)
        d = report.to_dict()
        assert isinstance(d["highest_risk_pair"], list)
        assert len(d["highest_risk_pair"]) == 2  # type: ignore[arg-type]

    def test_to_dict_empty_report(self) -> None:
        report = IntersectionalReport()
        d = report.to_dict()
        assert d["highest_risk_pair"] is None
        assert d["amplified_risk"] == 0.0
        assert d["co_failing_pairs"] == []
        assert d["probe_correlations"] == []

    def test_to_dict_rounded_values(self) -> None:
        suite = _make_suite(
            _make_probe("a", 0.123456, True),
            _make_probe("b", 0.234567, True),
        )
        report = compute_intersectional_report(suite)
        d = report.to_dict()
        corr = d["probe_correlations"][0]  # type: ignore[index]
        assert isinstance(corr["combined_risk"], float)
        assert len(str(corr["combined_risk"]).split(".")[-1]) <= 4
