"""
Example 05 — Cost Intelligence (Tracker + Analyzer + Router)
Run: python examples/05_cost_intelligence.py
"""

import random
from responsibleai.cost.models import TokenUsage
from responsibleai.cost.tracker import CostTracker
from responsibleai.cost.analyzer import CostAnalyzer
from responsibleai.cost.router import ModelRouter

tracker = CostTracker()
analyzer = CostAnalyzer()
router = ModelRouter()

# Simulate 30 days of AI usage across teams
teams = ["ml-team", "product", "data-science"]
model_mix = [
    ("openai",    "gpt-4o",           0.3),
    ("openai",    "gpt-4o-mini",      0.4),
    ("anthropic", "claude-haiku-4",   0.2),
    ("anthropic", "claude-sonnet-4",  0.1),
]

random.seed(42)
for _ in range(500):
    r = random.random()
    cumulative = 0.0
    for provider, model, weight in model_mix:
        cumulative += weight
        if r <= cumulative:
            break
    tracker.record(TokenUsage.create(
        provider=provider, model=model,
        input_tokens=random.randint(200, 4000),
        output_tokens=random.randint(100, 1200),
        team=random.choice(teams),
    ))

print("\n" + "=" * 60)
print("  COST INTELLIGENCE REPORT — ResponsibleAI v0.4.0")
print("=" * 60)

summary = tracker.monthly_summary()
print(f"\n  Monthly Summary")
print(f"  Total Cost    : ${summary['total_cost_usd']:.4f}")
print(f"  Total Tokens  : {summary['total_tokens']:,}")
print(f"  Requests      : {summary['total_requests']:,}")
print(f"  Distinct Models: {summary['distinct_models']}")

print(f"\n  Model Breakdown")
for model_key, cost in summary["model_breakdown"].items():
    bar = "█" * max(1, int(cost / max(summary["model_breakdown"].values()) * 20))
    print(f"  {model_key:35s} {bar:20s} ${cost:.4f}")

print(f"\n  Team Breakdown")
for team, cost in summary["team_breakdown"].items():
    print(f"  {team:20s} ${cost:.4f}")

budget = tracker.check_budget()
pct = budget.percentage_used
status = "OVER BUDGET" if budget.is_exceeded else ("WARNING" if budget.alert_triggered else "OK")
print(f"\n  Budget Status : {status} ({pct:.1f}% of ${budget.monthly_limit_usd:,.0f}/mo)")

# Prompt efficiency
print(f"\n  Prompt Efficiency Analysis")
bloated = (
    "Please note that as an AI language model, I want you to be aware that "
    "you should summarize the following text. It is important to note that "
    "firstly, secondly, and thirdly you must be concise in your response. "
    "In conclusion, it is clear that brevity is key."
)
result = analyzer.analyze_prompt_efficiency(
    prompt=bloated, provider="openai", model="gpt-4o", monthly_requests=50_000
)
print(f"  Efficiency Score  : {result.efficiency_score:.1f}/100")
print(f"  Token reduction   : {result.original_tokens} → {result.estimated_optimized_tokens} tokens")
print(f"  Monthly savings   : ${result.estimated_monthly_savings_usd:.2f}")
for f in result.waste_findings:
    print(f"  [{f.severity.upper():6s}] {f.category}: {f.description[:55]}")

# Routing
print(f"\n  Model Router Recommendations")
tasks = [
    "Classify this support ticket as billing, technical, or general",
    "Summarize this 20-page contract into key clauses",
    "Analyze churn trends and design a retention strategy",
    "Review medical diagnosis notes for compliance",
]
for task in tasks:
    d = router.route(task)
    savings_pct = round(d.estimated_savings_vs_gpt4o / max(d.estimated_cost_usd + d.estimated_savings_vs_gpt4o, 0.0001) * 100)
    print(f"  [{d.complexity:9s}] {d.recommended_provider}/{d.recommended_model:20s} saves ~{savings_pct}% vs GPT-4o")

print("\n" + "=" * 60 + "\n")
