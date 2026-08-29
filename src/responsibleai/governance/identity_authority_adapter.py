"""Identity → Heart Root-Authority Adapter (Heart → WhitePact
Production Integration, Phase 2).

**Authentication is not authority** — this module's entire purpose is
to keep that boundary explicit rather than blurred. `docs/heart-production/00_CURRENT_RUNTIME_MAP.md`
§2 confirms three real, already-live authentication mechanisms exist
today (static API key, OIDC JWT, VC-JWT bearer, each already producing
a real `IdentityContext`/`PrincipalClaim`). This module does **not**
invent a fourth authentication system, and it does **not** grant any
authority. It answers exactly one question: *given an already-verified
identity, what does that identity look like in the Heart's own
`RootAuthorityRecord` vocabulary* — the necessary first input to
`root_authority.validate_root_chain()` (Phase H3), not a replacement
for it.

**Producing a `RootAuthorityRecord` here proves nothing about
legitimate authority by itself.** A `RootAuthorityRecord` for a
non-terminal `RootType` (`SERVICE_PRINCIPAL`/`WORKLOAD_IDENTITY`) still
needs a resolvable `authority_source` chain reaching a terminal root
before `validate_root_chain()` reports `VALID` — this module never
supplies that chain (that is Phase 5's Authority Resolver, working
against real persisted state, Phase 3). Constructing a record here is
exactly as inert as `governance/root_authority.py`'s own
`build_root_authority_record()` already is on its own — this module
only adds the *mapping*, not new trust.

**The root-type mapping is deliberately conservative (fail-safe, not
fail-open)**: only `IdentityContext.kind` values this codebase already
treats as directly, unambiguously human- or organization-controlled
(`"human"`, `"api_key"` — a static key an org's own admin provisioned,
`docs/heart-production/00_CURRENT_RUNTIME_MAP.md` §12) map to a
terminal `RootType` (`HUMAN`/`ORGANIZATION`, self-originating, no
further chain required). Every other kind — `"oidc"` (ambiguous:
today's `IdentityContext.from_org_context()` sets `kind="oidc"`
whether the token authenticated a human via SSO or a machine via
client-credentials, with no discriminator in the live code to tell
them apart), `"vc"`/`"agent"`/`"workload"` (verified-principal and
agent identities, never human by construction) — maps to a
**non-terminal** type (`WORKLOAD_IDENTITY`/`SERVICE_PRINCIPAL`),
which `validate_root_chain()` will only ever accept once it resolves
to a real, legitimate source. Getting this mapping wrong in the unsafe
direction (treating something non-human as `HUMAN`/terminal) would let
authority originate where constitutional law H2 ("machines cannot
originate authority") forbids it; getting it wrong in the safe
direction (treating something actually human as non-terminal) merely
produces a deny (`ROOT_TYPE_CANNOT_SELF_ORIGINATE`) until Phase 5
supplies a real source — an availability cost, never a security one.
This asymmetry is why the conservative direction was chosen for the
one genuinely ambiguous case (`"oidc"`).
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from responsibleai.governance.models import IdentityKind
from responsibleai.governance.root_authority import RootType, build_root_authority_record

if TYPE_CHECKING:
    from datetime import datetime

    from responsibleai.governance.models import IdentityContext
    from responsibleai.governance.principal import PrincipalClaim
    from responsibleai.governance.root_authority import RootAuthorityRecord

# IdentityContext.kind -> RootType. Kept as an explicit, reviewable
# mapping table rather than inline conditionals -- see module
# docstring for the fail-safe reasoning behind each entry, especially
# "oidc"'s deliberately non-terminal classification. DEVICE/BCI_SESSION/
# TOOL/SERVICE (Zero-Trust Identity Phase 1,
# docs/heart-production/03_ZERO_TRUST_IDENTITY.md) are new entries: none
# of the four is human- or organization-controlled by construction, so
# each maps non-terminal for the same reason "agent"/"workload" already
# do -- a device, a BCI session, a tool, or a service account is never
# itself a legitimate root, only ever a link needing a resolvable chain
# to one.
_KIND_TO_ROOT_TYPE: dict[IdentityKind, RootType] = {
    IdentityKind.HUMAN: RootType.HUMAN,
    IdentityKind.ORGANIZATION: RootType.ORGANIZATION,
    IdentityKind.OIDC: RootType.WORKLOAD_IDENTITY,
    IdentityKind.VERIFIED_CREDENTIAL: RootType.SERVICE_PRINCIPAL,
    IdentityKind.AGENT: RootType.SERVICE_PRINCIPAL,
    IdentityKind.WORKLOAD: RootType.WORKLOAD_IDENTITY,
    IdentityKind.DEVICE: RootType.WORKLOAD_IDENTITY,
    IdentityKind.BCI_SESSION: RootType.WORKLOAD_IDENTITY,
    IdentityKind.TOOL: RootType.SERVICE_PRINCIPAL,
    IdentityKind.SERVICE: RootType.SERVICE_PRINCIPAL,
}

# The fail-safe default for any IdentityContext.kind this table
# doesn't recognize -- non-terminal, never silently treated as a
# legitimate root in its own right.
_DEFAULT_ROOT_TYPE = RootType.WORKLOAD_IDENTITY

# PrincipalClaim.holder_kind (Authority Everywhere Phase 3,
# governance/principal.py) is a second, independently-sourced kind
# string -- part of the Verifiable Credential wire format
# (auth/verifiable_credential.py's `holderKind` claim), so its two
# values are kept unchanged rather than renamed to match IdentityKind's
# names (that would be a breaking wire-format change, not an internal
# type-safety improvement). This mapping is the reconciliation point
# Zero-Trust Identity Phase 1 adds: both wire values already meant one
# of IdentityKind's own members, just spelled differently.
_HOLDER_KIND_TO_IDENTITY_KIND: dict[str, IdentityKind] = {
    "service_account": IdentityKind.SERVICE,
    "external_agent": IdentityKind.AGENT,
}


def identity_kind_from_holder_kind(holder_kind: str) -> IdentityKind:
    """Reconciles `PrincipalClaim.holder_kind`'s wire-format values with
    `IdentityKind`. An unrecognized `holder_kind` (a future VC wire
    value this mapping doesn't have yet) fails safe to `AGENT` -- both
    of today's known `IdentityKind` targets for this claim
    (`SERVICE`/`AGENT`) already map to the same non-terminal
    `RootType.SERVICE_PRINCIPAL`, so this default changes no root-type
    outcome; it exists so an unrecognized value is still a real
    `IdentityKind` rather than silently falling through untyped."""
    return _HOLDER_KIND_TO_IDENTITY_KIND.get(holder_kind, IdentityKind.AGENT)


def identity_context_to_root_type(identity: IdentityContext) -> RootType:
    """Maps `identity.kind` to a Heart `RootType`, conservatively.
    An unrecognized `kind` (a future value `IdentityContext` doesn't
    have yet) maps to the same fail-safe non-terminal default as
    `"oidc"` -- never silently assumed terminal."""
    return _KIND_TO_ROOT_TYPE.get(identity.kind, _DEFAULT_ROOT_TYPE)


def build_root_authority_record_from_identity(
    identity: IdentityContext,
    *,
    issuer: str,
    verification_method: str,
    authority_source: str | None = None,
    jurisdiction: str | None = None,
    evidence_refs: tuple[str, ...] = (),
    not_before: datetime | None = None,
    expires_at: datetime | None = None,
) -> RootAuthorityRecord:
    """Builds a `RootAuthorityRecord` describing `identity` in Heart
    vocabulary. `subject_id` is `identity.identity_id` (already opaque
    per `IdentityContext`'s own convention); `organization_id` is
    `identity.org_id` unchanged. Does not resolve or validate a chain
    -- callers still need `root_authority.validate_root_chain()`
    (Phase H3) with a real `RootResolver` (Phase 5) before treating
    this record as proof of anything."""
    root_type = identity_context_to_root_type(identity)
    return build_root_authority_record(
        identity.identity_id,
        root_type,
        issuer,
        verification_method,
        organization_id=identity.org_id,
        authority_source=authority_source,
        jurisdiction=jurisdiction,
        evidence_refs=evidence_refs,
        not_before=not_before,
        expires_at=expires_at,
    )


def build_root_authority_record_from_principal_claim(
    claim: PrincipalClaim,
    *,
    authority_source: str | None = None,
    jurisdiction: str | None = None,
) -> RootAuthorityRecord:
    """The Verified Principal (VC) path's own analogue --
    `PrincipalClaim` (`governance/principal.py`, Authority Everywhere
    Phase 3) already carries `issuer`/`credential_type` directly from
    a real verification event, more precise than routing through the
    generic `IdentityContext` mapping above. Always `SERVICE_PRINCIPAL`
    -- a verified principal (`holder_kind` `"service_account"` or
    `"external_agent"`) is never human by construction, so this is not
    a judgment call the way `"oidc"` above is; both `holder_kind`
    values are non-human and therefore non-terminal, consistently.
    Routes through `identity_kind_from_holder_kind()` +
    `_KIND_TO_ROOT_TYPE` (rather than hardcoding `SERVICE_PRINCIPAL`
    directly) so this stays the single source of truth for the
    kind -> root-type mapping; both `SERVICE` and `AGENT` resolve to
    `SERVICE_PRINCIPAL` today, so this is a documentation/consistency
    change, not a behavior change."""
    identity_kind = identity_kind_from_holder_kind(claim.holder_kind)
    root_type = _KIND_TO_ROOT_TYPE.get(identity_kind, _DEFAULT_ROOT_TYPE)
    return build_root_authority_record(
        claim.principal_id,
        root_type,
        claim.issuer,
        claim.credential_type,
        organization_id=claim.org_id,
        authority_source=authority_source,
        jurisdiction=jurisdiction,
        evidence_refs=(claim.verification_id,),
    )
