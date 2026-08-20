"""Async database layer — supports SQLite (default) and PostgreSQL."""

from responsibleai.db.approval_repository import (
    AlreadyVotedError,
    ApprovalActionMismatchError,
    ApprovalAlreadyResolvedError,
    ApprovalExpiredError,
    ApprovalNotApprovedError,
    ApprovalNotFoundError,
    ApprovalRepository,
    SelfApprovalError,
)
from responsibleai.db.audit_repository import AuditRepository
from responsibleai.db.credential_issuance_repository import CredentialIssuanceRepository
from responsibleai.db.delegation_repository import (
    DelegationEscalationError,
    DelegationNotFoundError,
    DelegationRepository,
)
from responsibleai.db.engine import DatabaseEngine, create_engine
from responsibleai.db.eval_repository import EvalRepository
from responsibleai.db.evidence_repository import EvidenceRepository
from responsibleai.db.incident_repository import IncidentRepository
from responsibleai.db.leaderboard_repository import LeaderboardRepository
from responsibleai.db.mcp_usage_repository import McpUsageRepository
from responsibleai.db.org_authority_ceiling_repository import OrgAuthorityCeilingRepository
from responsibleai.db.org_autonomy_budget_repository import OrgAutonomyBudgetRepository
from responsibleai.db.org_repository import OrgRepository, SSORequiredError
from responsibleai.db.outcome_repository import OutcomeRepository
from responsibleai.db.passport_repository import PassportRepository
from responsibleai.db.policy_repository import PolicyRepository, PolicyRuleNotFoundError
from responsibleai.db.principal_repository import PrincipalRepository
from responsibleai.db.public_incident_repository import PublicIncidentRepository
from responsibleai.db.repositories import CostRepository, TrustRepository
from responsibleai.db.tool_trust_repository import ToolTrustRepository
from responsibleai.db.upstream_repository import (
    UpstreamServerNotFoundError,
    UpstreamServerRepository,
)
from responsibleai.db.webhook_repository import (
    WebhookConfigRepository,
    WebhookDeliveryRepository,
)
from responsibleai.db.workflow_rule_repository import (
    WorkflowRuleAlreadyExistsError,
    WorkflowRuleNotFoundError,
    WorkflowRuleRepository,
)

__all__ = [
    "AlreadyVotedError",
    "ApprovalActionMismatchError",
    "ApprovalAlreadyResolvedError",
    "ApprovalExpiredError",
    "ApprovalNotApprovedError",
    "ApprovalNotFoundError",
    "ApprovalRepository",
    "SelfApprovalError",
    "DatabaseEngine",
    "CostRepository",
    "TrustRepository",
    "OrgRepository",
    "OutcomeRepository",
    "PrincipalRepository",
    "AuditRepository",
    "CredentialIssuanceRepository",
    "EvalRepository",
    "EvidenceRepository",
    "WebhookConfigRepository",
    "WebhookDeliveryRepository",
    "McpUsageRepository",
    "IncidentRepository",
    "LeaderboardRepository",
    "PassportRepository",
    "PublicIncidentRepository",
    "PolicyRepository",
    "PolicyRuleNotFoundError",
    "SSORequiredError",
    "create_engine",
    "ToolTrustRepository",
    "UpstreamServerNotFoundError",
    "UpstreamServerRepository",
    "OrgAuthorityCeilingRepository",
    "WorkflowRuleAlreadyExistsError",
    "WorkflowRuleNotFoundError",
    "WorkflowRuleRepository",
    "DelegationEscalationError",
    "DelegationNotFoundError",
    "DelegationRepository",
    "OrgAutonomyBudgetRepository",
]
