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

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from responsibleai.governance.models import ActionRequest, DecisionResult
from responsibleai.governance.risk import RiskTier


class ApprovalStatus(StrEnum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    DENIED = "DENIED"


@dataclass
class ApprovalRequest:
    action_id: str
    action_type: str
    target: str
    reason_codes: list[str]
    requested_at: datetime
    approval_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str | None = None
    risk_tier: str | None = None
    requested_by: str | None = None  # identity_id of the agent/actor that proposed the action
    status: ApprovalStatus = ApprovalStatus.PENDING
    resolved_by: str | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None

    @property
    def is_resolved(self) -> bool:
        return self.status is not ApprovalStatus.PENDING

    def to_dict(self) -> dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "organization_id": self.organization_id,
            "action_id": self.action_id,
            "action_type": self.action_type,
            "target": self.target,
            "reason_codes": self.reason_codes,
            "risk_tier": self.risk_tier,
            "requested_by": self.requested_by,
            "status": self.status.value,
            "requested_at": self.requested_at.isoformat(),
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
        reason_codes=list(decision.reason_codes),
        requested_at=decision.evaluated_at,
        organization_id=action.agent.organization_id,
        risk_tier=decision.risk_tier.value if isinstance(decision.risk_tier, RiskTier) else None,
        requested_by=action.agent.identity.identity_id,
    )
