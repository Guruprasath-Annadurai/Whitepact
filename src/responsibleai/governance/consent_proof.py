"""Consent Proof (Heart Phase H4) — a structured, digest-bound record
that a specific human (or otherwise-legitimate root) actually
consented to a specific grant of authority, for a specific purpose,
distinguishable from mere *authentication*.

**Why this is not the same thing as authentication or a delegation
grant**: `IdentityContext`/`JWTClaims`/`SAMLAssertionClaims` (see
`docs/heart/HEART_CURRENT_STATE.md` §1) prove *who someone is*.
`DelegationRecord` (`governance/delegation.py`) records *that* an
authority grant happened, with a free-text `purpose: str` field. Prior
to this phase, nothing in the codebase records the *consent act*
itself as a first-class, evidenced, verifiable event — "was this
grant actually agreed to by the party whose authority backs it, or
was it merely constructed by code that had the technical ability to
construct it." `docs/heart/HEART_CURRENT_STATE.md` §4 confirms this is
genuinely new (`ConsentProof (Phase H4) | *(none)* | NEW`).

**The rule this module enforces**: a `ConsentProof` is only legitimate
evidence of consent if (a) it is temporally valid (not revoked,
expired, or not yet in effect), and (b) the party who gave consent
(`consenting_root_id`) itself traces to a legitimate root via
`validate_root_chain()` (Heart Phase H3, `root_authority.py`) — a
"consent" whose own root is illegitimate proves nothing. This module
does not re-verify the root chain itself; `validate_consent_proof()`
takes an already-computed `RootValidationResult` for the consenting
root as a parameter, so this module stays free of any dependency on
how root resolution actually happens (continuing the Heart's
TCB-minimization discipline — see `authority_lattice.py` and
`root_authority.py` for the same pattern: an abstract input, not a
live call to another module's resolver).

**Deliberately minimal PII**: `subject_id` is the same opaque
identifier convention `root_authority.py` already establishes — not a
name, email, or other personal attribute. The `consent_method` and
`evidence_refs` fields record *how* consent was captured and an
opaque pointer to *where* the evidence lives (a signed-form ID, a
recorded-call ID, a UI click-event ID) — never the consent artifact
itself, which stays out of this module by design, exactly like
`RootAuthorityRecord.evidence_refs` already does for root verification
evidence.

**Not built here**: real wiring from an actual consent-capture UI/flow
into a persisted `ConsentProof`, and any DB persistence layer for this
type. This phase ships the record type and its validation semantics
only — the same scope discipline every prior Heart phase (H1-H3) has
held to.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from responsibleai.governance.root_authority import RootValidationResult


class ConsentMethod(StrEnum):
    """How a consent act was actually captured -- never inferred,
    never defaulted. A `ConsentProof` with no defensible method is not
    proof of anything; callers must pick one honestly rather than
    reach for a vague default."""

    EXPLICIT_UI_ACTION = (
        "EXPLICIT_UI_ACTION"  # a recorded click/tap/toggle on a specific consent prompt
    )
    SIGNED_DOCUMENT = "SIGNED_DOCUMENT"  # a signed form, contract, or DocuSign-style envelope
    VERBAL_RECORDED = "VERBAL_RECORDED"  # a recorded verbal consent (call, meeting)
    API_AUTHENTICATED_REQUEST = "API_AUTHENTICATED_REQUEST"  # an authenticated API call whose payload is itself the consent act
    DELEGATED_POLICY = (
        "DELEGATED_POLICY"  # a standing, previously-consented-to policy this act falls under
    )


def _canonical_json(payload: dict[str, Any]) -> str:
    """Same canonicalization discipline `constitution.py`, `approval.py`,
    and `root_authority.py` already use."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_consent_digest(
    consent_id: str,
    subject_id: str,
    consenting_root_id: str,
    grantee_id: str,
    scope_description: str,
    purpose: str,
    consent_method: ConsentMethod,
    evidence_refs: tuple[str, ...],
    consented_at: datetime,
    not_before: datetime | None,
    expires_at: datetime | None,
) -> str:
    """SHA-256 over the canonical JSON of every field that defines what
    this consent act actually asserts. Complete over these fields --
    see `root_authority.py`'s own digest function for why this
    codebase calls that out explicitly rather than leaving readers to
    guess."""
    payload = {
        "consent_id": consent_id,
        "subject_id": subject_id,
        "consenting_root_id": consenting_root_id,
        "grantee_id": grantee_id,
        "scope_description": scope_description,
        "purpose": purpose,
        "consent_method": consent_method.value,
        "evidence_refs": list(evidence_refs),
        "consented_at": consented_at.isoformat(),
        "not_before": not_before.isoformat() if not_before else None,
        "expires_at": expires_at.isoformat() if expires_at else None,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ConsentProof:
    """A claimed act of consent: `subject_id` gave consent, backed by
    the legitimate root `consenting_root_id`, for `grantee_id` to
    exercise authority described by `scope_description`, for
    `purpose`. `evidence_refs` holds opaque references to wherever the
    real consent artifact lives -- WhitePact records that consent
    happened and by what method, not the artifact itself (see module
    docstring)."""

    subject_id: str
    consenting_root_id: str
    grantee_id: str
    scope_description: str
    purpose: str
    consent_method: ConsentMethod
    evidence_refs: tuple[str, ...] = ()
    consent_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    consented_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    not_before: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None
    canonical_digest: str = ""

    def is_temporally_valid(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        if self.revoked_at is not None:
            return False
        if self.not_before is not None and current < self.not_before:
            return False
        if self.expires_at is not None and current >= self.expires_at:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "consent_id": self.consent_id,
            "subject_id": self.subject_id,
            "consenting_root_id": self.consenting_root_id,
            "grantee_id": self.grantee_id,
            "scope_description": self.scope_description,
            "purpose": self.purpose,
            "consent_method": self.consent_method.value,
            "evidence_refs": list(self.evidence_refs),
            "consented_at": self.consented_at.isoformat(),
            "not_before": self.not_before.isoformat() if self.not_before else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoked_by": self.revoked_by,
            "revoke_reason": self.revoke_reason,
            "canonical_digest": self.canonical_digest,
        }


def build_consent_proof(
    subject_id: str,
    consenting_root_id: str,
    grantee_id: str,
    scope_description: str,
    purpose: str,
    consent_method: ConsentMethod,
    *,
    evidence_refs: tuple[str, ...] = (),
    not_before: datetime | None = None,
    expires_at: datetime | None = None,
) -> ConsentProof:
    """The only intended constructor -- computes `canonical_digest`
    from the other fields, mirroring `build_root_authority_record()`'s
    own pattern (Phase H3) so two proofs are the same proof if and
    only if their digests match."""
    consent_id = str(uuid.uuid4())
    consented_at = datetime.now(UTC)
    digest = compute_consent_digest(
        consent_id,
        subject_id,
        consenting_root_id,
        grantee_id,
        scope_description,
        purpose,
        consent_method,
        evidence_refs,
        consented_at,
        not_before,
        expires_at,
    )
    return ConsentProof(
        consent_id=consent_id,
        subject_id=subject_id,
        consenting_root_id=consenting_root_id,
        grantee_id=grantee_id,
        scope_description=scope_description,
        purpose=purpose,
        consent_method=consent_method,
        evidence_refs=evidence_refs,
        consented_at=consented_at,
        not_before=not_before,
        expires_at=expires_at,
        canonical_digest=digest,
    )


class ConsentValidationStatus(StrEnum):
    VALID = "VALID"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    NOT_YET_VALID = "NOT_YET_VALID"
    ROOT_NOT_LEGITIMATE = "ROOT_NOT_LEGITIMATE"
    ROOT_MISMATCH = "ROOT_MISMATCH"


@dataclass(frozen=True)
class ConsentValidationResult:
    status: ConsentValidationStatus
    consent_id: str
    detail: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status == ConsentValidationStatus.VALID


def validate_consent_proof(
    proof: ConsentProof, root_validation: RootValidationResult
) -> ConsentValidationResult:
    """Checks a `ConsentProof` is legitimate evidence of consent:
    temporally valid on its own terms, AND backed by a
    `RootValidationResult` (Heart Phase H3) for the exact root
    `proof.consenting_root_id` claims, that itself came back VALID.
    Callers are responsible for actually computing `root_validation`
    (via `root_authority.validate_root_chain()`) for
    `proof.consenting_root_id` -- this function never resolves a root
    itself, staying dependency-free of `root_authority.py` at runtime
    (only imported under `TYPE_CHECKING`), per the Heart's
    TCB-minimization principle."""
    if root_validation.root_id != proof.consenting_root_id:
        return ConsentValidationResult(
            ConsentValidationStatus.ROOT_MISMATCH,
            proof.consent_id,
            detail=(
                f"root_validation is for root {root_validation.root_id!r}, "
                f"but this proof claims consenting_root_id {proof.consenting_root_id!r}"
            ),
        )
    if not root_validation.is_valid:
        return ConsentValidationResult(
            ConsentValidationStatus.ROOT_NOT_LEGITIMATE,
            proof.consent_id,
            detail=f"consenting root failed validation with status {root_validation.status.value}",
        )
    if not proof.is_temporally_valid():
        if proof.revoked_at is not None:
            return ConsentValidationResult(ConsentValidationStatus.REVOKED, proof.consent_id)
        if proof.not_before is not None and datetime.now(UTC) < proof.not_before:
            return ConsentValidationResult(ConsentValidationStatus.NOT_YET_VALID, proof.consent_id)
        return ConsentValidationResult(ConsentValidationStatus.EXPIRED, proof.consent_id)
    return ConsentValidationResult(ConsentValidationStatus.VALID, proof.consent_id)
