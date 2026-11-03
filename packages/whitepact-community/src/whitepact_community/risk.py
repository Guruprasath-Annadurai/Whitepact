"""Risk-tier classification for community-local action types."""

from __future__ import annotations

from enum import StrEnum


class RiskTier(StrEnum):
    MINIMAL = "MINIMAL"
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"


# Only tools Community Core actually implements. Unknown targets default
# to MEDIUM (unclassified is not verified-safe).
COMMUNITY_TOOL_RISK: dict[str, RiskTier] = {
    "local_echo": RiskTier.MINIMAL,
    "local_health": RiskTier.MINIMAL,
    "policy_evaluate": RiskTier.LOW,
    "governed_local_action": RiskTier.LOW,
}

_DEFAULT_TIER = RiskTier.MEDIUM


def classify_action_risk(action_type: str, target: str) -> RiskTier:
    if target in COMMUNITY_TOOL_RISK:
        return COMMUNITY_TOOL_RISK[target]
    if action_type in COMMUNITY_TOOL_RISK:
        return COMMUNITY_TOOL_RISK[action_type]
    return _DEFAULT_TIER
