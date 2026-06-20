"""Intelligent model router — cheapest acceptable model for a given task."""

from __future__ import annotations

from responsibleai.cost.analyzer import classify_task_complexity, _TIER_RECOMMENDATIONS
from responsibleai.cost.models import MODEL_CATALOG, RoutingDecision, get_pricing

_GPT4O_1K_COST = (
    MODEL_CATALOG["openai/gpt-4o"].input_cost_per_million / 1_000
    + MODEL_CATALOG["openai/gpt-4o"].output_cost_per_million / 1_000
) / 2  # average of input+output per 1K tokens


_ROUTING_RATIONALE: dict[str, str] = {
    "simple": (
        "Simple classification or extraction tasks do not require frontier model reasoning. "
        "A local model (Ollama) costs $0 and is sufficient. "
        "GPT-4o-mini is the best cloud fallback at 97% lower cost than GPT-4o."
    ),
    "medium": (
        "Medium tasks (summarisation, translation, generation) need good instruction following "
        "but not frontier-level reasoning. Claude Haiku-4 delivers strong quality at "
        "84% lower cost than GPT-4o."
    ),
    "complex": (
        "Complex reasoning, analysis, or code generation tasks benefit from a capable model. "
        "Claude Sonnet-4 or GPT-4o balance capability and cost. "
        "40% savings vs GPT-4o without meaningful quality loss."
    ),
    "high_risk": (
        "High-risk tasks in regulated domains (medical, legal, financial) require maximum "
        "accuracy and should use the most capable available model. Add governance checks, "
        "hallucination detection, and compliance validation for every response."
    ),
}


class ModelRouter:
    """
    Recommend the cheapest acceptable model for a described task.

    Usage
    -----
    router = ModelRouter()
    decision = router.route("Classify this customer email as spam or not spam")
    print(decision.recommended_model)   # → ollama/llama3.2
    """

    def route(self, task_description: str, quality_requirement: str = "balanced") -> RoutingDecision:
        """
        Recommend a model for *task_description*.

        Parameters
        ----------
        task_description : str
            Natural language description of the task to route.
        quality_requirement : str
            "maximum" — always use the most capable model.
            "balanced" — optimize cost vs quality (default).
            "cheapest" — minimize cost, accept lower quality.
        """
        if quality_requirement == "maximum":
            complexity = "high_risk"
        elif quality_requirement == "cheapest":
            complexity = "simple"
        else:
            complexity = classify_task_complexity(task_description)

        provider, model, alt_provider, alt_model = _TIER_RECOMMENDATIONS[complexity]

        pricing = get_pricing(provider, model)
        avg_cost_per_1k = (
            pricing.input_cost_per_million / 1_000
            + pricing.output_cost_per_million / 1_000
        ) / 2

        gpt4o_cost_per_1k = _GPT4O_1K_COST
        savings = gpt4o_cost_per_1k - avg_cost_per_1k

        return RoutingDecision(
            task_description=task_description[:200],
            complexity=complexity,
            recommended_provider=provider,
            recommended_model=model,
            alternative_provider=alt_provider,
            alternative_model=alt_model,
            estimated_cost_usd=round(avg_cost_per_1k, 6),
            estimated_savings_vs_gpt4o=round(max(savings, 0.0), 6),
            reasoning=_ROUTING_RATIONALE[complexity],
        )

    def batch_route(self, tasks: list[str]) -> list[RoutingDecision]:
        return [self.route(t) for t in tasks]

    def provider_comparison(self) -> list[dict]:
        """Return a cost comparison across all tracked models."""
        rows = []
        for key, pricing in MODEL_CATALOG.items():
            avg = (pricing.input_cost_per_million + pricing.output_cost_per_million) / 2
            rows.append({
                "key": key,
                "provider": pricing.provider,
                "model": pricing.model,
                "input_cost_per_1m": pricing.input_cost_per_million,
                "output_cost_per_1m": pricing.output_cost_per_million,
                "avg_cost_per_1m": round(avg, 3),
                "is_local": pricing.is_local,
                "monthly_cost_at_1m_tokens": round(avg, 3),
            })
        return sorted(rows, key=lambda r: r["avg_cost_per_1m"])
