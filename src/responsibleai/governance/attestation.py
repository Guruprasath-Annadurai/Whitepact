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
signing every single runtime decision automatically). The ordinary database hash chain is not resistant to an attacker who
rewrites the rows and recomputes the hashes. An in-process signature
made with a key stored next to the database would not change that.
``governance.evidence_witness`` defines an offline-verifiable head
witness whose signing key is held outside the database. This attestation
record still does not carry that witness. Live publication of witnesses
is an external deployment gate and is not claimed here.
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
                "Not cryptographically signed. evidence_hash links this "
                "attestation to the organization's database hash chain. That "
                "chain detects internal inconsistency. It does not detect a "
                "full rewrite that recomputes the hashes. Independent "
                "verification requires an EvidenceHeadWitness signed outside "
                "the database. Live witness publication is not deployed."
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
