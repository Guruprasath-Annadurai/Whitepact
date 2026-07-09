"""Data models for Cost Intelligence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class ModelPricing:
    provider: str
    model: str
    input_cost_per_million: float   # USD per 1M input tokens
    output_cost_per_million: float  # USD per 1M output tokens
    is_local: bool = False

    def cost_for(self, input_tokens: int, output_tokens: int) -> float:
        if self.is_local:
            return 0.0
        return (
            input_tokens / 1_000_000 * self.input_cost_per_million
            + output_tokens / 1_000_000 * self.output_cost_per_million
        )


# Pricing as of July 2026 (USD per 1M tokens)
MODEL_CATALOG: dict[str, ModelPricing] = {
    # OpenAI
    "openai/gpt-4o":              ModelPricing("openai",     "gpt-4o",              2.50,   10.00),
    "openai/gpt-4o-mini":         ModelPricing("openai",     "gpt-4o-mini",         0.15,    0.60),
    "openai/gpt-4-turbo":         ModelPricing("openai",     "gpt-4-turbo",        10.00,   30.00),
    "openai/gpt-3.5-turbo":       ModelPricing("openai",     "gpt-3.5-turbo",       0.50,    1.50),
    # Anthropic
    "anthropic/claude-opus-4":    ModelPricing("anthropic",  "claude-opus-4",      15.00,   75.00),
    "anthropic/claude-sonnet-4":  ModelPricing("anthropic",  "claude-sonnet-4",     3.00,   15.00),
    "anthropic/claude-haiku-4":   ModelPricing("anthropic",  "claude-haiku-4",      0.80,    4.00),
    # Google
    "google/gemini-1.5-pro":      ModelPricing("google",     "gemini-1.5-pro",      3.50,   10.50),
    "google/gemini-1.5-flash":    ModelPricing("google",     "gemini-1.5-flash",    0.075,   0.30),
    # Mistral
    "mistral/mistral-large":      ModelPricing("mistral",    "mistral-large",       2.00,    6.00),
    "mistral/mistral-small":      ModelPricing("mistral",    "mistral-small",       0.20,    0.60),
    "mistral/mistral-7b":         ModelPricing("mistral",    "mistral-7b",          0.08,    0.25),
    # Cohere
    "cohere/command-r-plus":      ModelPricing("cohere",     "command-r-plus",      3.00,   15.00),
    "cohere/command-r":           ModelPricing("cohere",     "command-r",           0.50,    1.50),
    # Local / self-hosted (zero cost)
    "ollama/llama3.2":            ModelPricing("ollama",     "llama3.2",            0.0,     0.0,  True),
    "ollama/mistral":             ModelPricing("ollama",     "mistral",             0.0,     0.0,  True),
    "ollama/phi3":                ModelPricing("ollama",     "phi3",                0.0,     0.0,  True),
    "ollama/gemma2":              ModelPricing("ollama",     "gemma2",              0.0,     0.0,  True),
}

_UNKNOWN_PRICING = ModelPricing("unknown", "unknown", 0.0, 0.0)


def get_pricing(provider: str, model: str) -> ModelPricing:
    key = f"{provider.lower()}/{model.lower()}"
    if key in MODEL_CATALOG:
        return MODEL_CATALOG[key]
    # Provider-level fallback
    for catalog_key, pricing in MODEL_CATALOG.items():
        if catalog_key.startswith(f"{provider.lower()}/"):
            return pricing
    return _UNKNOWN_PRICING


@dataclass
class TokenUsage:
    """A single LLM API call's token consumption."""

    request_id: str
    provider: str
    model: str
    input_tokens: int
    output_tokens: int
    cached_tokens: int = 0
    timestamp: datetime = field(default_factory=lambda: datetime.now(UTC))
    team: str = "default"
    application: str = "default"
    prompt_hash: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    org_id: str | None = None

    @classmethod
    def create(
        cls,
        provider: str,
        model: str,
        input_tokens: int,
        output_tokens: int,
        prompt: str = "",
        cached_tokens: int = 0,
        team: str = "default",
        application: str = "default",
        metadata: dict[str, Any] | None = None,
        org_id: str | None = None,
    ) -> TokenUsage:
        import uuid
        prompt_hash = hashlib.sha256(prompt.encode()).hexdigest()[:16] if prompt else ""
        return cls(
            request_id=str(uuid.uuid4()),
            provider=provider,
            model=model,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            cached_tokens=cached_tokens,
            team=team,
            application=application,
            prompt_hash=prompt_hash,
            metadata=metadata or {},
            org_id=org_id,
        )

    @property
    def total_tokens(self) -> int:
        return self.input_tokens + self.output_tokens


@dataclass(frozen=True)
class CostRecord:
    """Computed cost for a single TokenUsage."""

    usage: TokenUsage
    pricing: ModelPricing
    input_cost: float
    output_cost: float
    total_cost: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "request_id": self.usage.request_id,
            "provider": self.usage.provider,
            "model": self.usage.model,
            "team": self.usage.team,
            "application": self.usage.application,
            "input_tokens": self.usage.input_tokens,
            "output_tokens": self.usage.output_tokens,
            "total_tokens": self.usage.total_tokens,
            "input_cost_usd": round(self.input_cost, 6),
            "output_cost_usd": round(self.output_cost, 6),
            "total_cost_usd": round(self.total_cost, 6),
            "timestamp": self.usage.timestamp.isoformat(),
        }


@dataclass
class BudgetPolicy:
    """Monthly budget limits and alert thresholds."""

    monthly_limit_usd: float = 10_000.0
    team_limits: dict[str, float] = field(default_factory=dict)
    model_limits: dict[str, float] = field(default_factory=dict)
    alert_threshold_pct: float = 0.80

    def to_dict(self) -> dict[str, Any]:
        return {
            "monthly_limit_usd": self.monthly_limit_usd,
            "team_limits": self.team_limits,
            "model_limits": self.model_limits,
            "alert_threshold_pct": self.alert_threshold_pct,
        }


@dataclass
class BudgetStatus:
    """Current budget consumption state."""

    total_spent_usd: float
    monthly_limit_usd: float
    percentage_used: float
    is_exceeded: bool
    alert_triggered: bool
    team_breakdown: dict[str, float]
    model_breakdown: dict[str, float]

    def to_dict(self) -> dict[str, Any]:
        return {
            "total_spent_usd": round(self.total_spent_usd, 4),
            "monthly_limit_usd": self.monthly_limit_usd,
            "percentage_used": round(self.percentage_used, 2),
            "is_exceeded": self.is_exceeded,
            "alert_triggered": self.alert_triggered,
            "team_breakdown": {k: round(v, 4) for k, v in self.team_breakdown.items()},
            "model_breakdown": {k: round(v, 4) for k, v in self.model_breakdown.items()},
        }


@dataclass(frozen=True)
class WasteFinding:
    category: str          # duplicate_request / model_overkill / prompt_bloat / verbose_response
    severity: str          # low / medium / high
    description: str
    estimated_savings_usd: float
    recommendation: str


@dataclass
class PromptEfficiencyResult:
    original_tokens: int
    estimated_optimized_tokens: int
    reduction_pct: float
    estimated_monthly_savings_usd: float
    waste_findings: list[WasteFinding]
    efficiency_score: float    # 0-100

    def to_dict(self) -> dict[str, Any]:
        return {
            "original_tokens": self.original_tokens,
            "estimated_optimized_tokens": self.estimated_optimized_tokens,
            "reduction_pct": round(self.reduction_pct, 1),
            "estimated_monthly_savings_usd": round(self.estimated_monthly_savings_usd, 2),
            "efficiency_score": round(self.efficiency_score, 1),
            "waste_findings": [
                {
                    "category": f.category,
                    "severity": f.severity,
                    "description": f.description,
                    "savings_usd": round(f.estimated_savings_usd, 4),
                    "recommendation": f.recommendation,
                }
                for f in self.waste_findings
            ],
        }


@dataclass(frozen=True)
class RoutingDecision:
    task_description: str
    complexity: str                 # simple / medium / complex / high_risk
    recommended_provider: str
    recommended_model: str
    alternative_provider: str
    alternative_model: str
    estimated_cost_usd: float       # per 1K tokens
    estimated_savings_vs_gpt4o: float  # USD per 1K tokens
    reasoning: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "complexity": self.complexity,
            "recommended_model": f"{self.recommended_provider}/{self.recommended_model}",
            "alternative_model": f"{self.alternative_provider}/{self.alternative_model}",
            "estimated_cost_per_1k_tokens_usd": round(self.estimated_cost_usd, 6),
            "estimated_savings_vs_gpt4o_usd": round(self.estimated_savings_vs_gpt4o, 6),
            "reasoning": self.reasoning,
        }
