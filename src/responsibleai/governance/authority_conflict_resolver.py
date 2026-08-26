"""Authority Conflict Resolver (Heart Phase H10) — the single point
that decides, when multiple independent Heart legitimacy checks
(Phases H3-H9) are available for the same authority decision and they
disagree, which verdict wins and in what deterministic order.

**The gap this closes**: every Heart phase so far built one
independent check — root legitimacy (H3), consent legitimacy (H4),
purpose binding (H5), delegation legitimacy (H6), non-delegable
category (H7), verdict staleness (H8), revocation-epoch currency (H9).
Nothing decides what a caller holding several of these results at once
should conclude when they conflict — e.g. a root that's VALID but an
epoch that shows `REVOKED_SINCE_ISSUANCE`, or a delegation that's
`LEGITIMATE` but a `NonDelegableViolation` present for the same
request. Silently picking "whichever one I happened to check first"
would make the overall answer depend on call order, not on the actual
severity of what's wrong — this module fixes one deterministic
precedence order instead.

**Precedence, most severe/foundational first** (mirrors the same
"most fundamental problem surfaces first" principle H4-H9 already
established, generalized here across phases rather than within one):

1. `NON_DELEGABLE` (H7) — this category of authority can never be
   delegated at all; nothing else about the request's legitimacy
   matters if this fires.
2. `REVOKED` (H9) — a revocation-epoch check that isn't `CURRENT`
   (either `REVOKED_SINCE_ISSUANCE` or `SCOPE_MISMATCH`, treated the
   same way here: fail closed — a scope mismatch means this module
   cannot even confirm it's comparing the right epoch, which is not
   evidence of safety) invalidates the request regardless of what any
   individual verdict below says.
3. `ROOT_NOT_LEGITIMATE` (H3) — everything downstream depends on a
   legitimate root; check it before anything that presupposes one.
4. `CONSENT_NOT_LEGITIMATE` (H4)
5. `PURPOSE_NOT_BOUND` (H5)
6. `DELEGATION_NOT_LEGITIMATE` (H6)
7. `STALE` (H8) — checked last among the blocking reasons, since a
   stale verdict is a "cannot currently confirm," not a "confirmed
   illegitimate" the way 1-6 are; if anything more severe already
   fired, that's the more informative answer to surface.
8. `LEGITIMATE` — every supplied check passed (or was not supplied at
   all; `None` inputs are skipped, not treated as failures — a caller
   that didn't compute a particular Heart phase's result for this
   request is not thereby denied for it).

**`human_reserved` is a separate, non-blocking signal, not a status**:
a `NonDelegableViolation` with `NonDelegableScope.HUMAN_RESERVED`
(rather than `NON_DELEGABLE`) does not by itself produce a denial —
`HUMAN_RESERVED` authority may be delegated to *initiate*, per H7's
own definition — but is still surfaced on the result so a caller can
act on it (e.g. enforcing mandatory human execution), exactly as H7's
own docstring already deferred that enforcement to "a future phase's
execution-time enforcement."

**TCB-minimization, continued**: every one of the seven possible
inputs is imported only under `TYPE_CHECKING`; `resolve_authority_conflicts()`
takes fully-resolved result objects as parameters and never calls any
of the seven Phase H3-H9 functions itself, continuing the same
"abstract input, not a live call into another module" pattern every
Heart phase has used since H4.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from responsibleai.governance.authority_lifetime import LifetimeCheckResult
    from responsibleai.governance.consent_proof import ConsentValidationResult
    from responsibleai.governance.delegation_kernel import DelegationLegitimacyResult
    from responsibleai.governance.non_delegable_authority import NonDelegableViolation
    from responsibleai.governance.purpose_binding import PurposeBindingValidationResult
    from responsibleai.governance.revocation_kernel import RevocationEpochCheckResult
    from responsibleai.governance.root_authority import RootValidationResult


class ConflictResolutionStatus(StrEnum):
    LEGITIMATE = "LEGITIMATE"
    NON_DELEGABLE = "NON_DELEGABLE"
    REVOKED = "REVOKED"
    ROOT_NOT_LEGITIMATE = "ROOT_NOT_LEGITIMATE"
    CONSENT_NOT_LEGITIMATE = "CONSENT_NOT_LEGITIMATE"
    PURPOSE_NOT_BOUND = "PURPOSE_NOT_BOUND"
    DELEGATION_NOT_LEGITIMATE = "DELEGATION_NOT_LEGITIMATE"
    STALE = "STALE"


@dataclass(frozen=True)
class ConflictResolutionResult:
    status: ConflictResolutionStatus
    human_reserved: bool = False
    detail: str | None = None

    @property
    def is_legitimate(self) -> bool:
        return self.status == ConflictResolutionStatus.LEGITIMATE


def resolve_authority_conflicts(
    *,
    non_delegable: NonDelegableViolation | None = None,
    revocation: RevocationEpochCheckResult | None = None,
    root: RootValidationResult | None = None,
    consent: ConsentValidationResult | None = None,
    purpose: PurposeBindingValidationResult | None = None,
    delegation: DelegationLegitimacyResult | None = None,
    lifetime: LifetimeCheckResult | None = None,
) -> ConflictResolutionResult:
    """Every parameter is optional -- a caller supplies whichever of
    the seven Phase H3-H9 results it has computed for this request;
    `None` means "not evaluated," never "failed." Returns the single
    most severe finding per the module docstring's precedence order,
    or `LEGITIMATE` if every supplied check passed. `human_reserved`
    is set independently of `status` whenever `non_delegable` names a
    `HUMAN_RESERVED`-scope finding, even when the overall `status`
    ends up `LEGITIMATE`."""
    human_reserved = False
    if non_delegable is not None:
        if non_delegable.scope.value == "NON_DELEGABLE":
            return ConflictResolutionResult(
                ConflictResolutionStatus.NON_DELEGABLE,
                detail=non_delegable.reason,
            )
        human_reserved = True

    if revocation is not None and not revocation.is_current:
        return ConflictResolutionResult(
            ConflictResolutionStatus.REVOKED,
            human_reserved=human_reserved,
            detail=f"revocation epoch check returned {revocation.status.value}",
        )

    if root is not None and not root.is_valid:
        return ConflictResolutionResult(
            ConflictResolutionStatus.ROOT_NOT_LEGITIMATE,
            human_reserved=human_reserved,
            detail=f"root validation returned {root.status.value}",
        )

    if consent is not None and not consent.is_valid:
        return ConflictResolutionResult(
            ConflictResolutionStatus.CONSENT_NOT_LEGITIMATE,
            human_reserved=human_reserved,
            detail=f"consent validation returned {consent.status.value}",
        )

    if purpose is not None and not purpose.is_valid:
        return ConflictResolutionResult(
            ConflictResolutionStatus.PURPOSE_NOT_BOUND,
            human_reserved=human_reserved,
            detail=f"purpose binding validation returned {purpose.status.value}",
        )

    if delegation is not None and not delegation.is_legitimate:
        return ConflictResolutionResult(
            ConflictResolutionStatus.DELEGATION_NOT_LEGITIMATE,
            human_reserved=human_reserved,
            detail=f"delegation legitimacy check returned {delegation.status.value}",
        )

    if lifetime is not None and not lifetime.is_fresh:
        return ConflictResolutionResult(
            ConflictResolutionStatus.STALE,
            human_reserved=human_reserved,
            detail=f"lifetime check returned {lifetime.status.value}",
        )

    return ConflictResolutionResult(
        ConflictResolutionStatus.LEGITIMATE, human_reserved=human_reserved
    )
