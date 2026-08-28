# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
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

from responsibleai.governance.root_authority import RootType, build_root_authority_record

if TYPE_CHECKING:
    from datetime import datetime

    from responsibleai.governance.models import IdentityContext
    from responsibleai.governance.principal import PrincipalClaim
    from responsibleai.governance.root_authority import RootAuthorityRecord

# IdentityContext.kind -> RootType. Kept as an explicit, reviewable
# mapping table rather than inline conditionals -- see module
# docstring for the fail-safe reasoning behind each entry, especially
# "oidc"'s deliberately non-terminal classification.
_KIND_TO_ROOT_TYPE: dict[str, RootType] = {
    "human": RootType.HUMAN,
    "api_key": RootType.ORGANIZATION,
    "oidc": RootType.WORKLOAD_IDENTITY,
    "vc": RootType.SERVICE_PRINCIPAL,
    "agent": RootType.SERVICE_PRINCIPAL,
    "workload": RootType.WORKLOAD_IDENTITY,
}

# The fail-safe default for any IdentityContext.kind this table
# doesn't recognize -- non-terminal, never silently treated as a
# legitimate root in its own right.
_DEFAULT_ROOT_TYPE = RootType.WORKLOAD_IDENTITY


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
    values are non-human and therefore non-terminal, consistently."""
    return build_root_authority_record(
        claim.principal_id,
        RootType.SERVICE_PRINCIPAL,
        claim.issuer,
        claim.credential_type,
        organization_id=claim.org_id,
        authority_source=authority_source,
        jurisdiction=jurisdiction,
        evidence_refs=(claim.verification_id,),
    )
