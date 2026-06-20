"""Cost waste detection and prompt efficiency analysis."""

from __future__ import annotations

import re
from typing import Any

from responsibleai.cost.models import (
    MODEL_CATALOG,
    ModelPricing,
    PromptEfficiencyResult,
    WasteFinding,
    get_pricing,
)

_BLOAT_PATTERNS = [
    (r"(please\s+)?(?:note that|be aware that|keep in mind that)", "filler_preamble"),
    (r"as an? (?:ai|language model|llm|assistant)", "model_identity_disclaimer"),
    (r"i (?:want|need|would like) you to", "verbose_instruction_prefix"),
    (r"(?:first|firstly),?\s+(?:second|secondly),?\s+(?:third|thirdly)", "enumeration_overhead"),
    (r"in\s+(?:conclusion|summary),?\s+(?:it is|we can)\s+(?:clear|see)", "redundant_conclusion"),
    (r"(?:it is|it's)\s+(?:important|crucial|essential|vital)\s+to\s+(?:note|mention|remember)", "emphasis_filler"),
]

_COMPILED_BLOAT = [(re.compile(p, re.IGNORECASE), tag) for p, tag in _BLOAT_PATTERNS]

# Complexity signals for task categorisation
_SIMPLE_SIGNALS = frozenset([
    "classify", "yes or no", "true or false", "extract", "list",
    "translate", "correct", "fix grammar", "format", "convert",
])
_MEDIUM_SIGNALS = frozenset([
    "summarize", "summarise", "rewrite", "paraphrase", "explain briefly",
    "describe", "generate", "draft",
])
_COMPLEX_SIGNALS = frozenset([
    "analyze", "analyse", "reason", "compare", "evaluate", "design",
    "architect", "debug", "optimize", "research", "strategy",
])
_HIGH_RISK_SIGNALS = frozenset([
    "medical", "diagnosis", "legal", "financial advice", "clinical",
    "compliance", "audit", "safety critical", "regulated",
])


def classify_task_complexity(task: str) -> str:
    t = task.lower()
    if any(sig in t for sig in _HIGH_RISK_SIGNALS):
        return "high_risk"
    if any(sig in t for sig in _COMPLEX_SIGNALS):
        return "complex"
    if any(sig in t for sig in _MEDIUM_SIGNALS):
        return "medium"
    return "simple"


_TIER_RECOMMENDATIONS: dict[str, tuple[str, str, str, str]] = {
    # complexity → (provider, model, alt_provider, alt_model)
    "simple":    ("ollama",     "llama3.2",       "openai",    "gpt-4o-mini"),
    "medium":    ("anthropic",  "claude-haiku-4", "openai",    "gpt-4o-mini"),
    "complex":   ("anthropic",  "claude-sonnet-4","openai",    "gpt-4o"),
    "high_risk": ("anthropic",  "claude-opus-4",  "openai",    "gpt-4o"),
}

_GPT4O_PRICING = MODEL_CATALOG["openai/gpt-4o"]


class CostAnalyzer:
    """
    Detect waste and inefficiency in AI spending.

    Analyses prompt text for bloat patterns, detects model overkill,
    and produces actionable savings recommendations.
    """

    def analyze_prompt_efficiency(
        self,
        prompt: str,
        response: str = "",
        provider: str = "openai",
        model: str = "gpt-4o",
        monthly_requests: int = 10_000,
    ) -> PromptEfficiencyResult:
        """
        Analyse a prompt for token waste and estimate savings potential.

        Parameters
        ----------
        prompt : str
            The prompt text to analyse.
        response : str
            Optional response text to include in the output analysis.
        provider / model : str
            The model being used (for cost calculations).
        monthly_requests : int
            Estimated monthly volume (for extrapolated savings).
        """
        pricing = get_pricing(provider, model)
        findings: list[WasteFinding] = []

        tokens = _estimate_tokens(prompt)
        resp_tokens = _estimate_tokens(response)

        # Bloat detection
        for pattern, tag in _COMPILED_BLOAT:
            matches = pattern.findall(prompt)
            if matches:
                bloat_tokens = sum(len(m.split()) for m in matches) * 1.3
                cost_per_request = pricing.cost_for(int(bloat_tokens), 0)
                monthly_savings = cost_per_request * monthly_requests
                findings.append(WasteFinding(
                    category="prompt_bloat",
                    severity="low",
                    description=f"Filler phrase detected ({tag}): '{matches[0][:60]}'",
                    estimated_savings_usd=monthly_savings,
                    recommendation=f"Remove filler pattern '{tag}'. Saves ~{int(bloat_tokens)} tokens per request.",
                ))

        # Model overkill check
        if not pricing.is_local:
            cheaper = _find_cheaper_model(provider, model)
            if cheaper and cheaper.input_cost_per_million < pricing.input_cost_per_million * 0.5:
                savings_per_req = pricing.cost_for(tokens, resp_tokens) - cheaper.cost_for(tokens, resp_tokens)
                monthly_savings = savings_per_req * monthly_requests
                findings.append(WasteFinding(
                    category="model_overkill",
                    severity="medium" if savings_per_req * 12 * monthly_requests > 100 else "low",
                    description=(
                        f"Current model ({provider}/{model}) costs "
                        f"${pricing.input_cost_per_million:.2f}/1M input tokens. "
                        f"{cheaper.provider}/{cheaper.model} costs "
                        f"${cheaper.input_cost_per_million:.2f}/1M."
                    ),
                    estimated_savings_usd=monthly_savings,
                    recommendation=(
                        f"Consider {cheaper.provider}/{cheaper.model} for routine tasks. "
                        f"Estimated annual savings: ${monthly_savings * 12:,.0f}."
                    ),
                ))

        # Verbose response check (output/input ratio)
        if resp_tokens > 0 and tokens > 0:
            ratio = resp_tokens / tokens
            if ratio > 3.0:
                excess = int(resp_tokens - tokens * 1.5)
                cost_per_req = pricing.cost_for(0, excess)
                findings.append(WasteFinding(
                    category="verbose_response",
                    severity="medium" if ratio > 5 else "low",
                    description=(
                        f"Response is {ratio:.1f}x longer than the prompt. "
                        f"Approximately {excess} tokens may be unnecessary."
                    ),
                    estimated_savings_usd=cost_per_req * monthly_requests,
                    recommendation=(
                        "Add 'Be concise' or set max_tokens to cap response length. "
                        "Reduces output costs significantly at scale."
                    ),
                ))

        optimized_tokens = max(int(tokens * 0.75), tokens - sum(
            int(f.estimated_savings_usd / pricing.cost_for(1, 0)) if pricing.cost_for(1, 0) > 0 else 10
            for f in findings if f.category == "prompt_bloat"
        ))
        reduction_pct = (1 - optimized_tokens / tokens) * 100 if tokens > 0 else 0.0
        total_monthly_savings = sum(f.estimated_savings_usd for f in findings)
        efficiency_score = max(0.0, 100.0 - len(findings) * 10 - reduction_pct * 0.5)

        return PromptEfficiencyResult(
            original_tokens=tokens,
            estimated_optimized_tokens=optimized_tokens,
            reduction_pct=round(reduction_pct, 1),
            estimated_monthly_savings_usd=round(total_monthly_savings, 2),
            waste_findings=findings,
            efficiency_score=round(efficiency_score, 1),
        )

    def governance_score(
        self,
        total_cost_usd: float,
        monthly_limit_usd: float,
        distinct_models: int,
        waste_pct: float,
    ) -> dict[str, Any]:
        """Compute a FinOps governance score (0-100)."""
        budget_score = max(0.0, 100.0 - max(0, total_cost_usd - monthly_limit_usd) / monthly_limit_usd * 100)
        diversity_score = min(100.0, distinct_models / 3 * 50)  # using 3+ models = diverse
        efficiency_score = max(0.0, 100.0 - waste_pct)
        overall = (budget_score * 0.40 + efficiency_score * 0.40 + diversity_score * 0.20)
        grade = "A" if overall >= 90 else "B" if overall >= 80 else "C" if overall >= 70 else "D" if overall >= 60 else "F"
        return {
            "governance_score": round(overall, 1),
            "grade": grade,
            "budget_compliance": round(budget_score, 1),
            "efficiency": round(efficiency_score, 1),
            "model_diversity": round(diversity_score, 1),
        }


def _estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token for English text."""
    return max(1, len(text) // 4)


def _find_cheaper_model(provider: str, model: str) -> ModelPricing | None:
    current = get_pricing(provider, model)
    candidates = [
        p for p in MODEL_CATALOG.values()
        if not p.is_local
        and p.input_cost_per_million < current.input_cost_per_million * 0.5
        and f"{p.provider}/{p.model}" != f"{provider}/{model}"
    ]
    if not candidates:
        return None
    return min(candidates, key=lambda p: p.input_cost_per_million)
