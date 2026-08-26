"""Authority Lifetime (Heart Phase H8) — the executable form of
constitutional laws H6 ("expiry overrides previous authorization"),
H13 ("historical authorization does not imply current authorization"),
and H14 ("material authority mutation requires reauthorization").

**The gap this closes**: every object-level expiry check in this
codebase (`RootAuthorityRecord.is_temporally_valid()`,
`ConsentProof.is_temporally_valid()`, `IntentContract.is_active()`,
`DelegationRecord.is_active()`) answers "is *this object* still valid
right now" — a question about the object's own `expires_at`/
`revoked_at` fields. None of them answer a different question: how old
is a *previously-computed verdict* about that object (a
`RootValidationResult`, `ConsentValidationResult`,
`PurposeBindingValidationResult`, or `DelegationLegitimacyResult` from
Phases H3-H6), and is it still safe to trust without re-evaluating.
None of those four result types carry an evaluation timestamp at
all — nothing currently stops a caller from computing one once and
treating it as permanently true, which is exactly the gap
constitutional law H13 names: a `RootValidationResult` that was VALID
an hour ago is not evidence the root is VALID now, only that it *was*.

**Two independent kinds of staleness, not one**:
- **Staleness by age** (H13) — a verdict older than its
  `LifetimeWindow.max_age_seconds` must be treated as stale and
  re-evaluated, regardless of what it originally said. Mirrors the
  existing, live "continuous re-authorization" pattern already
  documented in `MACHINE_AUTHORITY_V1.md` §2 (a delegation is checked
  fresh on every governed call, not cached from grant time) —
  generalized here from one specific object type to all four Heart
  verdict types.
- **Staleness by mutation** (H14) — even a verdict computed moments
  ago is stale if the underlying object it describes has since
  materially changed, detected by comparing the object's
  `canonical_digest` (every Heart record type from H1/H3/H4/H5 already
  computes one) at evaluation time against its current value. A
  digest mismatch is checked *before* age, since a materially mutated
  object invalidates a verdict regardless of how recently it was
  computed — the same "most fundamental problem surfaces first"
  ordering principle H4-H7 already established.

**Deliberately does not itself re-run any validation** — this module
answers "is this verdict still safe to trust," not "what would a fresh
evaluation say." A caller that receives `STALE_BY_AGE` or
`STALE_BY_MUTATION` is expected to re-run the relevant Phase H3-H6
validation function itself; `check_lifetime()` never calls
`validate_root_chain()`/`validate_consent_proof()`/
`validate_purpose_binding()`/`validate_delegation_legitimacy()`,
keeping this module dependency-free of all four, continuing the
Heart's TCB-minimization discipline.

**Default lifetime windows are suggestions, not enforced defaults** —
named constants below reflect how frequently each artifact type is
expected to change (delegation state can change fastest — revocation
is immediate and continuous re-authorization already treats it that
way; a root of authority changes rarest). Callers may supply any
`LifetimeWindow`; nothing in this module requires using the named
presets.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


@dataclass(frozen=True)
class LifetimeWindow:
    """How long a computed verdict may be trusted before it must be
    treated as stale and re-evaluated, purely on the basis of age
    (independent of the mutation check)."""

    max_age_seconds: float


# Suggested defaults, not enforced -- see module docstring. Shortest
# for delegation (matches the existing "checked fresh on every call"
# continuous-reauthorization pattern), longest for root authority
# (changes rarest of the four).
ROOT_AUTHORITY_LIFETIME_WINDOW = LifetimeWindow(max_age_seconds=86_400.0)  # 24h
CONSENT_PROOF_LIFETIME_WINDOW = LifetimeWindow(max_age_seconds=86_400.0)  # 24h
PURPOSE_BINDING_LIFETIME_WINDOW = LifetimeWindow(max_age_seconds=3_600.0)  # 1h
DELEGATION_LEGITIMACY_LIFETIME_WINDOW = LifetimeWindow(max_age_seconds=300.0)  # 5min


class LifetimeStatus(StrEnum):
    FRESH = "FRESH"
    STALE_BY_MUTATION = "STALE_BY_MUTATION"
    STALE_BY_AGE = "STALE_BY_AGE"


@dataclass(frozen=True)
class LifetimeCheckResult:
    status: LifetimeStatus
    age_seconds: float
    max_age_seconds: float
    evaluated_digest: str | None = None
    current_digest: str | None = None

    @property
    def is_fresh(self) -> bool:
        return self.status == LifetimeStatus.FRESH


def check_lifetime(
    evaluated_at: datetime,
    window: LifetimeWindow,
    *,
    evaluated_digest: str | None = None,
    current_digest: str | None = None,
    now: datetime | None = None,
) -> LifetimeCheckResult:
    """Checks whether a verdict computed at `evaluated_at` is still
    safe to trust. Order: mutation first (`STALE_BY_MUTATION` if both
    digests are supplied and differ -- a materially changed object
    invalidates a verdict regardless of age), then age
    (`STALE_BY_AGE` if older than `window.max_age_seconds`), otherwise
    `FRESH`. Digest comparison is skipped entirely (never contributes
    a `STALE_BY_MUTATION` result) when either digest is `None` --
    callers without a digest to compare (or checking a verdict type
    this phase didn't originally have a digest for) still get a valid
    age-only check rather than an error."""
    current = now or datetime.now(UTC)
    age_seconds = (current - evaluated_at).total_seconds()
    if (
        evaluated_digest is not None
        and current_digest is not None
        and evaluated_digest != current_digest
    ):
        return LifetimeCheckResult(
            LifetimeStatus.STALE_BY_MUTATION,
            age_seconds=age_seconds,
            max_age_seconds=window.max_age_seconds,
            evaluated_digest=evaluated_digest,
            current_digest=current_digest,
        )
    if age_seconds > window.max_age_seconds:
        return LifetimeCheckResult(
            LifetimeStatus.STALE_BY_AGE,
            age_seconds=age_seconds,
            max_age_seconds=window.max_age_seconds,
            evaluated_digest=evaluated_digest,
            current_digest=current_digest,
        )
    return LifetimeCheckResult(
        LifetimeStatus.FRESH,
        age_seconds=age_seconds,
        max_age_seconds=window.max_age_seconds,
        evaluated_digest=evaluated_digest,
        current_digest=current_digest,
    )
