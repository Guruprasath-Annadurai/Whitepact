"""Identity Bridge — provider-specific claims adapters for Entra ID, Google
Workspace, Okta, and AWS (Cognito / IAM Identity Center), turning each
provider's own token shape into WhitePact's `IdentityContext`.

**Why this exists, beyond the generic OIDC layer already in `auth/oidc.py`**:
`JWTClaims.from_payload()` does one generic `roles`/`groups`,
`org_id`/`tenant_id` extraction that happens to work for a vanilla OIDC
token, but every real IdP diverges from that in provider-specific ways —
Entra ID's tenant claim is `tid`, not `tenant_id`; Google's org signal is
the `hd` (hosted domain) claim, which has no OIDC-standard equivalent;
Okta has no standard tenant claim at all (it's app-specific); AWS Cognito
prefixes its custom claims (`cognito:groups`, `cognito:username`). This
module is that provider-specific knowledge, isolated so `auth/oidc.py`
stays a genuinely provider-agnostic OIDC validator.

**Honestly scoped — read before wiring this into a live deployment**:

- These are *pure claims-mapping functions*. They take an already-decoded
  claims payload (e.g. `JWTClaims.raw`, after `OIDCProvider.validate_token()`
  has already verified the token's signature) and return an `IdentityContext`
  — they do not themselves validate a token, call a network endpoint, or
  authenticate anything.
- Each mapping is verified against that provider's own *publicly documented*
  ID token claim shape (Microsoft identity platform, Google's OpenID Connect
  docs, Okta's ID token reference, AWS Cognito's ID token reference) — see
  `tests/test_identity_bridge.py` for the exact sample payloads used. None
  of this has been tested against a real, live tenant of any of these four
  providers — that would require this project having a real Entra/Google
  Workspace/Okta/AWS account to test against, which it does not.
- **Entra ID's `groups` claim, when present, is a list of group *object
  GUIDs*, not names** — resolving those to human-readable group names or
  their full transitive membership requires a live Microsoft Graph API
  call (`GET /me/memberOf` or similar), which this module does not make.
  `map_groups_to_authority()` below works directly against whatever
  identifiers are in the claim (GUIDs or names), so this is usable as-is
  if the caller's own authority-mapping config is keyed by the same GUIDs
  Entra actually emits — just not a name-resolution convenience.
- **Google Workspace group membership is not in the ID token at all** by
  default — `google_claims_to_identity()` always returns an empty
  `groups` tuple unless the caller's own OIDC app config injects a custom
  `groups` claim; real group membership requires the Admin SDK Directory
  API, not implemented here.
- **AWS is covered for OIDC-issued tokens only** (Amazon Cognito ID
  tokens, and IAM Identity Center's OIDC-compliant tokens) — both are
  bearer JWTs that fit this bridge's model. The other real AWS workload-
  identity mechanism, SigV4-signed `AssumeRoleWithWebIdentity`/STS calls,
  is **not** a bearer JWT and is architecturally a different integration
  (it needs `boto3` and a live AWS account to build and test against
  honestly) — not built here, not claimed here.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from responsibleai.governance.models import AuthorityContext, IdentityContext, IdentityKind


@dataclass(frozen=True)
class BridgeIdentity:
    """The provider-agnostic result of mapping one IdP's claims — an
    `IdentityContext` plus the raw group/role identifiers a caller needs
    to make its own authority-mapping decision (`map_groups_to_authority`
    below is one option, not the only one)."""

    provider: str
    identity_id: str
    org_id: str | None
    display_name: str | None
    email: str | None
    groups: tuple[str, ...] = field(default_factory=tuple)
    raw: dict[str, Any] = field(default_factory=dict)

    def to_identity_context(self, *, kind: IdentityKind = IdentityKind.OIDC) -> IdentityContext:
        return IdentityContext(
            identity_id=self.identity_id,
            kind=kind,
            org_id=self.org_id,
            display_name=self.display_name,
        )


def entra_claims_to_identity(claims: dict[str, Any]) -> BridgeIdentity:
    """Microsoft Entra ID (Azure AD) v2.0 ID token claims. `oid` (the
    object ID) is the stable per-tenant identity, not `sub` — `sub` is
    only stable per-application, per Microsoft's own documentation, and
    would silently produce a different `identity_id` for the same human
    across two different Entra app registrations. `tid` is the tenant
    GUID, this project's natural `org_id`. `groups`, when present, are
    object GUIDs (see module docstring); falls back to `roles` (Entra
    App Roles, which *are* human-chosen names) when `groups` is absent.
    """
    groups_raw = claims.get("groups") or claims.get("roles") or []
    return BridgeIdentity(
        provider="entra",
        identity_id=claims.get("oid") or claims.get("sub", ""),
        org_id=claims.get("tid"),
        display_name=claims.get("name"),
        email=claims.get("preferred_username") or claims.get("upn"),
        groups=tuple(groups_raw),
        raw=claims,
    )


def google_claims_to_identity(claims: dict[str, Any]) -> BridgeIdentity:
    """Google OpenID Connect ID token claims. `sub` is Google's stable
    per-account identifier. `hd` (hosted domain) identifies the Google
    Workspace organization a personal @gmail.com account never has —
    its absence is itself a meaningful signal (a personal account, not
    a managed Workspace identity), not an error. `groups` is always
    empty here (see module docstring)."""
    return BridgeIdentity(
        provider="google",
        identity_id=claims.get("sub", ""),
        org_id=claims.get("hd"),
        display_name=claims.get("name"),
        email=claims.get("email"),
        groups=(),
        raw=claims,
    )


def okta_claims_to_identity(claims: dict[str, Any], *, org_claim: str = "org_id") -> BridgeIdentity:
    """Okta ID token claims. Okta's standard claim set (`sub`, `name`,
    `email`, `preferred_username`, `groups` when the Authorization
    Server's `groups` claim is configured) otherwise matches generic
    OIDC closely — the one real gap is that Okta has **no standard
    tenant/org claim at all** (unlike Entra's `tid`); which claim
    carries an org identifier is entirely dependent on how the caller's
    own Okta Authorization Server custom claims are configured, hence
    the configurable `org_claim` parameter rather than a hardcoded
    guess."""
    return BridgeIdentity(
        provider="okta",
        identity_id=claims.get("sub", ""),
        org_id=claims.get(org_claim),
        display_name=claims.get("name"),
        email=claims.get("email") or claims.get("preferred_username"),
        groups=tuple(claims.get("groups") or []),
        raw=claims,
    )


def aws_claims_to_identity(claims: dict[str, Any]) -> BridgeIdentity:
    """AWS-issued OIDC ID token claims — Amazon Cognito user pools and
    IAM Identity Center's OIDC-compliant tokens **only**; see the module
    docstring for the SigV4/STS mechanism this does not cover. Detected
    by Cognito's own distinguishing claim (`token_use` — Cognito is the
    only one of the four providers here that stamps this); Cognito's
    `cognito:username`/`cognito:groups` claims are used when present,
    since `sub` alone is a random UUID with no human-readable form.
    IAM Identity Center tokens carry no such prefix and fall through to
    plain `sub`/`groups`, matching the same shape as a generic OIDC
    token — this function's only real value-add for that case is
    documenting that AWS's own token *is* OIDC-shaped here, not the
    SigV4 alternative."""
    is_cognito = "token_use" in claims
    groups_raw = claims.get("cognito:groups") if is_cognito else claims.get("groups")
    return BridgeIdentity(
        provider="aws",
        identity_id=(claims.get("cognito:username") if is_cognito else None)
        or claims.get("sub", ""),
        org_id=claims.get("custom:org_id"),
        display_name=claims.get("name"),
        email=claims.get("email"),
        groups=tuple(groups_raw or []),
        raw=claims,
    )


def map_groups_to_authority(
    groups: tuple[str, ...],
    mapping: dict[str, frozenset[str]],
    *,
    delegated_by: str,
) -> AuthorityContext | None:
    """Turns an IdP's group/role identifiers into a granted-action-types
    `AuthorityContext`, via a caller-supplied `mapping` (group identifier
    -> the action types that membership grants) — this project has no
    opinion on what any given group *should* grant; that mapping is a
    deployment's own policy decision, not something derivable from the
    IdP alone. Returns `None` when none of `groups` appear in `mapping`
    (no authority to grant), the same "no config means no authority"
    default `OrgAuthorityCeilingRepository.get()` uses elsewhere in this
    codebase — never a silent full-access fallback.
    """
    granted: set[str] = set()
    for g in groups:
        granted |= mapping.get(g, frozenset())
    if not granted:
        return None
    return AuthorityContext(delegated_by=delegated_by, granted_action_types=frozenset(granted))
