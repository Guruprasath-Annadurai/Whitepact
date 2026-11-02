"""Heart Veto (Heart Phase H11) — the executable form of
constitutional law H12 ("Heart veto cannot be overridden"), and the
first Heart module whose entire purpose is to have real teeth rather
than only report a status.

**What this phase adds over H10**: `resolve_authority_conflicts()`
(Phase H10) produces a `ConflictResolutionResult` — a report. Nothing
before this phase actually stops anything from happening on the basis
of that report; a caller could compute a non-`LEGITIMATE` result and
still proceed, since nothing forced a decision. `apply_heart_veto()`
turns that report into a `HeartVetoRecord` — still just data — and
`enforce_heart_veto()` is the sharp edge: it raises `HeartVetoError`
for a vetoed record and is a no-op otherwise, with **no parameter of
any kind that could suppress, downgrade, or bypass a veto**. That
absence is the actual enforcement mechanism for H12, not a comment
promising it: there is no `force=True`, no `override_authority`
argument, no exception subclass a caller could catch and silently
continue past that this module itself provides. A `VETOED` record can
only become `NOT_VETOED` by re-running `apply_heart_veto()` against a
genuinely different, freshly-legitimate `ConflictResolutionResult` —
never by acting on the same one twice with different arguments.

**Why the veto derives from H10, not from any single H3-H9 check
directly**: `ConflictResolutionResult` already resolved which of the
(up to) seven independent Heart legitimacy checks is the single most
severe finding, in the deterministic precedence order H10 established.
The veto does not re-derive or second-guess that precedence — it is a
strict function of it: any `status` other than `LEGITIMATE` vetoes,
full stop. This keeps the veto itself trivially simple and auditable —
its only real decision (what counts as illegitimate enough to veto) was
already made, deliberately, in H10.

**`human_reserved` passes through unchanged**: a vetoed record and a
not-vetoed record can each independently carry `human_reserved=True`
(inherited from the `ConflictResolutionResult` it derives from) — the
veto's binary allow/deny decision and the human-reserved *signal* (H7)
are orthogonal; this module does not conflate them.

**TCB-minimization, continued**: `ConflictResolutionResult` (H10) is
imported only under `TYPE_CHECKING`; this module never calls
`resolve_authority_conflicts()` itself, continuing the same "abstract
input, not a live call into another module" pattern every Heart phase
has used since H4.

**Not built here**: any wiring that calls `enforce_heart_veto()` from
`WhitePactRuntimeGateway.evaluate()` or any other live decision path.
This phase ships the veto's data shape and its enforcement primitive
only — the same scope discipline every Heart phase (H1-H10) has held
to. The veto has no teeth in production until something in the live
path actually calls `enforce_heart_veto()`; this phase makes sure that
when something does, there is no way to build an override into the
call.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from responsibleai.governance.authority_conflict_resolver import ConflictResolutionResult


class HeartVetoStatus(StrEnum):
    NOT_VETOED = "NOT_VETOED"
    VETOED = "VETOED"


@dataclass(frozen=True)
class HeartVetoRecord:
    status: HeartVetoStatus
    reason: str | None = None
    detail: str | None = None
    human_reserved: bool = False

    @property
    def is_vetoed(self) -> bool:
        return self.status == HeartVetoStatus.VETOED


class HeartVetoError(RuntimeError):
    """Raised by `enforce_heart_veto()` for a `VETOED` record.
    Deliberately carries no override/bypass mechanism of its own --
    constitutional law H12 is enforced by this exception's, and
    `enforce_heart_veto()`'s, own signature, not by convention. A
    caller that wants a different outcome must obtain a genuinely
    different, freshly-legitimate `ConflictResolutionResult` and run
    `apply_heart_veto()` again -- there is no parameter here to
    negotiate with."""


def apply_heart_veto(conflict_resolution: ConflictResolutionResult) -> HeartVetoRecord:
    """Derives a `HeartVetoRecord` from an already-computed
    `ConflictResolutionResult` (Phase H10). Any `status` other than
    `LEGITIMATE` vetoes -- this function does not re-derive or
    second-guess H10's own precedence ordering, it is a strict,
    total function of it."""
    if not conflict_resolution.is_legitimate:
        return HeartVetoRecord(
            HeartVetoStatus.VETOED,
            reason=conflict_resolution.status.value,
            detail=conflict_resolution.detail,
            human_reserved=conflict_resolution.human_reserved,
        )
    return HeartVetoRecord(
        HeartVetoStatus.NOT_VETOED,
        human_reserved=conflict_resolution.human_reserved,
    )


def enforce_heart_veto(record: HeartVetoRecord) -> None:
    """Raises `HeartVetoError` if `record.is_vetoed`; otherwise a
    no-op. The only two possible outcomes, deliberately -- no
    parameter here accepts an override authority, a force flag, or a
    bypass reason, because constitutional law H12 requires that none
    can exist."""
    if record.is_vetoed:
        raise HeartVetoError(f"Heart veto: {record.reason} -- {record.detail}")
