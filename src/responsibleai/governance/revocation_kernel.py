"""Revocation Kernel (Heart Phase H9) — `RevocationEpoch`, the thin,
additive primitive `docs/heart/HEART_CURRENT_STATE.md` §6 specifies
for closing the one confirmed real gap in this codebase's revocation
story: no unifying revocation-state primitive exists today.

**The gap, confirmed by that audit's own grep**: five independent
revocation mechanisms exist, each scoped correctly to its own object
type, none sharing a counter or epoch:

1. Delegation cascading revocation — `db/delegation_repository.py`'s
   `revoke_branch()`.
2. Delegation natural expiry — `governance/delegation.py`'s
   `DelegationRecord.is_active()`.
3. Authority Passport revocation — `db/authority_passport_repository.py`.
4. Authority Passport drift detection — `governance/authority_passport.py`
   (functions as a revocation signal, not literally one).
5. API key revocation — `db/org_repository.py`.

Answering "has anything relevant been revoked since I was issued"
today means separately re-checking all five live, every time — no
existing mechanism lets that become one cheap comparison.

**What this phase deliberately is, and is not**: per the audit's own
classification, this is **not** a refactor of the five mechanisms
above — each keeps its exact existing revocation logic, unchanged.
`RevocationEpoch` is additive: a monotonically increasing counter,
scoped per `(organization_id, scope)`, that something issuing a
point-in-time verdict (a `RootValidationResult`, `ConsentValidationResult`,
`DelegationLegitimacyResult`, or the future `LegitimacyEnvelope`,
Phase H12) can be stamped with at issuance. `check_revocation_epoch()`
then answers "has this scope's epoch advanced since I was issued" as
one integer comparison — `REVOKED_SINCE_ISSUANCE` if so, `CURRENT`
otherwise — without walking any of the five mechanisms individually.

**What actually bumps an epoch is deliberately not decided here**:
this phase does not wire any of the five existing revocation call
sites to call `bump_epoch()`. That wiring is real, separate,
integration work — this phase ships the primitive and its comparison
semantics only, the same scope discipline every Heart phase (H1-H8)
has held to. A `scope` string is intentionally an opaque
caller-defined identifier (e.g. `"delegation"`, `"root_authority"`,
`"org"`) — this module does not enumerate or validate scope names,
since deciding what scopes exist is exactly the wiring decision this
phase defers.

**The other half of this phase**: `docs/heart/HEART_CURRENT_STATE.md`
§3 names a second, concrete, previously-untested gap — cascading
revocation (`revoke_branch()`) has no latency measurement and no
dedicated concurrency/race-condition test, unlike the grant side
(`tests/test_concurrency.py::TestDelegationGrantConcurrency`). This
phase adds both directly to `tests/test_concurrency.py`, honestly
reporting what they actually find rather than assuming cascading
revocation was already a solved problem — see
`TestDelegationRevokeBranchConcurrency` in that file.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


@dataclass(frozen=True)
class RevocationEpoch:
    """A monotonically increasing counter for one `(organization_id,
    scope)` pair. `epoch` starts at `0` for a scope that has never had
    anything revoked; each real revocation event (by whatever
    mechanism a future integration decides bumps this scope) advances
    it by exactly one. Two `RevocationEpoch`s are only comparable when
    their `organization_id` and `scope` match — `check_revocation_epoch()`
    enforces this explicitly rather than silently comparing unrelated
    scopes' counters."""

    organization_id: str
    scope: str
    epoch: int = 0


def bump_epoch(current: RevocationEpoch) -> RevocationEpoch:
    """Advances `current` by exactly one, preserving its
    `organization_id`/`scope`. The only intended way to advance an
    epoch — never construct a `RevocationEpoch` with a hand-picked
    `epoch` value to simulate a bump."""
    return RevocationEpoch(
        organization_id=current.organization_id,
        scope=current.scope,
        epoch=current.epoch + 1,
    )


class RevocationEpochCheckStatus(StrEnum):
    CURRENT = "CURRENT"
    REVOKED_SINCE_ISSUANCE = "REVOKED_SINCE_ISSUANCE"
    SCOPE_MISMATCH = "SCOPE_MISMATCH"


@dataclass(frozen=True)
class RevocationEpochCheckResult:
    status: RevocationEpochCheckStatus
    issued_at_epoch: int
    current_epoch: int

    @property
    def is_current(self) -> bool:
        return self.status == RevocationEpochCheckStatus.CURRENT


def check_revocation_epoch(
    issued_at: RevocationEpoch, current: RevocationEpoch
) -> RevocationEpochCheckResult:
    """`issued_at` is the epoch a verdict was stamped with when
    issued; `current` is the scope's epoch right now. `SCOPE_MISMATCH`
    if `organization_id`/`scope` differ (comparing counters across
    different scopes is meaningless, never silently allowed).
    Otherwise `REVOKED_SINCE_ISSUANCE` if `current.epoch >
    issued_at.epoch` (something in this scope was revoked after this
    verdict was issued — the verdict cannot be trusted as-is,
    regardless of what it originally said), else `CURRENT`. An epoch
    can only advance, never regress (`bump_epoch()` is the only
    constructor that changes `epoch`, and it only increments) so
    `current.epoch < issued_at.epoch` is impossible through normal use
    and is treated the same as equality (`CURRENT`) rather than raising
    -- defensive, not an assumed invariant this function re-verifies."""
    if issued_at.organization_id != current.organization_id or issued_at.scope != current.scope:
        return RevocationEpochCheckResult(
            RevocationEpochCheckStatus.SCOPE_MISMATCH,
            issued_at_epoch=issued_at.epoch,
            current_epoch=current.epoch,
        )
    if current.epoch > issued_at.epoch:
        return RevocationEpochCheckResult(
            RevocationEpochCheckStatus.REVOKED_SINCE_ISSUANCE,
            issued_at_epoch=issued_at.epoch,
            current_epoch=current.epoch,
        )
    return RevocationEpochCheckResult(
        RevocationEpochCheckStatus.CURRENT,
        issued_at_epoch=issued_at.epoch,
        current_epoch=current.epoch,
    )
