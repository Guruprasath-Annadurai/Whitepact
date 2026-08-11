"""WhitePact runtime governance core — SPEC.md Section 2's pipeline
(Agent -> Action -> Policy/Authority -> Decision), Phase 8 of
MIGRATION_WHITEPACT_V2.md. See governance/models.py and
governance/gateway.py module docstrings for what is and is not
implemented yet; SPEC.md remains the authoritative architecture
document."""

from __future__ import annotations

from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.policy import Policy, PolicyMatch, PolicyRule
from responsibleai.governance.risk import RiskTier, classify_action_risk

__all__ = [
    "ActionRequest",
    "AgentContext",
    "AuthorityContext",
    "DecisionResult",
    "GovernanceDecision",
    "IdentityContext",
    "Policy",
    "PolicyMatch",
    "PolicyRule",
    "RiskTier",
    "WhitePactRuntimeGateway",
    "classify_action_risk",
]
