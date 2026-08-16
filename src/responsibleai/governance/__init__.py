"""WhitePact runtime governance core — SPEC.md Section 2's pipeline
(Agent -> Action -> Policy/Authority -> Decision), Phase 8 of
MIGRATION_WHITEPACT_V2.md. See governance/models.py and
governance/gateway.py module docstrings for what is and is not
implemented yet; SPEC.md remains the authoritative architecture
document."""

from __future__ import annotations

from responsibleai.governance.autonomy_budget import (
    AutonomyBudgetPolicy,
    recent_autonomous_action_count,
)
from responsibleai.governance.ceiling import OrgAuthorityCeiling
from responsibleai.governance.delegation import DelegationRecord
from responsibleai.governance.evidence_bundle import (
    BundleVerificationResult,
    EvidenceBundle,
    build_evidence_bundle,
    verify_evidence_bundle,
)
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
from responsibleai.governance.memory_firewall import MemoryFirewallResult, scan_memory_write
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    AuthorityContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
    validate_attenuation,
)
from responsibleai.governance.policy import Policy, PolicyMatch, PolicyRule
from responsibleai.governance.quarantine import (
    QUARANTINE_VIOLATION_THRESHOLD,
    QUARANTINE_WINDOW_MINUTES,
    recent_violation_count,
)
from responsibleai.governance.reason_codes import ReasonCode, format_reason
from responsibleai.governance.risk import RiskTier, classify_action_risk
from responsibleai.governance.trust_integration import enrich_agent_trust_state
from responsibleai.governance.workflow import (
    TimestampedAction,
    WorkflowSequenceRule,
    check_composition_violation,
)

__all__ = [
    "ActionRequest",
    "AgentContext",
    "AuthorityContext",
    "AutonomyBudgetPolicy",
    "AuthorizationActionMismatchError",
    "AuthorizationAlreadyConsumedError",
    "AuthorizationExpiredError",
    "AuthorizationOrganizationMismatchError",
    "BundleVerificationResult",
    "DecisionNotExecutableError",
    "DecisionResult",
    "DelegationRecord",
    "EvidenceBundle",
    "ExecutionAuthorization",
    "ExecutionNotAuthorizedError",
    "Executor",
    "GovernanceDecision",
    "IdentityContext",
    "InternalToolExecutor",
    "MemoryFirewallResult",
    "OrgAuthorityCeiling",
    "Policy",
    "PolicyMatch",
    "PolicyRule",
    "QUARANTINE_VIOLATION_THRESHOLD",
    "QUARANTINE_WINDOW_MINUTES",
    "ReasonCode",
    "RiskTier",
    "TimestampedAction",
    "WhitePactRuntimeGateway",
    "WorkflowSequenceRule",
    "authorize_execution",
    "build_evidence_bundle",
    "check_composition_violation",
    "classify_action_risk",
    "enrich_agent_trust_state",
    "format_reason",
    "recent_autonomous_action_count",
    "recent_violation_count",
    "scan_memory_write",
    "validate_attenuation",
    "verify_evidence_bundle",
]
