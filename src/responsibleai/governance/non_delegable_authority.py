# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Non-Delegable and Human-Reserved Authority (Heart Phase H7) — the
executable form of constitutional law H11 ("non-delegable authority
remains non-delegable").

**The gap this closes**: every Heart phase so far (H3-H6) answers
"is this specific grant of authority legitimate" — a well-formed
question about *provenance*. None of them answer a logically prior
question: is this *category* of authority even the kind of thing that
can be delegated at all, regardless of how legitimate its root,
consent, and purpose are. A `DelegationRecord` whose `granted_action_types`
includes "amend the WhitePact constitution" can be perfectly
attenuation-checked, root-legitimate, consented-to, and purpose-bound
(H2-H6 all pass) and still be something no delegated authority may
ever hold — machines may exercise authority, they may never be handed
the authority to redefine what authority itself means (constitutional
laws H1/H2, enforced here specifically for the meta-operations that
would let a delegate rewrite the rules governing delegation itself).

**Two distinct severities, not one**:
- `NON_DELEGABLE` — this action type can never appear in any
  delegated grant, at any depth, under any circumstances. Reserved for
  the Heart's own self-protecting, meta-level operations: amending the
  constitution, issuing or revoking a root of authority, overriding a
  Heart veto. If a machine could be delegated these, delegation itself
  could be used to escape every other constraint this codebase
  enforces.
- `HUMAN_RESERVED` — this action type *can* be delegated (an agent may
  hold the authority to *initiate* or *request* it), but its actual
  execution must always require a human in the loop, unconditionally —
  a constitutional floor beneath the org-configurable
  `require_approval_for` mechanism (`governance/models.py`), which an
  org's own policy could otherwise choose to drop for actions it deems
  low-risk. `HUMAN_RESERVED` is a signal this module surfaces, not an
  outright block; a future phase's execution-time enforcement (outside
  this phase's scope) is responsible for turning it into an actual
  mandatory-approval gate.

**Deliberately narrow, deliberately not org-configurable**: the
registry below is fixed, code-defined, and Heart-owned — the exact
"WhitePact constitution vs. customer policy" distinction
`governance/constitution.py`'s own docstring already establishes for
constitutional laws generally. It intentionally does not include
ordinary business-domain action types (payments, deployments, data
access) — those stay governed by the existing, org-mutable
`Policy`/`AuthorityContext.require_approval_for` machinery. This
registry only reserves the meta-operations that would let a delegate
undermine the Heart's own guarantees.

**Pattern matching reuses `fnmatch`**, the same mechanism
`IntentContract.denied_targets`/`allowed_targets` (`intent.py`) already
uses, rather than inventing a second pattern language.

**Not built here**: any extension mechanism for an organization to add
its own `HUMAN_RESERVED` action types on top of this fixed set (a
real, plausible future need, but a live, persisted, org-configurable
registry is separate work this phase doesn't attempt); and any
execution-time enforcement that actually turns a `HUMAN_RESERVED`
finding into a mandatory approval gate — this phase surfaces the
finding, it does not yet act on it.
"""

from __future__ import annotations

import fnmatch
from dataclasses import dataclass
from enum import StrEnum
from types import MappingProxyType


class NonDelegableScope(StrEnum):
    NON_DELEGABLE = "NON_DELEGABLE"
    HUMAN_RESERVED = "HUMAN_RESERVED"


# Fixed, Heart-owned registry: action-type fnmatch pattern -> (scope, reason).
# Ordering is significant only for test determinism (MappingProxyType
# preserves insertion order); severity, not position, decides which
# violation wins when multiple action types match (see
# check_non_delegable_authority()'s own two-pass logic below).
_REGISTRY: MappingProxyType[str, tuple[NonDelegableScope, str]] = MappingProxyType(
    {
        "heart.constitution.*": (
            NonDelegableScope.NON_DELEGABLE,
            "Amending or re-ratifying the WhitePact constitution is a human/organization-only "
            "act (constitutional laws H1, H2) -- no delegated authority may hold this action type.",
        ),
        "heart.root_authority.issue": (
            NonDelegableScope.NON_DELEGABLE,
            "Issuing a new root of authority is a human/organization-only act (constitutional "
            "law H2: machines cannot originate authority) -- delegating the power to mint roots "
            "would let a delegate manufacture its own legitimacy.",
        ),
        "heart.root_authority.revoke": (
            NonDelegableScope.NON_DELEGABLE,
            "Revoking a root of authority is a human/organization-only act -- delegating this "
            "would let a delegate sever the very chain its own legitimacy depends on.",
        ),
        "heart.veto.override": (
            NonDelegableScope.NON_DELEGABLE,
            "A Heart veto cannot be overridden by any authority, delegated or otherwise "
            "(constitutional law H12) -- the authority to override one cannot exist to delegate "
            "in the first place.",
        ),
        "heart.consent.revoke_on_behalf_of_other": (
            NonDelegableScope.NON_DELEGABLE,
            "Revoking another party's consent on their behalf is a human/organization-only act "
            "-- only the consenting party or an authorized human may revoke a ConsentProof.",
        ),
        "legal.attestation.sign": (
            NonDelegableScope.HUMAN_RESERVED,
            "Signing a legally binding attestation may be initiated by a delegated agent, but "
            "its actual execution must always require a human in the loop, regardless of any "
            "org policy's require_approval_for configuration.",
        ),
        "heart.authority.emergency_override": (
            NonDelegableScope.HUMAN_RESERVED,
            "An emergency authority override may be requested by a delegated agent, but its "
            "actual execution must always require a human in the loop.",
        ),
    }
)


@dataclass(frozen=True)
class NonDelegableViolation:
    action_type: str
    matched_pattern: str
    scope: NonDelegableScope
    reason: str


def check_non_delegable_authority(action_types: frozenset[str]) -> NonDelegableViolation | None:
    """`None` if no `action_types` entry matches any reserved pattern.
    Otherwise the single most severe violation: every `NON_DELEGABLE`
    match is checked before any `HUMAN_RESERVED` match, so a request
    that trips both severities is reported as the stronger one, not
    whichever happened to match first. Within one severity level,
    `action_types` are checked in sorted order and `_REGISTRY` patterns
    in their fixed definition order, so the result is deterministic
    for a given input regardless of set iteration order.

    **Matching is deliberately case-insensitive** -- `fnmatch.fnmatch()`'s
    own case-sensitivity is platform-dependent (normalizes via
    `os.path.normcase`, a no-op on POSIX, lowercasing on Windows), which
    Phase H15's adversarial gauntlet found meant a request for
    `"HEART.VETO.OVERRIDE"` was silently *not* caught by the
    all-lowercase `_REGISTRY` patterns on this codebase's actual
    deployment platform -- a real, trivial case-relabeling bypass of a
    security-critical deny-list. Both `action_type` and `pattern` are
    explicitly `.casefold()`-ed before comparison here, independent of
    platform, closing that gap outright rather than depending on
    `fnmatch`'s own, inconsistent case behavior."""
    for scope in (NonDelegableScope.NON_DELEGABLE, NonDelegableScope.HUMAN_RESERVED):
        for action_type in sorted(action_types):
            for pattern, (pattern_scope, reason) in _REGISTRY.items():
                if pattern_scope is scope and fnmatch.fnmatch(
                    action_type.casefold(), pattern.casefold()
                ):
                    return NonDelegableViolation(
                        action_type=action_type,
                        matched_pattern=pattern,
                        scope=scope,
                        reason=reason,
                    )
    return None
