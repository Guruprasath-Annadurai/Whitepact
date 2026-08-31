# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WhitePact Authority Constitution (Heart Phase H1) — the versioned,
immutable set of laws that protect the integrity of the authority
system itself, distinct from `governance/policy.py`'s `Policy`.

**Constitution vs. Policy — the distinction this module exists to
enforce**: `Policy` (`governance/policy.py`) is deliberately
org-mutable — an admin can add, remove, or reorder rules for their own
organization via `PolicyRepository`, and `Policy.version` tracks that
mutation history. The Constitution is the opposite: a small, fixed set
of laws that protect the *mechanism* every org's policy runs on top
of. No customer admin API exists to disable, weaken, or reorder a
constitutional law — there is no `add_law()`/`remove_law()` on this
module by design, mirroring `Policy`'s own mutability being a
deliberate feature, not an oversight to fix.

**Historical immutability**: `_CONSTITUTION_HISTORY` is a
`MappingProxyType`, not a plain dict — a real, enforced guarantee
(not just a comment) that a ratified version's law set can never be
mutated in place once published. Amending the constitution means
ratifying a new, higher-numbered version and adding it to the
registry; every prior version stays exactly as it was, forever,
because evidence recorded against version N must remain explicable
against exactly what version N actually said, even after version N+1
exists.

**Scope of this phase**: this module implements the constitution
object and its registry only — `AuthorityConstitutionVersion`,
`current_constitution()`, `get_constitution_version()`,
`explain_constitution()`. Wiring a `constitution_version` field into
`DecisionResult`/`EvidenceRecord` so every future decision is stamped
with which version was active, and building a Heart veto that
actually *evaluates* inputs against these laws, are later phases
(H11-H12) — this phase's job is to make the constitution a real,
digestible, testable object other Heart phases can reference, not to
wire it into the live decision path yet.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum
from types import MappingProxyType
from typing import Any


class ConstitutionalLawCode(StrEnum):
    """The fifteen constitutional laws (Heart master prompt, Phase H1).
    Each value is the law's short code; `LAW_TEXT` below carries the
    actual normative text, kept separate from the enum so the text can
    be reviewed/quoted without needing the enum's own machinery."""

    H1 = "H1"  # Every machine authority has a legitimate root.
    H2 = "H2"  # Machines cannot originate authority.
    H3 = "H3"  # Delegation may only attenuate.
    H4 = "H4"  # Authority remains bound to purpose.
    H5 = "H5"  # Revocation overrides previous authorization.
    H6 = "H6"  # Expiry overrides previous authorization.
    H7 = "H7"  # Memory cannot create authority.
    H8 = "H8"  # Probabilistic reasoning cannot create authority.
    H9 = "H9"  # Tools cannot create authority.
    H10 = "H10"  # Unknown required legitimacy is not authority.
    H11 = "H11"  # Non-delegable authority remains non-delegable.
    H12 = "H12"  # Heart veto cannot be overridden.
    H13 = "H13"  # Historical authorization does not imply current authorization.
    H14 = "H14"  # Material authority mutation requires reauthorization.
    H15 = "H15"  # Execution may never exceed Heart effective authority.


LAW_TEXT: MappingProxyType[ConstitutionalLawCode, str] = MappingProxyType(
    {
        ConstitutionalLawCode.H1: "Every machine authority has a legitimate root.",
        ConstitutionalLawCode.H2: "Machines cannot originate authority.",
        ConstitutionalLawCode.H3: "Delegation may only attenuate.",
        ConstitutionalLawCode.H4: "Authority remains bound to purpose.",
        ConstitutionalLawCode.H5: "Revocation overrides previous authorization.",
        ConstitutionalLawCode.H6: "Expiry overrides previous authorization.",
        ConstitutionalLawCode.H7: "Memory cannot create authority.",
        ConstitutionalLawCode.H8: "Probabilistic reasoning cannot create authority.",
        ConstitutionalLawCode.H9: "Tools cannot create authority.",
        ConstitutionalLawCode.H10: "Unknown required legitimacy is not authority.",
        ConstitutionalLawCode.H11: "Non-delegable authority remains non-delegable.",
        ConstitutionalLawCode.H12: "Heart veto cannot be overridden.",
        ConstitutionalLawCode.H13: (
            "Historical authorization does not imply current authorization."
        ),
        ConstitutionalLawCode.H14: "Material authority mutation requires reauthorization.",
        ConstitutionalLawCode.H15: "Execution may never exceed Heart effective authority.",
    }
)


def _canonical_json(payload: dict[str, Any]) -> str:
    """Sorted-key, separator-normalized JSON — the same canonicalization
    discipline `governance/approval.py`'s action-digest computation
    already establishes for this codebase, reused here rather than
    inventing a second convention."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_constitution_digest(
    version: int,
    laws: tuple[ConstitutionalLawCode, ...],
    ratified_at: datetime,
    description: str,
) -> str:
    """SHA-256 over the canonical JSON of every field that defines
    what this constitution version actually says — `version`, the
    exact ordered law set, `ratified_at`, and `description`. Complete
    over these fields, not a narrower subset a reader might assume is
    covered (see `governance/constitution.py`'s module docstring for
    why this is called out explicitly, per the same discipline
    `db/evidence_repository.py`'s hash-chain limitation taught this
    codebase to be honest about)."""
    payload = {
        "version": version,
        "laws": [law.value for law in laws],
        "ratified_at": ratified_at.isoformat(),
        "description": description,
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthorityConstitutionVersion:
    """One ratified, immutable version of the WhitePact Authority
    Constitution. `canonical_digest` is computed once at construction
    (via `build_constitution_version()`, the only intended
    constructor) and never recomputed — two versions are the same
    version if and only if their digests match."""

    version: int
    laws: tuple[ConstitutionalLawCode, ...]
    ratified_at: datetime
    description: str
    canonical_digest: str

    def law_text(self, code: ConstitutionalLawCode) -> str:
        return LAW_TEXT[code]

    def contains(self, code: ConstitutionalLawCode) -> bool:
        return code in self.laws

    def explain(self) -> dict[str, Any]:
        """A deterministic, structured explanation of this version --
        no LLM call, matching `DelegationRepository.explain_authority()`'s
        own "prefer deterministic security controls" discipline."""
        return {
            "version": self.version,
            "ratified_at": self.ratified_at.isoformat(),
            "description": self.description,
            "canonical_digest": self.canonical_digest,
            "laws": [{"code": law.value, "text": self.law_text(law)} for law in self.laws],
        }


def build_constitution_version(
    version: int,
    laws: tuple[ConstitutionalLawCode, ...],
    ratified_at: datetime,
    description: str,
) -> AuthorityConstitutionVersion:
    """The only intended constructor for `AuthorityConstitutionVersion`
    -- computes `canonical_digest` from the other fields so the two can
    never drift apart. Pure; no I/O."""
    digest = compute_constitution_digest(version, laws, ratified_at, description)
    return AuthorityConstitutionVersion(
        version=version,
        laws=laws,
        ratified_at=ratified_at,
        description=description,
        canonical_digest=digest,
    )


# ── The ratified constitution history ───────────────────────────────────────
#
# Append-only. Never edit an existing entry's laws/description/ratified_at
# once published -- doing so would silently change what a past
# `constitution_version` reference actually meant. To amend the
# constitution, ratify a new version with a higher number and add it
# below; every prior version stays exactly as it was.

CONSTITUTION_V1: AuthorityConstitutionVersion = build_constitution_version(
    version=1,
    laws=tuple(ConstitutionalLawCode),
    ratified_at=datetime(2026, 8, 25, tzinfo=UTC),
    description=(
        "Initial ratification of the WhitePact Authority Constitution -- "
        "all fifteen founding laws (H1-H15), establishing that legitimate "
        "machine authority must trace to a human- or organization-established "
        "root, that delegation may only attenuate, and that the Heart's veto "
        "cannot be overridden by any downstream subsystem."
    ),
)

_CONSTITUTION_HISTORY: MappingProxyType[int, AuthorityConstitutionVersion] = MappingProxyType(
    {1: CONSTITUTION_V1}
)


def get_constitution_version(version: int) -> AuthorityConstitutionVersion | None:
    """`None` for a version that was never ratified -- callers must
    handle absence explicitly, never assume version 1 as a silent
    fallback (that would violate H10: unknown required legitimacy is
    not authority)."""
    return _CONSTITUTION_HISTORY.get(version)


def current_constitution() -> AuthorityConstitutionVersion:
    """The highest ratified version -- what a newly-issued
    `LegitimacyEnvelope` (a later Heart phase) is stamped with."""
    return _CONSTITUTION_HISTORY[max(_CONSTITUTION_HISTORY)]


def explain_constitution(version: int) -> dict[str, Any] | None:
    """`None` for an unratified version, matching
    `get_constitution_version()`'s own explicit-absence convention."""
    found = get_constitution_version(version)
    return found.explain() if found is not None else None
