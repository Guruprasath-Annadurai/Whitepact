"""Verified Principal (Authority Everywhere Phase 3) — the governance-
layer, audit-safe representation of a cryptographically verified
non-human principal, decoupled from how it was verified.

**Why this is a separate module from `auth/verifiable_credential.py`**:
mirrors the existing split in this codebase between verification (an
`auth/*` concern — signatures, JWKS, expiry) and the governance-domain
record of what was decided (a `governance/*` concern). `PrincipalClaim`
is deliberately not the same object as `VerifiableCredentialClaims` —
it is the field-names-only summary of one, discarding the raw JWT
payload for the same reason `EvidenceRecord.argument_keys` discards raw
argument values and `OutcomeRecord.result_summary` discards raw tool
output: this record may be persisted and queried long after the
credential itself expires, and should never become a second place a
credential's full claim set (which could carry arbitrary
issuer-supplied data) leaks into.

**Not built here**: revocation-list checking (a presented VC could
already be revoked by its issuer; this module has no revocation-status
protocol implemented — same "greenfield" gap noted in
`auth/verifiable_credential.py`'s docstring for DID/JSON-LD), and
credential-to-`AuthorityContext` binding (whether a verified principal
should get a *different* authority ceiling than an API-key identity is
a real, separate policy question `governance/ceiling.py` doesn't
answer yet).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class PrincipalClaim:
    """The persisted, audit-safe record of one verified-principal
    authentication event. `claim_keys` records which fields the
    presented credential's `vc.credentialSubject` carried — field
    names only, never values, matching `EvidenceRecord.argument_keys`'s
    discipline."""

    principal_id: str
    org_id: str | None
    issuer: str
    credential_type: str
    holder_kind: str  # "service_account" | "external_agent"
    claim_keys: tuple[str, ...] = ()
    verification_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    verified_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def to_dict(self) -> dict[str, Any]:
        return {
            "verification_id": self.verification_id,
            "principal_id": self.principal_id,
            "org_id": self.org_id,
            "issuer": self.issuer,
            "credential_type": self.credential_type,
            "holder_kind": self.holder_kind,
            "claim_keys": list(self.claim_keys),
            "verified_at": self.verified_at.isoformat(),
        }


def build_principal_claim(vc_claims: Any) -> PrincipalClaim:
    """Pure assembly from an `auth.verifiable_credential.VerifiableCredentialClaims`
    (typed `Any` here to keep this module free of an `auth/*` import,
    consistent with the category boundary elsewhere in `governance/*` —
    callers pass the already-verified claims object, this function never
    performs verification itself). No I/O; persist via
    `db.PrincipalRepository.record()`."""
    subject = vc_claims.raw.get("vc", {}).get("credentialSubject", {})
    return PrincipalClaim(
        principal_id=vc_claims.sub,
        org_id=vc_claims.org_id,
        issuer=vc_claims.issuer,
        credential_type=vc_claims.credential_type,
        holder_kind=vc_claims.holder_kind,
        claim_keys=tuple(sorted(subject.keys())) if isinstance(subject, dict) else (),
    )
