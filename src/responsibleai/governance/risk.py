"""Risk-tiered routing — SPEC.md Section 4's "proposed tiering for
Phase 9's risk router", made executable. That section explicitly
recorded the tool→tier mapping below "so the tiering decision is made
once, deliberately, and reviewably, rather than invented ad hoc when
Phase 9 starts" — this module is that decision becoming code, not a new
one made up here.

``TOOL_RISK_TIERS`` is deliberately hardcoded (not derived by importing
``mcp.tools.TOOL_DEFS``) to keep this package dependency-free from the
MCP layer, consistent with the target architecture's direction: MCP
tools are intelligence the governance pipeline calls *into*
(SPEC.md Section 4), not the other way around.
``tests/test_governance_risk.py`` verifies this mapping stays in sync
with the real tool list by importing ``TOOL_DEFS`` itself.
"""

from __future__ import annotations

from enum import StrEnum


class RiskTier(StrEnum):
    """Coarse severity, not the five-way `GovernanceDecision` — a
    classification input to a decision, not a decision itself."""

    MINIMAL = "MINIMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# SPEC.md Section 4's table, tier-for-tier:
#   Identity/health (near-zero cost)              -> MINIMAL
#   Deterministic scan (fast, no LLM)              -> LOW
#   Trust/cost lookups (cached-friendly)           -> LOW
#   Compliance classification                      -> MEDIUM
#   Record-keeping (writes)                        -> MEDIUM
#   Deeper/probabilistic evaluation                -> HIGH
TOOL_RISK_TIERS: dict[str, RiskTier] = {
    # Identity/health
    "rai_health": RiskTier.MINIMAL,
    "rai_audit_summary": RiskTier.MINIMAL,
    "rai_org_status": RiskTier.MINIMAL,
    # Deterministic scan
    "rai_scan": RiskTier.LOW,
    "rai_pii_report": RiskTier.LOW,
    "rai_policy_check": RiskTier.LOW,
    "rai_stream_scan": RiskTier.LOW,
    "rai_memory_write_check": RiskTier.LOW,
    "rai_memory_read_check": RiskTier.LOW,
    "rai_causal_influence_check": RiskTier.LOW,
    # Trust/cost lookups
    "rai_trust_score": RiskTier.LOW,
    "rai_check_trust": RiskTier.LOW,
    "rai_cost_estimate": RiskTier.LOW,
    "rai_budget_check": RiskTier.LOW,
    "rai_model_route": RiskTier.LOW,
    # Compliance classification
    "rai_compliance": RiskTier.MEDIUM,
    "rai_eu_ai_act_classify": RiskTier.MEDIUM,
    "rai_iso42001_gap": RiskTier.MEDIUM,
    # Record-keeping (writes) -- elevated regardless of compute cost,
    # since these persist data rather than just reading/scoring it.
    "rai_incident_log": RiskTier.MEDIUM,
    "rai_passport_generate": RiskTier.MEDIUM,
    "rai_executive_summary": RiskTier.MEDIUM,
    "rai_webhook_status": RiskTier.MEDIUM,
    # Deeper/probabilistic evaluation
    "rai_hallucination": RiskTier.HIGH,
    "rai_bias_evaluate": RiskTier.HIGH,
    "rai_drift_check": RiskTier.HIGH,
    "rai_redteam_payloads": RiskTier.HIGH,
    "rai_redteam_analyze": RiskTier.HIGH,
    "rai_compare_models": RiskTier.HIGH,
    "rai_benchmark": RiskTier.HIGH,
    "rai_benchmark_prompts": RiskTier.HIGH,
}

# The action_type governance/upstream_executor.py's UpstreamMCPExecutor
# uses -- defined here, not there, so this module (imported by
# governance/models.py) never has to import upstream_executor.py
# (which imports governance/execution.py, which imports models.py --
# upstream_executor importing this constant from here is the only
# direction that doesn't cycle).
UPSTREAM_ACTION_TYPE = "upstream_mcp_tool_call"

# Non-MCP action types (SPEC.md Section 3.4's other action_type values:
# "api_call", "transaction", "db_operation", ...) have no tool-name table
# to classify by. MEDIUM, not MINIMAL, is the honest default -- treating
# an unrecognized action as low-risk by default would be a silent,
# unreviewed policy decision, not a neutral one.
_DEFAULT_TIER = RiskTier.MEDIUM


def classify_action_risk(action_type: str, target: str) -> RiskTier:
    """The router: SPEC.md Section 2's "Risk (classified severity of the
    action)" pipeline stage. `target` is looked up in `TOOL_RISK_TIERS`
    whenever `action_type == "mcp_tool_call"` (the literal convention
    this module originally assumed) *or* whenever `target` itself is a
    recognized tool name — the second branch exists because
    `mcp/governance_integration.py`'s real, live `apply_governance()`
    builds `ActionRequest(action_type=name, target=name, ...)` for a
    tool call (the tool name in both fields, never the literal string
    `"mcp_tool_call"`), so requiring an exact `action_type` match here
    silently forced every live governed call through the MEDIUM
    default regardless of its real tier — `TOOL_RISK_TIERS` was dead
    code on the one path that matters until this fix. An unrecognized
    tool name (a new tool added without updating this table, or a
    genuinely unknown one) still gets the same honest MEDIUM default,
    not MINIMAL — unclassified is not the same claim as verified-safe.
    """
    if action_type == UPSTREAM_ACTION_TYPE:
        # A call proxied to a third-party MCP server (governance/
        # upstream_executor.py) is inherently less verified than this
        # platform's own 27 tools -- the honest default is the top
        # tier, not the same MEDIUM given to a merely-unrecognized
        # internal action_type. Registration itself is the approval
        # gate (ReasonCode.UNAPPROVED_MCP_SERVER); this is a
        # risk-tiering decision, not a substitute for that gate.
        return RiskTier.HIGH
    if action_type == "mcp_tool_call" or target in TOOL_RISK_TIERS:
        return TOOL_RISK_TIERS.get(target, _DEFAULT_TIER)
    return _DEFAULT_TIER
