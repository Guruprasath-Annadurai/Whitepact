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
]


async def dispatch_resource(uri: str) -> str:
    """Return the serialised content of a resource URI."""
    if uri == "rai://health":
        return json.dumps({
            "status": "ok",
            "version": "1.1.0",
            "modules": ["guardrails", "trust_score", "hallucination", "compliance", "redteam", "cost"],
        })

    if uri == "rai://models/catalog":
        catalog: dict[str, dict[str, object]] = {}
        for pricing in MODEL_CATALOG.values():
            provider = pricing.provider
            model = pricing.model
            catalog.setdefault(provider, {})[model] = {
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
                },
                {
                    "id": "EU_AI_ACT",
                    "name": "EU Artificial Intelligence Act",
                    "version": "2024",
                    "risk_tiers": ["UNACCEPTABLE", "HIGH", "LIMITED", "MINIMAL"],
                },
                {
                    "id": "ISO_42001",
                    "name": "ISO/IEC 42001 AI Management System",
                    "version": "2023",
                    "clauses": [
                        "Context", "Leadership", "Planning",
                        "Support", "Operation", "Evaluation", "Improvement",
                    ],
                },
            ],
        })

    if uri == "rai://redteam/categories":
        return json.dumps({
            "categories": [
                {"id": "prompt_injection", "description": "Override system instructions via injected content", "cwe": "CWE-77"},
                {"id": "jailbreak", "description": "Bypass safety via roleplay, hypotheticals, or identity manipulation", "cwe": "CWE-693"},
                {"id": "data_leakage", "description": "Extract system prompts or training data", "cwe": "CWE-200"},
                {"id": "role_confusion", "description": "False authority claims or impersonation", "cwe": "CWE-290"},
                {"id": "delimiter_attack", "description": "Use markdown/XML delimiters to inject context", "cwe": "CWE-74"},
            ],
        })

    if uri == "rai://trust/dimensions":
        return json.dumps({
            "dimensions": [
                {"id": "fairness",     "weight": 0.20, "description": "Bias/fairness — 1 = no detected bias"},
                {"id": "privacy",      "weight": 0.15, "description": "Privacy protection level"},
                {"id": "security",     "weight": 0.20, "description": "Security posture and attack resistance"},
                {"id": "robustness",   "weight": 0.15, "description": "Factual reliability / anti-hallucination"},
                {"id": "compliance",   "weight": 0.20, "description": "Regulatory compliance maturity"},
                {"id": "authenticity", "weight": 0.10, "description": "Media authenticity (anti-deepfake)"},
            ],
            "scoring": {
                "scale": "0-100 composite score",
                "grades": {"A": ">=90", "B": ">=80", "C": ">=70", "D": ">=60", "F": "<60"},
                "risk_tiers": {"LOW": ">=80", "MEDIUM": ">=60", "HIGH": ">=40", "CRITICAL": "<40"},
            },
        })

    return json.dumps({"error": f"Resource not found: {uri}"})
