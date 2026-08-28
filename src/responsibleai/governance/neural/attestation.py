"""Phase 7 (Enterprise Neural directive) — `NeuralIntentAttestation`,
per the master directive §8-9. See
`docs/enterprise-neural/07_PHASE7_DESIGN.md`.

**What this object proves, stated exactly, not softened** (directive
§8): it does NOT prove a human thought. It proves that a particular
authenticated decoder, using a particular model/calibration, during a
particular session, produced a particular inference, under documented
conditions — bound to an exact proposed action, so that changing any
security-relevant field of that action invalidates the attestation
(§9's mutation-invalidates-authorization requirement, the actual
security property this module exists to implement).

Reuses `governance/crypto`'s `sign`/`verify`/`KeyId` directly (Phase 2)
rather than inventing new cryptography (directive rule 13). The
canonical action-digest helper here deliberately does **not** reuse
`governance/approval.py::compute_action_digest` — that function
requires a full `ActionRequest` (which itself requires an
`AgentContext` neural attestation has no natural value for) and omits
`purpose`, which the directive explicitly lists as a security-relevant
field for action binding. This module follows the same pattern
(canonical JSON, `sort_keys=True`, SHA-256) rather than importing a
function coupled to a different domain object.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from responsibleai.governance.crypto import sign, verify
from responsibleai.governance.neural.decision import NeuralDecision, NeuralDecisionStatus

if TYPE_CHECKING:
    from responsibleai.governance.crypto import KeyId
    from responsibleai.governance.neural.types import ConsentCategory


def compute_neural_action_digest(
    action_type: str,
    target: str,
    purpose: str,
    arguments: dict[str, Any],
) -> str:
    """A stable SHA-256 digest over exactly the fields that define
    "what was attested" — including `purpose`, unlike
    `governance/approval.py::compute_action_digest`, since the
    directive explicitly lists purpose as a security-relevant field
    for action binding (§9)."""
    canonical = json.dumps(
        {
            "action_type": action_type,
            "target": target,
            "purpose": purpose,
            "arguments": arguments,
        },
        sort_keys=True,
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


class NeuralAttestationStatus(StrEnum):
    VALID = "valid"
    REJECTED = "rejected"


class NeuralAttestationRejectReason(StrEnum):
    INVALID_SIGNATURE = "invalid_signature"
    EXPIRED = "expired"
    ACTION_MUTATED = "action_mutated"
    DECISION_NOT_VALID = "decision_not_valid"


@dataclass(frozen=True)
class NeuralAttestationVerificationResult:
    status: NeuralAttestationStatus
    reason: NeuralAttestationRejectReason | None = None

    @property
    def is_valid(self) -> bool:
        return self.status is NeuralAttestationStatus.VALID


@dataclass(frozen=True)
class NeuralIntentAttestation:
    """See module docstring for exactly what this proves and does not
    prove. `decision` embeds the full Phase 6 `NeuralDecision`, not a
    summary — a verifier must be able to check `decision.status`
    directly (see `verify_neural_intent_attestation`), not trust a
    separately-reported flag."""

    schema_version: int
    attestation_id: str
    session_id: str
    subject_id: str
    decision: NeuralDecision
    purpose: str
    target: str
    action_digest: str
    consent_scope: tuple[ConsentCategory, ...]
    issued_at: datetime
    expires_at: datetime
    nonce: str
    signing_key_id: KeyId
    signature: str

    def __post_init__(self) -> None:
        if not self.attestation_id:
            raise ValueError("NeuralIntentAttestation.attestation_id must be non-empty")
        if not self.session_id:
            raise ValueError("NeuralIntentAttestation.session_id must be non-empty")
        if not self.subject_id:
            raise ValueError("NeuralIntentAttestation.subject_id must be non-empty")
        if not self.action_digest:
            raise ValueError("NeuralIntentAttestation.action_digest must be non-empty")
        if not self.nonce:
            raise ValueError("NeuralIntentAttestation.nonce must be non-empty")
        if self.expires_at <= self.issued_at:
            raise ValueError("NeuralIntentAttestation.expires_at must be strictly after issued_at")

    def _signed_material(self) -> bytes:
        """The exact bytes `sign`/`verify` operate over — every field
        that must be tamper-evident, canonically ordered. Excludes
        `signature` itself (obviously) and `signing_key_id` (already
        bound via `KeyId.to_aad()` inside `governance/crypto.sign`)."""
        payload = {
            "schema_version": self.schema_version,
            "attestation_id": self.attestation_id,
            "session_id": self.session_id,
            "subject_id": self.subject_id,
            "decoder_id": self.decision.decoder_id,
            "decoder_version": self.decision.decoder_version,
            "decoder_hash": self.decision.decoder_hash,
            "prediction": self.decision.prediction,
            "purpose": self.purpose,
            "target": self.target,
            "action_digest": self.action_digest,
            "consent_scope": sorted(c.value for c in self.consent_scope),
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "nonce": self.nonce,
        }
        return json.dumps(payload, sort_keys=True).encode("utf-8")


def mint_neural_intent_attestation(
    decision: NeuralDecision,
    *,
    purpose: str,
    target: str,
    action_digest: str,
    consent_scope: tuple[ConsentCategory, ...],
    dek: bytes,
    key_id: KeyId,
    attestation_id: str,
    nonce: str,
    issued_at: datetime,
    ttl_seconds: float,
    schema_version: int = 1,
) -> NeuralIntentAttestation:
    """Mint a new attestation, signed under *dek*/*key_id*. Does not
    itself check `decision.status` — a caller minting an attestation
    for a REJECTED/AMBIGUOUS decision gets one that
    `verify_neural_intent_attestation` will always reject (defense in
    depth: the check exists at verify time regardless of mint-time
    discipline)."""
    unsigned = NeuralIntentAttestation(
        schema_version=schema_version,
        attestation_id=attestation_id,
        session_id=decision.session_id,
        subject_id=decision.subject_id,
        decision=decision,
        purpose=purpose,
        target=target,
        action_digest=action_digest,
        consent_scope=consent_scope,
        issued_at=issued_at,
        expires_at=issued_at + timedelta(seconds=ttl_seconds),
        nonce=nonce,
        signing_key_id=key_id,
        signature="",
    )
    signature = sign(dek, key_id, unsigned._signed_material())
    return NeuralIntentAttestation(
        schema_version=unsigned.schema_version,
        attestation_id=unsigned.attestation_id,
        session_id=unsigned.session_id,
        subject_id=unsigned.subject_id,
        decision=unsigned.decision,
        purpose=unsigned.purpose,
        target=unsigned.target,
        action_digest=unsigned.action_digest,
        consent_scope=unsigned.consent_scope,
        issued_at=unsigned.issued_at,
        expires_at=unsigned.expires_at,
        nonce=unsigned.nonce,
        signing_key_id=unsigned.signing_key_id,
        signature=signature,
    )


def verify_neural_intent_attestation(
    attestation: NeuralIntentAttestation,
    *,
    dek: bytes,
    current_action_digest: str,
    now: datetime,
) -> NeuralAttestationVerificationResult:
    """Fail-closed at every step — any failure returns REJECTED, never
    a partial-trust state. Checked in this order (directive §9's own
    example: recompute the digest for what's actually about to execute
    and reject on mismatch, *before* trusting anything else about the
    attestation)."""
    if not verify(
        dek, attestation.signing_key_id, attestation._signed_material(), attestation.signature
    ):
        return NeuralAttestationVerificationResult(
            status=NeuralAttestationStatus.REJECTED,
            reason=NeuralAttestationRejectReason.INVALID_SIGNATURE,
        )
    if now >= attestation.expires_at:
        return NeuralAttestationVerificationResult(
            status=NeuralAttestationStatus.REJECTED,
            reason=NeuralAttestationRejectReason.EXPIRED,
        )
    if attestation.action_digest != current_action_digest:
        return NeuralAttestationVerificationResult(
            status=NeuralAttestationStatus.REJECTED,
            reason=NeuralAttestationRejectReason.ACTION_MUTATED,
        )
    if attestation.decision.status is not NeuralDecisionStatus.VALID:
        return NeuralAttestationVerificationResult(
            status=NeuralAttestationStatus.REJECTED,
            reason=NeuralAttestationRejectReason.DECISION_NOT_VALID,
        )
    return NeuralAttestationVerificationResult(status=NeuralAttestationStatus.VALID)
