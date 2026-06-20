"""Tests for CostAnalyzer."""

from __future__ import annotations

import pytest

from responsibleai.cost.analyzer import CostAnalyzer, classify_task_complexity


class TestClassifyTaskComplexity:
    def test_high_risk_medical(self):
        assert classify_task_complexity("diagnose this medical condition") == "high_risk"

    def test_high_risk_legal(self):
        assert classify_task_complexity("provide legal advice for my contract") == "high_risk"

    def test_high_risk_financial(self):
        assert classify_task_complexity("give financial advice for my portfolio") == "high_risk"

    def test_complex_analysis(self):
        assert classify_task_complexity("analyze customer churn and compare retention strategies") == "complex"

    def test_complex_debug(self):
        assert classify_task_complexity("debug this production outage and optimize the query") == "complex"

    def test_medium_summarize(self):
        assert classify_task_complexity("summarize this 10-page report") == "medium"

    def test_medium_draft(self):
        assert classify_task_complexity("draft a welcome email for new users") == "medium"

    def test_simple_classify(self):
        assert classify_task_complexity("classify this email as spam or not") == "simple"

    def test_simple_default(self):
        assert classify_task_complexity("hello world") == "simple"


@pytest.fixture()
def analyzer() -> CostAnalyzer:
    return CostAnalyzer()


class TestPromptEfficiency:
    def test_clean_prompt_high_score(self, analyzer):
        result = analyzer.analyze_prompt_efficiency(
            prompt="List the top 5 programming languages by popularity.",
            provider="openai",
            model="gpt-4o",
        )
        assert result.efficiency_score >= 80.0
        assert result.original_tokens > 0

    def test_bloated_prompt_finds_findings(self, analyzer):
        prompt = (
            "Please note that as an AI language model I want you to "
            "summarize the following document. It is important to note "
            "that you should be concise."
        )
        result = analyzer.analyze_prompt_efficiency(prompt=prompt, monthly_requests=10_000)
        assert len(result.waste_findings) > 0

    def test_bloat_category_present(self, analyzer):
        prompt = "As an AI language model, please note that I want you to extract keywords."
        result = analyzer.analyze_prompt_efficiency(prompt=prompt)
        categories = [f.category for f in result.waste_findings]
        assert any(c in ("prompt_bloat",) for c in categories)

    def test_model_overkill_detected(self, analyzer):
        prompt = "classify this as spam or not"
        result = analyzer.analyze_prompt_efficiency(
            prompt=prompt,
            provider="openai",
            model="gpt-4-turbo",
            monthly_requests=100_000,
        )
        categories = [f.category for f in result.waste_findings]
        assert "model_overkill" in categories

    def test_verbose_response_detected(self, analyzer):
        short_prompt = "yes or no"
        long_response = " ".join(["word"] * 500)
        result = analyzer.analyze_prompt_efficiency(
            prompt=short_prompt, response=long_response, monthly_requests=5000
        )
        categories = [f.category for f in result.waste_findings]
        assert "verbose_response" in categories

    def test_result_to_dict(self, analyzer):
        result = analyzer.analyze_prompt_efficiency("Test prompt")
        d = result.to_dict()
        assert "original_tokens" in d
        assert "efficiency_score" in d
        assert "waste_findings" in d

    def test_local_model_no_overkill(self, analyzer):
        result = analyzer.analyze_prompt_efficiency(
            prompt="classify this email", provider="ollama", model="llama3.2"
        )
        categories = [f.category for f in result.waste_findings]
        assert "model_overkill" not in categories

    def test_monthly_savings_nonnegative(self, analyzer):
        result = analyzer.analyze_prompt_efficiency("Test")
        assert result.estimated_monthly_savings_usd >= 0.0


class TestGovernanceScore:
    def test_perfect_governance(self, analyzer):
        result = analyzer.governance_score(
            total_cost_usd=500.0,
            monthly_limit_usd=1000.0,
            distinct_models=4,
            waste_pct=0.0,
        )
        assert result["governance_score"] > 90
        assert result["grade"] == "A"

    def test_budget_exceeded_lowers_score(self, analyzer):
        result = analyzer.governance_score(
            total_cost_usd=2000.0,
            monthly_limit_usd=1000.0,
            distinct_models=3,
            waste_pct=10.0,
        )
        assert result["governance_score"] < 80

    def test_high_waste_lowers_score(self, analyzer):
        result = analyzer.governance_score(
            total_cost_usd=100.0,
            monthly_limit_usd=1000.0,
            distinct_models=3,
            waste_pct=80.0,
        )
        assert result["governance_score"] < 70

    def test_grade_present(self, analyzer):
        result = analyzer.governance_score(500, 1000, 3, 5)
        assert result["grade"] in ("A", "B", "C", "D", "F")
