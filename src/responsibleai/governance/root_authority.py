# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Root of Authority (Heart Phase H3) — the first place this codebase
implements constitutional laws H1 ("every machine authority has a
legitimate root") and H2 ("machines cannot originate authority") as
executable code, not just documented intent.

**The core rule this module enforces**: `SERVICE_PRINCIPAL` and
`WORKLOAD_IDENTITY` roots cannot be independent origins of legitimate
organizational authority — their `authority_source` must point to
another root, and walking that chain (`validate_root_chain()`) must
eventually reach a `HUMAN` or `ORGANIZATION` root, the only two types
this module treats as terminal (self-originating). A service
principal whose source chain dead-ends at another service principal,
or points nowhere, or cycles back on itself, has no legitimate root —
`RootValidationStatus.SOURCE_NOT_HUMAN_OR_ORG`/`SOURCE_NOT_FOUND`/
`CYCLE_DETECTED`, never silently treated as valid.

**Deliberately minimal PII**: `subject_id` is an opaque identifier
(the same `identity_id`/`sub` claim `IdentityContext`/`JWTClaims`
already carry elsewhere in this codebase), not a name, email, or any
other personal attribute. This module verifies authority provenance;
it is not, and must not become, a surveillance identity database — see
the master Heart spec's own explicit instruction on this point.

**Not built here**: actual issuance of a `RootAuthorityRecord` from a
real OIDC/SAML/VC verification event (that wiring — turning an
already-verified `IdentityContext` into a persisted root record — is
later integration work, once a Heart veto (H11) exists to consult
these records for something). This phase ships the record type and
its validation semantics only, exactly like Phase H1's constitution
and Phase H2's lattice shipped their own objects without live wiring.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any, Protocol


class RootType(StrEnum):
    HUMAN = "HUMAN"
    ORGANIZATION = "ORGANIZATION"
    SERVICE_PRINCIPAL = "SERVICE_PRINCIPAL"
    WORKLOAD_IDENTITY = "WORKLOAD_IDENTITY"


# The only root types this module treats as terminal -- a legitimate
# root in its own right, needing no further `authority_source` chain.
_TERMINAL_ROOT_TYPES: frozenset[RootType] = frozenset({RootType.HUMAN, RootType.ORGANIZATION})

# Bounds how far validate_root_chain() will walk before giving up --
# a legitimate chain should never be long; this exists purely as a
# defensive circuit breaker against a misconfigured or adversarial
# chain that isn't a true cycle but is unreasonably deep.
_MAX_CHAIN_DEPTH = 32


def _canonical_json(payload: dict[str, Any]) -> str:
    """Same canonicalization discipline `governance/constitution.py`
    and `governance/approval.py` already use -- reused, not
    reinvented, for the third time in this codebase."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def compute_root_digest(
    root_id: str,
    root_type: RootType,
    subject_id: str,
    organization_id: str | None,
    issuer: str,
    verification_method: str,
    authority_source: str | None,
    issued_at: datetime,
) -> str:
    """SHA-256 over the canonical JSON of every field that defines
    what this root record actually asserts. Complete over these
    fields -- see `governance/constitution.py`'s own digest function
    for why this codebase calls that out explicitly rather than
    leaving readers to guess."""
    payload = {
        "root_id": root_id,
        "root_type": root_type.value,
        "subject_id": subject_id,
        "organization_id": organization_id,
        "issuer": issuer,
        "verification_method": verification_method,
        "authority_source": authority_source,
        "issued_at": issued_at.isoformat(),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class RootAuthorityRecord:
    """A claimed root of legitimate authority. `subject_id` is opaque
    -- no name/email/other personal attribute belongs here (see module
    docstring). `evidence_refs` holds opaque references to whatever
    real verification event produced this record (an OIDC `sub`, a
    SAML assertion ID, a VC `jti`) — WhitePact records that
    verification happened and by what method, not the verification
    material itself."""

    subject_id: str
    root_type: RootType
    issuer: str
    verification_method: str
    organization_id: str | None = None
    authority_source: str | None = None  # another root_id, required for non-terminal types
    jurisdiction: str | None = None
    evidence_refs: tuple[str, ...] = ()
    root_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    not_before: datetime | None = None
    expires_at: datetime | None = None
    revoked_at: datetime | None = None
    revoked_by: str | None = None
    revoke_reason: str | None = None
    canonical_digest: str = ""

    def is_terminal(self) -> bool:
        """`True` for `HUMAN`/`ORGANIZATION` -- a legitimate root in
        its own right, needing no further chain."""
        return self.root_type in _TERMINAL_ROOT_TYPES

    def is_temporally_valid(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        if self.revoked_at is not None:
            return False
        if self.not_before is not None and current < self.not_before:
            return False
        if self.expires_at is not None and current >= self.expires_at:
            return False
        return True

    def to_dict(self) -> dict[str, Any]:
        return {
            "root_id": self.root_id,
            "root_type": self.root_type.value,
            "subject_id": self.subject_id,
            "organization_id": self.organization_id,
            "issuer": self.issuer,
            "verification_method": self.verification_method,
            "authority_source": self.authority_source,
            "jurisdiction": self.jurisdiction,
            "evidence_refs": list(self.evidence_refs),
            "issued_at": self.issued_at.isoformat(),
            "not_before": self.not_before.isoformat() if self.not_before else None,
            "expires_at": self.expires_at.isoformat() if self.expires_at else None,
            "revoked_at": self.revoked_at.isoformat() if self.revoked_at else None,
            "revoked_by": self.revoked_by,
            "revoke_reason": self.revoke_reason,
            "canonical_digest": self.canonical_digest,
        }


def build_root_authority_record(
    subject_id: str,
    root_type: RootType,
    issuer: str,
    verification_method: str,
    *,
    organization_id: str | None = None,
    authority_source: str | None = None,
    jurisdiction: str | None = None,
    evidence_refs: tuple[str, ...] = (),
    not_before: datetime | None = None,
    expires_at: datetime | None = None,
) -> RootAuthorityRecord:
    """The only intended constructor -- computes `canonical_digest`
    from the other fields, mirroring `build_constitution_version()`'s
    own pattern (Phase H1) so two records are the same record if and
    only if their digests match."""
    root_id = str(uuid.uuid4())
    issued_at = datetime.now(UTC)
    digest = compute_root_digest(
        root_id,
        root_type,
        subject_id,
        organization_id,
        issuer,
        verification_method,
        authority_source,
        issued_at,
    )
    return RootAuthorityRecord(
        root_id=root_id,
        subject_id=subject_id,
        root_type=root_type,
        organization_id=organization_id,
        issuer=issuer,
        verification_method=verification_method,
        authority_source=authority_source,
        jurisdiction=jurisdiction,
        evidence_refs=evidence_refs,
        issued_at=issued_at,
        not_before=not_before,
        expires_at=expires_at,
        canonical_digest=digest,
    )


class RootValidationStatus(StrEnum):
    VALID = "VALID"
    ROOT_TYPE_CANNOT_SELF_ORIGINATE = "ROOT_TYPE_CANNOT_SELF_ORIGINATE"
    SOURCE_NOT_FOUND = "SOURCE_NOT_FOUND"
    SOURCE_NOT_HUMAN_OR_ORG = "SOURCE_NOT_HUMAN_OR_ORG"
    CYCLE_DETECTED = "CYCLE_DETECTED"
    CHAIN_TOO_DEEP = "CHAIN_TOO_DEEP"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"
    NOT_YET_VALID = "NOT_YET_VALID"


@dataclass(frozen=True)
class RootValidationResult:
    status: RootValidationStatus
    root_id: str
    chain: tuple[str, ...] = ()  # root_ids walked, root-record first
    detail: str | None = None

    @property
    def is_valid(self) -> bool:
        return self.status == RootValidationStatus.VALID


class RootResolver(Protocol):
    """The interface `validate_root_chain()` needs to walk a chain --
    deliberately abstract (no DB/network dependency baked into this
    module itself, per the Heart TCB-minimization principle) so this
    function stays testable with a plain in-memory dict and usable
    against a real repository without this module importing `db.*` at
    all."""

    def __call__(self, root_id: str) -> RootAuthorityRecord | None: ...


def validate_root_chain(record: RootAuthorityRecord, resolve: RootResolver) -> RootValidationResult:
    """Walks `authority_source` pointers until reaching a terminal
    (`HUMAN`/`ORGANIZATION`) root, or failing for one of the reasons
    `RootValidationStatus` names. This is the executable form of
    constitutional laws H1/H2: a `SERVICE_PRINCIPAL`/`WORKLOAD_IDENTITY`
    root with no legitimate human/organization ancestor is not a
    legitimate root, full stop -- never silently treated as one."""
    if not record.is_temporally_valid():
        if record.revoked_at is not None:
            return RootValidationResult(RootValidationStatus.REVOKED, record.root_id)
        if record.not_before is not None and datetime.now(UTC) < record.not_before:
            return RootValidationResult(RootValidationStatus.NOT_YET_VALID, record.root_id)
        return RootValidationResult(RootValidationStatus.EXPIRED, record.root_id)

    if record.is_terminal():
        return RootValidationResult(
            RootValidationStatus.VALID, record.root_id, chain=(record.root_id,)
        )

    chain: list[str] = [record.root_id]
    seen: set[str] = {record.root_id}
    current = record
    while not current.is_terminal():
        if len(chain) > _MAX_CHAIN_DEPTH:
            return RootValidationResult(
                RootValidationStatus.CHAIN_TOO_DEEP, record.root_id, chain=tuple(chain)
            )
        source_id = current.authority_source
        if source_id is None:
            return RootValidationResult(
                RootValidationStatus.ROOT_TYPE_CANNOT_SELF_ORIGINATE,
                record.root_id,
                chain=tuple(chain),
                detail=(
                    f"{current.root_type.value} root {current.root_id!r} has no "
                    "authority_source and is not a terminal root type"
                ),
            )
        if source_id in seen:
            return RootValidationResult(
                RootValidationStatus.CYCLE_DETECTED, record.root_id, chain=tuple(chain)
            )
        source = resolve(source_id)
        if source is None:
            return RootValidationResult(
                RootValidationStatus.SOURCE_NOT_FOUND,
                record.root_id,
                chain=tuple(chain),
                detail=f"authority_source {source_id!r} does not resolve to any known root",
            )
        if not source.is_temporally_valid():
            # The source's own temporal state, not its type, is the
            # problem here -- a revoked/expired/not-yet-valid ancestor
            # invalidates the whole chain regardless of what type it is.
            if source.revoked_at is not None:
                source_status = RootValidationStatus.REVOKED
            elif source.not_before is not None and datetime.now(UTC) < source.not_before:
                source_status = RootValidationStatus.NOT_YET_VALID
            else:
                source_status = RootValidationStatus.EXPIRED
            return RootValidationResult(
                source_status,
                record.root_id,
                chain=tuple(chain),
                detail=f"authority_source {source_id!r} is {source_status.value.lower()}",
            )
        chain.append(source_id)
        seen.add(source_id)
        current = source

    return RootValidationResult(RootValidationStatus.VALID, record.root_id, chain=tuple(chain))
