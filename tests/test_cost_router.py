"""Tests for ModelRouter."""

from __future__ import annotations

import pytest

from responsibleai.cost.router import ModelRouter


@pytest.fixture()
def router() -> ModelRouter:
    return ModelRouter()


class TestRoute:
    def test_simple_task_uses_local_model(self, router):
        decision = router.route("classify this email as spam or not spam")
        assert decision.complexity == "simple"
        assert decision.recommended_provider == "ollama"

    def test_medium_task_uses_haiku(self, router):
        decision = router.route("summarize this document in 3 bullet points")
        assert decision.complexity == "medium"
        assert "haiku" in decision.recommended_model.lower()

    def test_complex_task_uses_sonnet(self, router):
        decision = router.route("analyze and compare these two system architectures")
        assert decision.complexity == "complex"
        assert "sonnet" in decision.recommended_model.lower()

    def test_high_risk_task_uses_opus(self, router):
        decision = router.route("provide medical diagnosis recommendation")
        assert decision.complexity == "high_risk"
        assert "opus" in decision.recommended_model.lower()

    def test_maximum_quality_overrides_complexity(self, router):
        decision = router.route("classify spam", quality_requirement="maximum")
        assert decision.complexity == "high_risk"

    def test_cheapest_forces_simple(self, router):
        decision = router.route("complex reasoning task", quality_requirement="cheapest")
        assert decision.complexity == "simple"

    def test_decision_has_reasoning(self, router):
        decision = router.route("summarize this article")
        assert len(decision.reasoning) > 20

    def test_decision_has_savings(self, router):
        decision = router.route("summarize this article")
        assert decision.estimated_savings_vs_gpt4o >= 0.0

    def test_decision_to_dict(self, router):
        decision = router.route("classify this text")
        d = decision.to_dict()
        assert "complexity" in d
        assert "recommended_model" in d
        assert "reasoning" in d
        assert "estimated_cost_per_1k_tokens_usd" in d

    def test_alternative_model_present(self, router):
        decision = router.route("generate a short story")
        assert decision.alternative_provider
        assert decision.alternative_model

    def test_batch_route(self, router):
        tasks = [
            "classify this email",
            "summarize this report",
            "analyze and reason about this dataset",
        ]
        decisions = router.batch_route(tasks)
        assert len(decisions) == 3
        complexities = [d.complexity for d in decisions]
        assert "simple" in complexities
        assert "medium" in complexities


class TestProviderComparison:
    def test_returns_list(self, router):
        rows = router.provider_comparison()
        assert isinstance(rows, list)
        assert len(rows) > 5

    def test_sorted_by_cost(self, router):
        rows = router.provider_comparison()
        costs = [r["avg_cost_per_1m"] for r in rows]
        assert costs == sorted(costs)

    def test_local_models_free(self, router):
        rows = router.provider_comparison()
        local = [r for r in rows if r["is_local"]]
        assert all(r["avg_cost_per_1m"] == 0.0 for r in local)

    def test_row_schema(self, router):
        rows = router.provider_comparison()
        row = rows[0]
        assert "key" in row
        assert "provider" in row
        assert "model" in row
        assert "avg_cost_per_1m" in row
