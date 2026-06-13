from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest

from biasbuster.core.result import ProbeResult, SuiteResult, TemplateResult, VariantResponse
from biasbuster.reporting.json_reporter import JsonReporter


def _make_suite() -> SuiteResult:
    vr = VariantResponse(
        variant_name="masculine",
        prompt="Write a bio for James.",
        response="James is a great engineer.",
    )
    tr = TemplateResult(
        template="Write a bio for {name}.",
        variant_responses=[vr],
        divergence_score=0.12,
        severity="low",
        most_divergent_pair=("masculine", "feminine"),
    )
    probe = ProbeResult(
        probe_name="gender-bias",
        probe_description="Tests gender bias in professional contexts.",
        provider_name="mock",
        model_name="mock-1.0",
        overall_score=0.12,
        severity="low",
        passed=True,
        threshold=0.20,
        template_results=[tr],
        confidence_interval=(0.08, 0.16),
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )
    return SuiteResult(
        provider_name="mock",
        model_name="mock-1.0",
        probe_results=[probe],
        timestamp=datetime(2026, 1, 1, tzinfo=timezone.utc),
    )


class TestJsonReporter:
    def test_dumps_suite_returns_valid_json(self) -> None:
        raw = JsonReporter().dumps(_make_suite())
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_dumps_probe_returns_valid_json(self) -> None:
        suite = _make_suite()
        raw = JsonReporter().dumps(suite.probe_results[0])
        parsed = json.loads(raw)
        assert isinstance(parsed, dict)

    def test_suite_has_provider_field(self) -> None:
        parsed = json.loads(JsonReporter().dumps(_make_suite()))
        assert parsed["provider"] == "mock"

    def test_suite_has_model_field(self) -> None:
        parsed = json.loads(JsonReporter().dumps(_make_suite()))
        assert parsed["model"] == "mock-1.0"

    def test_suite_has_overall_score(self) -> None:
        parsed = json.loads(JsonReporter().dumps(_make_suite()))
        assert "overall_score" in parsed
        assert isinstance(parsed["overall_score"], float)

    def test_suite_has_passed_field(self) -> None:
        parsed = json.loads(JsonReporter().dumps(_make_suite()))
        assert "passed" in parsed
        assert parsed["passed"] is True

    def test_suite_has_probes_list(self) -> None:
        parsed = json.loads(JsonReporter().dumps(_make_suite()))
        assert "probes" in parsed
        assert len(parsed["probes"]) == 1

    def test_suite_has_timestamp(self) -> None:
        parsed = json.loads(JsonReporter().dumps(_make_suite()))
        assert "timestamp" in parsed
        assert "2026" in parsed["timestamp"]

    def test_probe_has_confidence_interval(self) -> None:
        parsed = json.loads(JsonReporter().dumps(_make_suite().probe_results[0]))
        ci = parsed["confidence_interval"]
        assert ci is not None
        assert len(ci) == 2
        assert ci[0] <= ci[1]

    def test_probe_has_template_results(self) -> None:
        parsed = json.loads(JsonReporter().dumps(_make_suite().probe_results[0]))
        assert len(parsed["template_results"]) == 1
        tr = parsed["template_results"][0]
        assert "divergence_score" in tr
        assert "responses" in tr

    def test_custom_indent_applied(self) -> None:
        raw = JsonReporter(indent=4).dumps(_make_suite())
        assert "    " in raw

    def test_default_indent_is_two_spaces(self) -> None:
        raw = JsonReporter().dumps(_make_suite())
        assert "  " in raw

    def test_save_writes_readable_file(self, tmp_path: Path) -> None:
        out = tmp_path / "report.json"
        JsonReporter().save(_make_suite(), out)
        assert out.exists()
        parsed = json.loads(out.read_text())
        assert parsed["provider"] == "mock"

    def test_save_creates_parent_directories(self, tmp_path: Path) -> None:
        out = tmp_path / "nested" / "dir" / "report.json"
        JsonReporter().save(_make_suite(), out)
        assert out.exists()

    def test_print_outputs_valid_json(self, capsys: pytest.CaptureFixture[str]) -> None:
        JsonReporter().print(_make_suite())
        captured = capsys.readouterr()
        parsed = json.loads(captured.out)
        assert parsed["provider"] == "mock"

    def test_probe_serialised_confidence_interval_none(self) -> None:
        suite = _make_suite()
        suite.probe_results[0].confidence_interval = None  # type: ignore[misc]
        parsed = json.loads(JsonReporter().dumps(suite.probe_results[0]))
        assert parsed["confidence_interval"] is None
