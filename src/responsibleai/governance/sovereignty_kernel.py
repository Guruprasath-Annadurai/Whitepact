# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Sovereignty Kernel Entry Point (Heart Phase H13) — the first, and
so far only, place in this codebase that actually calls the H3-H12
Heart functions together, for one real request, and returns one
`LegitimacyEnvelope`.

**Why this phase looks different from every phase before it**: H1-H12
each deliberately avoided calling any other Heart module at runtime —
every composing phase (H4 onward) took its upstream phase's *already-
computed result* as a parameter rather than resolving it itself, the
"abstract input, not a live call into another module" discipline
named explicitly in every one of their docstrings. That discipline was
never an end in itself; it existed so that *this* module, the one
place actually meant to wire everything together, could do so without
any of H3-H12 secretly depending on each other in ways that would make
this wiring redundant, circular, or surprising. `SovereigntyKernel.evaluate()`
is that wiring, and it is the one Heart module allowed — required — to
import and call H3-H12's real functions directly.

**What `evaluate()` does**: given whichever of root/consent/purpose/
delegation/requested-action-types/revocation-epoch inputs a caller
supplies for one `(organization_id, subject_identity_id)` decision, it
runs the applicable Phase H3-H9 checks (skipping any whose
prerequisites weren't supplied — see "Partial input is a first-class
case" below), composes their verdicts via H10's
`resolve_authority_conflicts()`, applies H11's Heart veto, and wraps
the result in H12's `LegitimacyEnvelope`. One call, one envelope, the
Heart's answer to "does this identity have legitimate authority to
exercise this action right now."

**Partial input is a first-class case, not degraded behavior**: a
caller need not supply every one of root/consent/purpose/delegation —
each downstream check only runs when its own prerequisites are
present (e.g. purpose binding validation needs both a `PurposeBinding`
*and* an already-successful consent validation to check against; if
either is missing, that check is simply skipped, not treated as a
failure). This mirrors H10's own "every input is optional, `None`
means not evaluated, never failed" design exactly — `evaluate()` is
the thing that actually produces those optional inputs for H10 to
consume, but the "optional" contract flows through unchanged.

**Deliberately does not resolve anything from a database** — per every
prior phase's own "not built here," no DB persistence layer exists yet
for `RootAuthorityRecord`, `ConsentProof`, `PurposeBinding`, or
`DelegationRecord`. `evaluate()` accepts already-constructed domain
objects (and, for root-chain walking specifically, an abstract
`RootResolver` callable — the same TCB-minimized resolver shape H3
itself defined) rather than looking anything up. Wiring this to real
persisted state is exactly the kind of live-request integration every
phase before this one has deferred, and remains deferred here too —
this phase makes the *orchestration logic* real, not the data source
behind it.

**No lifetime (H8) or non-delegable (H7) staleness applies to what
this function itself produces** — every verdict `evaluate()` computes
is freshly issued in this same call, so passing a `lifetime` check
into `resolve_authority_conflicts()` here would always trivially
report `FRESH` and add nothing. `check_non_delegable_authority()` (H7)
*is* run, against `requested_action_types`, since that check is
independent of freshness — it is deliberately the eighth input to
`resolve_authority_conflicts()` alongside the five H3-H9 legitimacy
checks this function resolves.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from responsibleai.governance.authority_conflict_resolver import resolve_authority_conflicts
from responsibleai.governance.consent_proof import validate_consent_proof
from responsibleai.governance.delegation_kernel import validate_delegation_legitimacy
from responsibleai.governance.heart_veto import apply_heart_veto
from responsibleai.governance.legitimacy_envelope import (
    LegitimacyEnvelope,
    build_legitimacy_envelope,
)
from responsibleai.governance.non_delegable_authority import check_non_delegable_authority
from responsibleai.governance.purpose_binding import validate_purpose_binding
from responsibleai.governance.revocation_kernel import check_revocation_epoch
from responsibleai.governance.root_authority import validate_root_chain

if TYPE_CHECKING:
    from responsibleai.governance.consent_proof import ConsentProof
    from responsibleai.governance.delegation import DelegationRecord
    from responsibleai.governance.intent import IntentContract
    from responsibleai.governance.purpose_binding import PurposeBinding
    from responsibleai.governance.revocation_kernel import RevocationEpoch
    from responsibleai.governance.root_authority import RootAuthorityRecord, RootResolver


def _default_resolver() -> RootResolver:
    """Default `RootResolver` when the caller doesn't supply one --
    every non-terminal `authority_source` resolves to `None`
    (`SOURCE_NOT_FOUND`), the safe default: a root that needs a chain
    walked but has no way to walk it is not silently treated as
    legitimate."""

    def _no_resolution(root_id: str) -> RootAuthorityRecord | None:  # noqa: ARG001
        return None

    return _no_resolution


def evaluate(
    organization_id: str,
    subject_identity_id: str,
    *,
    root: RootAuthorityRecord | None = None,
    root_resolver: RootResolver | None = None,
    consent: ConsentProof | None = None,
    intent: IntentContract | None = None,
    purpose_binding: PurposeBinding | None = None,
    delegation: DelegationRecord | None = None,
    requested_action_types: frozenset[str] = frozenset(),
    revocation_issued_at: RevocationEpoch | None = None,
    revocation_current: RevocationEpoch | None = None,
    now: datetime | None = None,
) -> LegitimacyEnvelope:
    """Runs whichever of the H3-H9 legitimacy checks the supplied
    inputs make possible, composes them via H10, applies the H11 veto,
    and returns an H12 `LegitimacyEnvelope`. Every input beyond
    `organization_id`/`subject_identity_id` is optional; a check whose
    prerequisites are missing is simply not run, exactly as H10 itself
    already treats a missing input (not evaluated, never failed)."""
    resolver: RootResolver = root_resolver if root_resolver is not None else _default_resolver()
    root_result = validate_root_chain(root, resolver) if root is not None else None

    consent_result = (
        validate_consent_proof(consent, root_result)
        if consent is not None and root_result is not None
        else None
    )

    purpose_result = (
        validate_purpose_binding(purpose_binding, consent, consent_result, intent, now=now)
        if purpose_binding is not None
        and consent is not None
        and consent_result is not None
        and intent is not None
        else None
    )

    delegation_result = (
        validate_delegation_legitimacy(
            delegation,
            root_result,
            consent_result,
            purpose_result,
            expected_subject_identity_id=subject_identity_id,
            expected_purpose=purpose_binding.purpose if purpose_binding is not None else None,
            now=now,
        )
        if delegation is not None
        and root_result is not None
        and consent_result is not None
        and purpose_result is not None
        else None
    )

    non_delegable_result = (
        check_non_delegable_authority(requested_action_types) if requested_action_types else None
    )

    revocation_result = (
        check_revocation_epoch(revocation_issued_at, revocation_current)
        if revocation_issued_at is not None and revocation_current is not None
        else None
    )

    conflict = resolve_authority_conflicts(
        non_delegable=non_delegable_result,
        revocation=revocation_result,
        root=root_result,
        consent=consent_result,
        purpose=purpose_result,
        delegation=delegation_result,
    )
    veto = apply_heart_veto(conflict)
    return build_legitimacy_envelope(organization_id, subject_identity_id, veto)
