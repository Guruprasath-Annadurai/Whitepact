"""Purpose Binding (Heart Phase H5) — the executable form of
constitutional law H4 ("authority remains bound to purpose").

**Why this is not a new authority-scoping mechanism**: per
`docs/heart/HEART_CURRENT_STATE.md` §4, `governance/intent.py`'s
`IntentContract` already does almost exactly what "purpose binding"
needs -- `allowed_action_types`, `allowed_targets`/`denied_targets`,
`max_value_usd`, `intent_violation()`. Per the master prompt's own
instruction not to duplicate a working feature, `PurposeBinding`
**wraps and references** an existing `IntentContract` via `intent_ref`
(its `contract_id`) rather than reimplementing a second, parallel
purpose-scoping mechanism. What `PurposeBinding` adds is the piece
that didn't exist before: tying that declared intent to the specific
`ConsentProof` (Heart Phase H4) that actually authorized it, so
authority consented to for one purpose cannot be silently exercised
under a different declared intent later.

**The rule this module enforces**: a `PurposeBinding` is only
legitimate when (a) it references the exact `ConsentProof` supplied,
and that proof is itself legitimate (composing with Phase H4's
`ConsentValidationResult`, taken as an already-computed parameter --
never re-derived here), (b) its declared `purpose` matches, verbatim,
the `purpose` the referenced `ConsentProof` actually recorded, and
(c) it references the exact `IntentContract` supplied, and that
contract is currently active.

**Deliberately no semantic purpose matching**: exactly like
`IntentContract.goal` (`intent.py`'s own docstring: "never
machine-parsed"), this module never attempts to judge whether two
*different* purpose strings are "close enough" or "still basically the
same goal." Matching is exact-string only. A caller that wants a
`PurposeBinding` under a rephrased purpose must obtain a new
`ConsentProof` for that exact purpose -- silently accepting "close
enough" is exactly the kind of purpose-drift constitutional law H4
exists to prevent.

**TCB-minimization, continued**: this module imports `ConsentProof`/
`ConsentValidationResult` (`consent_proof.py`) and `IntentContract`
(`intent.py`) only under `TYPE_CHECKING`. `validate_purpose_binding()`
takes fully-resolved objects and an already-computed
`ConsentValidationResult` as parameters -- it never calls
`validate_consent_proof()` or resolves an `IntentContract` by ID
itself, continuing the same "abstract input, not a live call into
another module" pattern `root_authority.py` and `consent_proof.py`
already established.

**Not built here**: any wiring from a real authorization flow that
constructs a `PurposeBinding` from a live `ConsentProof` +
`IntentContract` pair, and any DB persistence layer for this type.
This phase ships the record type and its validation semantics only,
the same scope discipline every prior Heart phase has held to.
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
    from responsibleai.governance.consent_proof import ConsentProof, ConsentValidationResult
    from responsibleai.governance.intent import IntentContract


def _canonical_json(payload: dict[str, Any]) -> str:
    """Same canonicalization discipline every prior Heart module uses."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_purpose_binding_digest(
    binding_id: str,
    purpose: str,
    intent_ref: str,
    consent_ref: str,
    bound_at: datetime,
) -> str:
    """SHA-256 over the canonical JSON of every field that defines what
    this binding actually asserts."""
    payload = {
        "binding_id": binding_id,
        "purpose": purpose,
        "intent_ref": intent_ref,
        "consent_ref": consent_ref,
        "bound_at": bound_at.isoformat(),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class PurposeBinding:
    """Ties a declared `purpose` to the exact `IntentContract`
    (`intent_ref` -- a `contract_id`) that operationally bounds it and
    the exact `ConsentProof` (`consent_ref` -- a `consent_id`) that
    authorized it. Neither referenced object is duplicated here --
    both are resolved and passed in by the caller at validation time,
    per this module's TCB-minimization discipline."""

    purpose: str
    intent_ref: str
    consent_ref: str
    binding_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    bound_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    canonical_digest: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "binding_id": self.binding_id,
            "purpose": self.purpose,
            "intent_ref": self.intent_ref,
            "consent_ref": self.consent_ref,
            "bound_at": self.bound_at.isoformat(),
            "canonical_digest": self.canonical_digest,
        }


def build_purpose_binding(purpose: str, intent_ref: str, consent_ref: str) -> PurposeBinding:
    """The only intended constructor -- computes `canonical_digest`
    from the other fields, mirroring `build_consent_proof()`'s own
    pattern (Phase H4)."""
    binding_id = str(uuid.uuid4())
    bound_at = datetime.now(UTC)
    digest = compute_purpose_binding_digest(binding_id, purpose, intent_ref, consent_ref, bound_at)
    return PurposeBinding(
        purpose=purpose,
        intent_ref=intent_ref,
        consent_ref=consent_ref,
        binding_id=binding_id,
        bound_at=bound_at,
        canonical_digest=digest,
    )


class PurposeBindingStatus(StrEnum):
    VALID = "VALID"
    CONSENT_MISMATCH = "CONSENT_MISMATCH"
    CONSENT_NOT_LEGITIMATE = "CONSENT_NOT_LEGITIMATE"
    PURPOSE_MISMATCH = "PURPOSE_MISMATCH"
    INTENT_MISMATCH = "INTENT_MISMATCH"
    INTENT_NOT_ACTIVE = "INTENT_NOT_ACTIVE"


@dataclass(frozen=True)
class PurposeBindingValidationResult:
    status: PurposeBindingStatus
    binding_id: str
    detail: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status == PurposeBindingStatus.VALID


def validate_purpose_binding(
    binding: PurposeBinding,
    consent_proof: ConsentProof,
    consent_validation: ConsentValidationResult,
    intent_contract: IntentContract,
    *,
    now: datetime | None = None,
) -> PurposeBindingValidationResult:
    """Checks a `PurposeBinding` is legitimate evidence that authority
    exercised under `intent_contract` was actually consented to, for
    the exact purpose declared, via `consent_proof`. Order: does
    `consent_validation` describe the exact `consent_proof` referenced
    (`CONSENT_MISMATCH` if not -- catches a caller passing mismatched
    objects) -> is that consent itself legitimate
    (`CONSENT_NOT_LEGITIMATE` if not) -> does `binding.purpose` match,
    verbatim, `consent_proof.purpose` (`PURPOSE_MISMATCH` if not) ->
    does `intent_contract` match `binding.intent_ref`
    (`INTENT_MISMATCH` if not) -> is `intent_contract` currently active
    (`INTENT_NOT_ACTIVE` if not). Each check is independent and
    explicit -- never silently skipped."""
    if (
        consent_validation.consent_id != binding.consent_ref
        or consent_proof.consent_id != binding.consent_ref
    ):
        return PurposeBindingValidationResult(
            PurposeBindingStatus.CONSENT_MISMATCH,
            binding.binding_id,
            detail=(
                f"binding.consent_ref={binding.consent_ref!r} does not match "
                f"consent_proof.consent_id={consent_proof.consent_id!r} / "
                f"consent_validation.consent_id={consent_validation.consent_id!r}"
            ),
        )
    if not consent_validation.is_valid:
        return PurposeBindingValidationResult(
            PurposeBindingStatus.CONSENT_NOT_LEGITIMATE,
            binding.binding_id,
            detail=f"referenced consent failed validation with status {consent_validation.status.value}",
        )
    if binding.purpose != consent_proof.purpose:
        return PurposeBindingValidationResult(
            PurposeBindingStatus.PURPOSE_MISMATCH,
            binding.binding_id,
            detail=(
                f"binding.purpose={binding.purpose!r} does not exactly match "
                f"consent_proof.purpose={consent_proof.purpose!r}"
            ),
        )
    if intent_contract.contract_id != binding.intent_ref:
        return PurposeBindingValidationResult(
            PurposeBindingStatus.INTENT_MISMATCH,
            binding.binding_id,
            detail=(
                f"binding.intent_ref={binding.intent_ref!r} does not match "
                f"intent_contract.contract_id={intent_contract.contract_id!r}"
            ),
        )
    if not intent_contract.is_active(now=now):
        return PurposeBindingValidationResult(
            PurposeBindingStatus.INTENT_NOT_ACTIVE,
            binding.binding_id,
            detail="referenced intent_contract is not currently active",
        )
    return PurposeBindingValidationResult(PurposeBindingStatus.VALID, binding.binding_id)
