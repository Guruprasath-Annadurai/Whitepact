"""Authority Grant — the production Authority Contract (Heart →
WhitePact Production Integration, Phase 1). See
`docs/heart-production/01_AUTHORITY_CONTRACT.md` for the full design
rationale and field classification table.

**The boundary object between the Heart and WhitePact's live decision
path.** Every field is explicitly classified there as an authenticated
fact, a user-provided claim, or an authorization fact — WhitePact must
never treat an unverified claim as verified authority, so
`effective_authority`/`legitimacy` are never derived from
`requested_action_type`/`requested_target`/`requested_purpose`; they
come only from the Heart's own `AuthorityEnvelope` (H2) and
`LegitimacyEnvelope` (H12) composition.

**Why a new type, not a rewrite of either Heart type**: `AuthorityEnvelope`
(`authority_lattice.py`) says *what* is granted; `LegitimacyEnvelope`
(`legitimacy_envelope.py`) says *why* it's legitimate. Neither alone is
what a live request needs — `AuthorityGrant` bundles both plus the
minimal request-context `gateway.evaluate()` already requires, so a
real request can assemble a real `AuthorityContext` honestly instead
of the synthesize-from-authentication pattern
`docs/heart-production/00_CURRENT_RUNTIME_MAP.md` §12 documents as the
current gap.

**Not signed, same inherited, honestly-named limitation every Heart
record has** (`docs/heart/HEART_SIGNING_DECISION.md`) — `canonical_digest`
is a tamper-*evidence* aid (detectable on comparison), not
cryptographic tamper-*proof* authentication.

**TCB-minimization, continued**: `AuthorityEnvelope`/`LegitimacyEnvelope`
are imported only under `TYPE_CHECKING`; `build_authority_grant()`
takes already-computed instances as parameters. This module never
calls Heart evaluation functions itself — the same "abstract input,
not a live call into another module" discipline every Heart phase has
used since H4, extended here to the production boundary.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, field, fields, is_dataclass
from datetime import UTC, datetime, timedelta
from types import MappingProxyType
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from responsibleai.governance.authority_lattice import AuthorityEnvelope
    from responsibleai.governance.legitimacy_envelope import LegitimacyEnvelope
    from responsibleai.governance.models import AuthorityContext

# Mirrors ExecutionAuthorization's own existing TTL pattern
# (governance/execution.py) -- an AuthorityGrant is not a long-lived
# credential, it's a short-lived, single-decision authorization
# artifact.
DEFAULT_GRANT_TTL_SECONDS = 30.0


def _canonical_json(payload: dict[str, Any]) -> str:
    """Same canonicalization discipline every Heart module uses."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)


def _canonical_value(value: Any) -> Any:
    """Convert Heart values to a stable, JSON-compatible shape."""
    if is_dataclass(value) and not isinstance(value, type):
        return {item.name: _canonical_value(getattr(value, item.name)) for item in fields(value)}
    if isinstance(value, Mapping):
        return {str(key): _canonical_value(item) for key, item in value.items()}
    if isinstance(value, (set, frozenset)):
        return sorted(_canonical_value(item) for item in value)
    if isinstance(value, tuple):
        return [_canonical_value(item) for item in value]
    if isinstance(value, datetime):
        return value.isoformat()
    return value


def compute_authority_grant_digest(
    grant_id: str,
    organization_id: str,
    principal_id: str,
    acting_agent_id: str,
    requested_action_type: str,
    requested_target: str,
    requested_purpose: str | None,
    legitimacy_digest: str,
    root_reference: str | None,
    consent_reference: str | None,
    delegation_reference: str | None,
    issued_at: datetime,
    expires_at: datetime,
    effective_authority: AuthorityEnvelope,
    policy_constraints: Mapping[str, Any],
) -> str:
    """SHA-256 over the canonical JSON of every field that defines
    what this grant actually asserts, including the effective authority
    and policy constraints used by the execution boundary."""
    payload = {
        "grant_id": grant_id,
        "organization_id": organization_id,
        "principal_id": principal_id,
        "acting_agent_id": acting_agent_id,
        "requested_action_type": requested_action_type,
        "requested_target": requested_target,
        "requested_purpose": requested_purpose,
        "legitimacy_digest": legitimacy_digest,
        "root_reference": root_reference,
        "consent_reference": consent_reference,
        "delegation_reference": delegation_reference,
        "issued_at": issued_at.isoformat(),
        "expires_at": expires_at.isoformat(),
        "effective_authority": _canonical_value(effective_authority),
        "policy_constraints": _canonical_value(policy_constraints),
    }
    return hashlib.sha256(_canonical_json(payload).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class AuthorityGrant:
    """The production Authority Contract. `effective_authority` and
    `legitimacy` are the only two fields carrying verified authorization
    facts; everything prefixed `requested_` is an unverified,
    user-provided claim, kept for audit/comparison but never itself
    treated as authorization."""

    organization_id: str
    principal_id: str
    acting_agent_id: str
    requested_action_type: str
    requested_target: str
    effective_authority: AuthorityEnvelope
    legitimacy: LegitimacyEnvelope
    requested_purpose: str | None = None
    root_reference: str | None = None
    consent_reference: str | None = None
    delegation_reference: str | None = None
    policy_constraints: Mapping[str, Any] = field(default_factory=lambda: MappingProxyType({}))
    grant_id: str = field(default_factory=lambda: str(uuid.uuid4()))
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    canonical_digest: str = ""

    @property
    def is_legitimate(self) -> bool:
        """A pure read of the wrapped Heart verdict -- this type never
        overrides or second-guesses `legitimacy.is_legitimate`."""
        return self.legitimacy.is_legitimate

    @property
    def is_expired(self) -> bool:
        return datetime.now(UTC) >= self.expires_at

    @property
    def is_usable(self) -> bool:
        """Both conditions a caller must check before treating this
        grant as authorizing anything -- legitimate per the Heart's own
        verdict, AND not expired. Deliberately a single, unambiguous
        gate rather than two separate checks a caller could forget to
        AND together."""
        return self.is_legitimate and not self.is_expired

    def to_authority_context(self) -> AuthorityContext:
        """Converts `effective_authority` (the Heart's `AuthorityEnvelope`)
        into a live-path-compatible `AuthorityContext` via the
        already-existing, already-tested `envelope_to_authority_context()`
        (Phase H2) -- reused, not reimplemented. `gateway.evaluate()`
        itself is not modified; this is the one conversion point where
        Heart-derived authority becomes the type the existing gateway
        already knows how to evaluate."""
        from responsibleai.governance.authority_lattice import envelope_to_authority_context

        return envelope_to_authority_context(
            self.effective_authority, delegated_by=self.principal_id
        )

    def explain(self) -> dict[str, Any]:
        """A deterministic, structured explanation -- no LLM call, the
        same convention every other `explain_*()`/`.explain()` in this
        codebase already follows."""
        return {
            "grant_id": self.grant_id,
            "organization_id": self.organization_id,
            "principal_id": self.principal_id,
            "acting_agent_id": self.acting_agent_id,
            "requested_action_type": self.requested_action_type,
            "requested_target": self.requested_target,
            "requested_purpose": self.requested_purpose,
            "is_legitimate": self.is_legitimate,
            "is_expired": self.is_expired,
            "is_usable": self.is_usable,
            "legitimacy": self.legitimacy.explain(),
            "root_reference": self.root_reference,
            "consent_reference": self.consent_reference,
            "delegation_reference": self.delegation_reference,
            "policy_constraints": dict(self.policy_constraints),
            "issued_at": self.issued_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "canonical_digest": self.canonical_digest,
        }


def build_authority_grant(
    organization_id: str,
    principal_id: str,
    acting_agent_id: str,
    requested_action_type: str,
    requested_target: str,
    effective_authority: AuthorityEnvelope,
    legitimacy: LegitimacyEnvelope,
    *,
    requested_purpose: str | None = None,
    root_reference: str | None = None,
    consent_reference: str | None = None,
    delegation_reference: str | None = None,
    policy_constraints: dict[str, Any] | None = None,
    ttl_seconds: float = DEFAULT_GRANT_TTL_SECONDS,
) -> AuthorityGrant:
    """The only intended constructor -- computes `canonical_digest`
    from the other fields, mirroring every Heart record's own
    `build_*()` pattern. Takes an already-computed `AuthorityEnvelope`
    and `LegitimacyEnvelope` as parameters; never resolves either
    itself, continuing the Heart's TCB-minimization discipline at the
    production boundary."""
    grant_id = str(uuid.uuid4())
    issued_at = datetime.now(UTC)
    expires_at = issued_at + timedelta(seconds=ttl_seconds)
    immutable_constraints: Mapping[str, Any] = MappingProxyType(dict(policy_constraints or {}))
    digest = compute_authority_grant_digest(
        grant_id,
        organization_id,
        principal_id,
        acting_agent_id,
        requested_action_type,
        requested_target,
        requested_purpose,
        legitimacy.canonical_digest,
        root_reference,
        consent_reference,
        delegation_reference,
        issued_at,
        expires_at,
        effective_authority,
        immutable_constraints,
    )
    return AuthorityGrant(
        organization_id=organization_id,
        principal_id=principal_id,
        acting_agent_id=acting_agent_id,
        requested_action_type=requested_action_type,
        requested_target=requested_target,
        effective_authority=effective_authority,
        legitimacy=legitimacy,
        requested_purpose=requested_purpose,
        root_reference=root_reference,
        consent_reference=consent_reference,
        delegation_reference=delegation_reference,
        policy_constraints=immutable_constraints,
        grant_id=grant_id,
        issued_at=issued_at,
        expires_at=expires_at,
        canonical_digest=digest,
    )
