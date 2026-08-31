# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authority Passport (Authority Everywhere Phase 5) — a portable,
issuable, revocable, independently verifiable representation of a
principal's held authority, generalizing `governance/ceiling.py`'s
`OrgAuthorityCeiling` and `governance/delegation.py`'s `DelegationRecord`
beyond the in-process objects they are today.

**Naming**: `docs/architecture/AUTHORITY_EVERYWHERE.md`'s Phase 2
naming-collision resolution reserved "Authority Passport" for exactly
this concept, to avoid colliding with the unrelated, already-shipped
`trust/passport.py` (`AIPassport` — a *model's* Trust Index
certification, nothing to do with principal authority). `AuthorityPassport`
below is a new, distinctly-named type; nothing under `trust/*` is
touched.

**Not cryptographically signed** — the same reasoning
`governance/attestation.py` and `governance/execution.py` already give
for their own records, generalized: a live signing key held by the
running server process is a real secret-management/rotation burden
this project has no infrastructure for, and a forged passport would
require the same DB write access that could also rewrite its own
source ceiling/delegation row — at which point an automated in-process
signature would not be verifying anything an attacker couldn't also
forge. Crossing a process/trust boundary (a passport verified by a
*different* service than the one that issued it) is the condition
under which real signing would become load-bearing; not built here.

**What "independently verifiable" means here, concretely**: a passport
is never trusted on its own claimed fields. `verify_passport()` always
re-fetches the live source it was derived from (the org's current
`OrgAuthorityCeiling`, or the specific `DelegationRecord` it was
exported from) and compares — integrity by linkage to that already-real,
DB-backed source, the same pattern `attestation.py` already established
against `EvidenceRecord`'s hash chain. A passport whose source has
since been narrowed, widened, or removed is flagged `DRIFTED` or
`SOURCE_NOT_FOUND`, not silently trusted.

**Not built here**: wiring a *presented* passport into
`WhitePactRuntimeGateway.evaluate()`'s live per-call authority
resolution as an alternative to the fresh ceiling/delegation lookup
`mcp/governance_integration.py` already performs on every call. That is
real, separate integration work — deciding how much to trust a
passport a caller presents versus re-deriving authority fresh carries
its own threat model this phase doesn't attempt. Today
`AuthorityPassport` is the portable, exportable, independently
verifiable *representation* of a principal's authority, not (yet) a
new input to the hot governance-decision path.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import TYPE_CHECKING, Any

from responsibleai.governance.models import AuthorityContext

if TYPE_CHECKING:
    from responsibleai.governance.ceiling import OrgAuthorityCeiling
    from responsibleai.governance.delegation import DelegationRecord


@dataclass(frozen=True)
class AuthorityPassport:
    """A portable snapshot of what `principal_id` was authorized to do
    at `issued_at`, derived from exactly one source (`source`/`source_id`
    identify which). Revocation is tracked on the passport itself,
    independent of its source — an org can revoke one exported passport
    without touching the underlying ceiling or delegation it came from,
    narrowing exposure of that one credential."""

    organization_id: str
    principal_id: str
    source: str  # "org_ceiling" | "delegation"
    source_id: str
    granted_action_types: tuple[str, ...]
    max_value_usd: float | None = None
    allowed_targets: tuple[str, ...] | None = None
    denied_targets: tuple[str, ...] | None = None
    require_approval_for: tuple[str, ...] = ()
    max_delegation_depth: int | None = None
    passport_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None

    def is_active(self, now: datetime | None = None) -> bool:
        if self.revoked_at is not None:
            return False
        current = now or datetime.now(UTC)
        if self.expires_at is not None and current >= self.expires_at:
            return False
        return True

    def to_authority_context(self) -> AuthorityContext:
        """The `AuthorityContext` this passport's grants correspond to
        -- not consumed by the live gateway path today (see module
        docstring), but the natural shape for a future caller that
        wants to evaluate an action against a *presented* passport
        directly, without re-deriving one from a ceiling/delegation."""
        constraints: dict[str, object] = {}
        if self.max_value_usd is not None:
            constraints["max_value_usd"] = self.max_value_usd
        if self.allowed_targets is not None:
            constraints["allowed_targets"] = list(self.allowed_targets)
        if self.denied_targets is not None:
            constraints["denied_targets"] = list(self.denied_targets)
        if self.max_delegation_depth is not None:
            constraints["max_delegation_depth"] = self.max_delegation_depth
        return AuthorityContext(
            delegated_by=f"passport:{self.passport_id}",
            granted_action_types=frozenset(self.granted_action_types),
            constraints=constraints,
            require_approval_for=frozenset(self.require_approval_for),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "passport_id": self.passport_id,
            "organization_id": self.organization_id,
            "principal_id": self.principal_id,
            "source": self.source,
            "source_id": self.source_id,
            "granted_action_types": list(self.granted_action_types),
            "max_value_usd": self.max_value_usd,
            "allowed_targets": list(self.allowed_targets) if self.allowed_targets else None,
            "denied_targets": list(self.denied_targets) if self.denied_targets else None,
            "require_approval_for": list(self.require_approval_for),
            "max_delegation_depth": self.max_delegation_depth,
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoked_by": self.revoked_by,
            "revoke_reason": self.revoke_reason,
        }


def build_authority_passport_from_ceiling(
    ceiling: OrgAuthorityCeiling,
    principal_id: str,
    *,
    expires_at: datetime | None = None,
) -> AuthorityPassport:
    """Exports the org's current structural ceiling as a portable
    passport for `principal_id`. `granted_action_types` mirrors
    `OrgAuthorityCeiling.to_authority_context()`'s own "unset means
    unrestricted" convention only where meaningful for a standalone
    export: an unset `allowed_action_types` on a ceiling synthesizes a
    single-action grant per call (it needs the action being evaluated);
    a passport has no such call to synthesize from, so an unset
    allowlist here means "no action-type grant at all" -- a caller
    wanting a broader passport must set the ceiling's
    `allowed_action_types` explicitly first."""
    return AuthorityPassport(
        organization_id=ceiling.org_id,
        principal_id=principal_id,
        source="org_ceiling",
        source_id=ceiling.org_id,
        granted_action_types=tuple(ceiling.allowed_action_types or ()),
        max_value_usd=ceiling.max_value_usd,
        allowed_targets=tuple(ceiling.allowed_targets) if ceiling.allowed_targets else None,
        denied_targets=tuple(ceiling.denied_targets) if ceiling.denied_targets else None,
        require_approval_for=tuple(sorted(ceiling.require_approval_for)),
        max_delegation_depth=ceiling.max_delegation_depth,
        expires_at=expires_at,
    )


def build_authority_passport_from_delegation(
    delegation: DelegationRecord,
    *,
    expires_at: datetime | None = None,
) -> AuthorityPassport:
    """Exports an active delegation grant as a portable passport for
    the identity it was granted to (`delegation.to_identity_id`)."""
    constraints = delegation.constraints
    return AuthorityPassport(
        organization_id=delegation.org_id,
        principal_id=delegation.to_identity_id,
        source="delegation",
        source_id=delegation.delegation_id,
        granted_action_types=tuple(sorted(delegation.granted_action_types)),
        max_value_usd=constraints.get("max_value_usd"),
        allowed_targets=(
            tuple(constraints["allowed_targets"]) if constraints.get("allowed_targets") else None
        ),
        denied_targets=(
            tuple(constraints["denied_targets"]) if constraints.get("denied_targets") else None
        ),
        require_approval_for=tuple(sorted(delegation.require_approval_for)),
        max_delegation_depth=constraints.get("max_delegation_depth"),
        expires_at=expires_at or delegation.expires_at,
    )


class PassportStatus(StrEnum):
    VALID = "VALID"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    DRIFTED = "DRIFTED"  # still active, but no longer matches its live source
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"  # the ceiling/delegation it came from is gone or inactive


@dataclass(frozen=True)
class PassportVerificationResult:
    status: PassportStatus
    passport_id: str
    detail: str | None = None


def _ceiling_grants_match(passport: AuthorityPassport, ceiling: OrgAuthorityCeiling) -> bool:
    return (
        tuple(sorted(passport.granted_action_types))
        == tuple(sorted(ceiling.allowed_action_types or ()))
        and passport.max_value_usd == ceiling.max_value_usd
        and (passport.allowed_targets or None)
        == (tuple(ceiling.allowed_targets) if ceiling.allowed_targets else None)
        and (passport.denied_targets or None)
        == (tuple(ceiling.denied_targets) if ceiling.denied_targets else None)
        and passport.max_delegation_depth == ceiling.max_delegation_depth
        and tuple(sorted(passport.require_approval_for))
        == tuple(sorted(ceiling.require_approval_for))
    )


def _delegation_grants_match(passport: AuthorityPassport, delegation: DelegationRecord) -> bool:
    constraints = delegation.constraints
    return (
        tuple(sorted(passport.granted_action_types))
        == tuple(sorted(delegation.granted_action_types))
        and passport.max_value_usd == constraints.get("max_value_usd")
        and (passport.allowed_targets or None)
        == (tuple(constraints["allowed_targets"]) if constraints.get("allowed_targets") else None)
        and (passport.denied_targets or None)
        == (tuple(constraints["denied_targets"]) if constraints.get("denied_targets") else None)
        and passport.max_delegation_depth == constraints.get("max_delegation_depth")
        and tuple(sorted(passport.require_approval_for))
        == tuple(sorted(delegation.require_approval_for))
    )


def verify_passport(
    passport: AuthorityPassport,
    *,
    ceiling: OrgAuthorityCeiling | None = None,
    delegation: DelegationRecord | None = None,
) -> PassportVerificationResult:
    """Re-checks `passport` against whichever live source object the
    caller fetched fresh (a `GET .../authority-passports/{id}` handler
    fetches the right one based on `passport.source`/`source_id` before
    calling this). Never trusts the passport's own claimed fields
    alone -- see module docstring."""
    if passport.revoked_at is not None:
        return PassportVerificationResult(PassportStatus.REVOKED, passport.passport_id)
    if passport.expires_at is not None and datetime.now(UTC) >= passport.expires_at:
        return PassportVerificationResult(PassportStatus.EXPIRED, passport.passport_id)

    if passport.source == "org_ceiling":
        if ceiling is None:
            return PassportVerificationResult(
                PassportStatus.SOURCE_NOT_FOUND,
                passport.passport_id,
                detail="ceiling no longer configured",
            )
        if not _ceiling_grants_match(passport, ceiling):
            return PassportVerificationResult(
                PassportStatus.DRIFTED,
                passport.passport_id,
                detail="ceiling has changed since issuance",
            )
        return PassportVerificationResult(PassportStatus.VALID, passport.passport_id)

    if passport.source == "delegation":
        if delegation is None or not delegation.is_active():
            return PassportVerificationResult(
                PassportStatus.SOURCE_NOT_FOUND,
                passport.passport_id,
                detail="source delegation no longer active",
            )
        if not _delegation_grants_match(passport, delegation):
            return PassportVerificationResult(
                PassportStatus.DRIFTED,
                passport.passport_id,
                detail="delegation has changed since issuance",
            )
        return PassportVerificationResult(PassportStatus.VALID, passport.passport_id)

    return PassportVerificationResult(
        PassportStatus.SOURCE_NOT_FOUND,
        passport.passport_id,
        detail=f"unknown source kind {passport.source!r}",
    )
