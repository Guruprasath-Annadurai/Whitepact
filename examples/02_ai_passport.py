"""
Example 02 — AI Passport Generator
Run: python examples/02_ai_passport.py
"""

from responsibleai.trust.passport import PassportGenerator
from responsibleai.trust.score import TrustScoreEngine

engine = TrustScoreEngine()
gen = PassportGenerator()

score = engine.compute(
    fairness=0.88,
    privacy=0.91,
    security=0.85,
    robustness=0.87,
    compliance=0.93,
    authenticity=0.90,
)

passport = gen.generate(
    model_name="claude-sonnet-4",
    provider="anthropic",
    trust_score=score,
    bias_summary={"gender_divergence": 0.04, "racial_divergence": 0.06, "probes_run": 6},
    hallucination_summary={"risk": 0.12, "level": "LOW"},
    security_summary={"attacks_passed": 9, "attacks_total": 10, "security_score": 0.90},
    compliance_summary={"nist_score": 0.91, "eu_ai_act_tier": "MINIMAL", "iso_score": 0.88},
    privacy_summary={"epsilon": 0.5, "delta": 1e-6, "mechanism": "gaussian"},
)

print("\n" + "=" * 60)
print("  AI PASSPORT — Verifiable Trust Certificate")
print("=" * 60)
print(f"  Passport ID : {passport.passport_id}")
print(f"  Model       : {passport.model_name} ({passport.provider})")
print(f"  Trust Score : {passport.trust_score.overall:.1f} / 100  [{passport.trust_score.grade}]")
print(f"  Risk Level  : {passport.trust_score.risk_level}")
print(f"  Generated   : {passport.generated_at.strftime('%Y-%m-%d %H:%M UTC')}")
print(f"  Verified    : {passport.verify()}")
print(f"  Hash        : {passport.verification_hash[:32]}...")
print("=" * 60)

out_path = "examples/output/passport_sample.json"
with open(out_path, "w") as f:
    f.write(passport.to_json(indent=2))
print(f"\n  JSON written to: {out_path}")

html_path = "examples/output/passport_sample.html"
with open(html_path, "w") as f:
    f.write(passport.to_html())
print(f"  HTML written to: {html_path}\n")
