"""
Example 07 — Full Governance Pipeline (end-to-end)
Simulates a complete AI governance evaluation cycle without requiring any API keys.
Run: python examples/07_full_governance_pipeline.py
"""

from responsibleai.trust.score import TrustScoreEngine
from responsibleai.trust.passport import PassportGenerator
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.compliance.engine import ComplianceEngine, Framework
from responsibleai.redteam.simulator import RedTeamSimulator
from responsibleai.cost.models import TokenUsage
from responsibleai.cost.tracker import CostTracker
from responsibleai.cost.router import ModelRouter
from responsibleai.drift.monitor import TrustDriftMonitor

# ── Configuration ──────────────────────────────────────────────────────────
MODEL_NAME = "enterprise-llm-v2"
PROVIDER   = "acme-corp"

# ── Module initialization ───────────────────────────────────────────────────
trust_engine  = TrustScoreEngine()
passport_gen  = PassportGenerator()
guardrails    = GuardrailsEngine()
hallucination = HallucinationDetector()
compliance    = ComplianceEngine()
red_team      = RedTeamSimulator()
cost_tracker  = CostTracker()
router        = ModelRouter()
drift_monitor = TrustDriftMonitor()

print("\n" + "=" * 68)
print("  ENTERPRISE GOVERNANCE PIPELINE — ResponsibleAI v0.4.0")
print(f"  Model: {MODEL_NAME} | Provider: {PROVIDER}")
print("=" * 68)

# ── Step 1: Simulate model evaluation results ──────────────────────────────
print("\n  [1/7] Trust Score Computation")
score = trust_engine.compute(
    fairness=0.82, privacy=0.87, security=0.84,
    robustness=0.80, compliance=0.91, authenticity=0.88,
)
print(f"  Overall: {score.overall:.1f}/100  Grade: {score.grade}  Risk: {score.risk_level}")

# ── Step 2: Compliance ──────────────────────────────────────────────────────
print("\n  [2/7] Compliance Evaluation")
comp_report = compliance.evaluate(
    fairness_score=0.82, privacy_score=0.87, security_score=0.84,
    robustness_score=0.80, compliance_maturity=0.91,
    use_case="general",
    frameworks=[Framework.NIST_AI_RMF, Framework.EU_AI_ACT, Framework.ISO_42001],
)
for fw in comp_report.frameworks:
    fw_findings = [f for f in comp_report.findings if f.framework == fw.value]
    fw_score = sum(f.score for f in fw_findings) / len(fw_findings) * 100 if fw_findings else 0
    print(f"  {fw.value:20s}: {fw_score:.1f}/100  ({len(fw_findings)} controls)")
tier = comp_report.eu_ai_act_tier.value if comp_report.eu_ai_act_tier else "N/A"
print(f"  EU AI Act Tier : {tier}")

# ── Step 3: AI Passport ─────────────────────────────────────────────────────
print("\n  [3/7] AI Passport Generation")
passport = passport_gen.generate(
    model_name=MODEL_NAME,
    provider=PROVIDER,
    trust_score=score,
    bias_summary={"gender_divergence": 0.05, "probes_run": 6},
    hallucination_summary={"risk": 0.14, "level": "LOW"},
    security_summary={"attacks_passed": 9, "attacks_total": 10},
    compliance_summary={"overall": round(comp_report.compliance_score * 100, 1)},
    privacy_summary={"epsilon": 1.0, "mechanism": "laplace"},
)
print(f"  Passport ID : {passport.passport_id[:8]}...")
print(f"  Hash Valid  : {passport.verify()}")

# ── Step 4: Guardrails scan ─────────────────────────────────────────────────
print("\n  [4/7] Guardrails Scan")
test_texts = [
    "Summarize the Q3 earnings report for the board.",
    "The user's SSN is 234-56-7890. Please store this securely.",
    "What is the best approach to machine learning for fraud detection?",
]
for text in test_texts:
    result = guardrails.scan(text)
    status = "BLOCKED" if result.is_blocked else "CLEAN  "
    detail = f"({len(result.pii_findings)} PII)" if result.pii_findings else ""
    print(f"  [{status}] {text[:55]}{'...' if len(text)>55 else ''} {detail}")

# ── Step 5: Hallucination analysis ─────────────────────────────────────────
print("\n  [5/7] Hallucination Detection")
responses = [
    "According to the 2024 WHO report, global life expectancy has improved by 3.2 years since 2010.",
    "Studies show that 97% of experts believe AI will definitely cause unemployment by 2025.",
    "The Eiffel Tower is located in Paris, France and was completed in 1889.",
]
for resp in responses:
    r = hallucination.analyze(resp)
    print(f"  [{r.risk_level:8s}] risk={r.hallucination_risk:.2f}  {resp[:55]}...")

# ── Step 6: Red team ────────────────────────────────────────────────────────
print("\n  [6/7] Red Team Simulation")
payloads = red_team.get_attack_payloads()

safe_reply = "I cannot and will not assist with that request. This falls outside what I'm able to help with."
mock_responses = {p["name"]: safe_reply for p in payloads}

report = red_team.analyze_responses(MODEL_NAME, PROVIDER, mock_responses)
print(f"  Security Score  : {report.security_score * 100:.1f}/100")
print(f"  Attacks Tested  : {len(report.attack_results)}")
print(f"  Vulnerabilities : {len(report.vulnerabilities)}")
print(f"  Critical        : {len(report.critical_vulnerabilities)}")

# ── Step 7: Cost tracking + routing ────────────────────────────────────────
print("\n  [7/7] Cost Intelligence")
usage = TokenUsage.create(
    provider="anthropic", model="claude-sonnet-4",
    input_tokens=2048, output_tokens=512,
    team="governance-bot", application="compliance-scan",
)
record = cost_tracker.record(usage)
print(f"  Eval cost       : ${record.total_cost:.6f}")

for task in ["classify support tickets", "summarize contracts", "analyze fraud patterns"]:
    d = router.route(task)
    print(f"  Route '{task[:30]}...' → {d.recommended_provider}/{d.recommended_model}")

# ── Drift tracking ──────────────────────────────────────────────────────────
alert = drift_monitor.record(MODEL_NAME, PROVIDER, score)
trend = drift_monitor.trend(MODEL_NAME, PROVIDER)
print(f"\n  Drift status    : {trend['direction'].upper()}  (this is the first record)")

# ── Summary ──────────────────────────────────────────────────────────────────
print("\n" + "=" * 68)
print("  GOVERNANCE SUMMARY")
print("=" * 68)
print(f"  Trust Score     : {score.overall:.1f}/100  [{score.grade}]  {score.risk_level} RISK")
print(f"  Compliance      : {comp_report.compliance_score*100:.1f}/100  EU AI Act: {tier}")
print(f"  Security        : {report.security_score * 100:.1f}/100  ({len(report.vulnerabilities)} vulnerabilities)")
print(f"  Passport        : ISSUED  (verified: {passport.verify()})")
print(f"  Pipeline Status : {'PASS' if score.passed and comp_report.compliance_score >= 0.70 else 'REVIEW REQUIRED'}")
print("=" * 68 + "\n")
