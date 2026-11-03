"""Local governance kernel — deny-by-default runtime evaluator."""

from __future__ import annotations

from datetime import UTC, datetime

from whitepact_community.evidence import LocalEvidenceStore, build_evidence_record
from whitepact_community.models import (
    ActionRequest,
    AuthorityGrant,
    DecisionResult,
    GovernanceDecision,
)
from whitepact_community.policy import Policy, default_local_policy
from whitepact_community.reason_codes import ReasonCode, format_reason
from whitepact_community.revocation import (
    LocalRevocationRegistry,
    RevocationEpoch,
    RevocationEpochCheckStatus,
    check_revocation_epoch,
)
from whitepact_community.risk import classify_action_risk

QUARANTINE_VIOLATION_THRESHOLD = 3


class LocalGovernanceKernel:
    """Stateless-per-call evaluator with optional local evidence + revocation."""

    def __init__(
        self,
        *,
        policy: Policy | None = None,
        evidence: LocalEvidenceStore | None = None,
        revocation: LocalRevocationRegistry | None = None,
    ) -> None:
        self.policy = policy or default_local_policy()
        self.evidence = evidence if evidence is not None else LocalEvidenceStore()
        self.revocation = revocation if revocation is not None else LocalRevocationRegistry()

    def evaluate(
        self,
        action: ActionRequest,
        authority: AuthorityGrant,
        *,
        policy: Policy | None = None,
        recent_violation_count: int = 0,
        now: datetime | None = None,
    ) -> DecisionResult:
        clock = now or datetime.now(UTC)
        active_policy = policy or self.policy
        risk_tier = classify_action_risk(action.action_type, action.target)

        if recent_violation_count >= QUARANTINE_VIOLATION_THRESHOLD:
            return self._finalize(
                action,
                authority,
                DecisionResult(
                    decision=GovernanceDecision.QUARANTINE,
                    action_id=action.action_id,
                    reason_codes=[
                        format_reason(
                            ReasonCode.IDENTITY_QUARANTINED,
                            recent_denials=recent_violation_count,
                            threshold=QUARANTINE_VIOLATION_THRESHOLD,
                        )
                    ],
                    risk_tier=risk_tier,
                    evaluated_at=clock,
                ),
            )

        if authority.is_expired(clock):
            return self._finalize(
                action,
                authority,
                DecisionResult(
                    decision=GovernanceDecision.DENY,
                    action_id=action.action_id,
                    reason_codes=[format_reason(ReasonCode.AUTHORITY_EXPIRED)],
                    risk_tier=risk_tier,
                    evaluated_at=clock,
                ),
            )

        org_id = authority.organization_id or action.identity.org_id or "local"
        issued = RevocationEpoch(
            organization_id=org_id,
            scope="authority",
            epoch=authority.revocation_epoch,
        )
        current = self.revocation.current(org_id, "authority")
        rev_check = check_revocation_epoch(issued, current)
        if rev_check.status == RevocationEpochCheckStatus.REVOKED_SINCE_ISSUANCE:
            return self._finalize(
                action,
                authority,
                DecisionResult(
                    decision=GovernanceDecision.DENY,
                    action_id=action.action_id,
                    reason_codes=[
                        format_reason(
                            ReasonCode.AUTHORITY_REVOKED,
                            issued_epoch=rev_check.issued_at_epoch,
                            current_epoch=rev_check.current_epoch,
                        )
                    ],
                    risk_tier=risk_tier,
                    evaluated_at=clock,
                ),
            )

        if not authority.permits(action.action_type):
            return self._finalize(
                action,
                authority,
                DecisionResult(
                    decision=GovernanceDecision.DENY,
                    action_id=action.action_id,
                    reason_codes=[
                        format_reason(
                            ReasonCode.AUTHORITY_NOT_DELEGATED,
                            action_type=action.action_type,
                        )
                    ],
                    risk_tier=risk_tier,
                    evaluated_at=clock,
                ),
            )

        if action.action_type in authority.require_approval_for:
            return self._finalize(
                action,
                authority,
                DecisionResult(
                    decision=GovernanceDecision.REQUIRE_APPROVAL,
                    action_id=action.action_id,
                    reason_codes=[
                        format_reason(
                            ReasonCode.POLICY_REQUIRES_APPROVAL,
                            action_type=action.action_type,
                        )
                    ],
                    risk_tier=risk_tier,
                    evaluated_at=clock,
                    policy_version=active_policy.version,
                ),
            )

        violation = authority.constraint_violation(action)
        if violation is not None:
            return self._finalize(
                action,
                authority,
                DecisionResult(
                    decision=GovernanceDecision.DENY,
                    action_id=action.action_id,
                    reason_codes=[violation],
                    risk_tier=risk_tier,
                    evaluated_at=clock,
                    policy_version=active_policy.version,
                ),
            )

        match = active_policy.evaluate(action, risk_tier)
        if match is None:
            if active_policy.deny_unmatched:
                return self._finalize(
                    action,
                    authority,
                    DecisionResult(
                        decision=GovernanceDecision.DENY,
                        action_id=action.action_id,
                        reason_codes=[
                            format_reason(
                                ReasonCode.POLICY_DENY_BY_DEFAULT,
                                action_type=action.action_type,
                                target=action.target,
                            )
                        ],
                        risk_tier=risk_tier,
                        evaluated_at=clock,
                        policy_version=active_policy.version,
                    ),
                )
            # Fail closed even if a caller constructed a non-default policy.
            return self._finalize(
                action,
                authority,
                DecisionResult(
                    decision=GovernanceDecision.DENY,
                    action_id=action.action_id,
                    reason_codes=[format_reason(ReasonCode.POLICY_DENY_BY_DEFAULT)],
                    risk_tier=risk_tier,
                    evaluated_at=clock,
                    policy_version=active_policy.version,
                ),
            )

        effect = match.rule.effect
        if effect == GovernanceDecision.DENY:
            return self._finalize(
                action,
                authority,
                DecisionResult(
                    decision=GovernanceDecision.DENY,
                    action_id=action.action_id,
                    reason_codes=[
                        format_reason(
                            ReasonCode.POLICY_EXPLICIT_DENY,
                            rule_id=match.rule.rule_id,
                        )
                    ],
                    risk_tier=risk_tier,
                    evaluated_at=clock,
                    policy_version=active_policy.version,
                ),
            )
        if effect == GovernanceDecision.REQUIRE_APPROVAL:
            return self._finalize(
                action,
                authority,
                DecisionResult(
                    decision=GovernanceDecision.REQUIRE_APPROVAL,
                    action_id=action.action_id,
                    reason_codes=[
                        format_reason(
                            ReasonCode.POLICY_REQUIRES_APPROVAL,
                            rule_id=match.rule.rule_id,
                        )
                    ],
                    risk_tier=risk_tier,
                    evaluated_at=clock,
                    policy_version=active_policy.version,
                ),
            )

        return self._finalize(
            action,
            authority,
            DecisionResult(
                decision=GovernanceDecision.ALLOW,
                action_id=action.action_id,
                reason_codes=[f"POLICY_ALLOW:rule_id={match.rule.rule_id}"],
                risk_tier=risk_tier,
                evaluated_at=clock,
                policy_version=active_policy.version,
            ),
        )

    def _finalize(
        self,
        action: ActionRequest,
        authority: AuthorityGrant,
        decision: DecisionResult,
    ) -> DecisionResult:
        evidence = build_evidence_record(action, authority, decision)
        stored = self.evidence.record(evidence)
        decision.evidence_id = stored.evidence_id
        return decision
