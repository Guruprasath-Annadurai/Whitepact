from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

import pytest

from biasbuster.core.result import ProbeResult, SuiteResult, TemplateResult, VariantResponse
from biasbuster.reporting.html_reporter import HtmlReporter


def _make_variant(name: str = "masculine", response: str = "Alex is great.") -> VariantResponse:
    return VariantResponse(variant_name=name, prompt="Write a bio.", response=response)


def _make_suite(*, passed: bool = True, with_ci: bool = False) -> SuiteResult:
    tr = TemplateResult(
        template="Write a bio for {name}.",
        variant_responses=[
            _make_variant("masculine", "He is a great engineer."),
            _make_variant("feminine", "She is a great engineer."),
        ],
        divergence_score=0.05 if passed else 0.35,
        severity="none" if passed else "high",
        most_divergent_pair=None if passed else ("masculine", "feminine"),
    )
    ci = (0.10, 0.20) if with_ci else None
    probe = ProbeResult(
        probe_name="gender-bias",
        probe_description="Tests gender bias in professional contexts.",
        provider_name="mock",
        model_name="mock-1.0",
        overall_score=0.05 if passed else 0.35,
        severity="none" if passed else "high",
        passed=passed,
        threshold=0.20,
        template_results=[tr],
        confidence_interval=ci,
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return SuiteResult(
        provider_name="mock",
        model_name="mock-1.0",
        probe_results=[probe],
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestHtmlReporter:
    def test_render_returns_string(self) -> None:
        output = HtmlReporter().render(_make_suite())
        assert isinstance(output, str)
        assert len(output) > 100

    def test_render_contains_doctype(self) -> None:
        output = HtmlReporter().render(_make_suite())
        assert "<!DOCTYPE html>" in output

    def test_render_contains_probe_name(self) -> None:
        output = HtmlReporter().render(_make_suite())
        assert "gender-bias" in output

    def test_render_contains_model_name(self) -> None:
        output = HtmlReporter().render(_make_suite())
        assert "mock-1.0" in output

    def test_render_contains_passed_status(self) -> None:
        output = HtmlReporter().render(_make_suite(passed=True))
        assert "PASSED" in output

    def test_render_contains_failed_status(self) -> None:
        output = HtmlReporter().render(_make_suite(passed=False))
        assert "FAILED" in output

    def test_render_contains_score(self) -> None:
        output = HtmlReporter().render(_make_suite(passed=False))
        assert "0.35" in output or "0.3500" in output

    def test_render_with_confidence_interval(self) -> None:
        output = HtmlReporter().render(_make_suite(with_ci=True))
        assert "CI" in output

    def test_render_contains_biasbuster_branding(self) -> None:
        output = HtmlReporter().render(_make_suite())
        assert "BiasBuster" in output

    def test_render_contains_timestamp(self) -> None:
        output = HtmlReporter().render(_make_suite())
        assert "2026" in output

    def test_save_writes_file(self, tmp_path: Path) -> None:
        out = tmp_path / "report.html"
        HtmlReporter().save(_make_suite(), out)
        assert out.exists()
        content = out.read_text(encoding="utf-8")
        assert "BiasBuster" in content

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "deep" / "report.html"
        HtmlReporter().save(_make_suite(), out)
        assert out.exists()

    def test_multiple_probes_all_rendered(self) -> None:
        suite = _make_suite()
        extra = ProbeResult(
            probe_name="racial-bias",
            probe_description="Tests racial bias.",
            provider_name="mock",
            model_name="mock-1.0",
            overall_score=0.08,
            severity="low",
            passed=True,
            threshold=0.20,
            template_results=[],
            timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
        )
        suite.probe_results.append(extra)
        output = HtmlReporter().render(suite)
        assert "gender-bias" in output
        assert "racial-bias" in output

    def test_render_html_is_valid_structure(self) -> None:
        output = HtmlReporter().render(_make_suite())
        assert "<html" in output
        assert "</html>" in output
        assert "<body" in output
        assert "</body>" in output

    def test_render_probe_description_present(self) -> None:
        output = HtmlReporter().render(_make_suite())
        assert "gender bias" in output.lower()
