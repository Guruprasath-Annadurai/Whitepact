"""WhitePact runtime governance core — SPEC.md Section 2's pipeline
(Agent -> Action -> Policy/Authority -> Decision), Phase 8 of
MIGRATION_WHITEPACT_V2.md. See governance/models.py and
governance/gateway.py module docstrings for what is and is not
implemented yet; SPEC.md remains the authoritative architecture
document."""

from __future__ import annotations

from responsibleai.governance.execution import (
    AuthorizationActionMismatchError,
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationOrganizationMismatchError,
    DecisionNotExecutableError,
    ExecutionAuthorization,
    ExecutionNotAuthorizedError,
    Executor,
    InternalToolExecutor,
    authorize_execution,
)
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
from responsibleai.governance.quarantine import (
    QUARANTINE_VIOLATION_THRESHOLD,
    QUARANTINE_WINDOW_MINUTES,
    recent_violation_count,
)
from responsibleai.governance.risk import RiskTier, classify_action_risk
from responsibleai.governance.trust_integration import enrich_agent_trust_state

__all__ = [
    "ActionRequest",
    "AgentContext",
    "AuthorityContext",
    "AuthorizationActionMismatchError",
    "AuthorizationAlreadyConsumedError",
    "AuthorizationExpiredError",
    "AuthorizationOrganizationMismatchError",
    "DecisionNotExecutableError",
    "DecisionResult",
    "ExecutionAuthorization",
    "ExecutionNotAuthorizedError",
    "Executor",
    "GovernanceDecision",
    "IdentityContext",
    "InternalToolExecutor",
    "Policy",
    "PolicyMatch",
    "PolicyRule",
    "QUARANTINE_VIOLATION_THRESHOLD",
    "QUARANTINE_WINDOW_MINUTES",
    "RiskTier",
    "WhitePactRuntimeGateway",
    "authorize_execution",
    "classify_action_risk",
    "enrich_agent_trust_state",
    "recent_violation_count",
]
