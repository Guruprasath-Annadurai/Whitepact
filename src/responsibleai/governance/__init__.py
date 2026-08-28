"""WhitePact runtime governance core — SPEC.md Section 2's pipeline
(Agent -> Action -> Policy/Authority -> Decision), Phase 8 of
MIGRATION_WHITEPACT_V2.md. See governance/models.py and
governance/gateway.py module docstrings for what is and is not
implemented yet; SPEC.md remains the authoritative architecture
document.

**The WhitePact Heart** (SPEC.md Section 2.5, `docs/heart/`) is
exported below too, Phase H17's own hardening fix: Heart Phases H1-H13
(`constitution`, `authority_lattice`, `root_authority`, `consent_proof`,
`purpose_binding`, `delegation_kernel`, `non_delegable_authority`,
`authority_lifetime`, `revocation_kernel`, `authority_conflict_resolver`,
`heart_veto`, `legitimacy_envelope`, `sovereignty_kernel`) shipped
without ever being re-exported here — every prior phase's own tests
imported directly from `responsibleai.governance.<module>`, which
still works, but nothing let a caller reach the Heart's public API
the same way every other governance type in this file already is
reachable, via `from responsibleai.governance import ...`.
`sovereignty_kernel` itself is exported as the module (not its bare
`evaluate` function) to avoid a needlessly generic top-level name and
to match the `sk.evaluate(...)` import convention this session's own
Heart test suites already established.

**Production Integration Phase 1** (`docs/heart-production/`) adds
`AuthorityGrant` (`governance/authority_grant.py`) — the boundary
object between the Heart and WhitePact's live decision path, exported
here for the same reason every Heart symbol already is.

**Enterprise Neural Phase 2** (`docs/enterprise-neural/`) adds the
`crypto` subpackage — key hierarchy, the `KeyProvider` Protocol, and
`LocalEnvelopeKeyProvider` (`governance/crypto/`) — exported as a
module, the same `sovereignty_kernel`-style convention above, since its
public surface is a dozen names better reached as `crypto.KeyId`
etc. than flattened individually into this file's own `__all__`.

**Enterprise Neural Phase 4** adds the `neural` subpackage —
`NeuralDataClass`/`NeuralPayload` classification, per-category
`ConsentRecord`, and the fail-closed `evaluate_neural_data_flow` policy
evaluator (`governance/neural/`) — exported as a module, same
convention. Net-new product surface (Phases 5-7's BCI device adapters,
decoders, and intent attestation don't exist yet); see
`docs/enterprise-neural/04_PHASE4_DESIGN.md`."""

from __future__ import annotations

from responsibleai.governance import crypto, neural, sovereignty_kernel
from responsibleai.governance.authority_conflict_resolver import (
    ConflictResolutionResult,
    ConflictResolutionStatus,
    resolve_authority_conflicts,
)
from responsibleai.governance.authority_grant import (
    DEFAULT_GRANT_TTL_SECONDS,
    AuthorityGrant,
    build_authority_grant,
)
from responsibleai.governance.authority_lattice import (
    AuthorityEnvelope,
    LatticeComparisonResult,
    LatticeComparisonStatus,
    UnrepresentableConstraintError,
    authority_context_to_envelope,
    compare_authority_contexts,
    compare_envelopes,
    envelope_to_authority_context,
    intersect_envelopes,
)
from responsibleai.governance.authority_lifetime import (
    CONSENT_PROOF_LIFETIME_WINDOW,
    DELEGATION_LEGITIMACY_LIFETIME_WINDOW,
    PURPOSE_BINDING_LIFETIME_WINDOW,
    ROOT_AUTHORITY_LIFETIME_WINDOW,
    LifetimeCheckResult,
    LifetimeStatus,
    LifetimeWindow,
    check_lifetime,
)
from responsibleai.governance.autonomy_budget import (
    AutonomyBudgetPolicy,
    recent_autonomous_action_count,
)
from responsibleai.governance.ceiling import OrgAuthorityCeiling
from responsibleai.governance.consent_proof import (
    ConsentMethod,
    ConsentProof,
    ConsentValidationResult,
    ConsentValidationStatus,
    build_consent_proof,
    validate_consent_proof,
)
from responsibleai.governance.constitution import (
    CONSTITUTION_V1,
    AuthorityConstitutionVersion,
    ConstitutionalLawCode,
    build_constitution_version,
    current_constitution,
    explain_constitution,
    get_constitution_version,
)
from responsibleai.governance.delegation import DelegationRecord
from responsibleai.governance.delegation_kernel import (
    DelegationLegitimacyResult,
    DelegationLegitimacyStatus,
    validate_delegation_legitimacy,
)
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
    AuthorizationTargetDriftError,
    DecisionNotExecutableError,
    ExecutionAuthorization,
    ExecutionNotAuthorizedError,
    Executor,
    InternalToolExecutor,
    authorize_execution,
)
from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.heart_veto import (
    HeartVetoError,
    HeartVetoRecord,
    HeartVetoStatus,
    apply_heart_veto,
    enforce_heart_veto,
)
from responsibleai.governance.identity_authority_adapter import (
    build_root_authority_record_from_identity,
    build_root_authority_record_from_principal_claim,
    identity_context_to_root_type,
)
from responsibleai.governance.legitimacy_envelope import (
    LegitimacyEnvelope,
    build_legitimacy_envelope,
)
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
from responsibleai.governance.non_delegable_authority import (
    NonDelegableScope,
    NonDelegableViolation,
    check_non_delegable_authority,
)
from responsibleai.governance.policy import Policy, PolicyMatch, PolicyRule
from responsibleai.governance.purpose_binding import (
    PurposeBinding,
    PurposeBindingStatus,
    PurposeBindingValidationResult,
    build_purpose_binding,
    validate_purpose_binding,
)
from responsibleai.governance.quarantine import (
    QUARANTINE_VIOLATION_THRESHOLD,
    QUARANTINE_WINDOW_MINUTES,
    recent_violation_count,
)
from responsibleai.governance.reason_codes import ReasonCode, format_reason
from responsibleai.governance.revocation_kernel import (
    RevocationEpoch,
    RevocationEpochCheckResult,
    RevocationEpochCheckStatus,
    bump_epoch,
    check_revocation_epoch,
)
from responsibleai.governance.risk import RiskTier, classify_action_risk
from responsibleai.governance.root_authority import (
    RootAuthorityRecord,
    RootResolver,
    RootType,
    RootValidationResult,
    RootValidationStatus,
    build_root_authority_record,
    validate_root_chain,
)
from responsibleai.governance.trust_integration import enrich_agent_trust_state
from responsibleai.governance.workflow import (
    TimestampedAction,
    WorkflowSequenceRule,
    check_composition_violation,
)

__all__ = [
    "CONSENT_PROOF_LIFETIME_WINDOW",
    "CONSTITUTION_V1",
    "DEFAULT_GRANT_TTL_SECONDS",
    "DELEGATION_LEGITIMACY_LIFETIME_WINDOW",
    "PURPOSE_BINDING_LIFETIME_WINDOW",
    "QUARANTINE_VIOLATION_THRESHOLD",
    "QUARANTINE_WINDOW_MINUTES",
    "ROOT_AUTHORITY_LIFETIME_WINDOW",
    "ActionRequest",
    "AgentContext",
    "AuthorityConstitutionVersion",
    "AuthorityContext",
    "AuthorityEnvelope",
    "AuthorityGrant",
    "AutonomyBudgetPolicy",
    "AuthorizationActionMismatchError",
    "AuthorizationAlreadyConsumedError",
    "AuthorizationExpiredError",
    "AuthorizationOrganizationMismatchError",
    "AuthorizationTargetDriftError",
    "BundleVerificationResult",
    "ConflictResolutionResult",
    "ConflictResolutionStatus",
    "ConsentMethod",
    "ConsentProof",
    "ConsentValidationResult",
    "ConsentValidationStatus",
    "ConstitutionalLawCode",
    "DecisionNotExecutableError",
    "DecisionResult",
    "DelegationLegitimacyResult",
    "DelegationLegitimacyStatus",
    "DelegationRecord",
    "EvidenceBundle",
    "ExecutionAuthorization",
    "ExecutionNotAuthorizedError",
    "Executor",
    "GovernanceDecision",
    "HeartVetoError",
    "HeartVetoRecord",
    "HeartVetoStatus",
    "IdentityContext",
    "InternalToolExecutor",
    "LatticeComparisonResult",
    "LatticeComparisonStatus",
    "LegitimacyEnvelope",
    "LifetimeCheckResult",
    "LifetimeStatus",
    "LifetimeWindow",
    "MemoryFirewallResult",
    "NonDelegableScope",
    "NonDelegableViolation",
    "OrgAuthorityCeiling",
    "Policy",
    "PolicyMatch",
    "PolicyRule",
    "PurposeBinding",
    "PurposeBindingStatus",
    "PurposeBindingValidationResult",
    "ReasonCode",
    "RevocationEpoch",
    "RevocationEpochCheckResult",
    "RevocationEpochCheckStatus",
    "RiskTier",
    "RootAuthorityRecord",
    "RootResolver",
    "RootType",
    "RootValidationResult",
    "RootValidationStatus",
    "TimestampedAction",
    "UnrepresentableConstraintError",
    "WhitePactRuntimeGateway",
    "WorkflowSequenceRule",
    "apply_heart_veto",
    "authority_context_to_envelope",
    "authorize_execution",
    "build_authority_grant",
    "build_consent_proof",
    "build_constitution_version",
    "build_evidence_bundle",
    "build_legitimacy_envelope",
    "build_purpose_binding",
    "build_root_authority_record",
    "bump_epoch",
    "check_composition_violation",
    "check_lifetime",
    "check_non_delegable_authority",
    "check_revocation_epoch",
    "classify_action_risk",
    "compare_authority_contexts",
    "compare_envelopes",
    "crypto",
    "current_constitution",
    "enforce_heart_veto",
    "enrich_agent_trust_state",
    "envelope_to_authority_context",
    "explain_constitution",
    "format_reason",
    "build_root_authority_record_from_identity",
    "build_root_authority_record_from_principal_claim",
    "get_constitution_version",
    "identity_context_to_root_type",
    "intersect_envelopes",
    "neural",
    "recent_autonomous_action_count",
    "recent_violation_count",
    "resolve_authority_conflicts",
    "scan_memory_write",
    "sovereignty_kernel",
    "validate_attenuation",
    "validate_consent_proof",
    "validate_delegation_legitimacy",
    "validate_purpose_binding",
    "validate_root_chain",
    "verify_evidence_bundle",
]
