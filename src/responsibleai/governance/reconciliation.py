"""Reconciliation (Authority Everywhere Phase 13) — does an observed
`OutcomeRecord` actually match what its `EvidenceRecord` authorized.

**What this honestly checks, and why it's narrower than it might
sound**: the strongest reconciliation invariant this platform has —
"the action that actually executed was byte-identical to the one
governance authorized" — is already structurally enforced *before*
execution ever happens, synchronously, by `ExecutionAuthorization.
matches_action()` (`governance/execution.py`) and, for upstream calls,
`check_target_fingerprint()`. An `OutcomeRecord` can only exist for an
action that already passed those checks — so this module is not a
second, redundant mutation check. What it *does* add: linking an
outcome back to its evidence and asking two questions a synchronous
digest check can't answer on its own — (1) was an outcome ever reported
at all for a decision that authorized execution, and (2) does the
`action_id` on the two records actually agree (a defensive check
against a caller wiring the wrong evidence_id/outcome pair together,
which no other invariant in this codebase currently catches).

**Not built here**: outcome-content verification (e.g. "did the tool's
result plausibly match its risk tier or arguments") — that would
require understanding what a *correct* result looks like per tool,
real, separate, per-tool-domain work this module doesn't attempt.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum

from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.governance.models import GovernanceDecision
from responsibleai.governance.outcome import OutcomeRecord

# Decisions that actually authorize an execution attempt -- the only
# ones an OutcomeRecord is ever expected to exist for. DENY/QUARANTINE/
# REQUIRE_APPROVAL (until resumed and separately re-decided) never
# produce an ExecutionAuthorization at all (execution.authorize_execution()'s
# own DecisionNotExecutableError), so "no outcome" for one of those is
# not missing anything -- it's the correct, expected state.
_EXECUTABLE_DECISIONS = frozenset(
    {GovernanceDecision.ALLOW.value, GovernanceDecision.ALLOW_WITH_REDACTION.value}
)


class ReconciliationStatus(StrEnum):
    RECONCILED = "RECONCILED"  # outcome exists and links correctly to its evidence
    MISSING_OUTCOME = "MISSING_OUTCOME"  # decision authorized execution, no outcome ever reported
    ACTION_MISMATCH = "ACTION_MISMATCH"  # outcome.action_id != evidence.action_id
    NOT_APPLICABLE = "NOT_APPLICABLE"  # decision never authorized execution -- no outcome expected


@dataclass(frozen=True)
class ReconciliationResult:
    status: ReconciliationStatus
    evidence_id: str
    outcome_id: str | None


def reconcile_outcome(
    evidence: EvidenceRecord, outcome: OutcomeRecord | None
) -> ReconciliationResult:
    """*outcome* is `None` when no `OutcomeRecord` was ever reported
    for *evidence* — the caller (`OutcomeRepository.get_for_evidence()`)
    is the one deciding "how long to wait before treating absence as
    meaningful," not this function; this function only classifies
    whatever it's handed."""
    if evidence.decision not in _EXECUTABLE_DECISIONS:
        return ReconciliationResult(
            status=ReconciliationStatus.NOT_APPLICABLE,
            evidence_id=evidence.evidence_id,
            outcome_id=outcome.outcome_id if outcome else None,
        )

    if outcome is None:
        return ReconciliationResult(
            status=ReconciliationStatus.MISSING_OUTCOME,
            evidence_id=evidence.evidence_id,
            outcome_id=None,
        )

    if outcome.action_id != evidence.action_id:
        return ReconciliationResult(
            status=ReconciliationStatus.ACTION_MISMATCH,
            evidence_id=evidence.evidence_id,
            outcome_id=outcome.outcome_id,
        )

    return ReconciliationResult(
        status=ReconciliationStatus.RECONCILED,
        evidence_id=evidence.evidence_id,
        outcome_id=outcome.outcome_id,
    )
