"""
Example 04 — Compliance Engine (NIST AI RMF, EU AI Act, ISO 42001)
Run: python examples/04_compliance.py
"""

from responsibleai.compliance.engine import ComplianceEngine, Framework, ComplianceStatus

engine = ComplianceEngine()

scenarios = [
    ("General chatbot",    "chatbot",    dict(fairness_score=0.85, privacy_score=0.80, security_score=0.88, robustness_score=0.82, compliance_maturity=0.90)),
    ("Medical AI",         "medical",    dict(fairness_score=0.91, privacy_score=0.95, security_score=0.93, robustness_score=0.90, compliance_maturity=0.92)),
    ("HR recruitment AI",  "employment", dict(fairness_score=0.72, privacy_score=0.78, security_score=0.75, robustness_score=0.70, compliance_maturity=0.65)),
    ("Low-risk assistant", "general",   dict(fairness_score=0.60, privacy_score=0.65, security_score=0.70, robustness_score=0.68, compliance_maturity=0.60)),
]

print("\n" + "=" * 68)
print("  COMPLIANCE REPORT — ResponsibleAI v0.4.0")
print("=" * 68)

for label, use_case, scores in scenarios:
    report = engine.evaluate(use_case=use_case, **scores)
    overall_pct = report.compliance_score * 100
    bar_len = int(overall_pct / 100 * 25)
    bar = "█" * bar_len + "░" * (25 - bar_len)
    tier = report.eu_ai_act_tier.value if report.eu_ai_act_tier else "N/A"
    print(f"\n  {label}")
    print(f"  [{bar}] {overall_pct:.1f}/100  EU AI Act: {tier}")
    print(f"  Status: {report.overall_status.value}  Violations: {len(report.violations)}  Warnings: {len(report.warnings)}")

    non_compliant = [f for f in report.findings if f.status == ComplianceStatus.NON_COMPLIANT]
    if non_compliant:
        print(f"  Non-compliant controls ({len(non_compliant)}):")
        for f in non_compliant[:3]:
            print(f"    ✗ [{f.framework}] {f.control_id}: {f.control_name[:55]}")

print("\n  Multi-framework breakdown:")
report = engine.evaluate(
    fairness_score=0.88, privacy_score=0.90, security_score=0.85,
    robustness_score=0.87, compliance_maturity=0.91, use_case="general",
    frameworks=[Framework.NIST_AI_RMF, Framework.ISO_42001, Framework.EU_AI_ACT],
)
for fw in report.frameworks:
    fw_findings = [f for f in report.findings if f.framework == fw.value]
    fw_score = sum(f.score for f in fw_findings) / len(fw_findings) * 100 if fw_findings else 0
    print(f"    {fw.value:20s} : {fw_score:.1f}/100  ({len(fw_findings)} controls)")

print("\n" + "=" * 68 + "\n")
