# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Attestation (Authority Everywhere Phase 14) — the packaged, final
statement of one action's Decision -> Outcome -> Reconciliation chain.

**Deliberately not cryptographically signed, and this module says so
rather than overclaiming**: the same reasoning
`governance/execution.py`'s module docstring already gives for
`ExecutionAuthorization` applies here, generalized. Signing every
runtime `AttestationRecord` automatically would require a live signing
key held by the running server process — a real secret-management and
rotation burden this project has no infrastructure for (compare the
release-tag signing set up for `version_tags_signed`, which
deliberately uses the *founder's own, out-of-band, human-operated* SSH
key for infrequent, human-triggered release events — not applicable to
signing every single runtime decision automatically). A forged
attestation would require the same DB write access that could also
rewrite `EvidenceRecord`'s own hash chain, at which point an
automated in-process signature would not be verifying anything an
attacker couldn't also forge. What *is* real: this record packages the
`EvidenceRecord`'s own tamper-evident `hash` (from
`db/evidence_repository.py`'s per-org hash chain) alongside the
outcome and reconciliation status, so verifying an attestation means
verifying it against that already-real hash chain — integrity by
linkage to existing tamper-evidence, not a new cryptographic claim.
Publishing periodic chain-checkpoint commitments somewhere external
(so a compromised DB alone isn't sufficient to also rewrite history
undetected) is real, valuable, separate future work, not built here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from responsibleai.governance.evidence import EvidenceRecord
from responsibleai.governance.outcome import OutcomeRecord
from responsibleai.governance.reconciliation import (
    ReconciliationResult,
    reconcile_outcome,
)


@dataclass(frozen=True)
class AttestationRecord:
    evidence_id: str
    action_id: str
    organization_id: str | None
    decision: str
    risk_tier: str | None
    reason_codes: tuple[str, ...]
    evidence_hash: str | None
    outcome_status: str | None
    reconciliation_status: str
    attested_at: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "evidence_id": self.evidence_id,
            "action_id": self.action_id,
            "organization_id": self.organization_id,
            "decision": self.decision,
            "risk_tier": self.risk_tier,
            "reason_codes": list(self.reason_codes),
            "evidence_hash": self.evidence_hash,
            "outcome_status": self.outcome_status,
            "reconciliation_status": self.reconciliation_status,
            "attested_at": self.attested_at,
            "integrity_note": (
                "Not cryptographically signed. Verify evidence_hash against "
                "this organization's evidence chain via db/evidence_repository.py "
                "(or governance/evidence_bundle.py's bundle verification) -- "
                "integrity here is by linkage to that hash chain, not a "
                "separate signature. See this module's own docstring for why."
            ),
        }


def build_attestation_record(
    evidence: EvidenceRecord, outcome: OutcomeRecord | None
) -> AttestationRecord:
    """Pure assembly from an already-persisted `EvidenceRecord` (must
    have gone through `EvidenceRepository.record()` at least once —
    `evidence.hash` is `None` otherwise, which this function will
    faithfully carry through rather than raising, since an attestation
    over an unpersisted decision is still meaningful to return, just
    not yet chain-verifiable) and an optional `OutcomeRecord`."""
    reconciliation: ReconciliationResult = reconcile_outcome(evidence, outcome)
    return AttestationRecord(
        evidence_id=evidence.evidence_id,
        action_id=evidence.action_id,
        organization_id=evidence.organization_id,
        decision=evidence.decision,
        risk_tier=evidence.risk_tier,
        reason_codes=tuple(evidence.reason_codes),
        evidence_hash=evidence.hash,
        outcome_status=outcome.status.value if outcome else None,
        reconciliation_status=reconciliation.status.value,
        attested_at=datetime.now(UTC).isoformat(),
    )
