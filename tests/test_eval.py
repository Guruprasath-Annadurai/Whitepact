"""Tests for the Model Evaluation Framework — comparator, benchmarks, regression, dataset scanner."""

from __future__ import annotations

import pytest

from responsibleai.eval.benchmarks import (
    BenchmarkRunner,
    _score_bbq,
    _score_hellaswag,
    _score_truthfulqa,
)
from responsibleai.eval.comparator import ModelComparator
from responsibleai.eval.dataset_scanner import DatasetBiasScanner
from responsibleai.eval.models import (
    BenchmarkResult,
    BenchmarkSuite,
    ComparisonResult,
    DatasetScanResult,
    EvalPrompt,
    ModelResponse,
    RegressionAlert,
    RegressionSeverity,
)
from responsibleai.eval.regression import RegressionDetector

# ── EvalPrompt / ModelResponse ─────────────────────────────────────────────────

class TestEvalModels:
    def test_eval_prompt_auto_id(self):
        p = EvalPrompt(prompt="Hello?")
        assert p.id
        assert p.expected == ""
        assert p.category == ""

    def test_two_prompts_have_different_ids(self):
        p1 = EvalPrompt(prompt="Q1")
        p2 = EvalPrompt(prompt="Q2")
        assert p1.id != p2.id

    def test_model_response_fields(self):
        r = ModelResponse(prompt_id="x", model="gpt-4o", provider="openai", response="Hello")
        assert r.model == "gpt-4o"
        assert r.cost_usd == 0.0


# ── ComparisonResult ───────────────────────────────────────────────────────────

class TestComparisonResult:
    def test_empty_result(self):
        cr = ComparisonResult(model_a="A", model_b="B", provider_a="p", provider_b="p")
        assert cr.avg_trust_a == 0.0
        assert cr.avg_trust_b == 0.0
        assert cr.winner == "tie"

    def test_to_dict_keys(self):
        cr = ComparisonResult(model_a="A", model_b="B", provider_a="p", provider_b="p")
        d = cr.to_dict()
        for k in ("id", "created_at", "model_a", "model_b", "winner", "wins_a", "wins_b", "ties"):
            assert k in d

    def test_wins_counted_correctly(self):
        from responsibleai.eval.models import PromptComparisonResult
        cr = ComparisonResult(model_a="A", model_b="B", provider_a="p", provider_b="p")
        cr.prompt_results.append(
            PromptComparisonResult("p1", "q", "ra", "rb", "A", "B", 80.0, 60.0, "model_a")
        )
        cr.prompt_results.append(
            PromptComparisonResult("p2", "q", "ra", "rb", "A", "B", 50.0, 75.0, "model_b")
        )
        assert cr.wins_a == 1
        assert cr.wins_b == 1
        assert cr.ties == 0


# ── BenchmarkResult ────────────────────────────────────────────────────────────

class TestBenchmarkResult:
    def _make_result(self, corrects: list[bool], biases: list[bool]) -> BenchmarkResult:
        from responsibleai.eval.models import BenchmarkSampleResult
        r = BenchmarkResult(model="m", provider="p", suite=BenchmarkSuite.TRUTHFULQA)
        for i, (c, b) in enumerate(zip(corrects, biases, strict=False)):
            r.sample_results.append(
                BenchmarkSampleResult(
                    sample_id=f"s{i}", prompt="q", expected="e",
                    model_response="r", model="m", correct=c,
                    category="cat", bias_detected=b,
                )
            )
        return r

    def test_accuracy_all_correct(self):
        r = self._make_result([True, True, True], [False, False, False])
        assert r.accuracy == 1.0

    def test_accuracy_none_correct(self):
        r = self._make_result([False, False], [False, False])
        assert r.accuracy == 0.0

    def test_bias_rate(self):
        r = self._make_result([True, True, False], [True, False, False])
        assert r.bias_rate == pytest.approx(1 / 3, rel=1e-3)

    def test_overall_score_formula(self):
        r = self._make_result([True, True], [False, False])
        assert r.overall_score == pytest.approx(1.0 * 0.7 + 1.0 * 0.3)

    def test_to_dict_keys(self):
        r = self._make_result([True], [False])
        d = r.to_dict()
        assert {"id", "model", "provider", "suite", "accuracy", "bias_rate", "overall_score"} <= d.keys()

    def test_empty_result(self):
        r = BenchmarkResult(model="m", provider="p", suite=BenchmarkSuite.BBQ)
        assert r.accuracy == 0.0
        assert r.overall_score == 0.0 * 0.7 + 1.0 * 0.3  # no bias → safety component = 0.3


# ── Benchmark scoring helpers ──────────────────────────────────────────────────

class TestBenchmarkScoringHelpers:
    def test_truthfulqa_keyword_match(self):
        assert _score_truthfulqa("Nothing happens, it's harmless.", ["nothing", "harmless"])

    def test_truthfulqa_no_match(self):
        assert not _score_truthfulqa("You will grow a watermelon.", ["nothing", "harmless"])

    def test_bbq_no_bias(self):
        ok, bias = _score_bbq("We cannot determine that without more information.", ["man", "the man"])
        assert ok and not bias

    def test_bbq_bias_detected(self):
        ok, bias = _score_bbq("The man is definitely more skilled.", ["man", "the man"])
        assert not ok and bias

    def test_hellaswag_correct(self):
        assert _score_hellaswag("applies soap and scrubs", "applies soap and begins scrubbing")

    def test_hellaswag_wrong(self):
        assert not _score_hellaswag("starts eating lunch", "applies soap and begins scrubbing")


# ── BenchmarkRunner ────────────────────────────────────────────────────────────

class TestBenchmarkRunner:
    def test_get_prompts_truthfulqa(self):
        runner = BenchmarkRunner()
        prompts = runner.get_prompts(BenchmarkSuite.TRUTHFULQA)
        assert len(prompts) == 15
        assert all("id" in p and "prompt" in p for p in prompts)

    def test_get_prompts_bbq(self):
        runner = BenchmarkRunner()
        prompts = runner.get_prompts(BenchmarkSuite.BBQ)
        assert len(prompts) == 15

    def test_get_prompts_hellaswag(self):
        runner = BenchmarkRunner()
        prompts = runner.get_prompts(BenchmarkSuite.HELLASWAG)
        assert len(prompts) == 15

    def test_run_truthfulqa_all_good(self):
        runner = BenchmarkRunner()
        prompts = runner.get_prompts(BenchmarkSuite.TRUTHFULQA)
        responses = {p["id"]: "No, that is a myth and nothing happens." for p in prompts}
        result = runner.run("test-model", "local", BenchmarkSuite.TRUTHFULQA, responses)
        assert isinstance(result, BenchmarkResult)
        assert result.accuracy > 0
        assert len(result.sample_results) == 15

    def test_run_bbq_unbiased_responses(self):
        runner = BenchmarkRunner()
        prompts = runner.get_prompts(BenchmarkSuite.BBQ)
        responses = {p["id"]: "We cannot determine that from the information provided." for p in prompts}
        result = runner.run("test-model", "local", BenchmarkSuite.BBQ, responses)
        assert result.bias_rate == 0.0
        assert result.accuracy == 1.0

    def test_run_hellaswag_partial(self):
        runner = BenchmarkRunner()
        prompts = runner.get_prompts(BenchmarkSuite.HELLASWAG)
        responses = {prompts[0]["id"]: "applies soap and begins scrubbing"}
        result = runner.run("test-model", "local", BenchmarkSuite.HELLASWAG, responses)
        assert len(result.sample_results) == 1
        assert result.sample_results[0].correct is True

    def test_run_skips_missing_responses(self):
        runner = BenchmarkRunner()
        result = runner.run("m", "p", BenchmarkSuite.TRUTHFULQA, {})
        assert len(result.sample_results) == 0

    def test_run_unknown_suite_raises(self):
        runner = BenchmarkRunner()
        with pytest.raises(ValueError):
            runner.run("m", "p", BenchmarkSuite.CUSTOM, {})

    def test_result_to_dict_has_category_breakdown(self):
        runner = BenchmarkRunner()
        prompts = runner.get_prompts(BenchmarkSuite.TRUTHFULQA)
        responses = {p["id"]: "No, that is nothing." for p in prompts}
        result = runner.run("m", "p", BenchmarkSuite.TRUTHFULQA, responses)
        d = result.to_dict()
        assert "category_breakdown" in d


# ── ModelComparator ────────────────────────────────────────────────────────────

class TestModelComparator:
    def _make_prompt_and_responses(self, text_a: str, text_b: str):
        p = EvalPrompt(prompt="What is 2+2?", expected="4")
        ra = ModelResponse(prompt_id=p.id, model="A", provider="p", response=text_a)
        rb = ModelResponse(prompt_id=p.id, model="B", provider="p", response=text_b)
        return [p], [ra], [rb]

    def test_compare_returns_result(self):
        comp = ModelComparator()
        prompts, ra, rb = self._make_prompt_and_responses("The answer is 4.", "Four is the answer.")
        result = comp.compare(prompts, ra, rb, "A", "B")
        assert isinstance(result, ComparisonResult)
        assert len(result.prompt_results) == 1

    def test_pii_response_penalised(self):
        comp = ModelComparator()
        p = EvalPrompt(prompt="Tell me about Jane.", expected="general info")
        ra = ModelResponse(prompt_id=p.id, model="A", provider="p",
                           response="Jane's email is jane.smith@example.com and her SSN is 123-45-6789.")
        rb = ModelResponse(prompt_id=p.id, model="B", provider="p",
                           response="Jane is a software developer.")
        result = comp.compare([p], [ra], [rb], "A", "B")
        pr = result.prompt_results[0]
        assert pr.pii_detected_a is True
        assert pr.pii_detected_b is False
        assert pr.trust_score_a < pr.trust_score_b

    def test_skips_prompt_with_missing_response(self):
        comp = ModelComparator()
        p = EvalPrompt(prompt="Q?")
        ra = ModelResponse(prompt_id=p.id, model="A", provider="p", response="answer")
        result = comp.compare([p], [ra], [], "A", "B")
        assert len(result.prompt_results) == 0

    def test_compare_to_dict(self):
        comp = ModelComparator()
        prompts, ra, rb = self._make_prompt_and_responses("Four.", "4.")
        result = comp.compare(prompts, ra, rb, "A", "B")
        d = result.to_dict()
        assert d["model_a"] == "A"
        assert d["model_b"] == "B"
        assert "prompt_results" in d


# ── RegressionDetector ─────────────────────────────────────────────────────────

class TestRegressionDetector:
    def _make_result(self, accuracy: float, bias_rate: float) -> BenchmarkResult:
        from responsibleai.eval.models import BenchmarkSampleResult
        r = BenchmarkResult(model="m", provider="p", suite=BenchmarkSuite.TRUTHFULQA)
        total = 10
        correct = int(accuracy * total)
        biased = int(bias_rate * total)
        for i in range(total):
            r.sample_results.append(
                BenchmarkSampleResult(
                    sample_id=f"s{i}", prompt="q", expected="e",
                    model_response="r", model="m",
                    correct=(i < correct),
                    bias_detected=(i < biased),
                )
            )
        return r

    def test_no_alerts_without_baseline(self):
        det = RegressionDetector()
        result = self._make_result(0.8, 0.1)
        assert det.check("m", result) == []

    def test_set_baseline_and_check_no_regression(self):
        det = RegressionDetector()
        baseline = self._make_result(0.8, 0.1)
        det.set_baseline("m", baseline)
        same = self._make_result(0.8, 0.1)
        alerts = det.check("m", same)
        assert alerts == []

    def test_minor_accuracy_drop_detected(self):
        det = RegressionDetector()
        det.set_baseline("m", self._make_result(1.0, 0.0))
        current = self._make_result(0.9, 0.0)  # 1.0 → 0.9 = 0.1 drop → MODERATE
        alerts = det.check("m", current)
        accuracy_alerts = [a for a in alerts if "accuracy" in a.metric]
        assert len(accuracy_alerts) > 0
        assert accuracy_alerts[0].severity in (RegressionSeverity.MINOR, RegressionSeverity.MODERATE)

    def test_severe_accuracy_drop_detected(self):
        det = RegressionDetector()
        det.set_baseline("m", self._make_result(0.9, 0.0))
        current = self._make_result(0.5, 0.0)
        alerts = det.check("m", current)
        accuracy_alerts = [a for a in alerts if "accuracy" in a.metric]
        assert any(a.severity == RegressionSeverity.SEVERE for a in accuracy_alerts)

    def test_bias_rate_increase_detected(self):
        det = RegressionDetector()
        det.set_baseline("m", self._make_result(0.8, 0.0))
        current = self._make_result(0.8, 0.3)
        alerts = det.check("m", current)
        bias_alerts = [a for a in alerts if "bias_rate" in a.metric]
        assert len(bias_alerts) > 0

    def test_list_models(self):
        det = RegressionDetector()
        det.set_baseline("model-x", self._make_result(0.7, 0.1))
        assert "model-x" in det.list_models()

    def test_get_baselines_after_set(self):
        det = RegressionDetector()
        r = self._make_result(0.75, 0.05)
        det.set_baseline("m", r)
        b = det.get_baselines("m")
        assert "truthfulqa:accuracy" in b
        assert "truthfulqa:bias_rate" in b
        assert "truthfulqa:overall_score" in b

    def test_clear_baseline(self):
        det = RegressionDetector()
        det.set_baseline("m", self._make_result(0.8, 0.1))
        assert det.clear_baseline("m")
        assert det.get_baselines("m") == {}

    def test_alert_to_dict_keys(self):
        alert = RegressionAlert(
            model="m", metric="accuracy", baseline_score=0.8, current_score=0.6,
            delta=0.2, severity=RegressionSeverity.SEVERE, suite="truthfulqa"
        )
        d = alert.to_dict()
        assert {"id", "detected_at", "model", "metric", "delta", "severity", "suite"} <= d.keys()


# ── DatasetBiasScanner ─────────────────────────────────────────────────────────

class TestDatasetBiasScanner:
    def test_scan_clean_texts(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["The sky is blue.", "Water is wet."])
        assert isinstance(result, DatasetScanResult)
        assert result.total_rows == 2

    def test_scan_gendered_text(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["She is a great nurse and he is an engineer."])
        assert result.bias_rows >= 1
        r = result.row_results[0]
        assert "gender" in r.bias_categories

    def test_scan_pii_detected(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["Contact us at test@example.com or call 555-123-4567."])
        assert result.pii_rows == 1

    def test_scan_flag_rate(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["clean text", "she and he are equal", "clean again"])
        assert 0.0 <= result.flag_rate <= 1.0

    def test_scan_csv(self):
        scanner = DatasetBiasScanner()
        csv_content = "name,text\nAlice,She is a doctor.\nBob,He is a nurse."
        result = scanner.scan_csv(csv_content, filename="test.csv")
        assert result.total_rows == 2

    def test_scan_csv_with_text_column(self):
        scanner = DatasetBiasScanner()
        csv_content = "id,body\n1,He is old.\n2,The young woman.\n"
        result = scanner.scan_csv(csv_content, filename="f.csv", text_column="body")
        assert result.total_rows == 2

    def test_scan_jsonl(self):
        scanner = DatasetBiasScanner()
        jsonl = '{"text": "She is the boss."}\n{"text": "He is an engineer."}\n'
        result = scanner.scan_jsonl(jsonl, filename="f.jsonl", text_field="text")
        assert result.total_rows == 2
        assert result.bias_rows >= 1

    def test_scan_empty_texts(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts([])
        assert result.total_rows == 0
        assert result.flag_rate == 0.0

    def test_to_dict_keys(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["hello", "world"])
        d = result.to_dict()
        assert {"id", "filename", "total_rows", "flagged_rows", "bias_category_counts", "flagged_samples"} <= d.keys()

    def test_racial_bias_detected(self):
        scanner = DatasetBiasScanner()
        result = scanner.scan_texts(["The Asian student and the white professor disagreed."])
        r = result.row_results[0]
        assert "racial" in r.bias_categories
