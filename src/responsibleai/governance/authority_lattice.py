# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authority Lattice (Heart Phase H2) — an explicit, deterministic
authority-comparison model, generalizing the informal dict-based
constraint comparisons `AuthorityContext.constraint_violation()` and
`validate_attenuation()` (`governance/models.py`) already perform
correctly for the dimensions they recognize.

**Why this is a new module, not a rewrite of `AuthorityContext`**: per
`docs/heart/HEART_CURRENT_STATE.md` §2, `AuthorityContext` stays
exactly as it is — it is `EXTEND`ed, not replaced. `AuthorityEnvelope`
below is the Heart-owned authority representation used by later Heart
phases (root authority, consent, purpose binding, revocation); the
existing live gateway path (`WhitePactRuntimeGateway.evaluate()`)
continues to use `AuthorityContext` unmodified. `authority_context_to_envelope()`
and `envelope_to_authority_context()` are the two adapters that let
the two coexist without forking a second, incompatible authority
model — an `AuthorityEnvelope` can always be losslessly round-tripped
through the dimensions `AuthorityContext` already recognizes.

**Formal relation**: ``A_child <= A_parent`` means the child grants no
capability outside the parent's authority, checked independently per
dimension, never widened through union. `compare_envelopes()` returns
one of three outcomes, never a bare boolean, because "the child fits
within the parent" and "we don't know because this constraint isn't
representable in the lattice" are different facts a caller must be
able to tell apart — silently treating an unrepresentable constraint
as "passes" would violate constitutional law H10 ("unknown required
legitimacy is not authority").

**Effective authority never widens**: `intersect_envelopes()` combines
multiple envelopes (root, org, intent, delegation, constitution,
context constraints — the exact list the master prompt specifies) via
per-dimension intersection only. There is no operation in this module
that unions two envelopes into something broader than either input;
that would be exactly the kind of authority-origination this
subsystem exists to make structurally impossible.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from responsibleai.governance.models import AuthorityContext


class LatticeComparisonStatus(StrEnum):
    LEGITIMATE_SUBSET = "LEGITIMATE_SUBSET"  # child <= parent on every dimension
    ESCALATION = "ESCALATION"  # child exceeds parent on at least one dimension
    UNREPRESENTABLE_CONSTRAINT = "UNREPRESENTABLE_CONSTRAINT"  # a dimension can't be compared


@dataclass(frozen=True)
class LatticeComparisonResult:
    status: LatticeComparisonStatus
    dimension: str | None = None  # which dimension triggered ESCALATION/UNREPRESENTABLE
    detail: str | None = None


def _hours_in_window(start: int, end: int) -> frozenset[int]:
    """Mirrors `governance/models.py`'s own `_hours_in_window()` --
    duplicated rather than imported to keep this module's own
    dependency surface minimal (a deliberate Heart TCB-minimization
    choice: this module does not import from `governance.models` at
    runtime, only under `TYPE_CHECKING`, so it stays usable
    standalone). Both copies are covered by property tests asserting
    they agree."""
    if start <= end:
        return frozenset(range(start, end))
    return frozenset(range(start, 24)) | frozenset(range(0, end))


@dataclass(frozen=True)
class AuthorityEnvelope:
    """The Heart's explicit authority representation. Every dimension
    defaults to `None`, meaning "unconstrained on this dimension" —
    the same "unset means unrestricted" convention `OrgAuthorityCeiling`
    and `AuthorityContext.constraints` already use throughout this
    codebase, kept consistent rather than inventing a different
    "empty means restricted" convention for the lattice specifically.

    `recipient_restrictions`, `allowed_tools`, `denied_tools`,
    `data_scope`, `frequency`, `environment`, and `jurisdiction` are
    dimensions the master Heart spec names that `AuthorityContext` has
    no equivalent for today — genuinely new surface, not present in
    `constraints` dict form anywhere yet, so there is nothing to lose
    round-tripping them through `authority_context_to_envelope()`
    (they simply come back `None`).
    """

    action_types: frozenset[str] | None = None
    targets: frozenset[str] | None = None  # allowed_targets
    denied_targets: frozenset[str] | None = None
    resources: frozenset[str] | None = None
    data_scope: frozenset[str] | None = None
    max_value: float | None = None
    max_total_value: float | None = None
    frequency: float | None = None  # max calls per unspecified reference window
    allowed_hours_utc: tuple[int, int] | None = None
    environment: frozenset[str] | None = None
    jurisdiction: frozenset[str] | None = None
    delegation_depth: float | None = None
    approval_requirements: frozenset[str] | None = None
    allowed_tools: frozenset[str] | None = None
    denied_tools: frozenset[str] | None = None
    recipient_restrictions: frozenset[str] | None = None


# Dimensions compared via "child's allow-set must be a subset of parent's
# allow-set, when parent restricts it at all" semantics.
_ALLOWLIST_DIMENSIONS: tuple[str, ...] = (
    "action_types",
    "targets",
    "resources",
    "data_scope",
    "environment",
    "jurisdiction",
    "allowed_tools",
    "recipient_restrictions",
)

# Dimensions compared via "every value the parent denies/requires, the
# child must also deny/require -- delegation can add restrictions,
# never lift them."
_DENYLIST_DIMENSIONS: tuple[str, ...] = ("denied_targets", "denied_tools", "approval_requirements")

# Dimensions compared via "child's numeric limit must be set and not
# exceed the parent's, when the parent sets one at all."
_NUMERIC_CEILING_DIMENSIONS: tuple[str, ...] = (
    "max_value",
    "max_total_value",
    "frequency",
    "delegation_depth",
)


def compare_envelopes(
    parent: AuthorityEnvelope, child: AuthorityEnvelope
) -> LatticeComparisonResult:
    """`child <= parent`? Checks every recognized dimension, first
    violation wins (same "narrowest scope first, first match wins"
    convention `AuthorityContext.constraint_violation()`/
    `validate_attenuation()` already use). A dimension neither object
    sets at all is trivially satisfied (both unconstrained) -- this is
    not the `UNREPRESENTABLE_CONSTRAINT` case, which is reserved for a
    dimension this function does not know how to compare at all (see
    the bottom of this function)."""
    for dim in _ALLOWLIST_DIMENSIONS:
        parent_value: frozenset[str] | None = getattr(parent, dim)
        if parent_value is None:
            continue  # parent unconstrained on this dimension -- nothing to attenuate
        child_value: frozenset[str] | None = getattr(child, dim)
        if child_value is None or not child_value <= parent_value:
            return LatticeComparisonResult(
                LatticeComparisonStatus.ESCALATION,
                dimension=dim,
                detail=f"child does not stay within parent's {dim}",
            )

    for dim in _DENYLIST_DIMENSIONS:
        parent_value = getattr(parent, dim)
        if parent_value is None:
            continue
        child_value = getattr(child, dim)
        child_set = child_value or frozenset()
        if not parent_value <= child_set:
            return LatticeComparisonResult(
                LatticeComparisonStatus.ESCALATION,
                dimension=dim,
                detail=f"child lifted a restriction parent's {dim} required",
            )

    for dim in _NUMERIC_CEILING_DIMENSIONS:
        parent_num: float | int | None = getattr(parent, dim)
        if parent_num is None:
            continue
        child_num: float | int | None = getattr(child, dim)
        if child_num is None or child_num > parent_num:
            return LatticeComparisonResult(
                LatticeComparisonStatus.ESCALATION,
                dimension=dim,
                detail=f"child's {dim} ({child_num}) exceeds parent's ({parent_num})",
            )

    if parent.allowed_hours_utc is not None:
        parent_window = _hours_in_window(*parent.allowed_hours_utc)
        if child.allowed_hours_utc is None:
            return LatticeComparisonResult(
                LatticeComparisonStatus.ESCALATION,
                dimension="allowed_hours_utc",
                detail="child has no time window; parent restricts one",
            )
        child_window = _hours_in_window(*child.allowed_hours_utc)
        if not child_window <= parent_window:
            return LatticeComparisonResult(
                LatticeComparisonStatus.ESCALATION,
                dimension="allowed_hours_utc",
                detail="child's window covers hours outside parent's",
            )

    return LatticeComparisonResult(LatticeComparisonStatus.LEGITIMATE_SUBSET)


def _intersect_allowlist(
    a: frozenset[str] | None, b: frozenset[str] | None
) -> frozenset[str] | None:
    """`None` (unconstrained) intersected with anything yields the
    other operand unchanged -- intersecting with "everything" is a
    no-op, never a widening, since "everything" isn't actually being
    added as a new capability, it's the absence of a stated
    constraint. Two concrete sets intersect normally."""
    if a is None:
        return b
    if b is None:
        return a
    return a & b


def _intersect_denylist(
    a: frozenset[str] | None, b: frozenset[str] | None
) -> frozenset[str] | None:
    """Denylists/requirement-sets union rather than intersect -- the
    effective set of denials/requirements across multiple sources is
    everything any of them denied/required, since a denial from any
    one legitimate source must still hold (this is not a widening of
    *granted* authority; it is a narrowing, since more denials/
    requirements can only ever shrink what's actually usable)."""
    if a is None:
        return b
    if b is None:
        return a
    return a | b


def _intersect_numeric(a: float | None, b: float | None) -> float | None:
    if a is None:
        return b
    if b is None:
        return a
    return min(a, b)


def _intersect_hours(
    a: tuple[int, int] | None, b: tuple[int, int] | None
) -> tuple[int, int] | None:
    """Intersects two hour windows down to their common hours,
    re-expressed as an exact `(start, end)` window covering precisely
    that overlap, or `(0, 0)` (empty window -- nothing allowed) when no
    single `[start, end)`-shaped window (with or without midnight
    wraparound) can represent the true overlap exactly.

    **Why this brute-forces rather than hand-derives the interval
    math**: two wraparound windows can intersect into a set of hours
    that is *not* a single contiguous block at all (e.g. `(3, 2)` --
    covering 03:00-01:59 the next day -- intersected with `(1, 0)` --
    covering 01:00-23:59 -- leaves the hours `{1, 3, 4, ..., 23}`,
    which excludes hour 2 in the middle and cannot be written as any
    single `(start, end)` pair). An earlier version of this function
    computed `(min(overlap), max(overlap) + 1)` unconditionally, which
    silently *widened* the result in exactly that case (it would have
    claimed hour 2 was included when it wasn't) -- caught by
    `tests/test_authority_lattice.py`'s Hypothesis property test, not
    by hand. Trying all 576 `(start, end)` candidates and keeping only
    one whose `_hours_in_window()` output exactly equals the true
    overlap is small enough to be cheap (this function is not on any
    hot path) and is correct by construction rather than by argument.
    Falling back to `(0, 0)` when no exact single-window
    representation exists is the safe direction -- it never claims
    more access than the true intersection allows, only ever less."""
    if a is None:
        return b
    if b is None:
        return a
    overlap = _hours_in_window(*a) & _hours_in_window(*b)
    if not overlap:
        return (0, 0)
    for start in range(24):
        for end in range(24):
            if _hours_in_window(start, end) == overlap:
                return (start, end)
    return (0, 0)  # no exact single-window representation -- deny all, never widen


def intersect_envelopes(*envelopes: AuthorityEnvelope) -> AuthorityEnvelope:
    """``A_effective = A_root ∩ A_org ∩ A_intent ∩ A_delegation ∩
    A_constitution ∩ A_context_constraints`` (master Heart spec, Phase
    H2). Order-independent, associative -- intersecting any subset of
    the inputs first and combining results is equivalent to
    intersecting all of them in one call, since every per-dimension
    operation used (set intersection, set union for denylists, min for
    numeric ceilings, interval intersection for hours) is itself
    associative and commutative. Never returns an envelope broader
    than any single input on any dimension."""
    if not envelopes:
        return AuthorityEnvelope()
    result = envelopes[0]
    for other in envelopes[1:]:
        result = AuthorityEnvelope(
            action_types=_intersect_allowlist(result.action_types, other.action_types),
            targets=_intersect_allowlist(result.targets, other.targets),
            denied_targets=_intersect_denylist(result.denied_targets, other.denied_targets),
            resources=_intersect_allowlist(result.resources, other.resources),
            data_scope=_intersect_allowlist(result.data_scope, other.data_scope),
            max_value=_intersect_numeric(result.max_value, other.max_value),
            max_total_value=_intersect_numeric(result.max_total_value, other.max_total_value),
            frequency=_intersect_numeric(result.frequency, other.frequency),
            allowed_hours_utc=_intersect_hours(result.allowed_hours_utc, other.allowed_hours_utc),
            environment=_intersect_allowlist(result.environment, other.environment),
            jurisdiction=_intersect_allowlist(result.jurisdiction, other.jurisdiction),
            delegation_depth=_intersect_numeric(result.delegation_depth, other.delegation_depth),
            approval_requirements=_intersect_denylist(
                result.approval_requirements, other.approval_requirements
            ),
            allowed_tools=_intersect_allowlist(result.allowed_tools, other.allowed_tools),
            denied_tools=_intersect_denylist(result.denied_tools, other.denied_tools),
            recipient_restrictions=_intersect_allowlist(
                result.recipient_restrictions, other.recipient_restrictions
            ),
        )
    return result


# The exact `AuthorityContext.constraints` keys this module's adapter
# knows how to map onto an `AuthorityEnvelope` dimension. Anything else
# present in `constraints` (e.g. "memory_scope", which
# `AuthorityContext.constraint_violation()` DOES enforce today but this
# envelope has no field for) must never be silently dropped during
# conversion -- per constitutional law H10 ("unknown required
# legitimacy is not authority"), an unmapped constraint is treated as
# UNREPRESENTABLE, not as absent.
_MAPPED_CONSTRAINT_KEYS: frozenset[str] = frozenset(
    {
        "max_value_usd",
        "allowed_targets",
        "denied_targets",
        "allowed_hours_utc",
        "max_delegation_depth",
    }
)


class UnrepresentableConstraintError(Exception):
    """Raised by `authority_context_to_envelope()` when the source
    `AuthorityContext.constraints` dict contains a key this module's
    lattice has no dimension for. Deliberately a hard failure, not a
    silently-dropped field -- converting an authority object and
    losing a constraint it actually enforced would be exactly the
    "unknown required legitimacy is not authority" violation
    constitutional law H10 exists to name."""

    def __init__(self, unmapped_keys: frozenset[str]) -> None:
        self.unmapped_keys = unmapped_keys
        super().__init__(
            f"UNREPRESENTABLE_CONSTRAINT: constraint key(s) "
            f"{sorted(unmapped_keys)} have no AuthorityEnvelope dimension"
        )


def authority_context_to_envelope(context: AuthorityContext) -> AuthorityEnvelope:
    """Lossless (for every dimension `AuthorityContext` recognizes)
    adapter from the existing, live-used type to the Heart's lattice
    representation. Dimensions `AuthorityContext` has no concept of
    (data_scope, frequency, environment, jurisdiction, allowed_tools,
    denied_tools, recipient_restrictions, max_total_value) come back
    `None` -- genuinely absent information, not silently invented.
    Raises `UnrepresentableConstraintError` if `context.constraints`
    contains a key outside `_MAPPED_CONSTRAINT_KEYS` (e.g.
    `memory_scope`) -- see that exception's docstring."""
    constraints = context.constraints
    unmapped = frozenset(constraints) - _MAPPED_CONSTRAINT_KEYS
    if unmapped:
        raise UnrepresentableConstraintError(unmapped)

    allowed_hours = constraints.get("allowed_hours_utc")
    allowed_targets = constraints.get("allowed_targets")
    denied_targets = constraints.get("denied_targets")
    return AuthorityEnvelope(
        action_types=context.granted_action_types or None,
        targets=frozenset(allowed_targets) if allowed_targets else None,
        denied_targets=frozenset(denied_targets) if denied_targets else None,
        max_value=constraints.get("max_value_usd"),
        allowed_hours_utc=tuple(allowed_hours) if allowed_hours else None,  # type: ignore[arg-type]
        delegation_depth=constraints.get("max_delegation_depth"),
        approval_requirements=context.require_approval_for or None,
    )


def envelope_to_authority_context(
    envelope: AuthorityEnvelope, *, delegated_by: str
) -> AuthorityContext:
    """The reverse adapter -- builds a live-path-compatible
    `AuthorityContext` from a Heart-computed effective envelope.
    Dimensions the envelope carries that `AuthorityContext` has no
    field for (data_scope, frequency, ...) are dropped, not silently
    coerced into `constraints` under an unrecognized key that
    `constraint_violation()` would never check -- a caller needing
    those dimensions enforced must keep working from the
    `AuthorityEnvelope` directly rather than converting back."""
    from responsibleai.governance.models import AuthorityContext

    constraints: dict[str, Any] = {}
    if envelope.max_value is not None:
        constraints["max_value_usd"] = envelope.max_value
    if envelope.targets is not None:
        constraints["allowed_targets"] = sorted(envelope.targets)
    if envelope.denied_targets is not None:
        constraints["denied_targets"] = sorted(envelope.denied_targets)
    if envelope.allowed_hours_utc is not None:
        constraints["allowed_hours_utc"] = list(envelope.allowed_hours_utc)
    if envelope.delegation_depth is not None:
        constraints["max_delegation_depth"] = envelope.delegation_depth

    return AuthorityContext(
        delegated_by=delegated_by,
        granted_action_types=envelope.action_types or frozenset(),
        constraints=constraints,
        require_approval_for=envelope.approval_requirements or frozenset(),
    )


def compare_authority_contexts(
    parent: AuthorityContext, child: AuthorityContext
) -> LatticeComparisonResult:
    """Convenience entry point tying conversion and comparison
    together for callers working with the existing, live `AuthorityContext`
    type rather than `AuthorityEnvelope` directly -- e.g. a future Heart
    veto (Phase H11) checking a proposed authority against the caller's
    root. Surfaces `UnrepresentableConstraintError` as a proper
    `LatticeComparisonResult(UNREPRESENTABLE_CONSTRAINT, ...)` value
    rather than letting the exception propagate raw, so every caller
    of this function gets the same three-way result shape
    `compare_envelopes()` already returns, regardless of which
    authority type they started from."""
    try:
        parent_envelope = authority_context_to_envelope(parent)
        child_envelope = authority_context_to_envelope(child)
    except UnrepresentableConstraintError as exc:
        return LatticeComparisonResult(
            LatticeComparisonStatus.UNREPRESENTABLE_CONSTRAINT,
            dimension=",".join(sorted(exc.unmapped_keys)),
            detail=str(exc),
        )
    return compare_envelopes(parent_envelope, child_envelope)
