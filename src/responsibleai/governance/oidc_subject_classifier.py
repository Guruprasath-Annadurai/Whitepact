"""OIDC subject classifier — Zero-Trust Identity follow-up (see
`docs/heart-production/03_ZERO_TRUST_IDENTITY.md`'s "what this phase
does not resolve" section, which named this exact gap).

**The gap**: `IdentityContext.kind = IdentityKind.OIDC` is set for
every OIDC-authenticated request, whether the token came from a human
interactively logging in via SSO or a machine using an OAuth2
client-credentials grant (RFC 6749 §4.4) — both produce a Bearer JWT
`auth/oidc.py`'s `OIDCProvider.validate_token()` accepts identically.
`identity_authority_adapter.py`'s existing kind→`RootType` mapping
handles this by treating `OIDC` as always non-terminal
(`WORKLOAD_IDENTITY`) — safe (an availability cost, never a security
one, per that module's own docstring), but not a *resolution* of the
ambiguity, only a conservative default around it.

**Why this is deployer-configured, not a WhitePact-wide heuristic**:
no claim reliably distinguishes "a human authenticated" from "a client
authenticated" across every OIDC provider. The closest thing to a
standard is `amr` (RFC 8176, Authentication Methods References) — an
IdP populates it with how the *end user* authenticated ("pwd", "mfa",
"otp", ...) only when there *was* an end-user authentication event; a
client-credentials grant has no end user, so well-behaved IdPs omit
`amr` entirely for those tokens. But `amr` is optional even for human
logins, and some IdPs use non-standard claims instead (Auth0/Okta's
`gty`, for instance). Guessing wrong in the unsafe direction (treating
a machine token as human) would let authority originate where
constitutional law H2 forbids it — exactly the asymmetry
`identity_authority_adapter.py`'s own docstring already reasons about
for `"oidc"`'s current default. Rather than picking one heuristic and
hoping it's right for every deployment, this module makes the signal a
config knob (`Settings.oidc_human_indicator_claim`/
`oidc_human_indicator_values`) a deployer sets to match *their own*
IdP's actual claim shape — the same "configurable, not guessed"
discipline `integrations/identity_bridge.py`'s `org_claim` parameter
already established for Okta's missing standard tenant claim.

**Not wired into any live request path yet.** `auth/oidc.py`'s
`_resolve_oidc_context()` (both `mcp/server.py`'s and
`dashboard/app.py`'s copies) returns an `rbac.models.OrgContext`, which
has no field for this distinction and is used far beyond OIDC alone
(every auth mechanism shares it) — threading a per-request
human/machine hint through it, and through the three call sites that
build an `IdentityContext` from an `OrgContext`
(`mcp/governance_integration.py`, `mcp/upstream_dispatch.py`,
`mcp/server.py`), touches live authentication code every single
request goes through. That is a distinct, higher-risk change deserving
its own dedicated verification pass, matching exactly how Heart
Production Integration Phase 5 (`authority_resolver.py`) was built and
tested standalone before Phase 6 wires it into a live decision path.
This module ships the real, tested, ready-to-wire classification logic
now; wiring it into `_resolve_oidc_context()` is separate future work.
"""

from __future__ import annotations

from typing import Any

from responsibleai.governance.models import IdentityKind


def classify_oidc_subject(
    claims_raw: dict[str, Any],
    *,
    human_indicator_claim: str | None,
    human_indicator_values: list[str] | None = None,
) -> IdentityKind:
    """Returns `IdentityKind.HUMAN` only when `human_indicator_claim`
    is configured AND present in `claims_raw` AND its value (or, if a
    list, at least one of its values) is in `human_indicator_values`.
    Every other case -- unconfigured, claim absent, claim present but
    none of its values match -- returns `IdentityKind.OIDC`, identical
    to this codebase's behavior before this module existed. Fail-safe
    by construction: there is no code path here that returns `HUMAN`
    without an explicit, deployer-supplied signal actually matching.
    """
    if human_indicator_claim is None:
        return IdentityKind.OIDC

    value = claims_raw.get(human_indicator_claim)
    if value is None:
        return IdentityKind.OIDC

    expected = frozenset(human_indicator_values) if human_indicator_values else frozenset()
    if not expected:
        return IdentityKind.OIDC

    candidates = value if isinstance(value, list) else [value]
    if any(str(candidate) in expected for candidate in candidates):
        return IdentityKind.HUMAN
    return IdentityKind.OIDC
