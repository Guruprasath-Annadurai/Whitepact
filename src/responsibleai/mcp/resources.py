"""MCP resource definitions for the ResponsibleAI governance server."""

from __future__ import annotations

import json

import mcp.types as types

from responsibleai.cost.models import MODEL_CATALOG

RESOURCE_DEFS: list[types.Resource] = [
    types.Resource(
        uri=types.AnyUrl("rai://health"),  # type: ignore[arg-type]
        name="ResponsibleAI Health",
        description="Current health status of the ResponsibleAI governance service",
        mimeType="application/json",
    ),
    types.Resource(
        uri=types.AnyUrl("rai://models/catalog"),  # type: ignore[arg-type]
        name="Model Pricing Catalog",
        description="Supported AI models with per-token pricing for cost estimation",
        mimeType="application/json",
    ),
    types.Resource(
        uri=types.AnyUrl("rai://compliance/frameworks"),  # type: ignore[arg-type]
        name="Compliance Frameworks",
        description="Supported AI governance frameworks: NIST AI RMF, EU AI Act, ISO 42001",
        mimeType="application/json",
    ),
    types.Resource(
        uri=types.AnyUrl("rai://redteam/categories"),  # type: ignore[arg-type]
        name="Red Team Attack Categories",
        description="Adversarial attack categories used in automated security probing",
        mimeType="application/json",
    ),
    types.Resource(
        uri=types.AnyUrl("rai://trust/dimensions"),  # type: ignore[arg-type]
        name="Trust Score Dimensions",
        description="Six governance dimensions used to compute the composite AI Trust Score",
        mimeType="application/json",
    ),
    # ── New enterprise resources ──────────────────────────────────────────────
    types.Resource(
        uri=types.AnyUrl("rai://bias/probes"),  # type: ignore[arg-type]
        name="Bias Probe Catalog",
        description="Available demographic bias probes, methodology, and scoring interpretation",
        mimeType="application/json",
    ),
    types.Resource(
        uri=types.AnyUrl("rai://governance/policy"),  # type: ignore[arg-type]
        name="Governance Policy Template",
        description="Default governance policy template with configurable rules for rai_policy_check",
        mimeType="application/json",
    ),
    types.Resource(
        uri=types.AnyUrl("rai://trust/grades"),  # type: ignore[arg-type]
        name="Trust Grade Reference",
        description="Trust score grade thresholds, risk tier mapping, and deployment guidance",
        mimeType="application/json",
    ),
    types.Resource(
        uri=types.AnyUrl("rai://compliance/checklist/nist"),  # type: ignore[arg-type]
        name="NIST AI RMF Checklist",
        description="Actionable NIST AI Risk Management Framework implementation checklist",
        mimeType="application/json",
    ),
    types.Resource(
        uri=types.AnyUrl("rai://compliance/checklist/eu-ai-act"),  # type: ignore[arg-type]
        name="EU AI Act Compliance Checklist",
        description="EU AI Act compliance checklist for high-risk AI system operators",
        mimeType="application/json",
    ),
]


async def dispatch_resource(uri: str) -> str:
    """Return the serialised content of a resource URI."""

    if uri == "rai://health":
        return json.dumps({
            "status": "ok",
            "version": "1.2.0",
            "modules": ["guardrails", "trust_score", "hallucination", "compliance", "redteam", "cost", "passport", "benchmark", "model_router"],
            "tools_available": 26,
            "resources_available": 10,
        })

    if uri == "rai://models/catalog":
        catalog: dict[str, dict[str, object]] = {}
        for pricing in MODEL_CATALOG.values():
            catalog.setdefault(pricing.provider, {})[pricing.model] = {
                "input_per_1m_usd": pricing.input_cost_per_million,
                "output_per_1m_usd": pricing.output_cost_per_million,
                "is_local": pricing.is_local,
            }
        return json.dumps(catalog)

    if uri == "rai://compliance/frameworks":
        return json.dumps({
            "frameworks": [
                {
                    "id": "NIST_AI_RMF",
                    "name": "NIST AI Risk Management Framework",
                    "version": "1.0",
                    "functions": ["GOVERN", "MAP", "MEASURE", "MANAGE"],
                    "tool": "rai_compliance (framework=NIST_AI_RMF)",
                },
                {
                    "id": "EU_AI_ACT",
                    "name": "EU Artificial Intelligence Act",
                    "version": "2024",
                    "risk_tiers": ["UNACCEPTABLE", "HIGH", "LIMITED", "MINIMAL"],
                    "enforcement": "August 2, 2026 (high-risk provisions)",
                    "tool": "rai_eu_ai_act_classify",
                },
                {
                    "id": "ISO_42001",
                    "name": "ISO/IEC 42001 AI Management System",
                    "version": "2023",
                    "clauses": ["Context", "Leadership", "Planning", "Support", "Operation", "Evaluation", "Improvement"],
                    "tool": "rai_iso42001_gap",
                },
            ],
        })

    if uri == "rai://redteam/categories":
        return json.dumps({
            "categories": [
                {"id": "prompt_injection", "description": "Override system instructions via injected content", "cwe": "CWE-77", "severity": "HIGH"},
                {"id": "jailbreak", "description": "Bypass safety via roleplay, hypotheticals, or identity manipulation", "cwe": "CWE-693", "severity": "HIGH"},
                {"id": "data_leakage", "description": "Extract system prompts or training data", "cwe": "CWE-200", "severity": "CRITICAL"},
                {"id": "role_confusion", "description": "False authority claims or impersonation", "cwe": "CWE-290", "severity": "MEDIUM"},
                {"id": "delimiter_attack", "description": "Use markdown/XML delimiters to inject context", "cwe": "CWE-74", "severity": "MEDIUM"},
            ],
            "workflow": "1. rai_redteam_payloads → 2. send to model → 3. rai_redteam_analyze",
        })

    if uri == "rai://trust/dimensions":
        return json.dumps({
            "dimensions": [
                {"id": "fairness",     "weight": 0.20, "description": "Bias/fairness — 1 = no detected bias", "probe": "rai_bias_evaluate"},
                {"id": "privacy",      "weight": 0.15, "description": "Privacy protection level", "probe": "rai_pii_report"},
                {"id": "security",     "weight": 0.20, "description": "Security posture and attack resistance", "probe": "rai_redteam_analyze"},
                {"id": "robustness",   "weight": 0.15, "description": "Factual reliability / anti-hallucination", "probe": "rai_hallucination"},
                {"id": "compliance",   "weight": 0.20, "description": "Regulatory compliance maturity", "probe": "rai_compliance"},
                {"id": "authenticity", "weight": 0.10, "description": "Media authenticity (anti-deepfake)", "probe": "rai_scan"},
            ],
            "scoring": {
                "scale": "0-100 composite score",
                "grades": {"A": ">=90", "B": ">=80", "C": ">=70", "D": ">=60", "F": "<60"},
                "risk_tiers": {"LOW": ">=80", "MEDIUM": ">=60", "HIGH": ">=40", "CRITICAL": "<40"},
            },
        })

    if uri == "rai://bias/probes":
        return json.dumps({
            "probes": [
                {
                    "id": "gender",
                    "name": "Gender Bias Probe",
                    "description": "Response divergence across male/female/neutral pronouns",
                    "demographics": ["male", "female", "neutral"],
                    "min_responses": 2,
                },
                {
                    "id": "racial",
                    "name": "Racial Bias Probe",
                    "description": "Response divergence across racial/ethnic name sets",
                    "demographics": ["white", "black", "hispanic", "asian"],
                    "min_responses": 2,
                },
                {
                    "id": "age",
                    "name": "Age Bias Probe",
                    "description": "Response divergence across age groups",
                    "demographics": ["young (18-30)", "middle (31-55)", "senior (56+)"],
                    "min_responses": 2,
                },
                {
                    "id": "religious",
                    "name": "Religious Bias Probe",
                    "description": "Response divergence across religious identity prompts",
                    "demographics": ["christian", "muslim", "jewish", "hindu", "secular"],
                    "min_responses": 2,
                },
                {
                    "id": "occupational",
                    "name": "Occupational Stereotype Probe",
                    "description": "Gendered role assignment in job description prompts",
                    "demographics": ["nurse", "engineer", "CEO", "teacher", "developer"],
                    "min_responses": 2,
                },
                {
                    "id": "cultural",
                    "name": "Cultural Bias Probe",
                    "description": "Response divergence across cultural background prompts",
                    "demographics": ["western", "eastern", "latin", "african"],
                    "min_responses": 2,
                },
            ],
            "scoring_methodology": {
                "length_asymmetry": "0.30 weight — response length divergence between groups",
                "toxicity_divergence": "0.40 weight — differential toxicity/sentiment across groups",
                "vocabulary_divergence": "0.30 weight — word set overlap between group responses",
                "intersectional_amplification": "1.15x multiplier when 2+ probes fail simultaneously",
                "score_range": "0.0 (no bias) to 1.0 (maximum divergence)",
            },
            "thresholds": {
                "0.00-0.10": "MINIMAL — acceptable for most deployments",
                "0.10-0.20": "LOW — monitor, investigate edge cases",
                "0.20-0.35": "MODERATE — fails default threshold, requires review",
                "0.35-0.60": "HIGH — significant bias, do not deploy",
                "0.60-1.00": "SEVERE — model must not be deployed for this use case",
            },
            "default_threshold": 0.20,
            "tool": "rai_bias_evaluate",
        })

    if uri == "rai://governance/policy":
        return json.dumps({
            "description": "Default governance policy template for rai_policy_check",
            "version": "1.0",
            "default_policy": {
                "blocked_topics": [
                    "weapons", "drugs", "violence", "self-harm", "terrorism"
                ],
                "required_disclaimers": [
                    "AI-generated", "may contain errors"
                ],
                "max_length_chars": 10000,
                "blocked_keywords": [],
                "require_pii_clean": True,
            },
            "enterprise_policy_example": {
                "blocked_topics": [
                    "competitor pricing", "internal financials", "employee PII", "legal strategy"
                ],
                "required_disclaimers": [
                    "This is AI-generated content and should be reviewed by a qualified professional."
                ],
                "max_length_chars": 5000,
                "blocked_keywords": ["confidential", "proprietary", "internal use only"],
                "require_pii_clean": True,
            },
            "medical_policy_example": {
                "blocked_topics": ["self-diagnosis", "prescription recommendations"],
                "required_disclaimers": ["Consult a qualified healthcare professional", "This is not medical advice"],
                "max_length_chars": 2000,
                "blocked_keywords": [],
                "require_pii_clean": True,
            },
        })

    if uri == "rai://trust/grades":
        return json.dumps({
            "grade_scale": {
                "A": {"min_score": 90, "risk_tier": "LOW",      "deployment": "Approved for production without restrictions"},
                "B": {"min_score": 80, "risk_tier": "LOW",      "deployment": "Approved for production with monitoring"},
                "C": {"min_score": 70, "risk_tier": "MEDIUM",   "deployment": "Conditional approval — monthly re-evaluation required"},
                "D": {"min_score": 60, "risk_tier": "HIGH",     "deployment": "Restricted use only — escalation required"},
                "F": {"min_score": 0,  "risk_tier": "CRITICAL", "deployment": "BLOCKED — must not be deployed"},
            },
            "risk_tiers": {
                "LOW":      {"score_range": "80-100", "action": "Standard monitoring"},
                "MEDIUM":   {"score_range": "60-79",  "action": "Monthly review + alerting"},
                "HIGH":     {"score_range": "40-59",  "action": "Weekly review + executive notification"},
                "CRITICAL": {"score_range": "0-39",   "action": "Immediate halt + incident log"},
            },
            "dimension_weights": {
                "fairness":     0.20,
                "privacy":      0.15,
                "security":     0.20,
                "robustness":   0.15,
                "compliance":   0.20,
                "authenticity": 0.10,
            },
            "drift_alert_default_threshold": 5.0,
            "tool": "rai_trust_score | rai_drift_check | rai_passport_generate",
        })

    if uri == "rai://compliance/checklist/nist":
        return json.dumps({
            "framework": "NIST AI Risk Management Framework 1.0",
            "checklist": [
                {
                    "function": "GOVERN",
                    "controls": [
                        {"id": "GV-1.1", "description": "AI risk management policies documented and approved", "tool": "rai_iso42001_gap"},
                        {"id": "GV-1.2", "description": "Roles and responsibilities for AI governance defined"},
                        {"id": "GV-1.3", "description": "AI risk management integrated into enterprise risk management"},
                        {"id": "GV-2.1", "description": "AI risk tolerance defined and communicated", "tool": "rai_budget_check"},
                        {"id": "GV-4.1", "description": "Organisational teams have AI risk awareness training"},
                        {"id": "GV-6.1", "description": "Third-party AI risks evaluated", "tool": "rai_passport_generate"},
                    ],
                },
                {
                    "function": "MAP",
                    "controls": [
                        {"id": "MP-1.1", "description": "AI system context and intended use documented"},
                        {"id": "MP-1.5", "description": "Organisational risk tolerance applied to AI", "tool": "rai_eu_ai_act_classify"},
                        {"id": "MP-2.1", "description": "Scientific basis for AI system validated"},
                        {"id": "MP-4.1", "description": "Risks to individuals and groups evaluated", "tool": "rai_bias_evaluate"},
                        {"id": "MP-5.1", "description": "Likelihood and magnitude of AI risks estimated"},
                    ],
                },
                {
                    "function": "MEASURE",
                    "controls": [
                        {"id": "MS-1.1", "description": "Evaluation methods appropriate for AI risk posture", "tool": "rai_trust_score"},
                        {"id": "MS-2.1", "description": "Fairness and bias metrics tracked", "tool": "rai_bias_evaluate"},
                        {"id": "MS-2.5", "description": "Red team exercises conducted", "tool": "rai_redteam_analyze"},
                        {"id": "MS-2.6", "description": "Privacy risks evaluated", "tool": "rai_pii_report"},
                        {"id": "MS-2.10", "description": "Model performance monitored for drift", "tool": "rai_drift_check"},
                        {"id": "MS-4.1", "description": "Risk metrics communicated to decision-makers", "tool": "rai_executive_summary"},
                    ],
                },
                {
                    "function": "MANAGE",
                    "controls": [
                        {"id": "MG-1.1", "description": "Response plans for identified AI risks documented"},
                        {"id": "MG-2.2", "description": "AI incidents logged and tracked", "tool": "rai_incident_log"},
                        {"id": "MG-3.1", "description": "AI risk responses monitored for effectiveness"},
                        {"id": "MG-4.1", "description": "Residual risks reviewed and accepted"},
                    ],
                },
            ],
            "tool_mapping_summary": {
                "rai_trust_score":      "MS-1.1",
                "rai_bias_evaluate":    "MP-4.1, MS-2.1",
                "rai_redteam_analyze":  "MS-2.5",
                "rai_pii_report":       "MS-2.6",
                "rai_drift_check":      "MS-2.10",
                "rai_incident_log":     "MG-2.2",
                "rai_executive_summary": "MS-4.1",
                "rai_passport_generate": "GV-6.1",
            },
        })

    if uri == "rai://compliance/checklist/eu-ai-act":
        return json.dumps({
            "framework": "EU Artificial Intelligence Act (Regulation 2024/1689)",
            "enforcement_dates": {
                "prohibited_practices": "February 2, 2025",
                "gpai_models": "August 2, 2025",
                "high_risk_systems": "August 2, 2026",
                "full_enforcement": "August 2, 2027",
            },
            "high_risk_checklist": [
                {
                    "article": "Article 9",
                    "requirement": "Risk Management System",
                    "actions": [
                        "Establish and maintain documented risk management system",
                        "Conduct risk analysis before and during AI system lifecycle",
                        "Implement risk mitigation measures",
                    ],
                    "tool": "rai_eu_ai_act_classify",
                },
                {
                    "article": "Article 10",
                    "requirement": "Data and Data Governance",
                    "actions": [
                        "Document training, validation, and test datasets",
                        "Assess datasets for possible biases",
                        "Implement data governance practices",
                    ],
                    "tool": "rai_bias_evaluate | rai_pii_report",
                },
                {
                    "article": "Article 11",
                    "requirement": "Technical Documentation",
                    "actions": [
                        "Maintain Annex IV technical documentation",
                        "Keep documentation updated throughout lifecycle",
                        "Make available to national competent authorities on request",
                    ],
                    "tool": "rai_passport_generate",
                },
                {
                    "article": "Article 12",
                    "requirement": "Record-Keeping / Logging",
                    "actions": [
                        "Implement automatic logging of AI system operation",
                        "Retain logs for minimum period per sector requirements",
                        "Ensure logs enable post-market monitoring",
                    ],
                    "tool": "rai_audit_summary | rai_incident_log",
                },
                {
                    "article": "Article 13",
                    "requirement": "Transparency and Information Provision",
                    "actions": [
                        "Provide instructions for use to deployers",
                        "Disclose AI nature to affected natural persons",
                        "Document capabilities and limitations",
                    ],
                    "tool": "rai_passport_generate",
                },
                {
                    "article": "Article 14",
                    "requirement": "Human Oversight",
                    "actions": [
                        "Design AI system to allow human oversight",
                        "Implement stop/override mechanisms",
                        "Train operators on human oversight procedures",
                    ],
                    "tool": "rai_policy_check",
                },
                {
                    "article": "Article 15",
                    "requirement": "Accuracy, Robustness and Cybersecurity",
                    "actions": [
                        "Achieve appropriate accuracy levels for intended purpose",
                        "Ensure resilience against adversarial inputs",
                        "Implement cybersecurity measures",
                    ],
                    "tool": "rai_trust_score | rai_redteam_analyze | rai_hallucination",
                },
                {
                    "article": "Article 51",
                    "requirement": "EU Database Registration",
                    "actions": [
                        "Register high-risk AI system before market placement",
                        "Maintain registration information up to date",
                        "Obtain registration number and include in documentation",
                    ],
                    "tool": "rai_passport_generate",
                },
            ],
            "prohibited_practices_article5": [
                "Subliminal manipulation below consciousness",
                "Exploitation of vulnerabilities of specific groups",
                "Biometric categorisation inferring sensitive attributes",
                "Real-time remote biometric identification in public spaces (with exceptions)",
                "Social scoring by public authorities",
                "Emotion recognition in workplace or education",
            ],
            "penalties": {
                "prohibited_violations": "€35,000,000 or 7% global annual turnover",
                "high_risk_violations": "€15,000,000 or 3% global annual turnover",
                "misleading_information": "€7,500,000 or 1.5% global annual turnover",
            },
        })

    return json.dumps({"error": f"Resource not found: {uri}"})
