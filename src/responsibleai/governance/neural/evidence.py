"""Phase 16 (Enterprise Neural directive) — the scientific evidence
contract behind a `CapabilityState.VALIDATED` claim. See
`docs/enterprise-neural/16_PHASE16_DESIGN.md`.

`device.py`'s own module docstring quotes the master directive
directly: "WhitePact's own measured capability evidence determines
what WhitePact labels validated." `NeuralCapabilityManifest`'s
`max_capability_state_for_trust_level()` ceiling enforces a
*necessary* condition for that claim (a sufficiently trusted device
transport) but not the *sufficient* one the directive's own language
describes (actual measured evidence). This module is that missing
sufficient condition, made fail-closed and typed — no concrete study,
device, or measurement is fabricated here; see the design doc for why
building one now would be exactly the kind of prototype capability
fabrication the master directive prohibits, the same reasoning
`device.py`/`decision.py` already apply to hardware and decoders.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from responsibleai.governance.neural.device import NeuralCapabilityManifest


class NeuralEvidenceType(StrEnum):
    """Distinguished by *who measured it*, since that's the directive's
    own stated criterion for a VALIDATED claim. Deliberately not a
    single flat "has evidence" boolean -- the whole point is that not
    every kind of evidence qualifies."""

    WHITEPACT_MEASURED = "whitepact_measured"
    INDEPENDENT_THIRD_PARTY = "independent_third_party"
    REGULATORY_CLEARANCE = "regulatory_clearance"
    # Deliberately NOT a qualifying type on its own -- see
    # _QUALIFYING_EVIDENCE_TYPES below and this module's own docstring.
    VENDOR_SELF_REPORTED = "vendor_self_reported"


_QUALIFYING_EVIDENCE_TYPES: frozenset[NeuralEvidenceType] = frozenset(
    {
        NeuralEvidenceType.WHITEPACT_MEASURED,
        NeuralEvidenceType.INDEPENDENT_THIRD_PARTY,
        NeuralEvidenceType.REGULATORY_CLEARANCE,
    }
)


@dataclass(frozen=True)
class NeuralCapabilityEvidence:
    """One piece of evidence for one capability of one device. No
    assumption about where these are actually persisted -- an opaque,
    DB-agnostic shape, matching `ConsentRecord`'s own convention
    (Phase 4) of shipping the typed record ahead of any concrete
    storage layer.

    `evidence_ref` is an opaque citation/document pointer (a DOI, an
    internal report ID, a regulatory filing number) -- this module
    makes no claim about resolving or verifying it; recording *which*
    evidence backs a claim is this module's job, not adjudicating the
    evidence's own content.
    """

    device_identity: str
    capability_name: str
    evidence_type: NeuralEvidenceType
    description: str
    evidence_ref: str
    recorded_at: datetime

    def __post_init__(self) -> None:
        if not self.device_identity:
            raise ValueError("NeuralCapabilityEvidence.device_identity must be non-empty")
        if not self.capability_name:
            raise ValueError("NeuralCapabilityEvidence.capability_name must be non-empty")
        if not self.description:
            raise ValueError("NeuralCapabilityEvidence.description must be non-empty")
        if not self.evidence_ref:
            raise ValueError("NeuralCapabilityEvidence.evidence_ref must be non-empty")


class NeuralEvidenceDecision(StrEnum):
    ALLOW = "allow"
    DENY = "deny"


class NeuralEvidenceReason(StrEnum):
    EVIDENCE_QUALIFIES = "evidence_qualifies"
    NO_EVIDENCE_RECORD = "no_evidence_record"
    EVIDENCE_INSUFFICIENT = "evidence_insufficient"
    NOT_A_VALIDATED_CLAIM = "not_a_validated_claim"


@dataclass(frozen=True)
class NeuralEvidenceResult:
    decision: NeuralEvidenceDecision
    reason: NeuralEvidenceReason
    capability_name: str

    @property
    def is_allowed(self) -> bool:
        return self.decision is NeuralEvidenceDecision.ALLOW


def evaluate_capability_validation_claim(
    manifest: NeuralCapabilityManifest,
    capability_name: str,
    evidence_records: tuple[NeuralCapabilityEvidence, ...],
) -> NeuralEvidenceResult:
    """Whether *manifest*'s `VALIDATED` claim for *capability_name* is
    substantiated. Fail-closed: no matching evidence record at all, or
    only `VENDOR_SELF_REPORTED` ones, is DENY. A capability the
    manifest doesn't claim as VALIDATED in the first place returns
    NOT_A_VALIDATED_CLAIM -- there is nothing to substantiate, and
    folding that case into ALLOW or DENY would misrepresent which
    question this function actually answered.

    Deliberately does not check `evidence_records[i].device_identity ==
    manifest.device_identity` -- that cross-referencing is a caller
    concern (which evidence store to query for which device), not this
    function's; it evaluates exactly the *evidence_records* it's given
    against exactly the *capability_name* asked about.
    """
    if not manifest.is_validated(capability_name):
        return NeuralEvidenceResult(
            decision=NeuralEvidenceDecision.ALLOW,
            reason=NeuralEvidenceReason.NOT_A_VALIDATED_CLAIM,
            capability_name=capability_name,
        )

    matching = [e for e in evidence_records if e.capability_name == capability_name]
    if not matching:
        return NeuralEvidenceResult(
            decision=NeuralEvidenceDecision.DENY,
            reason=NeuralEvidenceReason.NO_EVIDENCE_RECORD,
            capability_name=capability_name,
        )

    if not any(e.evidence_type in _QUALIFYING_EVIDENCE_TYPES for e in matching):
        return NeuralEvidenceResult(
            decision=NeuralEvidenceDecision.DENY,
            reason=NeuralEvidenceReason.EVIDENCE_INSUFFICIENT,
            capability_name=capability_name,
        )

    return NeuralEvidenceResult(
        decision=NeuralEvidenceDecision.ALLOW,
        reason=NeuralEvidenceReason.EVIDENCE_QUALIFIES,
        capability_name=capability_name,
    )
