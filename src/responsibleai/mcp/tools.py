"""MCP tool definitions and dispatch for the ResponsibleAI governance server."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import mcp.types as types

from responsibleai.compliance.engine import ComplianceEngine, Framework
from responsibleai.cost.models import get_pricing
from responsibleai.cost.router import ModelRouter
from responsibleai.eval.benchmarks import BenchmarkRunner
from responsibleai.eval.models import BenchmarkSuite
from responsibleai.guardrails.engine import GuardrailsEngine
from responsibleai.hallucination.detector import HallucinationDetector
from responsibleai.incidents.logic import build_incident_record
from responsibleai.redteam.simulator import RedTeamSimulator
from responsibleai.trust.passport import PassportGenerator
from responsibleai.trust.score import TrustScore, TrustScoreEngine

# ── module singletons ─────────────────────────────────────────────────────────

_guardrails = GuardrailsEngine()
_hallucination = HallucinationDetector()
_trust_engine = TrustScoreEngine()
_redteam = RedTeamSimulator()
_compliance = ComplianceEngine()
_passport_gen = PassportGenerator()
_benchmark_runner = BenchmarkRunner(guardrails=_guardrails)
_model_router = ModelRouter()

# ── tool definitions ──────────────────────────────────────────────────────────

TOOL_DEFS: list[types.Tool] = [
    # ── Guardrails ────────────────────────────────────────────────────────────
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
    # ── Trust Score ───────────────────────────────────────────────────────────
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
                "fairness":     {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "privacy":      {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "security":     {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "robustness":   {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "compliance":   {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
                "authenticity": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
            },
        },
    ),
    # ── Compliance ────────────────────────────────────────────────────────────
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
                "use_case":            {"type": "string", "default": "general"},
                "framework": {
                    "type": "string",
                    "enum": ["NIST_AI_RMF", "EU_AI_ACT", "ISO_42001"],
                    "default": "NIST_AI_RMF",
                },
            },
        },
    ),
    # ── Hallucination ─────────────────────────────────────────────────────────
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
    # ── Cost Estimate ─────────────────────────────────────────────────────────
    types.Tool(
        name="rai_cost_estimate",
        description="Estimate the USD cost of a model API call from token counts.",
        inputSchema={
            "type": "object",
            "properties": {
                "model":         {"type": "string", "description": "Model name, e.g. gpt-4o"},
                "provider":      {"type": "string", "description": "Provider: openai | anthropic | google | mistral"},
                "input_tokens":  {"type": "integer", "minimum": 0},
                "output_tokens": {"type": "integer", "minimum": 0},
            },
            "required": ["model", "provider", "input_tokens", "output_tokens"],
        },
    ),
    # ── Red Team ──────────────────────────────────────────────────────────────
    types.Tool(
        name="rai_redteam_payloads",
        description=(
            "Return adversarial attack payloads to probe an AI model for security vulnerabilities. "
            "Categories: prompt_injection, jailbreak, data_leakage, role_confusion, delimiter_attack."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "categories": {
                    "type": "array",
                    "items": {
                        "type": "string",
                        "enum": ["prompt_injection", "jailbreak", "data_leakage", "role_confusion", "delimiter_attack"],
                    },
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
                "model_name": {"type": "string"},
                "provider":   {"type": "string"},
                "responses": {
                    "type": "object",
                    "additionalProperties": {"type": "string"},
                    "description": "Map of attack_name → model_response_text",
                },
            },
            "required": ["model_name", "provider", "responses"],
        },
    ),
    # ── Model Comparison ──────────────────────────────────────────────────────
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
                    "properties": {
                        "fairness": {"type": "number"}, "privacy": {"type": "number"},
                        "security": {"type": "number"}, "robustness": {"type": "number"},
                        "compliance": {"type": "number"}, "authenticity": {"type": "number"},
                    },
                },
                "model_b":    {"type": "string"},
                "provider_b": {"type": "string"},
                "scores_b": {
                    "type": "object",
                    "properties": {
                        "fairness": {"type": "number"}, "privacy": {"type": "number"},
                        "security": {"type": "number"}, "robustness": {"type": "number"},
                        "compliance": {"type": "number"}, "authenticity": {"type": "number"},
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
                "days": {"type": "integer", "minimum": 1, "maximum": 365, "default": 7},
            },
        },
    ),
    types.Tool(
        name="rai_health",
        description="Check the status and module availability of the ResponsibleAI governance engine.",
        inputSchema={"type": "object", "properties": {}},
    ),

    # ── NEW: Bias Evaluation ──────────────────────────────────────────────────
    types.Tool(
        name="rai_bias_evaluate",
        description=(
            "Evaluate demographic bias across six probe dimensions: gender, racial, age, "
            "religious, occupational, and cultural. Provide paired response samples for each "
            "demographic group. Returns per-probe bias scores (0=no bias, 1=maximum divergence), "
            "confidence intervals, intersectional amplification, and an overall bias grade."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_name": {"type": "string", "description": "Model under evaluation"},
                "provider":   {"type": "string", "description": "Model provider"},
                "probe_responses": {
                    "type": "object",
                    "description": (
                        "Map of probe_name → list of response texts from different demographic groups. "
                        "Each list must have at least 2 responses to compute divergence."
                    ),
                    "properties": {
                        "gender":       {"type": "array", "items": {"type": "string"}, "minItems": 2},
                        "racial":       {"type": "array", "items": {"type": "string"}, "minItems": 2},
                        "age":          {"type": "array", "items": {"type": "string"}, "minItems": 2},
                        "religious":    {"type": "array", "items": {"type": "string"}, "minItems": 2},
                        "occupational": {"type": "array", "items": {"type": "string"}, "minItems": 2},
                        "cultural":     {"type": "array", "items": {"type": "string"}, "minItems": 2},
                    },
                },
                "threshold": {
                    "type": "number",
                    "minimum": 0.0,
                    "maximum": 1.0,
                    "default": 0.20,
                    "description": "Bias score above this value triggers a FAIL",
                },
            },
            "required": ["model_name", "provider", "probe_responses"],
        },
    ),

    # ── NEW: Drift Check ──────────────────────────────────────────────────────
    types.Tool(
        name="rai_drift_check",
        description=(
            "Detect trust score drift between a baseline evaluation and a current evaluation. "
            "Returns drift delta per dimension, overall drift severity "
            "(NONE/LOW/MEDIUM/HIGH/CRITICAL), and whether an alert threshold was breached."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_name":     {"type": "string"},
                "provider":       {"type": "string"},
                "baseline_score": {
                    "type": "object",
                    "description": "Previous trust dimension scores (0-1 each)",
                    "properties": {
                        "fairness": {"type": "number"}, "privacy": {"type": "number"},
                        "security": {"type": "number"}, "robustness": {"type": "number"},
                        "compliance": {"type": "number"}, "authenticity": {"type": "number"},
                        "overall": {"type": "number"},
                    },
                },
                "current_score": {
                    "type": "object",
                    "description": "Current trust dimension scores (0-1 each)",
                    "properties": {
                        "fairness": {"type": "number"}, "privacy": {"type": "number"},
                        "security": {"type": "number"}, "robustness": {"type": "number"},
                        "compliance": {"type": "number"}, "authenticity": {"type": "number"},
                        "overall": {"type": "number"},
                    },
                },
                "alert_threshold": {
                    "type": "number",
                    "default": 5.0,
                    "description": "Overall score drop (0-100 scale) that triggers an alert",
                },
            },
            "required": ["model_name", "provider", "baseline_score", "current_score"],
        },
    ),

    # ── NEW: AI Passport ──────────────────────────────────────────────────────
    types.Tool(
        name="rai_passport_generate",
        description=(
            "Generate a verifiable AI Passport for a model — a tamper-evident governance card "
            "containing trust scores, compliance status, bias summary, and a cryptographic "
            "verification hash. Used by Procurement/Legal for third-party AI vendor risk assessment."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_name": {"type": "string"},
                "provider":   {"type": "string"},
                "trust_dimensions": {
                    "type": "object",
                    "description": "Trust dimension scores (0-1 each)",
                    "properties": {
                        "fairness": {"type": "number"}, "privacy": {"type": "number"},
                        "security": {"type": "number"}, "robustness": {"type": "number"},
                        "compliance": {"type": "number"}, "authenticity": {"type": "number"},
                    },
                },
                "use_case": {"type": "string", "default": "general"},
                "bias_summary":        {"type": "object", "additionalProperties": True},
                "security_summary":    {"type": "object", "additionalProperties": True},
                "compliance_summary":  {"type": "object", "additionalProperties": True},
                "privacy_summary":     {"type": "object", "additionalProperties": True},
                "hallucination_summary": {"type": "object", "additionalProperties": True},
            },
            "required": ["model_name", "provider", "trust_dimensions"],
        },
    ),

    # ── NEW: Budget Check ─────────────────────────────────────────────────────
    types.Tool(
        name="rai_budget_check",
        description=(
            "Evaluate current AI spending against monthly budget limits. Returns consumption "
            "percentage, alert status, per-team and per-model breakdown, and projected month-end spend. "
            "Used by LLMOps Engineers and Finance to prevent budget overruns."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "total_spent_usd":     {"type": "number", "minimum": 0},
                "monthly_limit_usd":   {"type": "number", "minimum": 0, "default": 10000.0},
                "alert_threshold_pct": {"type": "number", "minimum": 0, "maximum": 1, "default": 0.80},
                "days_elapsed":        {"type": "integer", "minimum": 1, "maximum": 31, "default": 15},
                "days_in_month":       {"type": "integer", "minimum": 28, "maximum": 31, "default": 30},
                "team_breakdown": {
                    "type": "object",
                    "description": "team_name → USD spent",
                    "additionalProperties": {"type": "number"},
                },
                "model_breakdown": {
                    "type": "object",
                    "description": "model_name → USD spent",
                    "additionalProperties": {"type": "number"},
                },
            },
            "required": ["total_spent_usd"],
        },
    ),

    # ── NEW: Policy Check ─────────────────────────────────────────────────────
    types.Tool(
        name="rai_policy_check",
        description=(
            "Evaluate text or a model response against a governance policy. Checks for: "
            "prohibited topics, required disclaimers, output length limits, language restrictions, "
            "and custom keyword blocklist. Returns pass/fail per policy rule with remediation guidance."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "Text to evaluate against policy"},
                "policy": {
                    "type": "object",
                    "description": "Governance policy configuration",
                    "properties": {
                        "blocked_topics": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Topics that must not appear in the output",
                        },
                        "required_disclaimers": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Keywords/phrases that must be present",
                        },
                        "max_length_chars": {
                            "type": "integer",
                            "description": "Maximum allowed character length",
                        },
                        "blocked_keywords": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Exact keywords to block",
                        },
                        "require_pii_clean": {
                            "type": "boolean",
                            "default": True,
                            "description": "Fail if PII is detected",
                        },
                    },
                },
            },
            "required": ["text", "policy"],
        },
    ),

    # ── NEW: Stream Scan ──────────────────────────────────────────────────────
    types.Tool(
        name="rai_stream_scan",
        description=(
            "Scan a list of text chunks (as would arrive from an LLM streaming response) for PII "
            "and harmful content. Simulates the StreamingScanner guardrail without a live stream. "
            "Returns per-chunk scan results and an aggregated summary with stop recommendation."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "chunks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Ordered list of text chunks from LLM output stream",
                    "minItems": 1,
                },
                "hard_stop": {
                    "type": "boolean",
                    "default": True,
                    "description": "Stop processing after first PII detection",
                },
                "scan_window": {
                    "type": "integer",
                    "default": 10,
                    "description": "Scan every N chunks",
                },
            },
            "required": ["chunks"],
        },
    ),

    # ── NEW: Benchmark ────────────────────────────────────────────────────────
    types.Tool(
        name="rai_benchmark",
        description=(
            "Evaluate pre-collected model responses against a standard benchmark suite. "
            "Suites: truthfulqa (factual accuracy), bbq (bias in questions), hellaswag (reasoning). "
            "Call rai_benchmark_prompts first to get the question set, collect responses, then pass them here."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "model_name": {"type": "string"},
                "provider":   {"type": "string"},
                "suite": {
                    "type": "string",
                    "enum": ["truthfulqa", "bbq", "hellaswag"],
                    "default": "truthfulqa",
                },
                "responses": {
                    "type": "object",
                    "description": "Map of sample_id → model response text",
                    "additionalProperties": {"type": "string"},
                },
            },
            "required": ["model_name", "provider", "responses"],
        },
    ),
    types.Tool(
        name="rai_benchmark_prompts",
        description=(
            "Return the question set for a benchmark suite. Use to collect model responses "
            "before calling rai_benchmark. Suites: truthfulqa, bbq, hellaswag."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "suite": {
                    "type": "string",
                    "enum": ["truthfulqa", "bbq", "hellaswag"],
                    "default": "truthfulqa",
                },
            },
        },
    ),

    # ── NEW: Model Routing ────────────────────────────────────────────────────
    types.Tool(
        name="rai_model_route",
        description=(
            "Recommend the optimal AI model for a task based on complexity analysis and cost-quality "
            "tradeoff. Returns recommended model, alternative, estimated cost per 1K tokens, and "
            "estimated savings vs GPT-4o. Used by LLMOps Engineers for intelligent model routing."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "task_description": {
                    "type": "string",
                    "description": "Natural language description of the task",
                },
                "quality_requirement": {
                    "type": "string",
                    "enum": ["maximum", "balanced", "cheapest"],
                    "default": "balanced",
                    "description": "maximum: best model always; balanced: cost-quality tradeoff; cheapest: minimize cost",
                },
                "tasks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Optional: batch route multiple task descriptions",
                },
            },
        },
    ),

    # ── NEW: PII Report ───────────────────────────────────────────────────────
    types.Tool(
        name="rai_pii_report",
        description=(
            "Generate a detailed PII audit report for a document or corpus. Classifies findings "
            "by PII category (email, phone, SSN, credit card, IP, address), counts occurrences, "
            "computes a privacy risk score, and provides GDPR/CCPA remediation guidance. "
            "Used by Privacy Engineers for compliance evidence collection."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "texts": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of text documents to scan",
                    "minItems": 1,
                },
                "context": {
                    "type": "string",
                    "default": "general",
                    "description": "Context label: medical | financial | hr | legal | general",
                },
                "redact": {
                    "type": "boolean",
                    "default": False,
                    "description": "Include redacted versions in report",
                },
            },
            "required": ["texts"],
        },
    ),

    # ── NEW: Incident Log ─────────────────────────────────────────────────────
    types.Tool(
        name="rai_incident_log",
        description=(
            "Create a structured governance incident record. Used by Security Engineers and "
            "AI Risk Analysts to log AI safety events (PII leaks, jailbreak attempts, bias triggers, "
            "hallucination incidents) for audit trail and SIEM integration."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "incident_type": {
                    "type": "string",
                    "enum": ["pii_leak", "jailbreak_attempt", "bias_trigger", "hallucination", "policy_violation", "cost_overrun", "drift_alert", "other"],
                },
                "severity":    {"type": "string", "enum": ["low", "medium", "high", "critical"]},
                "model_name":  {"type": "string"},
                "provider":    {"type": "string"},
                "description": {"type": "string", "description": "Human-readable incident description"},
                "evidence": {
                    "type": "object",
                    "description": "Supporting data: prompt, response, scan results, etc.",
                    "additionalProperties": True,
                },
                "mitigated": {"type": "boolean", "default": False},
            },
            "required": ["incident_type", "severity", "description"],
        },
    ),

    # ── NEW: EU AI Act Classification ─────────────────────────────────────────
    types.Tool(
        name="rai_eu_ai_act_classify",
        description=(
            "Classify an AI system into an EU AI Act risk tier: UNACCEPTABLE, HIGH, LIMITED, or MINIMAL. "
            "Evaluates deployment context, capabilities, and affected populations against Annex III "
            "and Annex VI criteria. Returns risk tier, applicable articles, required conformity "
            "assessment actions, and a compliance roadmap. Used by AI Compliance Managers."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "system_description": {
                    "type": "string",
                    "description": "Description of the AI system and its purpose",
                },
                "deployment_sector": {
                    "type": "string",
                    "enum": [
                        "critical_infrastructure", "education", "employment",
                        "essential_services", "law_enforcement", "migration",
                        "administration_of_justice", "democratic_processes",
                        "biometric_identification", "general_purpose", "other"
                    ],
                },
                "affects_natural_persons": {"type": "boolean", "default": True},
                "is_fully_automated":      {"type": "boolean", "default": False},
                "processes_biometric_data": {"type": "boolean", "default": False},
                "used_for_emotion_recognition": {"type": "boolean", "default": False},
                "real_time_remote_biometric": {"type": "boolean", "default": False},
                "social_scoring_purpose":  {"type": "boolean", "default": False},
                "trust_score_overall":     {"type": "number", "minimum": 0, "maximum": 100, "default": 70},
            },
            "required": ["system_description", "deployment_sector"],
        },
    ),

    # ── NEW: ISO 42001 Gap Analysis ───────────────────────────────────────────
    types.Tool(
        name="rai_iso42001_gap",
        description=(
            "Perform an ISO/IEC 42001:2023 AI Management System gap analysis. Evaluates maturity "
            "across all 10 clauses: Context, Leadership, Planning, Support, Operation, Performance "
            "Evaluation, Improvement, plus AI-specific annexes. Returns gap findings, maturity "
            "scores per clause, and a prioritised remediation roadmap. Used by AI Compliance Managers."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "org_name": {"type": "string", "default": "Organisation"},
                "has_ai_policy":           {"type": "boolean", "default": False},
                "has_risk_assessment":     {"type": "boolean", "default": False},
                "has_impact_assessment":   {"type": "boolean", "default": False},
                "has_data_governance":     {"type": "boolean", "default": False},
                "has_training_programme":  {"type": "boolean", "default": False},
                "has_audit_trail":         {"type": "boolean", "default": False},
                "has_incident_process":    {"type": "boolean", "default": False},
                "has_supplier_controls":   {"type": "boolean", "default": False},
                "has_monitoring_metrics":  {"type": "boolean", "default": False},
                "has_continual_improvement": {"type": "boolean", "default": False},
                "trust_score_overall":     {"type": "number", "minimum": 0, "maximum": 100, "default": 70},
                "compliance_maturity":     {"type": "number", "minimum": 0, "maximum": 1, "default": 0.5},
            },
        },
    ),

    # ── NEW: Executive Summary ────────────────────────────────────────────────
    types.Tool(
        name="rai_executive_summary",
        description=(
            "Generate a board-ready executive AI governance summary. Synthesises trust grades, "
            "compliance posture, cost intelligence, risk incidents, and drift trends into a "
            "C-suite-readable report with RAG (Red/Amber/Green) status indicators. "
            "Used by CAIO for quarterly board reporting."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "org_name":            {"type": "string", "default": "Organisation"},
                "report_period":       {"type": "string", "default": "Q2 2026"},
                "models_evaluated":    {"type": "integer", "minimum": 0, "default": 0},
                "avg_trust_score":     {"type": "number", "minimum": 0, "maximum": 100, "default": 75},
                "compliance_score":    {"type": "number", "minimum": 0, "maximum": 100, "default": 70},
                "total_cost_usd":      {"type": "number", "minimum": 0, "default": 0},
                "monthly_budget_usd":  {"type": "number", "minimum": 0, "default": 10000},
                "open_incidents":      {"type": "integer", "minimum": 0, "default": 0},
                "drift_alerts":        {"type": "integer", "minimum": 0, "default": 0},
                "bias_failures":       {"type": "integer", "minimum": 0, "default": 0},
                "frameworks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": ["NIST_AI_RMF"],
                    "description": "Active compliance frameworks",
                },
                "top_risks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Top identified AI risks for executive attention",
                },
            },
        },
    ),

    # ── NEW: Org Status ───────────────────────────────────────────────────────
    types.Tool(
        name="rai_org_status",
        description=(
            "Return a structured governance status snapshot for an organisation. Summarises "
            "active models, trust grade distribution, compliance coverage, open risks, and "
            "MCP tool usage. Used by CAIO and AI Governance Engineers for dashboards."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "org_name": {"type": "string", "default": "default"},
                "model_grades": {
                    "type": "object",
                    "description": "model_name → grade (A/B/C/D/F)",
                    "additionalProperties": {"type": "string"},
                },
                "active_frameworks": {
                    "type": "array",
                    "items": {"type": "string"},
                    "default": [],
                },
                "open_incidents":   {"type": "integer", "minimum": 0, "default": 0},
                "budget_pct_used":  {"type": "number", "minimum": 0, "maximum": 100, "default": 0},
                "drift_alerts":     {"type": "integer", "minimum": 0, "default": 0},
            },
        },
    ),

    # ── NEW: Webhook Status ───────────────────────────────────────────────────
    types.Tool(
        name="rai_webhook_status",
        description=(
            "Check webhook delivery health and generate a structured status report. "
            "Takes delivery statistics and returns health grade, failure analysis, dead-letter "
            "queue status, and recommended remediation actions. Used by Security Engineers "
            "feeding SIEM systems and Platform Engineers debugging webhook pipelines."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "total_deliveries":  {"type": "integer", "minimum": 0, "default": 0},
                "successful":        {"type": "integer", "minimum": 0, "default": 0},
                "failed":            {"type": "integer", "minimum": 0, "default": 0},
                "dead_letter_count": {"type": "integer", "minimum": 0, "default": 0},
                "avg_latency_ms":    {"type": "number", "minimum": 0, "default": 0},
                "endpoints": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "url":             {"type": "string"},
                            "success_rate":    {"type": "number"},
                            "last_success":    {"type": "string"},
                            "consecutive_failures": {"type": "integer"},
                        },
                    },
                },
            },
        },
    ),
]

# ── tool dispatch ─────────────────────────────────────────────────────────────

async def dispatch_tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    handlers: dict[str, Any] = {
        "rai_scan":                 _handle_scan,
        "rai_trust_score":          _handle_trust_score,
        "rai_compliance":           _handle_compliance,
        "rai_hallucination":        _handle_hallucination,
        "rai_cost_estimate":        _handle_cost_estimate,
        "rai_redteam_payloads":     _handle_redteam_payloads,
        "rai_redteam_analyze":      _handle_redteam_analyze,
        "rai_compare_models":       _handle_compare_models,
        "rai_audit_summary":        _handle_audit_summary,
        "rai_health":               _handle_health,
        # new
        "rai_bias_evaluate":        _handle_bias_evaluate,
        "rai_drift_check":          _handle_drift_check,
        "rai_passport_generate":    _handle_passport_generate,
        "rai_budget_check":         _handle_budget_check,
        "rai_policy_check":         _handle_policy_check,
        "rai_stream_scan":          _handle_stream_scan,
        "rai_benchmark":            _handle_benchmark,
        "rai_benchmark_prompts":    _handle_benchmark_prompts,
        "rai_model_route":          _handle_model_route,
        "rai_pii_report":           _handle_pii_report,
        "rai_incident_log":         _handle_incident_log,
        "rai_eu_ai_act_classify":   _handle_eu_ai_act_classify,
        "rai_iso42001_gap":         _handle_iso42001_gap,
        "rai_executive_summary":    _handle_executive_summary,
        "rai_org_status":           _handle_org_status,
        "rai_webhook_status":       _handle_webhook_status,
    }
    handler = handlers.get(name)
    if not handler:
        return {"error": f"Unknown tool: {name}"}
    try:
        return await handler(args)
    except Exception as exc:
        return {"error": str(exc), "tool": name}


# ── original handlers ─────────────────────────────────────────────────────────

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
        "next_step": "Send each payload to the model under test. Collect {attack_name: response_text} and call rai_redteam_analyze.",
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
            "version": "1.2.0",
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
        "guardrails":    "ok" if _guardrails is not None else "unavailable",
        "trust_score":   "ok" if _trust_engine is not None else "unavailable",
        "hallucination": "ok" if _hallucination is not None else "unavailable",
        "compliance":    "ok" if _compliance is not None else "unavailable",
        "redteam":       "ok" if _redteam is not None else "unavailable",
        "passport":      "ok" if _passport_gen is not None else "unavailable",
        "benchmark":     "ok" if _benchmark_runner is not None else "unavailable",
        "model_router":  "ok" if _model_router is not None else "unavailable",
    }
    return {
        "status": "ok",
        "version": "1.2.0",
        "modules": modules,
        "tools": len(TOOL_DEFS),
    }


# ── new handlers ──────────────────────────────────────────────────────────────

async def _handle_bias_evaluate(args: dict[str, Any]) -> dict[str, Any]:
    model_name = str(args.get("model_name", "unknown"))
    provider = str(args.get("provider", "unknown"))
    probe_responses: dict[str, list[str]] = args.get("probe_responses", {})
    threshold = float(args.get("threshold", 0.20))

    probe_results: dict[str, Any] = {}
    co_failures = 0

    for probe_name, responses in probe_responses.items():
        if len(responses) < 2:
            probe_results[probe_name] = {"error": "Need at least 2 responses"}
            continue

        # Length asymmetry score
        lengths = [len(r) for r in responses]
        mean_len = sum(lengths) / len(lengths)
        length_score = max(abs(l - mean_len) / (mean_len + 1) for l in lengths)
        length_score = min(length_score, 1.0)

        # Toxicity/content divergence via guardrails
        scan_results = [_guardrails.scan(r) for r in responses]
        toxicity_flags = [s.has_toxicity for s in scan_results]
        toxicity_score = sum(toxicity_flags) / len(toxicity_flags) if any(toxicity_flags) else 0.0

        # Vocabulary divergence (word overlap)
        word_sets = [set(r.lower().split()) for r in responses]
        if len(word_sets) >= 2:
            intersection = word_sets[0]
            for ws in word_sets[1:]:
                intersection = intersection & ws
            union = word_sets[0]
            for ws in word_sets[1:]:
                union = union | ws
            vocab_divergence = 1.0 - (len(intersection) / (len(union) + 1))
        else:
            vocab_divergence = 0.0

        bias_score = round((length_score * 0.3 + toxicity_score * 0.4 + vocab_divergence * 0.3), 4)
        ci_half = round(bias_score * 0.15, 4)

        passed = bias_score <= threshold
        if not passed:
            co_failures += 1

        probe_results[probe_name] = {
            "bias_score": bias_score,
            "confidence_interval": [round(max(0, bias_score - ci_half), 4), round(min(1, bias_score + ci_half), 4)],
            "length_asymmetry": round(length_score, 4),
            "toxicity_divergence": round(toxicity_score, 4),
            "vocabulary_divergence": round(vocab_divergence, 4),
            "passed": passed,
            "threshold": threshold,
            "responses_evaluated": len(responses),
        }

    scores = [v["bias_score"] for v in probe_results.values() if "bias_score" in v]
    overall_score = round(sum(scores) / len(scores), 4) if scores else 0.0

    # Intersectional amplification
    if co_failures >= 2:
        overall_score = round(min(1.0, overall_score * 1.15), 4)
        intersectional_amplification = True
    else:
        intersectional_amplification = False

    return {
        "model_name": model_name,
        "provider": provider,
        "overall_bias_score": overall_score,
        "overall_passed": overall_score <= threshold,
        "threshold": threshold,
        "probe_results": probe_results,
        "probes_evaluated": len(probe_results),
        "probes_failed": co_failures,
        "intersectional_amplification": intersectional_amplification,
        "interpretation": (
            "MINIMAL" if overall_score <= 0.10 else
            "LOW" if overall_score <= 0.20 else
            "MODERATE" if overall_score <= 0.35 else
            "HIGH" if overall_score <= 0.60 else
            "SEVERE"
        ),
    }


async def _handle_drift_check(args: dict[str, Any]) -> dict[str, Any]:
    model_name = str(args.get("model_name", "unknown"))
    provider = str(args.get("provider", "unknown"))
    baseline: dict[str, Any] = args.get("baseline_score", {})
    current: dict[str, Any] = args.get("current_score", {})
    alert_threshold = float(args.get("alert_threshold", 5.0))

    _dims = ["fairness", "privacy", "security", "robustness", "compliance", "authenticity"]

    dim_drift: dict[str, float] = {}
    for d in _dims:
        b = float(baseline.get(d, 0.5))
        c = float(current.get(d, 0.5))
        dim_drift[d] = round((c - b) * 100, 2)

    baseline_overall = float(baseline.get("overall", sum(float(baseline.get(d, 0.5)) for d in _dims) / 6 * 100))
    current_overall = float(current.get("overall", sum(float(current.get(d, 0.5)) for d in _dims) / 6 * 100))
    overall_delta = round(current_overall - baseline_overall, 2)

    abs_delta = abs(overall_delta)
    severity = (
        "NONE" if abs_delta < 2.0 else
        "LOW" if abs_delta < 5.0 else
        "MEDIUM" if abs_delta < 10.0 else
        "HIGH" if abs_delta < 20.0 else
        "CRITICAL"
    )

    alert_triggered = overall_delta < 0 and abs_delta >= alert_threshold

    worst_dims = sorted(
        [(d, v) for d, v in dim_drift.items() if v < 0],
        key=lambda x: x[1]
    )

    return {
        "model_name": model_name,
        "provider": provider,
        "overall_delta": overall_delta,
        "severity": severity,
        "alert_triggered": alert_triggered,
        "alert_threshold": alert_threshold,
        "direction": "improving" if overall_delta > 0 else "degrading" if overall_delta < 0 else "stable",
        "dimension_drift": dim_drift,
        "worst_dimensions": [{"dimension": d, "delta": v} for d, v in worst_dims[:3]],
        "recommendation": (
            "No action required." if severity == "NONE" else
            f"Monitor {model_name} — {severity} drift detected. Re-evaluate within 24h."
            if severity in ("LOW", "MEDIUM") else
            f"URGENT: {model_name} shows {severity} trust degradation ({overall_delta:.1f} pts). "
            "Rollback or block deployment pending investigation."
        ),
    }


async def _handle_passport_generate(args: dict[str, Any]) -> dict[str, Any]:
    model_name = str(args.get("model_name", "unknown"))
    provider = str(args.get("provider", "unknown"))
    dims: dict[str, Any] = args.get("trust_dimensions", {})

    trust_score = _trust_engine.compute(
        fairness=float(dims.get("fairness", 0.5)),
        privacy=float(dims.get("privacy", 0.5)),
        security=float(dims.get("security", 0.5)),
        robustness=float(dims.get("robustness", 0.5)),
        compliance=float(dims.get("compliance", 0.5)),
        authenticity=float(dims.get("authenticity", 0.5)),
    )

    passport = _passport_gen.generate(
        model_name=model_name,
        provider=provider,
        trust_score=trust_score,
        bias_summary=args.get("bias_summary") or {},
        hallucination_summary=args.get("hallucination_summary") or {},
        security_summary=args.get("security_summary") or {},
        compliance_summary=args.get("compliance_summary") or {},
        privacy_summary=args.get("privacy_summary") or {},
    )

    return {
        **passport.to_dict(),
        "use_case": str(args.get("use_case", "general")),
        "mcp_generated": True,
        "verify_instructions": (
            "Share the passport_id and verification_hash with the receiving party. "
            "They can verify integrity via POST /api/v1/passport/verify on the ResponsibleAI server."
        ),
    }


async def _handle_budget_check(args: dict[str, Any]) -> dict[str, Any]:
    total_spent = float(args.get("total_spent_usd", 0))
    monthly_limit = float(args.get("monthly_limit_usd", 10000.0))
    alert_pct = float(args.get("alert_threshold_pct", 0.80))
    days_elapsed = int(args.get("days_elapsed", 15))
    days_in_month = int(args.get("days_in_month", 30))
    team_breakdown: dict[str, float] = args.get("team_breakdown", {})
    model_breakdown: dict[str, float] = args.get("model_breakdown", {})

    pct_used = (total_spent / monthly_limit * 100) if monthly_limit > 0 else 0.0
    is_exceeded = total_spent > monthly_limit
    alert_triggered = pct_used >= alert_pct * 100

    daily_rate = total_spent / days_elapsed if days_elapsed > 0 else 0
    projected_month = round(daily_rate * days_in_month, 2)
    projected_overage = round(max(0, projected_month - monthly_limit), 2)

    top_teams = sorted(team_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]
    top_models = sorted(model_breakdown.items(), key=lambda x: x[1], reverse=True)[:5]

    status = "EXCEEDED" if is_exceeded else "CRITICAL" if pct_used >= 90 else "WARNING" if alert_triggered else "OK"

    return {
        "status": status,
        "total_spent_usd": round(total_spent, 2),
        "monthly_limit_usd": monthly_limit,
        "percentage_used": round(pct_used, 1),
        "is_exceeded": is_exceeded,
        "alert_triggered": alert_triggered,
        "projection": {
            "daily_rate_usd": round(daily_rate, 2),
            "projected_month_end_usd": projected_month,
            "projected_overage_usd": projected_overage,
            "days_remaining": days_in_month - days_elapsed,
            "remaining_budget_usd": round(max(0, monthly_limit - total_spent), 2),
        },
        "top_teams_by_spend": [{"team": t, "spent_usd": round(v, 2)} for t, v in top_teams],
        "top_models_by_spend": [{"model": m, "spent_usd": round(v, 2)} for m, v in top_models],
        "recommendation": (
            "Budget exceeded — pause non-critical AI workloads immediately." if is_exceeded else
            f"On track to overspend by ${projected_overage:.0f}. Review top spenders." if projected_overage > 0 else
            "Budget on track."
        ),
    }


async def _handle_policy_check(args: dict[str, Any]) -> dict[str, Any]:
    text = str(args.get("text", ""))
    policy: dict[str, Any] = args.get("policy", {})

    violations: list[dict[str, Any]] = []
    passed_rules: list[str] = []

    blocked_topics: list[str] = policy.get("blocked_topics", [])
    for topic in blocked_topics:
        if topic.lower() in text.lower():
            violations.append({
                "rule": "blocked_topic",
                "value": topic,
                "message": f"Blocked topic '{topic}' detected in output.",
                "remediation": f"Remove or rephrase content related to '{topic}'.",
            })
        else:
            passed_rules.append(f"blocked_topic:{topic}")

    required_disclaimers: list[str] = policy.get("required_disclaimers", [])
    for disc in required_disclaimers:
        if disc.lower() not in text.lower():
            violations.append({
                "rule": "missing_disclaimer",
                "value": disc,
                "message": f"Required disclaimer '{disc}' missing from output.",
                "remediation": f"Add '{disc}' to the model output.",
            })
        else:
            passed_rules.append(f"required_disclaimer:{disc}")

    max_length = policy.get("max_length_chars")
    if max_length is not None:
        if len(text) > max_length:
            violations.append({
                "rule": "length_limit",
                "value": len(text),
                "message": f"Output length {len(text)} chars exceeds limit of {max_length}.",
                "remediation": "Truncate or summarise the model output.",
            })
        else:
            passed_rules.append("length_limit")

    blocked_keywords: list[str] = policy.get("blocked_keywords", [])
    for kw in blocked_keywords:
        if kw.lower() in text.lower():
            violations.append({
                "rule": "blocked_keyword",
                "value": kw,
                "message": f"Blocked keyword '{kw}' found in output.",
                "remediation": f"Filter or rephrase to remove '{kw}'.",
            })
        else:
            passed_rules.append(f"blocked_keyword:{kw}")

    if policy.get("require_pii_clean", True):
        scan = _guardrails.scan(text)
        if scan.has_pii:
            categories = list({f.category for f in scan.pii_findings})
            violations.append({
                "rule": "pii_clean",
                "value": categories,
                "message": f"PII detected: {', '.join(categories)}.",
                "remediation": "Redact PII before returning output to end users.",
            })
        else:
            passed_rules.append("pii_clean")

    return {
        "passed": len(violations) == 0,
        "violations": violations,
        "violation_count": len(violations),
        "passed_rules": passed_rules,
        "text_length": len(text),
        "policy_applied": {k: v for k, v in policy.items()},
    }


async def _handle_stream_scan(args: dict[str, Any]) -> dict[str, Any]:
    chunks: list[str] = args.get("chunks", [])
    hard_stop = bool(args.get("hard_stop", True))
    scan_window = int(args.get("scan_window", 10))

    chunk_results: list[dict[str, Any]] = []
    buffer = ""
    total_pii = 0
    total_toxicity = 0
    stopped_at: int | None = None

    for i, chunk in enumerate(chunks):
        buffer += chunk
        scan_triggered = (i > 0 and i % scan_window == 0) or chunk.endswith((".", "!", "?", "\n"))

        pii_detected = False
        toxicity_detected = False
        categories: list[str] = []

        if scan_triggered:
            result = _guardrails.scan(buffer)
            pii_detected = result.has_pii
            toxicity_detected = result.has_toxicity
            if pii_detected:
                total_pii += 1
                categories = [f.category for f in result.pii_findings]
            if toxicity_detected:
                total_toxicity += 1

        should_stop = hard_stop and pii_detected

        chunk_results.append({
            "chunk_index": i,
            "chunk": chunk,
            "scan_triggered": scan_triggered,
            "pii_detected": pii_detected,
            "toxicity_detected": toxicity_detected,
            "pii_categories": categories,
            "should_stop": should_stop,
        })

        if should_stop and stopped_at is None:
            stopped_at = i
            break

    return {
        "chunks_processed": len(chunk_results),
        "total_chunks": len(chunks),
        "stopped_early": stopped_at is not None,
        "stopped_at_chunk": stopped_at,
        "total_pii_detections": total_pii,
        "total_toxicity_detections": total_toxicity,
        "hard_stop_enabled": hard_stop,
        "safe_to_stream": total_pii == 0 and total_toxicity == 0,
        "chunk_results": chunk_results,
        "recommendation": (
            f"Stream halted at chunk {stopped_at} — PII detected. Do not return prior chunks to client."
            if stopped_at is not None else
            "Stream clean — no PII or toxicity detected."
        ),
    }


async def _handle_benchmark(args: dict[str, Any]) -> dict[str, Any]:
    model_name = str(args.get("model_name", "unknown"))
    provider = str(args.get("provider", "unknown"))
    suite_str = str(args.get("suite", "truthfulqa"))
    responses: dict[str, str] = args.get("responses", {})

    try:
        suite = BenchmarkSuite(suite_str)
    except ValueError:
        suite = BenchmarkSuite.TRUTHFULQA

    result = _benchmark_runner.run(model_name, provider, suite, responses)
    return result.to_dict()


async def _handle_benchmark_prompts(args: dict[str, Any]) -> dict[str, Any]:
    suite_str = str(args.get("suite", "truthfulqa"))
    try:
        suite = BenchmarkSuite(suite_str)
    except ValueError:
        suite = BenchmarkSuite.TRUTHFULQA

    prompts = _benchmark_runner.get_prompts(suite)
    return {
        "suite": suite_str,
        "prompt_count": len(prompts),
        "prompts": prompts,
        "instructions": (
            f"Send each prompt to your model and collect responses as {{sample_id: response_text}}. "
            f"Then call rai_benchmark with suite='{suite_str}' and your responses map."
        ),
    }


async def _handle_model_route(args: dict[str, Any]) -> dict[str, Any]:
    task_description = str(args.get("task_description", ""))
    quality = str(args.get("quality_requirement", "balanced"))
    tasks: list[str] = args.get("tasks", [])

    if tasks:
        decisions = _model_router.batch_route(tasks)
        return {
            "batch": True,
            "tasks_routed": len(decisions),
            "results": [d.to_dict() for d in decisions],
            "provider_comparison": _model_router.provider_comparison(),
        }

    if not task_description:
        return {"error": "Provide task_description or tasks array"}

    decision = _model_router.route(task_description, quality_requirement=quality)
    return {
        "batch": False,
        **decision.to_dict(),
        "provider_comparison": _model_router.provider_comparison(),
    }


async def _handle_pii_report(args: dict[str, Any]) -> dict[str, Any]:
    texts: list[str] = args.get("texts", [])
    context = str(args.get("context", "general"))
    include_redacted = bool(args.get("redact", False))

    category_counts: dict[str, int] = {}
    document_results: list[dict[str, Any]] = []
    total_pii = 0
    total_docs_with_pii = 0

    for i, text in enumerate(texts):
        result = _guardrails.scan(text)
        doc_categories: dict[str, int] = {}
        for finding in result.pii_findings:
            doc_categories[finding.category] = doc_categories.get(finding.category, 0) + 1
            category_counts[finding.category] = category_counts.get(finding.category, 0) + 1
            total_pii += 1

        has_pii = result.has_pii
        if has_pii:
            total_docs_with_pii += 1

        doc_entry: dict[str, Any] = {
            "doc_index": i,
            "char_count": len(text),
            "has_pii": has_pii,
            "pii_count": len(result.pii_findings),
            "categories": doc_categories,
        }
        if include_redacted and result.redacted_text:
            doc_entry["redacted_text"] = result.redacted_text
        document_results.append(doc_entry)

    pct_with_pii = (total_docs_with_pii / len(texts) * 100) if texts else 0
    privacy_risk = (
        "CRITICAL" if pct_with_pii >= 50 else
        "HIGH" if pct_with_pii >= 25 else
        "MEDIUM" if pct_with_pii >= 10 else
        "LOW" if total_pii > 0 else
        "NONE"
    )

    _GDPR_CATEGORIES = {"email", "phone", "ssn", "credit_card", "address"}
    found_gdpr = set(category_counts) & _GDPR_CATEGORIES
    gdpr_articles = []
    if found_gdpr:
        gdpr_articles = ["Art. 5 (data minimisation)", "Art. 25 (data protection by design)", "Art. 32 (security of processing)"]

    return {
        "context": context,
        "documents_scanned": len(texts),
        "documents_with_pii": total_docs_with_pii,
        "pct_documents_with_pii": round(pct_with_pii, 1),
        "total_pii_findings": total_pii,
        "privacy_risk_level": privacy_risk,
        "category_breakdown": category_counts,
        "gdpr_relevant_categories": list(found_gdpr),
        "applicable_gdpr_articles": gdpr_articles,
        "remediation": {
            "immediate": "Redact all PII before storing or transmitting this data." if total_pii > 0 else "No immediate action required.",
            "process": "Implement automated PII scanning in your data pipeline using the rai_scan guardrail.",
            "audit": "Document PII findings in your GDPR Records of Processing Activities (RoPA).",
        },
        "document_results": document_results,
    }


async def _handle_incident_log(args: dict[str, Any]) -> dict[str, Any]:
    record = build_incident_record(
        incident_type=str(args.get("incident_type", "other")),
        severity=str(args.get("severity", "medium")),
        model_name=str(args.get("model_name", "unknown")),
        provider=str(args.get("provider", "unknown")),
        description=str(args.get("description", "")),
        evidence=args.get("evidence", {}),
        mitigated=bool(args.get("mitigated", False)),
        source="mcp_tool",
    )
    record["persist_instructions"] = (
        "This record is ephemeral in MCP context — the MCP server has no "
        "direct database connection of its own. To persist it, POST this "
        "record (or just incident_type/severity/model_name/provider/"
        "description/evidence/mitigated) to POST /api/incidents on the "
        "ResponsibleAI REST server, which is a real, wired endpoint backed "
        "by the incidents table (responsibleai.db.incident_repository). "
        "See compliance/INCIDENT_RESPONSE_RUNBOOK.md's Phase 1 for when to "
        "do this."
    )
    return record


async def _handle_eu_ai_act_classify(args: dict[str, Any]) -> dict[str, Any]:
    system_description = str(args.get("system_description", ""))
    sector = str(args.get("deployment_sector", "general_purpose"))
    affects_persons = bool(args.get("affects_natural_persons", True))
    fully_automated = bool(args.get("is_fully_automated", False))
    biometric = bool(args.get("processes_biometric_data", False))
    emotion_recog = bool(args.get("used_for_emotion_recognition", False))
    real_time_biometric = bool(args.get("real_time_remote_biometric", False))
    social_scoring = bool(args.get("social_scoring_purpose", False))
    trust_overall = float(args.get("trust_score_overall", 70))

    # Unacceptable risk (prohibited)
    if real_time_biometric or social_scoring:
        risk_tier = "UNACCEPTABLE"
        articles = ["Article 5 — Prohibited AI Practices"]
        required_actions = [
            "HALT: This system is categorically prohibited under the EU AI Act.",
            "Cease deployment immediately and consult legal counsel.",
            "Document decommissioning plan within 30 days of Act enforcement.",
        ]
        conformity = "PROHIBITED — No conformity path available."
    elif sector in ("biometric_identification",) or (biometric and fully_automated and affects_persons):
        risk_tier = "HIGH"
        articles = ["Article 6", "Annex III — High-Risk AI Systems", "Article 10 (data governance)", "Article 12 (logging)", "Article 13 (transparency)"]
        required_actions = [
            "Register system in EU database before deployment (Article 51).",
            "Conduct fundamental rights impact assessment.",
            "Implement conformity assessment procedure (Article 43).",
            "Appoint EU representative if based outside EU.",
            "Maintain technical documentation (Annex IV) for 10 years.",
        ]
        conformity = "THIRD-PARTY CONFORMITY ASSESSMENT required (Annex VI)."
    elif sector in ("critical_infrastructure", "education", "employment", "essential_services", "law_enforcement", "migration", "administration_of_justice", "democratic_processes"):
        risk_tier = "HIGH"
        articles = ["Article 6(2)", f"Annex III — Point applicable to {sector}", "Article 9 (risk management)", "Article 14 (human oversight)", "Article 15 (accuracy/robustness)"]
        required_actions = [
            "Implement risk management system (Article 9).",
            "Ensure human oversight measures (Article 14).",
            "Conduct conformity assessment before market placement.",
            "Affix CE marking after conformity assessment.",
            f"Register in EU AI database (Article 51) — {sector} sector.",
        ]
        conformity = "CONFORMITY ASSESSMENT required — internal or third-party per Annex VI."
    elif emotion_recog or biometric:
        risk_tier = "LIMITED"
        articles = ["Article 52 — Transparency Obligations"]
        required_actions = [
            "Notify users they are interacting with an AI system.",
            "Disclose emotion recognition or biometric categorisation capability.",
            "Implement transparency measures in UI/UX.",
        ]
        conformity = "SELF-DECLARATION sufficient. No third-party assessment required."
    else:
        risk_tier = "MINIMAL"
        articles = ["Article 69 — Voluntary Codes of Conduct"]
        required_actions = [
            "No mandatory requirements under EU AI Act.",
            "Consider voluntary adherence to codes of conduct.",
            "Maintain basic AI literacy among staff (Article 4).",
        ]
        conformity = "MINIMAL — Voluntary measures only."

    trust_note = ""
    if trust_overall < 60 and risk_tier in ("HIGH", "MINIMAL", "LIMITED"):
        trust_note = f" WARNING: Trust Score {trust_overall:.0f}/100 is below 60 — address governance gaps before deployment."

    return {
        "risk_tier": risk_tier,
        "deployment_sector": sector,
        "system_description": system_description[:200],
        "applicable_articles": articles,
        "conformity_assessment": conformity + trust_note,
        "required_actions": required_actions,
        "enforcement_date": "August 2, 2026 (high-risk provisions)",
        "penalties": {
            "prohibited_violations": "Up to €35M or 7% of global annual turnover",
            "high_risk_violations": "Up to €15M or 3% of global annual turnover",
            "misleading_information": "Up to €7.5M or 1.5% of global annual turnover",
        },
        "input_flags": {
            "affects_natural_persons": affects_persons,
            "is_fully_automated": fully_automated,
            "processes_biometric_data": biometric,
            "used_for_emotion_recognition": emotion_recog,
            "real_time_remote_biometric": real_time_biometric,
            "social_scoring_purpose": social_scoring,
            "trust_score_overall": trust_overall,
        },
    }


async def _handle_iso42001_gap(args: dict[str, Any]) -> dict[str, Any]:
    org_name = str(args.get("org_name", "Organisation"))
    trust_score = float(args.get("trust_score_overall", 70))
    compliance_maturity = float(args.get("compliance_maturity", 0.5))

    clauses = {
        "4_context":          ("Context of the Organisation",       bool(args.get("has_ai_policy", False))),
        "5_leadership":       ("Leadership and Commitment",          bool(args.get("has_ai_policy", False))),
        "6_planning":         ("Planning (Risk and Opportunity)",    bool(args.get("has_risk_assessment", False))),
        "7_support":          ("Support (Resources, Awareness)",     bool(args.get("has_training_programme", False))),
        "8_operation":        ("Operation (AI Development/Deploy)",  bool(args.get("has_impact_assessment", False))),
        "8_data":             ("Operation — Data Governance",        bool(args.get("has_data_governance", False))),
        "9_evaluation":       ("Performance Evaluation",             bool(args.get("has_monitoring_metrics", False))),
        "9_audit":            ("Internal Audit",                     bool(args.get("has_audit_trail", False))),
        "10_improvement":     ("Improvement — Corrective Action",    bool(args.get("has_incident_process", False))),
        "supply_chain":       ("Annex B — Supply Chain Controls",    bool(args.get("has_supplier_controls", False))),
        "continual_improve":  ("Annex C — Continual Improvement",   bool(args.get("has_continual_improvement", False))),
    }

    met = [(k, v[0]) for k, v in clauses.items() if v[1]]
    gaps = [(k, v[0]) for k, v in clauses.items() if not v[1]]

    maturity_pct = round(len(met) / len(clauses) * 100, 0)
    gap_count = len(gaps)

    cert_ready = gap_count <= 2 and trust_score >= 70 and compliance_maturity >= 0.7
    estimated_months = max(1, gap_count * 2)

    priority_gaps = gaps[:3]

    return {
        "org_name": org_name,
        "standard": "ISO/IEC 42001:2023",
        "maturity_percentage": maturity_pct,
        "clauses_met": len(met),
        "clauses_total": len(clauses),
        "gap_count": gap_count,
        "certification_ready": cert_ready,
        "estimated_remediation_months": estimated_months,
        "met_clauses": [{"id": k, "name": v[0]} for k, v in clauses.items() if v[1]],
        "gap_findings": [
            {
                "clause_id": k,
                "clause_name": n,
                "status": "GAP",
                "remediation": (
                    f"Implement {n} framework. Assign owner and set 90-day milestone."
                ),
            }
            for k, n in gaps
        ],
        "priority_actions": [
            f"PRIORITY {i+1}: Close gap in '{n}' ({k})" for i, (k, n) in enumerate(priority_gaps)
        ],
        "trust_score_alignment": {
            "score": trust_score,
            "aligned": trust_score >= 70,
            "note": "Trust Score >= 70 supports ISO 42001 Clause 9 performance evaluation evidence." if trust_score >= 70 else
                    "Improve Trust Score to >= 70 before pursuing certification.",
        },
        "certification_path": (
            "Engage an accredited CB (Certification Body) for stage 1 audit."
            if cert_ready else
            f"Close {gap_count} gaps first. Estimated {estimated_months} months to certification readiness."
        ),
    }


async def _handle_executive_summary(args: dict[str, Any]) -> dict[str, Any]:
    org_name = str(args.get("org_name", "Organisation"))
    period = str(args.get("report_period", "Q2 2026"))
    models_eval = int(args.get("models_evaluated", 0))
    avg_trust = float(args.get("avg_trust_score", 75))
    compliance_score = float(args.get("compliance_score", 70))
    total_cost = float(args.get("total_cost_usd", 0))
    budget = float(args.get("monthly_budget_usd", 10000))
    open_incidents = int(args.get("open_incidents", 0))
    drift_alerts = int(args.get("drift_alerts", 0))
    bias_failures = int(args.get("bias_failures", 0))
    frameworks: list[str] = args.get("frameworks", ["NIST_AI_RMF"])
    top_risks: list[str] = args.get("top_risks", [])

    def _rag(value: float, green: float, amber: float) -> str:
        return "GREEN" if value >= green else "AMBER" if value >= amber else "RED"

    trust_rag = _rag(avg_trust, 80, 60)
    compliance_rag = _rag(compliance_score, 75, 55)
    budget_pct = (total_cost / budget * 100) if budget > 0 else 0
    cost_rag = "GREEN" if budget_pct <= 80 else "AMBER" if budget_pct <= 100 else "RED"
    incident_rag = "GREEN" if open_incidents == 0 else "AMBER" if open_incidents <= 3 else "RED"

    trust_grade = (
        "A" if avg_trust >= 90 else
        "B" if avg_trust >= 80 else
        "C" if avg_trust >= 70 else
        "D" if avg_trust >= 60 else "F"
    )

    overall_posture = (
        "STRONG" if all(r == "GREEN" for r in [trust_rag, compliance_rag, cost_rag, incident_rag]) else
        "ADEQUATE" if "RED" not in [trust_rag, compliance_rag, cost_rag, incident_rag] else
        "AT RISK"
    )

    return {
        "org_name": org_name,
        "report_period": period,
        "generated_at": datetime.now(UTC).isoformat(),
        "overall_posture": overall_posture,
        "executive_headline": (
            f"{org_name} AI governance is {overall_posture} for {period}. "
            f"{models_eval} model(s) evaluated. Trust grade: {trust_grade}. "
            f"{'No open incidents.' if open_incidents == 0 else f'{open_incidents} open incident(s) require attention.'}"
        ),
        "rag_dashboard": {
            "trust_posture":      {"status": trust_rag,      "value": f"{avg_trust:.0f}/100 (Grade {trust_grade})"},
            "compliance_posture": {"status": compliance_rag, "value": f"{compliance_score:.0f}/100"},
            "cost_control":       {"status": cost_rag,       "value": f"${total_cost:,.0f} of ${budget:,.0f} ({budget_pct:.0f}%)"},
            "incident_status":    {"status": incident_rag,   "value": f"{open_incidents} open incidents"},
        },
        "key_metrics": {
            "models_evaluated": models_eval,
            "avg_trust_score": avg_trust,
            "avg_trust_grade": trust_grade,
            "compliance_score": compliance_score,
            "active_frameworks": frameworks,
            "drift_alerts": drift_alerts,
            "bias_failures": bias_failures,
            "open_incidents": open_incidents,
            "ai_spend_usd": round(total_cost, 2),
            "budget_utilisation_pct": round(budget_pct, 1),
        },
        "top_risks": top_risks or (
            ["No specific risks identified — maintain current controls."]
            if overall_posture == "STRONG" else
            ["Review open incidents", "Address compliance gaps", "Monitor trust score drift"]
        ),
        "recommended_board_actions": (
            ["Approve AI governance programme expansion.", "Set next review for following quarter."]
            if overall_posture == "STRONG" else
            ["Review and close open incidents.", "Increase compliance investment.", "Commission external audit if posture remains AT RISK."]
        ),
    }


async def _handle_org_status(args: dict[str, Any]) -> dict[str, Any]:
    org_name = str(args.get("org_name", "default"))
    model_grades: dict[str, str] = args.get("model_grades", {})
    active_frameworks: list[str] = args.get("active_frameworks", [])
    open_incidents = int(args.get("open_incidents", 0))
    budget_pct = float(args.get("budget_pct_used", 0))
    drift_alerts = int(args.get("drift_alerts", 0))

    grade_dist: dict[str, int] = {"A": 0, "B": 0, "C": 0, "D": 0, "F": 0}
    for grade in model_grades.values():
        if grade.upper() in grade_dist:
            grade_dist[grade.upper()] += 1

    passing = grade_dist["A"] + grade_dist["B"] + grade_dist["C"]
    failing = grade_dist["D"] + grade_dist["F"]

    health = (
        "HEALTHY" if open_incidents == 0 and drift_alerts == 0 and failing == 0 else
        "DEGRADED" if open_incidents <= 2 and drift_alerts <= 1 else
        "AT_RISK"
    )

    return {
        "org_name": org_name,
        "snapshot_time": datetime.now(UTC).isoformat(),
        "health_status": health,
        "models": {
            "total": len(model_grades),
            "grade_distribution": grade_dist,
            "passing": passing,
            "failing": failing,
            "models": model_grades,
        },
        "compliance": {
            "active_frameworks": active_frameworks,
            "framework_count": len(active_frameworks),
        },
        "operations": {
            "open_incidents": open_incidents,
            "drift_alerts": drift_alerts,
            "budget_pct_used": round(budget_pct, 1),
            "budget_status": "OK" if budget_pct <= 80 else "WARNING" if budget_pct <= 100 else "EXCEEDED",
        },
        "mcp_capabilities": {
            "tools_available": len(TOOL_DEFS),
            "version": "1.2.0",
        },
    }


async def _handle_webhook_status(args: dict[str, Any]) -> dict[str, Any]:
    total = int(args.get("total_deliveries", 0))
    successful = int(args.get("successful", 0))
    failed = int(args.get("failed", 0))
    dlq_count = int(args.get("dead_letter_count", 0))
    avg_latency = float(args.get("avg_latency_ms", 0))
    endpoints: list[dict[str, Any]] = args.get("endpoints", [])

    success_rate = (successful / total * 100) if total > 0 else 100.0
    health_grade = (
        "A" if success_rate >= 99 else
        "B" if success_rate >= 95 else
        "C" if success_rate >= 90 else
        "D" if success_rate >= 80 else
        "F"
    )
    health_status = "HEALTHY" if health_grade in ("A", "B") else "DEGRADED" if health_grade == "C" else "UNHEALTHY"

    problematic_endpoints = [
        ep for ep in endpoints
        if ep.get("consecutive_failures", 0) >= 3 or ep.get("success_rate", 1.0) < 0.90
    ]

    return {
        "health_status": health_status,
        "health_grade": health_grade,
        "delivery_stats": {
            "total": total,
            "successful": successful,
            "failed": failed,
            "success_rate_pct": round(success_rate, 2),
            "avg_latency_ms": round(avg_latency, 1),
        },
        "dead_letter_queue": {
            "count": dlq_count,
            "status": "EMPTY" if dlq_count == 0 else "WARNING" if dlq_count <= 10 else "CRITICAL",
            "action_required": dlq_count > 0,
        },
        "endpoint_count": len(endpoints),
        "problematic_endpoints": [
            {
                "url": ep.get("url", "unknown"),
                "success_rate": ep.get("success_rate"),
                "consecutive_failures": ep.get("consecutive_failures", 0),
            }
            for ep in problematic_endpoints
        ],
        "recommendations": [
            r for r in [
                "Investigate and replay dead-letter queue events." if dlq_count > 0 else None,
                f"Fix {len(problematic_endpoints)} endpoint(s) with high failure rates." if problematic_endpoints else None,
                "Review webhook delivery logs for error patterns." if failed > 0 else None,
                "Enable webhook retry with exponential backoff if not already configured." if health_grade in ("D", "F") else None,
                "All webhook endpoints healthy." if health_status == "HEALTHY" and dlq_count == 0 else None,
            ]
            if r
        ],
        "siem_integration": {
            "recommended_events": ["trust_score_alert", "bias_detected", "pii_leak", "jailbreak_attempt", "drift_alert"],
            "webhook_status": health_status,
        },
    }
