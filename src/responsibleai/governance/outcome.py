# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Outcome Observation (Authority Everywhere Phase 12) — what actually
happened when a governed action executed, captured independently of
what was authorized.

**The gap this closes**: `EvidenceRecord` (Phase 12's original scope,
`governance/evidence.py`) records the *decision* — what governance
allowed and why — but this package has never had visibility into
whether the executor's own attempt to carry that decision out actually
succeeded. `governance/execution.py`'s module docstring already states
this explicitly: `"execution_result_metadata` is not populated — this
package has no visibility into whether/how an allowed action was
actually executed."` This module is what starts populating that gap —
not by inferring anything, but by giving `InternalToolExecutor` and
`UpstreamMCPExecutor`'s own callers (`mcp/governance_integration.py`,
`mcp/upstream_dispatch.py`) a place to report what they directly
observed: did `executor.execute()` return, or did it raise.

**Honestly scoped**: this is not a general execution-tracing or
distributed-tracing system. It captures exactly one fact per executed
action — succeeded, failed (the tool itself reported an error), or
errored (the call raised) — plus an optional, deliberately minimal
result summary. Never the raw result payload: the same "field names
and shapes, never values" discipline `EvidenceRecord.argument_keys`
already applies, extended here to `result_summary` — a short, caller-
supplied description, not a serialized dump of whatever the tool
returned (which could carry arbitrary user data or secrets governance
has no business persisting).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any


class OutcomeStatus(StrEnum):
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"  # the executor ran, but the underlying call reported an error
    ERRORED = "ERRORED"  # the executor call itself raised


@dataclass
class OutcomeRecord:
    """One observation of what happened when a governed action's
    permit was actually consumed. Linked to the `EvidenceRecord` that
    authorized the attempt via `evidence_id` — an `OutcomeRecord` is
    never constructed without a corresponding, already-persisted
    evidence entry, since "what happened" is meaningless without "what
    was decided" to compare it against (see
    `governance/reconciliation.py`)."""

    evidence_id: str
    action_id: str
    status: OutcomeStatus
    outcome_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    organization_id: str | None = None
    result_summary: str | None = None
    observed_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "outcome_id": self.outcome_id,
            "evidence_id": self.evidence_id,
            "action_id": self.action_id,
            "organization_id": self.organization_id,
            "status": self.status.value,
            "result_summary": self.result_summary,
            "observed_at": self.observed_at.isoformat(),
        }


def build_outcome_record(
    evidence_id: str,
    action_id: str,
    status: OutcomeStatus,
    *,
    organization_id: str | None = None,
    result_summary: str | None = None,
) -> OutcomeRecord:
    """Pure assembly, mirroring `evidence.build_evidence_record()`'s own
    shape — no I/O here; persist via `OutcomeRepository.record()`."""
    return OutcomeRecord(
        evidence_id=evidence_id,
        action_id=action_id,
        status=status,
        organization_id=organization_id,
        result_summary=result_summary,
    )
