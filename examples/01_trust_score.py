"""
Example 01 — Trust Score Engine
Run: python examples/01_trust_score.py
"""

from responsibleai.trust.score import TrustScoreEngine

engine = TrustScoreEngine()

models = [
    ("GPT-4o",         "openai",    dict(fairness=0.82, privacy=0.75, security=0.88, robustness=0.79, compliance=0.91, authenticity=0.84)),
    ("Claude Sonnet",  "anthropic", dict(fairness=0.91, privacy=0.88, security=0.90, robustness=0.85, compliance=0.94, authenticity=0.93)),
    ("Mistral Large",  "mistral",   dict(fairness=0.74, privacy=0.70, security=0.76, robustness=0.72, compliance=0.78, authenticity=0.80)),
    ("Llama 3.2",      "ollama",    dict(fairness=0.65, privacy=0.60, security=0.62, robustness=0.68, compliance=0.55, authenticity=0.70)),
]

print("\n" + "=" * 62)
print("  TRUST SCORE REPORT — ResponsibleAI v1.1.0")
print("=" * 62)

for model_name, provider, dims in models:
    score = engine.compute(**dims)
    bar_len = int(score.overall / 100 * 30)
    bar = "█" * bar_len + "░" * (30 - bar_len)
    status = "PASS" if score.passed else "FAIL"
    print(f"\n  {model_name} ({provider})")
    print(f"  [{bar}] {score.overall:.1f}/100  Grade: {score.grade}  Risk: {score.risk_level}  [{status}]")
    print(f"  Fairness:{dims['fairness']*100:.0f}  Privacy:{dims['privacy']*100:.0f}  "
          f"Security:{dims['security']*100:.0f}  Robustness:{dims['robustness']*100:.0f}  "
          f"Compliance:{dims['compliance']*100:.0f}  Authenticity:{dims['authenticity']*100:.0f}")

print("\n" + "=" * 62)
print("  Dimensions weighted: Fairness 20% | Privacy 15% | Security 20%")
print("  | Robustness 15% | Compliance 20% | Authenticity 10%")
print("=" * 62 + "\n")
