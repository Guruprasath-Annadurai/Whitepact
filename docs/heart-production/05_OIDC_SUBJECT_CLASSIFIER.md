# OIDC Subject Classifier — resolving the "mechanism vs. identity type" ambiguity

> Continues `docs/heart-production/`'s numbered series (`03`
> Zero-Trust Identity, `04` Authority Resolver, this is `05`). Directly
> follows up on `03_ZERO_TRUST_IDENTITY.md`'s own "what this phase
> does not resolve" section, which named this exact gap.

## The gap

`IdentityContext.kind = IdentityKind.OIDC` is set for every
OIDC-authenticated request today (`governance/models.py::IdentityContext.
from_org_context()`), whether the Bearer JWT came from a human
interactively logging in via SSO or a machine using an OAuth2
client-credentials grant (RFC 6749 §4.4) — `auth/oidc.py`'s
`OIDCProvider.validate_token()` accepts both identically, and nothing
downstream distinguishes them. `identity_authority_adapter.py`'s
kind→`RootType` mapping already handles this conservatively (`OIDC`
always maps non-terminal, `WORKLOAD_IDENTITY`) — safe, but a default
*around* the ambiguity, not a resolution of it.

## Why a heuristic is the wrong fix

No claim reliably distinguishes "a human authenticated" from "a client
authenticated" across every OIDC provider. `amr` (RFC 8176,
Authentication Methods References) is the closest thing to a standard
signal — populated only for an actual end-user authentication event on
well-behaved IdPs — but it's optional even for genuine human logins,
and some providers use non-standard claims instead (`gty` on
Auth0/Okta). Picking one heuristic and applying it globally risks
guessing wrong in the *unsafe* direction — treating a machine's token
as human, letting authority originate where constitutional law H2
forbids it. That risk is exactly why the existing code stays
conservative by default.

## The fix: deployer-configured, not WhitePact-guessed

`governance/oidc_subject_classifier.py`'s `classify_oidc_subject()`
takes the raw JWT claims plus two new opt-in settings —
`Settings.oidc_human_indicator_claim` (a claim name, e.g. `"amr"`) and
`Settings.oidc_human_indicator_values` (which values of that claim
count as human evidence, default `["pwd", "mfa", "otp"]`) — and
returns `IdentityKind.HUMAN` only when the configured claim is present
**and** at least one of its values matches. Unconfigured (the
default), it returns `IdentityKind.OIDC`, byte-for-byte the same as
today's behavior.

This mirrors `integrations/identity_bridge.py`'s existing `org_claim`
parameter (added because "Okta has no standard tenant claim at all...
hence the configurable parameter rather than a hardcoded guess") —
the same "configurable, not guessed" discipline this codebase already
established for exactly this class of cross-IdP variability, applied
here to a second axis (identity type instead of tenant).

## What this does not do

**Not wired into any live request path.** `_resolve_oidc_context()`
(duplicated in `mcp/server.py` and `dashboard/app.py`) returns an
`rbac.models.OrgContext`, which has no field for this distinction and
is shared by every authentication mechanism, not just OIDC — adding a
per-request hint there, and threading it through the three call sites
that build an `IdentityContext` from an `OrgContext`
(`mcp/governance_integration.py`, `mcp/upstream_dispatch.py`,
`mcp/server.py`), touches live authentication code every single
request goes through, in two separate application entrypoints. That's
a distinct, higher-risk change deserving its own dedicated
verification pass — exactly the same reasoning
`04_AUTHORITY_RESOLVER.md` gives for deferring its own Phase 6 live
wiring. This phase ships the real, tested, ready-to-wire classifier
and its configuration surface now; wiring it into `_resolve_oidc_context()`
is separate future work.

## Verification

- 8 new tests (`tests/test_oidc_subject_classifier.py`) plus 3 new
  config tests (`tests/test_config.py::TestOidcHumanIndicatorValuesEnvParsing`),
  all passing.
- `ruff check` / `ruff format --check` clean.
- `mypy src/responsibleai`: clean, 169 source files.
- Full repository suite: see commit for the exact pass count at time
  of commit, run fresh.
