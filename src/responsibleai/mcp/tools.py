"""MCP tool definitions and dispatch for the ResponsibleAI governance server."""

from __future__ import annotations

from typing import Any

import mcp.types as types

from responsibleai.compliance.engine import ComplianceEngine, Framework
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.redteam.simulator import RedTeamSimulator
from responsibleai.trust.score import TrustScoreEngine

# ── module singletons (lazy-initialised at import time) ───────────────────────

_guardrails = GuardrailsEngine()
_hallucination = HallucinationDetector()
_trust_engine = TrustScoreEngine()
_redteam = RedTeamSimulator()
_compliance = ComplianceEngine()

# ── tool definitions ──────────────────────────────────────────────────────────

TOOL_DEFS: list[types.Tool] = [
    types.Tool(
        name="rai_scan",
        description=(
            "Scan text for PII (email, phone, SSN, credit card, IP address) and harmful "
            "content (hate speech, violence, self-harm). Returns findings and a redacted copy."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to scan"},
                "redact": {
                    "type": "boolean",
                    "default": True,
                    "description": "Replace detected PII with [REDACTED]",
                },
            },
            "required": ["text"],
        },
    ),
    types.Tool(
        name="rai_trust_score",
        description=(
            "Compute a composite AI Trust Score (0-100) across six governance dimensions: "
            "fairness, privacy, security, robustness, compliance, authenticity. "
            "Returns score, letter grade (A-F), and risk tier (LOW/MEDIUM/HIGH/CRITICAL)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "fairness":     {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5, "description": "Bias/fairness — 1 = no detected bias"},
                "privacy":      {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5, "description": "Privacy protection level"},
                "security":     {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5, "description": "Security posture"},
                "robustness":   {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5, "description": "Factual reliability"},
                "compliance":   {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5, "description": "Regulatory compliance maturity"},
                "authenticity": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5, "description": "Media authenticity"},
            },
        },
    ),
    types.Tool(
        name="rai_compliance",
        description=(
            "Evaluate AI governance compliance against NIST AI RMF, EU AI Act, or ISO 42001. "
            "Returns compliance score, findings per control, and remediation recommendations."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "fairness_score":      {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "privacy_score":       {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "security_score":      {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "robustness_score":    {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "compliance_maturity": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "use_case":            {"type": "string", "default": "general", "description": "Deployment use case description"},
                "framework": {
                    "type": "string",
                    "enum": ["NIST_AI_RMF", "EU_AI_ACT", "ISO_42001"],
                    "default": "NIST_AI_RMF",
                },
            },
        },
    ),
    types.Tool(
        name="rai_hallucination",
        description=(
            "Detect hallucination risk in AI-generated text. Analyses hedging language, "
            "self-consistency across candidate responses, and unsupported factual claims."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "AI-generated text to analyse"},
                "candidates": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional additional responses for consistency scoring",
                },
            },
            "required": ["text"],
        },
    ),
    types.Tool(
        name="rai_cost_estimate",
        description="Estimate the USD cost of a model API call from token counts.",
        inputSchema={
            "type": "object",
            "properties": {
                "model":         {"type": "string", "description": "Model name, e.g. gpt-4o or claude-sonnet-4"},
                "provider":      {"type": "string", "description": "Provider: openai | anthropic | google | mistral | cohere | ollama"},
                "input_tokens":  {"type": "integer", "minimum": 0, "description": "Number of input/prompt tokens"},
                "output_tokens": {"type": "integer", "minimum": 0, "description": "Number of output/completion tokens"},
            },
            "required": ["model", "provider", "input_tokens", "output_tokens"],
        },
    ),
    types.Tool(
        name="rai_redteam_payloads",
        description=(
            "Return adversarial attack payloads to probe an AI model for security vulnerabilities. "
            "Categories: prompt_injection, jailbreak, data_leakage, role_confusion, delimiter_attack. "
            "Pass responses to rai_redteam_analyze to get a security report."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": [
                            "prompt_injection", "jailbreak",
                            "data_leakage", "role_confusion", "delimiter_attack",
                        ],
                    },
                    "description": "Filter to specific categories (default: all five)",
                },
            },
        },
    ),
    types.Tool(
        name="rai_redteam_analyze",
        description=(
            "Analyse model responses to red team attack payloads. Returns a security report "
            "with vulnerability findings, severity breakdown, and an overall security score."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "description": "Name of the model under test"},
                "provider":   {"type": "string", "description": "Model provider"},
                "responses": {
                    "type": "object",
                    "description": "Map of attack_name → model_response_text",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["model_name", "provider", "responses"],
        },
    ),
    types.Tool(
        name="rai_compare_models",
        description=(
            "Compare two AI models across all six trust dimensions. Returns scores for each, "
            "delta analysis, and a recommendation on which model is more trustworthy."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_a":    {"type": "string"},
                "provider_a": {"type": "string"},
                "scores_a": {
                    "type": "object",
                    "description": "Trust dimension scores for model A (0-1 each)",
                    "properties": {
                        "fairness":     {"type": "number"},
                        "privacy":      {"type": "number"},
                        "security":     {"type": "number"},
                        "robustness":   {"type": "number"},
                        "compliance":   {"type": "number"},
                        "authenticity": {"type": "number"},
                    },
                },
                "model_b":    {"type": "string"},
                "provider_b": {"type": "string"},
                "scores_b": {
                    "type": "object",
                    "description": "Trust dimension scores for model B (0-1 each)",
                    "properties": {
                        "fairness":     {"type": "number"},
                        "privacy":      {"type": "number"},
                        "security":     {"type": "number"},
                        "robustness":   {"type": "number"},
                        "compliance":   {"type": "number"},
                        "authenticity": {"type": "number"},
                    },
                },
            },
            "required": ["model_a", "provider_a", "model_b", "provider_b"],
        },
    ),
    types.Tool(
        name="rai_audit_summary",
        description=(
            "Return a governance capability summary including supported tools, frameworks, "
            "and available attack vectors. Full audit log access requires the REST endpoint."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "days": {
                    "type": "integer",
                    "minimum": 1,
                    "maximum": 365,
                    "default": 7,
                    "description": "Lookback window in days",
                },
            },
        },
    ),
    types.Tool(
        name="rai_health",
        description="Check the status and module availability of the ResponsibleAI governance engine.",
        inputSchema={"type": "object", "properties": {}},
    ),
]

# ── tool dispatch ─────────────────────────────────────────────────────────────

async def dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    """Route a tool call to the appropriate handler. Returns a JSON-serialisable dict."""
    handlers: dict[str, Any] = {
        "rai_scan":              _handle_scan,
        "rai_trust_score":       _handle_trust_score,
        "rai_compliance":        _handle_compliance,
        "rai_hallucination":     _handle_hallucination,
        "rai_cost_estimate":     _handle_cost_estimate,
        "rai_redteam_payloads":  _handle_redteam_payloads,
        "rai_redteam_analyze":   _handle_redteam_analyze,
        "rai_compare_models":    _handle_compare_models,
        "rai_audit_summary":     _handle_audit_summary,
        "rai_health":            _handle_health,
    }
    handler = handlers.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    try:
        return await handler(args)
    except Exception as exc:
        return {"error": str(exc), "tool": name}


# ── handlers ──────────────────────────────────────────────────────────────────

async def _handle_scan(args: dict[str, Any]) -> dict[str, Any]:
    text = str(args.get("text", ""))
    redact = bool(args.get("redact", True))
    result = _guardrails.scan(text)
    return {
        "is_blocked": result.is_blocked,
        "has_pii": result.has_pii,
        "has_toxicity": result.has_toxicity,
        "pii_findings": [
            {"category": f.category, "match": f.match, "start": f.start, "end": f.end}
            for f in result.pii_findings
        ],
        "toxicity_findings": [
            {"category": f.category, "match": f.match}
            for f in result.toxicity_findings
        ],
        "block_reasons": result.block_reasons,
        "redacted_text": result.redacted_text if redact else None,
    }


async def _handle_trust_score(args: dict[str, Any]) -> dict[str, Any]:
    score = _trust_engine.compute(
        fairness=float(args.get("fairness", 0.5)),
        privacy=float(args.get("privacy", 0.5)),
        security=float(args.get("security", 0.5)),
        robustness=float(args.get("robustness", 0.5)),
        compliance=float(args.get("compliance", 0.5)),
        authenticity=float(args.get("authenticity", 0.5)),
    )
    return score.to_dict()


async def _handle_compliance(args: dict[str, Any]) -> dict[str, Any]:
    framework_str = args.get("framework", "NIST_AI_RMF")
    try:
        framework = Framework(framework_str)
    except ValueError:
        framework = Framework.NIST_AI_RMF

    report = _compliance.evaluate(
        fairness_score=float(args.get("fairness_score", 0.5)),
        privacy_score=float(args.get("privacy_score", 0.5)),
        security_score=float(args.get("security_score", 0.5)),
        robustness_score=float(args.get("robustness_score", 0.5)),
        compliance_maturity=float(args.get("compliance_maturity", 0.5)),
        use_case=str(args.get("use_case", "general")),
        frameworks=[framework],
    )
    return report.to_dict()


async def _handle_hallucination(args: dict[str, Any]) -> dict[str, Any]:
    text = str(args.get("text", ""))
    candidates = args.get("candidates", [])
    result = _hallucination.analyze(text, candidates=candidates if candidates else None)
    return result.to_dict()


async def _handle_cost_estimate(args: dict[str, Any]) -> dict[str, Any]:
    from responsibleai.cost.models import get_pricing

    model = str(args.get("model", ""))
    provider = str(args.get("provider", ""))
    input_tokens = int(args.get("input_tokens", 0))
    output_tokens = int(args.get("output_tokens", 0))

    pricing = get_pricing(provider, model)
    input_cost = pricing.cost_for(input_tokens, 0)
    output_cost = pricing.cost_for(0, output_tokens)
    total = input_cost + output_cost

    return {
        "model": model,
        "provider": provider,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "input_cost_usd": round(input_cost, 6),
        "output_cost_usd": round(output_cost, 6),
        "total_cost_usd": round(total, 6),
        "pricing_info": {
            "input_per_million_usd": pricing.input_cost_per_million,
            "output_per_million_usd": pricing.output_cost_per_million,
            "is_local": pricing.is_local,
        },
    }


async def _handle_redteam_payloads(args: dict[str, Any]) -> dict[str, Any]:
    categories: list[str] = args.get("categories", [])
    payloads = _redteam.get_attack_payloads()
    if categories:
        payloads = [p for p in payloads if p["category"] in categories]
    return {
        "count": len(payloads),
        "payloads": payloads,
        "next_step": (
            "Send each payload to the model under test. "
            "Collect {attack_name: response_text} and call rai_redteam_analyze."
        ),
    }


async def _handle_redteam_analyze(args: dict[str, Any]) -> dict[str, Any]:
    model_name = str(args.get("model_name", "unknown"))
    provider = str(args.get("provider", "unknown"))
    responses: dict[str, str] = args.get("responses", {})
    report = _redteam.analyze_responses(model_name, provider, responses)
    return report.to_dict()


async def _handle_compare_models(args: dict[str, Any]) -> dict[str, Any]:
    _dims = ["fairness", "privacy", "security", "robustness", "compliance", "authenticity"]

    def _extract(key: str) -> dict[str, float]:
        raw: dict[str, Any] = args.get(key, {})
        return {d: float(raw.get(d, 0.5)) for d in _dims}

    model_a = str(args.get("model_a", "model_a"))
    provider_a = str(args.get("provider_a", "unknown"))
    model_b = str(args.get("model_b", "model_b"))
    provider_b = str(args.get("provider_b", "unknown"))

    scores_a = _extract("scores_a")
    scores_b = _extract("scores_b")

    trust_a = _trust_engine.compute(**scores_a)
    trust_b = _trust_engine.compute(**scores_b)

    delta = {d: round(scores_b[d] - scores_a[d], 4) for d in _dims}
    winner = model_a if trust_a.overall >= trust_b.overall else model_b
    winner_provider = provider_a if trust_a.overall >= trust_b.overall else provider_b

    return {
        "model_a": {"name": model_a, "provider": provider_a, **trust_a.to_dict()},
        "model_b": {"name": model_b, "provider": provider_b, **trust_b.to_dict()},
        "delta": delta,
        "winner": winner,
        "winner_provider": winner_provider,
        "score_gap": round(abs(trust_a.overall - trust_b.overall), 2),
        "recommendation": (
            f"{winner} ({winner_provider}) has a higher trust score "
            f"by {round(abs(trust_a.overall - trust_b.overall), 2)} points."
        ),
    }


async def _handle_audit_summary(args: dict[str, Any]) -> dict[str, Any]:
    days = int(args.get("days", 7))
    payloads = _redteam.get_attack_payloads()
    return {
        "days_requested": days,
        "governance_engine": {
            "version": "1.1.0",
            "tools_available": len(TOOL_DEFS),
            "frameworks": ["NIST_AI_RMF", "EU_AI_ACT", "ISO_42001"],
            "attack_vectors": len(payloads),
            "attack_categories": list({p["category"] for p in payloads}),
        },
        "note": (
            "Full time-series audit log access (request history, by org/endpoint) "
            "is available at GET /api/audit on the ResponsibleAI REST server."
        ),
    }


async def _handle_health(args: dict[str, Any]) -> dict[str, Any]:
    modules = {
        "guardrails":   "ok" if _guardrails is not None else "unavailable",
        "trust_score":  "ok" if _trust_engine is not None else "unavailable",
        "hallucination": "ok" if _hallucination is not None else "unavailable",
        "compliance":   "ok" if _compliance is not None else "unavailable",
        "redteam":      "ok" if _redteam is not None else "unavailable",
    }
    return {
        "status": "ok",
        "version": "1.1.0",
        "modules": modules,
        "tools": len(TOOL_DEFS),
    }
