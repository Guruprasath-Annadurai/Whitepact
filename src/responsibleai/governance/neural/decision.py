"""Phase 6 (Enterprise Neural directive) — the typed `NeuralDecision`
contract, per the master directive §33-34. See
`docs/enterprise-neural/06_PHASE6_DESIGN.md`.

No decoder ships in this module — see the design doc Sec 0 for why
building one now (no real trained model or device signal to validate
against) would be exactly the kind of prototype the master directive
prohibits. This module builds the typed decision object and the
misuse-rejection logic (NaN/Inf, out-of-range, expired, stale decoder,
context mismatch) that operates purely on the *shape* of a decision,
which is genuinely testable without a real decoder.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from responsibleai.governance.neural.device import DeviceTrustLevel


class NeuralDecisionStatus(StrEnum):
    """Per the master directive §7: "uncertainty must not become forced
    intent." A REJECTED or AMBIGUOUS decision must never be treated as
    a command by any later phase."""

    VALID = "valid"
    AMBIGUOUS = "ambiguous"
    REJECTED = "rejected"


def _is_unit_probability(value: float) -> bool:
    """True iff *value* is a finite float in [0.0, 1.0]. A plain bounds
    check already rejects NaN and +/-Inf without a separate
    `math.isnan`/`math.isinf` call — Python's comparison operators
    always evaluate to False against NaN, and +/-Inf simply fail the
    bound — verified empirically before relying on it here."""
    return 0.0 <= value <= 1.0


@dataclass(frozen=True)
class NeuralDecision:
    """Every field the master directive's §7 requires. Never a naked
    confidence float — see that section's own reasoning. `__post_init__`
    rejects malformed values unconditionally; it does not merely warn.
    """

    schema_version: int
    prediction: str
    calibrated_probability: float
    uncertainty: float
    signal_quality: float
    decoder_id: str
    decoder_version: str
    decoder_hash: str
    calibration_id: str
    calibration_version: str
    subject_id: str
    session_id: str
    device_reference: str
    device_trust: DeviceTrustLevel
    issued_at: datetime
    expires_at: datetime
    status: NeuralDecisionStatus
    provenance: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for field_name in (
            "decoder_id",
            "decoder_hash",
            "calibration_id",
            "subject_id",
            "session_id",
        ):
            if not getattr(self, field_name):
                raise ValueError(f"NeuralDecision.{field_name} must be non-empty")
        if not _is_unit_probability(self.calibrated_probability):
            raise ValueError(
                "NeuralDecision.calibrated_probability must be a finite value in "
                f"[0.0, 1.0], got {self.calibrated_probability!r}"
            )
        if not _is_unit_probability(self.uncertainty):
            raise ValueError(
                f"NeuralDecision.uncertainty must be a finite value in [0.0, 1.0], "
                f"got {self.uncertainty!r}"
            )
        if not _is_unit_probability(self.signal_quality):
            raise ValueError(
                f"NeuralDecision.signal_quality must be a finite value in [0.0, 1.0], "
                f"got {self.signal_quality!r}"
            )
        if self.expires_at <= self.issued_at:
            raise ValueError(
                "NeuralDecision.expires_at must be strictly after issued_at "
                f"(issued_at={self.issued_at.isoformat()!r}, "
                f"expires_at={self.expires_at.isoformat()!r})"
            )


def classify_decision_status(
    calibrated_probability: float,
    uncertainty: float,
    *,
    ambiguous_uncertainty_threshold: float,
    min_valid_probability: float,
) -> NeuralDecisionStatus:
    """Pure classification, not baked into `NeuralDecision.__post_init__`
    — the thresholds are decoder-specific policy `NeuralDecision` itself
    has no opinion on. Callers assign the resulting status when
    constructing a `NeuralDecision`.

    Uncertainty is checked before probability: a genuinely uncertain
    decision is AMBIGUOUS regardless of where its point estimate landed,
    not silently REJECTED for a low probability that the uncertainty
    itself explains.
    """
    if not math.isfinite(calibrated_probability) or not math.isfinite(uncertainty):
        return NeuralDecisionStatus.REJECTED
    if uncertainty > ambiguous_uncertainty_threshold:
        return NeuralDecisionStatus.AMBIGUOUS
    if calibrated_probability < min_valid_probability:
        return NeuralDecisionStatus.REJECTED
    return NeuralDecisionStatus.VALID


def is_expired(decision: NeuralDecision, *, now: datetime) -> bool:
    return now >= decision.expires_at


def matches_context(
    decision: NeuralDecision,
    *,
    subject_id: str,
    session_id: str,
    device_reference: str,
) -> bool:
    """Wrong-user/wrong-session/wrong-device detection — all three must
    match, not any one of them (a decision for the right subject on the
    wrong device is still a mismatch)."""
    return (
        decision.subject_id == subject_id
        and decision.session_id == session_id
        and decision.device_reference == device_reference
    )


def is_stale_decoder(decision: NeuralDecision, *, current_decoder_version: str) -> bool:
    return decision.decoder_version != current_decoder_version
