# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Legitimacy Envelope (Heart Phase H12) — the single, portable,
digestible artifact that packages the Heart's final verdict (Phase
H11's `HeartVetoRecord`) about one identity's authority, at one point
in time, into an exportable object.

**Why this is the natural last stop before the Heart's own entry
point**: Phases H3-H11 each answer one question and hand a caller a
result object to reason about further — none of them are, by
themselves, "the thing you'd hand to an auditor, log alongside a
decision, or attach to an `ExecutionAuthorization`." A `HeartVetoRecord`
(H11) is the final, most-severe verdict, but it has no identity of its
own (no ID, no timestamp, no digest) — nothing distinguishes one
`HeartVetoRecord` from a structurally identical one computed for a
different identity five minutes later. `LegitimacyEnvelope` gives that
verdict exactly the identity, timestamp, and `canonical_digest` every
other Heart record type (H1's `AuthorityConstitutionVersion`, H3's
`RootAuthorityRecord`, H4's `ConsentProof`, H5's `PurposeBinding`)
already has — and nothing more. It does not re-derive the veto, does
not re-run any of H3-H11's checks, and does not embed the seven
individual upstream results (`RootValidationResult` etc.) — it embeds
exactly one thing, the already-final `HeartVetoRecord`, because that
record already *is* H10's precedence-resolved answer.

**Deliberately not the `SovereigntyKernel.evaluate()` entry point
itself** — that is Phase H13's separate, later scope. This phase ships
the envelope type and its own construction/explanation logic;
producing one from a real request (resolving all seven H3-H9 checks,
composing them via H10, applying the H11 veto, and finally wrapping
the result here) is the kind of end-to-end wiring every Heart phase so
far has deliberately deferred, and this phase is no exception.

**`explain()` mirrors the established deterministic-explanation
pattern** already used by `governance/constitution.py`'s
`explain_constitution()` and `db/delegation_repository.py`'s
`explain_authority()` — a plain, structured dict a human or an
auditor can read directly, never an LLM call, never free text
requiring interpretation.

**TCB-minimization, continued**: `HeartVetoRecord` (H11) is imported
only under `TYPE_CHECKING`; `build_legitimacy_envelope()` takes an
already-computed one as a parameter rather than calling
`apply_heart_veto()` itself, continuing the same "abstract input, not
a live call into another module" pattern every Heart phase has used
since H4.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from responsibleai.governance.heart_veto import HeartVetoRecord


def _canonical_json(payload: dict[str, Any]) -> str:
    """Same canonicalization discipline every prior Heart module uses."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_legitimacy_envelope_digest(
    envelope_id: str,
    organization_id: str,
    subject_identity_id: str,
    veto_status: str,
    veto_reason: str | None,
    veto_detail: str | None,
    human_reserved: bool,
    issued_at: datetime,
) -> str:
    """SHA-256 over the canonical JSON of every field that defines
    what this envelope actually asserts -- the veto's own fields are
    flattened in rather than nested, so the digest changes if and only
    if something about the actual verdict (or its context) changes,
    matching the same completeness discipline `root_authority.py`'s
    and `consent_proof.py`'s own digest functions already call out
    explicitly."""
    payload = {
        "envelope_id": envelope_id,
        "organization_id": organization_id,
        "subject_identity_id": subject_identity_id,
        "veto_status": veto_status,
        "veto_reason": veto_reason,
        "veto_detail": veto_detail,
        "human_reserved": human_reserved,
        "issued_at": issued_at.isoformat(),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class LegitimacyEnvelope:
    """One identity's Heart-level authority verdict, packaged as a
    portable, digestible, point-in-time artifact. `heart_veto` is the
    already-final, H10-precedence-resolved verdict (Phase H11) — this
    type adds identity (`envelope_id`), context
    (`organization_id`/`subject_identity_id`), a timestamp
    (`issued_at`), and a `canonical_digest`, nothing else."""

    organization_id: str
    subject_identity_id: str
    heart_veto: HeartVetoRecord
    envelope_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    canonical_digest: str = ""

    @property
    def is_legitimate(self) -> bool:
        return not self.heart_veto.is_vetoed

    def to_dict(self) -> dict[str, Any]:
        return {
            "envelope_id": self.envelope_id,
            "organization_id": self.organization_id,
            "subject_identity_id": self.subject_identity_id,
            "heart_veto": {
                "status": self.heart_veto.status.value,
                "reason": self.heart_veto.reason,
                "detail": self.heart_veto.detail,
                "human_reserved": self.heart_veto.human_reserved,
            },
            "issued_at": self.issued_at.isoformat(),
            "canonical_digest": self.canonical_digest,
        }

    def explain(self) -> dict[str, Any]:
        """A deterministic, structured explanation -- no LLM call,
        the same "prefer deterministic security controls" rule every
        other `explain_*()` in this codebase already follows."""
        return {
            "envelope_id": self.envelope_id,
            "organization_id": self.organization_id,
            "subject_identity_id": self.subject_identity_id,
            "is_legitimate": self.is_legitimate,
            "vetoed": self.heart_veto.is_vetoed,
            "veto_reason": self.heart_veto.reason,
            "veto_detail": self.heart_veto.detail,
            "human_reserved": self.heart_veto.human_reserved,
            "issued_at": self.issued_at.isoformat(),
            "canonical_digest": self.canonical_digest,
        }


def build_legitimacy_envelope(
    organization_id: str,
    subject_identity_id: str,
    heart_veto: HeartVetoRecord,
) -> LegitimacyEnvelope:
    """The only intended constructor -- computes `canonical_digest`
    from the other fields, mirroring `build_consent_proof()`'s and
    `build_purpose_binding()`'s own pattern (Phases H4/H5)."""
    envelope_id = str(uuid.uuid4())
    issued_at = datetime.now(UTC)
    digest = compute_legitimacy_envelope_digest(
        envelope_id,
        organization_id,
        subject_identity_id,
        heart_veto.status.value,
        heart_veto.reason,
        heart_veto.detail,
        heart_veto.human_reserved,
        issued_at,
    )
    return LegitimacyEnvelope(
        organization_id=organization_id,
        subject_identity_id=subject_identity_id,
        heart_veto=heart_veto,
        envelope_id=envelope_id,
        issued_at=issued_at,
        canonical_digest=digest,
    )
