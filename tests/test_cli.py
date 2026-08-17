"""Tests for the biasbuster CLI -- previously entirely untested (0% branch
coverage). Uses click's CliRunner plus a monkeypatched BiasBusterRunner.run
so no real provider network call ever happens; real providers are only
constructed (not called) where doing so needs no network access."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
from click.testing import CliRunner

from biasbuster.cli import PROBE_REGISTRY, _build_provider, main
from biasbuster.core.result import ProbeResult, SuiteResult, TemplateResult, VariantResponse


def _make_probe_result(*, passed: bool, severity: str, divergent_pair) -> ProbeResult:
    tr = TemplateResult(
        template="Tell me about {name}.",
        variant_responses=[
            VariantResponse(variant_name="a", prompt="p", response="r1"),
            VariantResponse(variant_name="b", prompt="p", response="r2"),
        ],
        divergence_score=0.5,
        severity=severity,
        most_divergent_pair=divergent_pair,
    )
    return ProbeResult(
        probe_name="gender-bias",
        probe_description="Detects gender bias.",
        provider_name="openai",
        model_name="gpt-4o",
        overall_score=0.5,
        severity=severity,
        passed=passed,
        threshold=0.25,
        template_results=[tr],
        timestamp=datetime.now(UTC),
    )


def _make_suite(*, passed: bool, empty: bool = False, severity: str = "medium") -> SuiteResult:
    results = [] if empty else [_make_probe_result(passed=passed, severity=severity, divergent_pair=("a", "b"))]
    return SuiteResult(provider_name="openai", model_name="gpt-4o", probe_results=results)


@pytest.fixture()
def runner():
    return CliRunner()


@pytest.fixture()
def fake_runner_class(monkeypatch):
    """Patches BiasBusterRunner used inside cli.run so no network call happens."""

    class _FakeRunner:
        def __init__(self, provider, **_kwargs):
            self.provider = provider

        async def run(self, probes):
            return fake_runner_class.suite

    monkeypatch.setattr("biasbuster.cli.BiasBusterRunner", _FakeRunner)
    fake_runner_class.suite = _make_suite(passed=True)
    return fake_runner_class


class TestBuildProvider:
    def test_openai_missing_key_exits(self, monkeypatch):
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc:
            _build_provider("openai", None)
        assert exc.value.code == 1

    def test_openai_with_key_returns_provider(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        provider = _build_provider("openai", None)
        assert provider.model_name == "gpt-4o"

    def test_openai_with_key_and_custom_model(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        provider = _build_provider("openai", "gpt-4-turbo")
        assert provider.model_name == "gpt-4-turbo"

    def test_anthropic_missing_key_exits(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        with pytest.raises(SystemExit) as exc:
            _build_provider("anthropic", None)
        assert exc.value.code == 1

    def test_anthropic_with_key_returns_provider(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-fake")
        provider = _build_provider("anthropic", None)
        assert provider.model_name == "claude-3-5-sonnet-20241022"

    def test_ollama_returns_provider_without_key(self):
        provider = _build_provider("ollama", "llama3.2")
        assert provider.model_name == "llama3.2"

    def test_ollama_default_model(self):
        provider = _build_provider("ollama", None)
        assert provider.model_name == "llama3.2"

    def test_huggingface_missing_transformers_raises_import_error(self):
        with pytest.raises(ImportError):
            _build_provider("huggingface", None)

    def test_unknown_provider_exits(self):
        with pytest.raises(SystemExit) as exc:
            _build_provider("nonexistent", None)
        assert exc.value.code == 1


class TestRunCommand:
    def test_unknown_probe_exits_nonzero(self, runner):
        result = runner.invoke(
            main, ["run", "--provider", "ollama", "--probes", "not-a-real-probe"]
        )
        assert result.exit_code == 1
        assert "Unknown probes" in result.output

    def test_quiet_mode_prints_json_and_passes(self, runner, fake_runner_class, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        fake_runner_class.suite = _make_suite(passed=True)
        result = runner.invoke(
            main, ["run", "--provider", "openai", "--quiet"]
        )
        assert result.exit_code == 0
        parsed = json.loads(result.output)
        assert parsed["provider"] == "openai"

    def test_non_quiet_mode_prints_rich_report_and_fails(self, runner, fake_runner_class, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        fake_runner_class.suite = _make_suite(passed=False, severity="high")
        result = runner.invoke(main, ["run", "--provider", "openai"])
        assert result.exit_code == 1
        assert "BiasBuster Report" in result.output
        assert "FAILED" in result.output

    def test_empty_probe_results_uses_default_color(self, runner, fake_runner_class, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        fake_runner_class.suite = _make_suite(passed=True, empty=True)
        result = runner.invoke(main, ["run", "--provider", "openai"])
        assert result.exit_code == 0
        assert "PASSED" in result.output

    def test_output_json_saves_report(self, runner, fake_runner_class, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        fake_runner_class.suite = _make_suite(passed=True)
        out = tmp_path / "report.json"
        result = runner.invoke(
            main, ["run", "--provider", "openai", "--quiet", "-o", str(out)]
        )
        assert result.exit_code == 0
        assert out.exists()

    def test_output_json_with_non_json_suffix_appends_suffix(
        self, runner, fake_runner_class, monkeypatch, tmp_path
    ):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        fake_runner_class.suite = _make_suite(passed=True)
        out = tmp_path / "report"
        result = runner.invoke(
            main, ["run", "--provider", "openai", "--quiet", "-o", str(out)]
        )
        assert result.exit_code == 0
        assert (tmp_path / "report.json").exists()

    def test_output_html_saves_html_report(self, runner, fake_runner_class, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        fake_runner_class.suite = _make_suite(passed=True)
        out = tmp_path / "report"
        result = runner.invoke(
            main, ["run", "--provider", "openai", "--quiet", "-o", str(out), "--format", "html"]
        )
        assert result.exit_code == 0
        assert (tmp_path / "report.html").exists()
        assert not (tmp_path / "report.json").exists()

    def test_output_both_saves_json_and_html(self, runner, fake_runner_class, monkeypatch, tmp_path):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        fake_runner_class.suite = _make_suite(passed=True)
        out = tmp_path / "report"
        result = runner.invoke(
            main, ["run", "--provider", "openai", "-o", str(out), "--format", "both"]
        )
        assert result.exit_code == 0
        assert (tmp_path / "report.json").exists()
        assert (tmp_path / "report.html").exists()

    def test_custom_threshold_and_multiple_probes(self, runner, fake_runner_class, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-fake")
        fake_runner_class.suite = _make_suite(passed=True)
        result = runner.invoke(
            main,
            [
                "run",
                "--provider",
                "openai",
                "--probes",
                "gender-bias,racial-bias",
                "--threshold",
                "0.5",
                "--quiet",
            ],
        )
        assert result.exit_code == 0


class TestListProbesCommand:
    def test_lists_all_registered_probes(self, runner):
        result = runner.invoke(main, ["list-probes"])
        assert result.exit_code == 0
        for name in PROBE_REGISTRY:
            assert name in result.output
