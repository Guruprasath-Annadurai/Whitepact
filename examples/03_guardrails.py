"""
Example 03 — Guardrails Engine (PII + Toxicity)
Run: python examples/03_guardrails.py
"""

from responsibleai.guardrails.engine import GuardrailsEngine, GuardrailsPolicy, PIICategory

engine = GuardrailsEngine()

texts = [
    ("Clean text", "The weather in London is currently 18°C with partly cloudy skies."),
    ("PII: email + phone", "Contact Sarah at sarah.jones@acme.com or call 555-867-5309 for support."),
    ("PII: SSN + credit card", "Account holder SSN: 123-45-6789, Card: 4532 1488 0343 6467 exp 12/26"),
    ("Toxic content", "I will hurt anyone who disagrees with me. This is violence."),
    ("Mixed PII + toxic", "Email john@corp.io. I hate all those people and want to harm them."),
]

print("\n" + "=" * 68)
print("  GUARDRAILS SCAN REPORT — ResponsibleAI v0.4.0")
print("=" * 68)

for label, text in texts:
    result = engine.scan(text)
    status = "BLOCKED" if result.is_blocked else "CLEAN  "
    pii_count = len(result.pii_findings)
    tox_count = len(result.toxicity_findings)
    print(f"\n  [{status}] {label}")
    print(f"  Input   : {text[:70]}{'...' if len(text) > 70 else ''}")
    if pii_count:
        cats = [f.category for f in result.pii_findings]
        print(f"  PII     : {pii_count} finding(s) — {', '.join(cats)}")
    if tox_count:
        cats = [f.category for f in result.toxicity_findings]
        print(f"  Toxicity: {tox_count} finding(s) — {', '.join(cats)}")
    if result.redacted_text:
        print(f"  Redacted: {result.redacted_text[:70]}{'...' if len(result.redacted_text) > 70 else ''}")
    if not pii_count and not tox_count:
        print("  Findings: none")

print("\n" + "=" * 68)

# Custom policy — only block SSN, allow emails
custom_policy = GuardrailsPolicy(
    block_pii=True,
    pii_categories=[PIICategory.SSN, PIICategory.CREDIT_CARD],
    block_toxicity=False,
)
strict_engine = GuardrailsEngine(policy=custom_policy)
r = strict_engine.scan("Email me at ceo@corp.com with your SSN 987-65-4321")
print(f"\n  Custom policy (SSN only): is_blocked={r.is_blocked}, PII findings={[f.category for f in r.pii_findings]}")
print("=" * 68 + "\n")
