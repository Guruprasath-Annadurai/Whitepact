"""Delegation Kernel (Heart Phase H6) — combines the three independent
legitimacy checks Phases H3-H5 already established (root, consent,
purpose) with a `DelegationRecord`'s own state into one composed
verdict: is this specific act of delegation actually legitimate, all
the way up, not just internally well-formed.

**Why this is not a new delegation data model** — per
`docs/heart/HEART_CURRENT_STATE.md` §3, `DelegationRecord`
(`governance/delegation.py`) already has "everything Phase H6 needs:
parent pointer, attenuation-checked grant, expiry, revocation fields,"
and `DelegationRepository` (`db/delegation_repository.py`) already
provides `grant()`, `get_active_delegation()`, `get_authority_chain()`,
`revoke_branch()`, `get_org_graph()`, `get_descendants()` — real,
tested, and exactly what a delegation kernel needs operationally.
`DelegationGraph`/`DelegationGraphNode` (Authority Everywhere Phase 6,
`governance/delegation_graph.py`) already provide the org-wide,
queryable *shape* of the delegation forest. None of that is rebuilt
here. What was missing is the Heart-level question none of those
answer: even a perfectly well-formed, correctly-attenuated
`DelegationRecord` (`validate_attenuation()`, `governance/models.py`,
already enforces `child ⊆ parent` at grant time) says nothing about
whether the *delegator's own authority* traces to a legitimate root
(H3), was actually consented to (H4), and stays bound to its declared
purpose (H5). `validate_delegation_legitimacy()` is the single
composition point for those three answers.

**TCB-minimization, continued**: this module takes fully-resolved
`RootValidationResult`/`ConsentValidationResult`/`PurposeBindingValidationResult`
objects (Phases H3, H4, H5) as parameters — it never resolves a root
chain, validates a consent proof, or validates a purpose binding
itself. `DelegationRecord` (`governance/delegation.py`) is imported
only under `TYPE_CHECKING`, so `delegation_kernel.py` has zero runtime
dependency on any of the four modules it composes.

**A partial cross-reference check, added in Phase H15**: `DelegationRecord`
has no field linking it to a specific `RootAuthorityRecord.root_id` or
`ConsentProof.consent_id` — it predates the Heart (Authority Everywhere
Phase 8) and per the H0 audit's own REUSE classification is not being
schema-changed by this phase. This module still cannot cross-check
that `root_validation`/`consent_validation` actually pertain to this
specific `delegation`. It *can*, however, cross-check the two fields
`DelegationRecord` already carries that any caller with the surrounding
context (an identity, a validated purpose) can compare against:
`to_identity_id` and `purpose`. `validate_delegation_legitimacy()`'s
optional `expected_subject_identity_id`/`expected_purpose` parameters
do exactly that, closing a real, concretely-demonstrated gap Phase
H15's adversarial gauntlet found: a `DelegationRecord` for a
completely unrelated identity and purpose, supplied alongside a
genuinely legitimate but unrelated root/consent/purpose chain,
previously validated as `LEGITIMATE` end-to-end via
`governance/sovereignty_kernel.py`'s `evaluate()`, since nothing
anywhere in the chain checked that the delegation being evaluated was
the delegation the chain was actually about. Both parameters are
optional and default to `None` (skip the check, exactly the prior
behavior) for backward compatibility with existing callers that don't
have this context to supply. The remaining, narrower gap (root/consent
still uncross-checkable) is unchanged and still named honestly.

**Not built here**: any wiring from a real delegation-grant flow that
resolves the three composed results for a specific `DelegationRecord`,
any `DelegationRecord` schema change to carry those cross-references,
and any DB persistence for this module's own result type (it has none
to persist — `DelegationLegitimacyResult` is a point-in-time
computation, not a stored record, the same way `RootValidationResult`
and `ConsentValidationResult` are never persisted either).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from responsibleai.governance.consent_proof import ConsentValidationResult
    from responsibleai.governance.delegation import DelegationRecord
    from responsibleai.governance.purpose_binding import PurposeBindingValidationResult
    from responsibleai.governance.root_authority import RootValidationResult


class DelegationLegitimacyStatus(StrEnum):
    LEGITIMATE = "LEGITIMATE"
    DELEGATION_MISMATCH = "DELEGATION_MISMATCH"
    ROOT_NOT_LEGITIMATE = "ROOT_NOT_LEGITIMATE"
    CONSENT_NOT_LEGITIMATE = "CONSENT_NOT_LEGITIMATE"
    PURPOSE_NOT_BOUND = "PURPOSE_NOT_BOUND"
    DELEGATION_NOT_ACTIVE = "DELEGATION_NOT_ACTIVE"


@dataclass(frozen=True)
class DelegationLegitimacyResult:
    status: DelegationLegitimacyStatus
    delegation_id: str
    detail: str | None = None

    @property
    def is_legitimate(self) -> bool:
        return self.status == DelegationLegitimacyStatus.LEGITIMATE


def validate_delegation_legitimacy(
    delegation: DelegationRecord,
    root_validation: RootValidationResult,
    consent_validation: ConsentValidationResult,
    purpose_validation: PurposeBindingValidationResult,
    *,
    expected_subject_identity_id: str | None = None,
    expected_purpose: str | None = None,
    now: datetime | None = None,
) -> DelegationLegitimacyResult:
    """Composes the three independent Heart legitimacy checks with
    `delegation`'s own active/revoked/expired state into one verdict.
    Order: cross-reference match (`DELEGATION_MISMATCH`, only checked
    when the caller supplies `expected_subject_identity_id`/
    `expected_purpose` -- see module docstring) -> root legitimacy
    (`ROOT_NOT_LEGITIMATE`) -> consent legitimacy
    (`CONSENT_NOT_LEGITIMATE`) -> purpose binding (`PURPOSE_NOT_BOUND`)
    -> the delegation's own current state (`DELEGATION_NOT_ACTIVE`) --
    the most foundational, upstream problem is always surfaced first,
    mirroring the same ordering principle Phases H4 and H5 already
    established (a downstream object's own local state is checked
    last, after every upstream legitimacy question is answered)."""
    if (
        expected_subject_identity_id is not None
        and delegation.to_identity_id != expected_subject_identity_id
    ):
        return DelegationLegitimacyResult(
            DelegationLegitimacyStatus.DELEGATION_MISMATCH,
            delegation.delegation_id,
            detail=(
                f"delegation.to_identity_id={delegation.to_identity_id!r} does not match "
                f"expected_subject_identity_id={expected_subject_identity_id!r}"
            ),
        )
    if expected_purpose is not None and delegation.purpose != expected_purpose:
        return DelegationLegitimacyResult(
            DelegationLegitimacyStatus.DELEGATION_MISMATCH,
            delegation.delegation_id,
            detail=(
                f"delegation.purpose={delegation.purpose!r} does not match "
                f"expected_purpose={expected_purpose!r}"
            ),
        )
    if not root_validation.is_valid:
        return DelegationLegitimacyResult(
            DelegationLegitimacyStatus.ROOT_NOT_LEGITIMATE,
            delegation.delegation_id,
            detail=f"delegator's root failed validation with status {root_validation.status.value}",
        )
    if not consent_validation.is_valid:
        return DelegationLegitimacyResult(
            DelegationLegitimacyStatus.CONSENT_NOT_LEGITIMATE,
            delegation.delegation_id,
            detail=f"consent behind this grant failed validation with status {consent_validation.status.value}",
        )
    if not purpose_validation.is_valid:
        return DelegationLegitimacyResult(
            DelegationLegitimacyStatus.PURPOSE_NOT_BOUND,
            delegation.delegation_id,
            detail=f"purpose binding failed validation with status {purpose_validation.status.value}",
        )
    if not delegation.is_active(now=now):
        return DelegationLegitimacyResult(
            DelegationLegitimacyStatus.DELEGATION_NOT_ACTIVE,
            delegation.delegation_id,
            detail="delegation itself is revoked or expired",
        )
    return DelegationLegitimacyResult(
        DelegationLegitimacyStatus.LEGITIMATE, delegation.delegation_id
    )
