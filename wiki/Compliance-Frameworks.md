# Compliance Frameworks

ResponsibleAI evaluates AI systems against three major governance frameworks. The compliance engine is deterministic — the same inputs always produce the same outputs — making it suitable for auditable governance workflows.

---

## How compliance scoring works

The compliance engine accepts 5 numeric scores (0.0–1.0) and a `use_case` string. It maps these to framework controls, computes per-control status, and aggregates to an overall compliance score.

**Important:** The inputs are *self-assessed* scores that your team provides. The engine does not gather its own evidence — it applies a consistent, documented framework to scores you supply.

```python
from responsibleai import ComplianceEngine

engine = ComplianceEngine()
report = engine.evaluate(
    fairness_score=0.80,       # bias/fairness posture
    privacy_score=0.85,        # data privacy controls
    security_score=0.82,       # system security
    robustness_score=0.78,     # reliability / adversarial robustness
    compliance_maturity=0.90,  # internal governance maturity
    use_case="credit_scoring", # deployment context
)
```

---

## NIST AI RMF

The NIST AI Risk Management Framework organises AI risk across four functions:

| Function | Controls included |
|---|---|
| GOVERN | Risk policies, accountability structures, responsible deployment policies |
| MAP | Context categorisation, bias risk identification, impact assessment |
| MEASURE | Bias testing, performance monitoring, adversarial testing |
| MANAGE | Incident response, mitigation, continuous improvement |

**Score mapping:** Controls in the `fairness` dimension map to GOVERN/MAP; `security` maps to MEASURE adversarial controls; `compliance_maturity` maps to MANAGE controls.

**Status thresholds:**
- ≥ 0.80 → COMPLIANT
- 0.60–0.79 → PARTIALLY_COMPLIANT
- < 0.60 → NON_COMPLIANT

---

## EU AI Act

The EU AI Act classifies AI systems into four risk tiers based on use case and capability:

| Tier | Score range | Example use cases |
|---|---|---|
| UNACCEPTABLE | n/a | Social scoring, subliminal manipulation (prohibited) |
| HIGH | < 0.70 average | Credit scoring, hiring, medical diagnosis, law enforcement |
| LIMITED | 0.70–0.84 | Customer-facing chatbots, recommendation systems |
| MINIMAL | ≥ 0.85 | Spam filters, AI-generated content labels |

The `use_case` parameter adjusts the tier boundary. High-risk use cases (`credit_scoring`, `medical`, `hiring`, `law_enforcement`) apply stricter thresholds.

**Article controls evaluated:**
- Article 9 — Risk management system
- Article 10 — Data governance
- Article 13 — Transparency and provision of information
- Article 14 — Human oversight
- Article 15 — Accuracy, robustness, cybersecurity

---

## ISO 42001

ISO 42001 is an AI management system standard (similar to ISO 27001 for information security). Controls evaluated:

| Clause | Focus |
|---|---|
| 6.1 — Risk assessment | Identification and treatment of AI risks |
| 8.2 — Design and development | Requirements, fairness, safety |
| 8.4 — Deployment | Monitoring, incident management |
| 9.1 — Performance evaluation | Measurement, monitoring, analysis |
| 10.1 — Improvement | Nonconformity and corrective action |

---

## Reading the report

```python
print(f"Overall: {report.compliance_score * 100:.1f}%")
print(f"Status: {report.overall_status.value}")
print(f"EU AI Act tier: {report.eu_ai_act_tier.value}")
print(f"Violations: {len(report.violations)}")
print(f"Warnings: {len(report.warnings)}")

for finding in report.violations:
    print(f"  [{finding.control_id}] {finding.control_name}")
    print(f"    Recommendation: {finding.recommendation}")
```

---

## REST API

```bash
# Full multi-framework compliance report
curl -X POST http://localhost:8765/api/evaluate \
  -H "Authorization: Bearer your-key" \
  -H "Content-Type: application/json" \
  -d '{
    "model_name": "gpt-4o",
    "provider": "openai",
    "fairness": 0.80,
    "privacy": 0.85,
    "security": 0.82,
    "robustness": 0.78,
    "compliance": 0.90,
    "authenticity": 0.88,
    "use_case": "credit_scoring"
  }'
```

---

## Limitations

The compliance engine is **deterministic and formula-based**. It does not:
- Gather evidence by inspecting your system
- Validate that your self-assessed scores are accurate
- Replace a certified auditor for regulatory filings
- Provide legal advice

It is designed as a **consistent, repeatable governance tool** for internal tracking, not as a substitute for external certification.
