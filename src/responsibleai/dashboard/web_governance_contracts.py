# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Web-console serialization of already-persisted governance records.

These helpers do not mint Judgment, ExecutionGrant, or evidence. They
project canonical ApprovalRepository / EvidenceRepository / OutcomeRepository
rows into a web-session-safe JSON shape. Argument *values* are never
returned; only keys/count when arguments were persisted.
"""

from __future__ import annotations

from typing import Any

from responsibleai.governance.approval import ApprovalRequest, ApprovalStatus, ApprovalVote
from responsibleai.governance.outcome import OutcomeStatus

UNKNOWN_EXECUTION_MESSAGE = (
    "The mutation may have applied; acknowledgement was lost. "
    "WhitePact will not retry automatically."
)
KNOWN_SUCCESS_MESSAGE = "Execution completed with a known outcome."

CHAIN_INTEGRITY_NOTE = (
    "This check recomputes the organization's evidence hash chain. "
    "It is not a cryptographic signature of individual records. "
    "INCOMPLETE means the chain hashes but still contains legacy "
    "pre-canonical entries."
)


def argument_summary(arguments: dict[str, Any] | None) -> dict[str, Any] | None:
    if arguments is None:
        return None
    return {
        "argument_keys": sorted(str(key) for key in arguments),
        "argument_count": len(arguments),
    }


def approval_detail_payload(approval: ApprovalRequest, votes: list[ApprovalVote]) -> dict[str, Any]:
    approved = sum(1 for vote in votes if vote.outcome is ApprovalStatus.APPROVED)
    denied = sum(1 for vote in votes if vote.outcome is ApprovalStatus.DENIED)
    payload = approval.to_dict()
    payload["requester"] = approval.requested_by
    payload["current_vote_count"] = approved
    payload["approved_vote_count"] = approved
    payload["denied_vote_count"] = denied
    payload["votes"] = [vote.to_dict() for vote in votes]
    payload["execution_state"] = approval.status.value
    payload["purpose"] = approval.purpose
    summary = argument_summary(approval.arguments)
    if summary is not None:
        payload["argument_summary"] = summary
    return payload


def web_execution_payload(
    *,
    approval_id: str,
    execution_status: OutcomeStatus,
    evidence_id: str | None,
    outcome_id: str | None,
    message: str,
) -> dict[str, Any]:
    unknown = execution_status is OutcomeStatus.UNKNOWN
    return {
        "approval_id": approval_id,
        "execution_status": execution_status.value,
        "reconciliation_required": unknown,
        "evidence_id": evidence_id,
        "outcome_id": outcome_id,
        "message": message,
    }
