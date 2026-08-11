"""Tests for risk-tiered routing (SPEC.md Section 4, Phase 9):
`governance/risk.py`'s tool -> tier table and `classify_action_risk()`.
"""

from __future__ import annotations

from responsibleai.governance.risk import TOOL_RISK_TIERS, RiskTier, classify_action_risk
from responsibleai.mcp.tools import TOOL_DEFS


class TestToolRiskTierCoverage:
    """Drift guard: SPEC.md Section 4's table must stay in sync with the
    real, live tool list. This is exactly the kind of check that catches
    a new tool being added without anyone updating the risk table."""

    def test_every_registered_tool_has_a_tier(self) -> None:
        tool_names = {t.name for t in TOOL_DEFS}
        missing = tool_names - TOOL_RISK_TIERS.keys()
        assert not missing, f"Tools with no risk tier assigned: {sorted(missing)}"

    def test_no_stale_tiered_tools(self) -> None:
        tool_names = {t.name for t in TOOL_DEFS}
        stale = TOOL_RISK_TIERS.keys() - tool_names
        assert not stale, f"Risk tiers assigned to tools that no longer exist: {sorted(stale)}"

    def test_tier_count_matches_tool_count(self) -> None:
        assert len(TOOL_RISK_TIERS) == len(TOOL_DEFS) == 27


class TestClassifyActionRisk:
    def test_identity_health_tools_are_minimal(self) -> None:
        assert classify_action_risk("mcp_tool_call", "rai_health") == RiskTier.MINIMAL
        assert classify_action_risk("mcp_tool_call", "rai_org_status") == RiskTier.MINIMAL

    def test_deterministic_scan_tools_are_low(self) -> None:
        assert classify_action_risk("mcp_tool_call", "rai_scan") == RiskTier.LOW

    def test_compliance_tools_are_medium(self) -> None:
        assert classify_action_risk("mcp_tool_call", "rai_compliance") == RiskTier.MEDIUM

    def test_probabilistic_eval_tools_are_high(self) -> None:
        assert classify_action_risk("mcp_tool_call", "rai_hallucination") == RiskTier.HIGH
        assert classify_action_risk("mcp_tool_call", "rai_bias_evaluate") == RiskTier.HIGH

    def test_unknown_tool_defaults_to_medium_not_minimal(self) -> None:
        """Unclassified must never silently read as low-risk."""
        assert classify_action_risk("mcp_tool_call", "some_future_tool") == RiskTier.MEDIUM

    def test_non_mcp_action_type_defaults_to_medium(self) -> None:
        assert classify_action_risk("api_call", "POST /api/webhooks") == RiskTier.MEDIUM
        assert classify_action_risk("transaction", "stripe") == RiskTier.MEDIUM
