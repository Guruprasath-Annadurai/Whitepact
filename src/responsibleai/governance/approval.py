"""The approval workflow's domain model — SPEC.md's `Decision.REQUIRE_APPROVAL`
made actionable, Phase 11. This module holds the pure shape
(`ApprovalRequest`, `ApprovalStatus`) and its pure assembly function;
persistence and resolution live in `db/approval_repository.py` (same
separation as `governance/evidence.py` from `db/evidence_repository.py`
— see that module's docstring for why).

What this delivers: a real, persisted record of "this action needs a
human (or delegated-authority) decision," queryable, and resolvable
through `ApprovalRepository.resolve()` with a state machine that
rejects double-resolution. What it does not deliver (real gaps, not
oversights): any notification beyond an optional webhook fire (see
`ApprovalRepository.create_from_decision`'s `webhook_manager` param —
email/Slack-app-specific integrations, in-app UI, or SLA/expiry timers
are not built), and no automatic re-evaluation or resumption of the
original action once resolved — resolving an `ApprovalRequest` records
a human decision; acting on it (actually executing the now-approved
action) is the caller's responsibility, same as an `ALLOW` decision.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from typing import Any

from responsibleai.governance.models import ActionRequest, AgentContext, DecisionResult
from responsibleai.governance.risk import RiskTier

# A single, hardcoded default rather than per-org configuration -- same
# reasoning as quarantine.py's QUARANTINE_VIOLATION_THRESHOLD: a
# circuit breaker/safety bound, not a tuning knob orgs are expected to
# reach for on day one.
DEFAULT_APPROVAL_TTL_HOURS = 24

# Fixed, risk-tier-keyed default for how many distinct human approvals
# a REQUIRE_APPROVAL action needs before it's actually approved --
# closes "no multi-approver quorum" without inventing a per-org
# configuration surface (no UI/API to set this per-org exists; a fixed,
# reviewable table is the honest scope here, same principle as
# QUARANTINE_VIOLATION_THRESHOLD above). HIGH-risk actions need two
# independent humans to agree; everything else needs the one this
# system already required before quorum existed -- MEDIUM/LOW/MINIMAL/
# unclassified (None) all default to 1, preserving exact prior behavior
# for every risk tier that isn't HIGH.
_DEFAULT_REQUIRED_APPROVALS_BY_TIER: dict[RiskTier | None, int] = {
    RiskTier.HIGH: 2,
}
_DEFAULT_REQUIRED_APPROVALS = 1


def default_required_approvals(risk_tier: RiskTier | None) -> int:
    return _DEFAULT_REQUIRED_APPROVALS_BY_TIER.get(risk_tier, _DEFAULT_REQUIRED_APPROVALS)


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"
    # A one-way transition out of APPROVED, entered only via
    # ApprovalRepository.consume() — see that method's docstring for
    # why this is the state that actually enforces "an approval
    # authorizes execution exactly once, of exactly the action a human
    # reviewed" (the mutation + replay invariants).
    CONSUMED = "CONSUMED"


def compute_action_digest(action: ActionRequest) -> str:
    """A stable SHA-256 digest over exactly the fields that define
    "what a human approved" — action_type, target, the argument
    values (not just their names, unlike `EvidenceRecord.argument_keys`
    — the mutation invariant needs to detect a *changed value*, e.g.
    the payment amount, not just a changed argument *name*), and
    (Enterprise Readiness Phase 5) `purpose` — an authorization or
    approval granted for one declared purpose must not silently cover
    execution under a different one; including it here means mutation
    detection for purpose comes for free through this same,
    already-tested mechanism, not a second, separate check.

    This function's whole job is producing a value comparable across
    two separately-constructed `ActionRequest`s for the same logical
    action — it is not a secrecy boundary, and `arguments` may still
    end up embedded in it indirectly via the hash input; that's why
    only the *digest* is ever persisted (`ApprovalRequest.action_digest`),
    never the canonical JSON itself.
    """
    canonical = json.dumps(
        {
            "action_type": action.action_type,
            "target": action.target,
            "arguments": action.arguments,
            "purpose": action.purpose,
        },
        sort_keys=True,
        default=str,
    )
    return hashlib.sha256(canonical.encode()).hexdigest()


@dataclass
class ApprovalVote:
    """One resolver's vote on a quorum approval -- persisted in
    ``governance_approval_votes``, distinct from ``ApprovalRequest``'s
    own ``resolved_by``/``resolved_at``/``resolution_notes`` (which
    reflect only the vote that actually closed the approval, for
    backward-compatible single-approver reads)."""

    approval_id: str
    resolver_identity_id: str
    outcome: ApprovalStatus
    resolved_at: datetime
    vote_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    notes: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "vote_id": self.vote_id,
            "approval_id": self.approval_id,
            "resolver_identity_id": self.resolver_identity_id,
            "outcome": self.outcome.value,
            "notes": self.notes,
            "resolved_at": self.resolved_at.isoformat(),
        }


@dataclass
class ApprovalRequest:
    action_id: str
    action_type: str
    target: str
    reason_codes: list[str]
    requested_at: datetime
    action_digest: str = ""
    approval_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str | None = None
    risk_tier: str | None = None
    requested_by: str | None = None  # identity_id of the agent/actor that proposed the action
    status: ApprovalStatus = ApprovalStatus.PENDING
    # None only for rows persisted before this field existed -- every
    # newly built ApprovalRequest always gets one, via
    # build_approval_request() below.
    expires_at: datetime | None = None
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    # How many distinct APPROVED votes close this approval -- see
    # default_required_approvals() above. 1 for every approval built
    # before this field existed (server_default="1" on the DB column),
    # which is exactly the single-approver behavior they always had.
    required_approvals: int = 1
    # The original action's arguments -- what build_resume_action()
    # needs to reconstruct the exact ActionRequest a human approved.
    # Persisted encrypted at rest (db/engine.py's EncryptedString on
    # this column); deliberately excluded from to_dict() below so the
    # approvals list/get REST API never echoes raw argument values back
    # out, even to an authenticated caller -- the whole reason this
    # wasn't persisted before was to avoid exposing raw/PII arguments,
    # and encrypting the column doesn't change that exposure risk once
    # the API itself hands the plaintext back over HTTP.
    arguments: dict[str, Any] | None = None
    # Enterprise Readiness Phase 5 (purpose binding). The requested
    # purpose a human is being asked to approve, carried unchanged
    # through to build_resume_action() so a resumed execution is
    # re-checked against the SAME purpose that was queued -- without
    # this, purpose would be silently dropped across a
    # REQUIRE_APPROVAL -> resume cycle, defeating Section 9's
    # revalidation requirement before it could even run.
    purpose: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.status is not ApprovalStatus.PENDING

    @property
    def is_expired(self) -> bool:
        """False (not expired) for a legacy row with no expires_at --
        same fail-closed-only-where-we-have-signal reasoning as
        matches_action()'s empty-digest case, but inverted: an absent
        TTL is a data-migration artifact, not a security signal, so it
        must not retroactively expire approvals nobody set a limit on."""
        return self.expires_at is not None and datetime.now(UTC) > self.expires_at

    def matches_action(self, action: ActionRequest) -> bool:
        """True only if *action* is byte-for-byte the same action_type/
        target/arguments a human approved — the mutation invariant's
        actual check. An approval with no digest (``action_digest ==
        ""``, e.g. one persisted before this field existed) never
        matches anything, deliberately fail-closed rather than
        skipping the check for old rows."""
        return bool(self.action_digest) and self.action_digest == compute_action_digest(action)

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "organization_id": self.organization_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "action_digest": self.action_digest,
            "reason_codes": self.reason_codes,
            "risk_tier": self.risk_tier,
            "requested_by": self.requested_by,
            "status": self.status.value,
            "requested_at": self.requested_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "required_approvals": self.required_approvals,
            "resolved_by": self.resolved_by,
            "resolved_at": self.resolved_at.isoformat() if self.resolved_at else None,
            "resolution_notes": self.resolution_notes,
        }


def build_approval_request(action: ActionRequest, decision: DecisionResult) -> ApprovalRequest:
    """Assemble a pending `ApprovalRequest` from a `REQUIRE_APPROVAL`
    decision. Pure -- persist via `ApprovalRepository.create_from_decision()`.
    Callers are expected to only call this when
    `decision.decision == GovernanceDecision.REQUIRE_APPROVAL`; it
    doesn't check that itself, since it has no opinion on what a caller
    does with an `ALLOW`/`DENY` decision.
    """
    return ApprovalRequest(
        action_id=action.action_id,
        action_type=action.action_type,
        target=action.target,
        action_digest=compute_action_digest(action),
        reason_codes=list(decision.reason_codes),
        requested_at=decision.evaluated_at,
        expires_at=decision.evaluated_at + timedelta(hours=DEFAULT_APPROVAL_TTL_HOURS),
        organization_id=action.agent.organization_id,
        risk_tier=decision.risk_tier.value if isinstance(decision.risk_tier, RiskTier) else None,
        requested_by=action.agent.identity.identity_id,
        arguments=dict(action.arguments),
        required_approvals=default_required_approvals(decision.risk_tier),
        purpose=action.purpose,
    )


def build_resume_action(approval: ApprovalRequest, *, agent: AgentContext) -> ActionRequest:
    """Reconstructs the exact `ActionRequest` a human approved, from an
    `ApprovalRequest`'s persisted `arguments` -- what a resume-after-
    approval flow needs to actually execute a previously-queued action
    (`db/approval_repository.py`'s `consume()` proves the binding, this
    function is what makes there be something to bind *to* at resume
    time, closing the gap `governance/approval.py`'s own module
    docstring used to flag: "no automatic re-evaluation or resumption
    of the original action once resolved").

    `action_id` is carried over unchanged, not regenerated -- it's the
    same logical action, and `EvidenceRecord`/webhook payloads elsewhere
    already reference the original `action_id`; a resume shouldn't mint
    a second identity for one action.

    Raises `ValueError` if `approval.arguments` is `None` -- a legacy
    approval persisted before this field existed has nothing to resume
    with; callers must treat that as "not resumable," not silently
    execute against an empty/guessed argument set.
    """
    if approval.arguments is None:
        raise ValueError(
            f"Approval {approval.approval_id!r} has no persisted arguments "
            "(created before resume-after-approval existed) and cannot be resumed."
        )
    return ActionRequest(
        agent=agent,
        action_type=approval.action_type,
        target=approval.target,
        arguments=approval.arguments,
        action_id=approval.action_id,
        purpose=approval.purpose,
    )
