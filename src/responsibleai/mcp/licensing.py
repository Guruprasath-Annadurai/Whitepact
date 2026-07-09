"""Tool tier gating for the ResponsibleAI MCP server — open-core monetization.

Self-hosted stdio usage (no org context) is always unrestricted — this only
gates the hosted HTTP/SSE MCP transport, where each request carries a Bearer
token resolved to an OrgContext with a billing Plan.

Tiers
-----
FREE       — self-hosted default. Core governance primitives.
PRO        — hosted subscription. Adds bias/drift/routing/streaming tooling.
ENTERPRISE — hosted subscription. Adds compliance frameworks, executive
             reporting, AI Passport, and incident/SIEM tooling.
"""

from __future__ import annotations

from responsibleai.rbac.models import Plan

# Tools available on the FREE tier (also the full set for self-hosted/stdio use).
FREE_TOOLS: frozenset[str] = frozenset({
    "rai_scan",
    "rai_trust_score",
    "rai_compliance",
    "rai_hallucination",
    "rai_cost_estimate",
    "rai_redteam_payloads",
    "rai_redteam_analyze",
    "rai_compare_models",
    "rai_audit_summary",
    "rai_health",
})

# Additional tools unlocked at PRO.
PRO_TOOLS: frozenset[str] = frozenset({
    "rai_bias_evaluate",
    "rai_drift_check",
    "rai_budget_check",
    "rai_policy_check",
    "rai_stream_scan",
    "rai_benchmark",
    "rai_benchmark_prompts",
    "rai_model_route",
    "rai_pii_report",
})

# Additional tools unlocked at ENTERPRISE (superset of PRO + FREE).
ENTERPRISE_TOOLS: frozenset[str] = frozenset({
    "rai_passport_generate",
    "rai_incident_log",
    "rai_eu_ai_act_classify",
    "rai_iso42001_gap",
    "rai_executive_summary",
    "rai_org_status",
    "rai_webhook_status",
})

_TIER_ORDER: dict[Plan, int] = {Plan.FREE: 0, Plan.PRO: 1, Plan.ENTERPRISE: 2}


def tool_tier(tool_name: str) -> Plan:
    """Return the minimum Plan required to call *tool_name*."""
    if tool_name in ENTERPRISE_TOOLS:
        return Plan.ENTERPRISE
    if tool_name in PRO_TOOLS:
        return Plan.PRO
    return Plan.FREE


def is_allowed(tool_name: str, plan: Plan) -> bool:
    """Return True if *plan* meets or exceeds the tool's required tier."""
    return _TIER_ORDER.get(plan, 0) >= _TIER_ORDER.get(tool_tier(tool_name), 0)


def upgrade_message(tool_name: str, current_plan: Plan) -> str:
    required = tool_tier(tool_name)
    return (
        f"'{tool_name}' requires the {required.value} plan "
        f"(current plan: {current_plan.value}). "
        f"Upgrade at https://responsibleai.dev/pricing or call rai_org_status "
        f"to check your organisation's current tier."
    )


def plan_catalog() -> dict[str, object]:
    """Return the full tier → tools mapping, for display in pricing pages / rai://billing/plans."""
    return {
        "FREE": {
            "price_usd_monthly": 0,
            "tools": sorted(FREE_TOOLS),
            "description": "Self-hosted, unlimited local use. Core trust scoring, guardrails, compliance, red team.",
        },
        "PRO": {
            "price_usd_monthly": 199,
            "tools": sorted(FREE_TOOLS | PRO_TOOLS),
            "description": "Hosted MCP endpoint. Adds bias evaluation, drift monitoring, model routing, PII auditing, streaming guardrails.",
        },
        "ENTERPRISE": {
            "price_usd_monthly": 999,
            "tools": sorted(FREE_TOOLS | PRO_TOOLS | ENTERPRISE_TOOLS),
            "description": "Adds AI Passport, EU AI Act / ISO 42001 compliance automation, executive reporting, incident/SIEM logging, SSO, audit export.",
            "contact_for_custom_pricing": True,
        },
    }
