# Migrating to WhitePact v2

> **Status of this document**: this is the migration *plan*. As of this
> writing, none of the renames described below have been executed in
> code — the package is still `rai-governance-platform`, imports are
> still `responsibleai.*`, env vars are still `RAI_*`, the MCP server
> still identifies as `responsibleai-mcp`, and the Helm chart is still
> named `rai-governance`. This document is the contract that execution
> follows, staged deliberately rather than done as one uncontrolled
> global rename — see `SPEC.md` Section 9 and the non-negotiable rule
> against blind global replacement of `responsibleai`/`ResponsibleAI`/
> `RAI_`.
>
> Every table below distinguishes **current name** (verified against
> source, not guessed) from **target name**, and states explicitly
> whether the current name will keep working after the target ships.

Last reviewed: 2026-07-26 · Current package version: 1.2.0 · Repository:
`Guruprasath-Annadurai/Whitepact` (renamed on GitHub from `ResponsibleAi`
— confirmed via `gh api repos/.../ResponsibleAi` → `full_name:
"Guruprasath-Annadurai/Whitepact"`; the local git remote has been
updated to match).

---

## 1. Why this migration exists

The GitHub repository has already been renamed. The internal product
identity has not caught up — 158 files still reference the
`responsibleai` import path, 55 files reference `RAI_`-prefixed
environment variables, and the PyPI-facing package name is still
`rai-governance-platform`. Left alone, this becomes a permanent,
worsening inconsistency between what the repository is *called* and what
the code *says it is*. This document is how that gap closes without
breaking anyone currently depending on the `RAI_*`/`responsibleai-mcp`
names.

---

## 2. Scope inventory (from the baseline audit)

| Legacy identifier | Files (grep count) | What it is |
|---|---|---|
| `responsibleai` (lowercase) | 158 | The Python import path (`src/responsibleai/`) |
| `ResponsibleAI` | 103 | Human-facing product name in docs |
| `RAI_` | 55 | Environment variable prefix (`pydantic-settings` `env_prefix="RAI_"`) |
| `rai-governance` | 32 | PyPI package name root + Helm chart name (`helm/rai-governance/`) |
| `ResponsibleAi` | 20 | GitHub-URL-casing variant in docs/badges |
| `responsibleai-mcp` | 17 | The published MCP server console script |
| `rai://` | 6 | MCP resource URI scheme (`src/responsibleai/mcp/resources.py`) |
| `responsibleai.dev` | 3 | A domain referenced in docs that was never registered/deployed — see Section 13. `whitepact.com` is now registered and live (2026-08-17), wired to the hosted dashboard. |

---

## 3. Package migration

**Current**: PyPI package name `rai-governance-platform`
(`pyproject.toml` `[project] name`), Python import path
`responsibleai.*` / `biasbuster.*` / `privacylabel.*`
(`[tool.hatch.build.targets.wheel] packages`).

**Target**: PyPI package name `whitepact`, with `rai-governance-platform`
kept as a **compatibility shim package** for at least one full major
version — a thin `rai-governance-platform` distribution that depends on
`whitepact` and re-exports its top-level names, so `pip install
rai-governance-platform` keeps working and `import responsibleai`
continues to resolve.

**Why not rename `src/responsibleai/` immediately**: 158 files import
from it, including every test in the 1349-test suite, every MCP tool,
the entire dashboard, and the newly built `src/responsibleai/
integrations/` LangChain/LangGraph/ADK adapters. A single mechanical
rename of the directory is exactly the "blind global replace" this
migration is explicitly forbidden from doing — it would touch import
statements, string-based dynamic imports (if any), documentation
examples, Docker `COPY` paths, and CI cache keys simultaneously, with no
way to verify each change independently. Instead:

1. **This phase (v2.0.0)**: `whitepact` becomes an *alias package* that
   re-exports everything from `responsibleai`/`biasbuster` — i.e.
   `import whitepact` works and returns the exact same objects as
   `import responsibleai`, implemented as a thin `src/whitepact/
   __init__.py` doing `from responsibleai import *` plus explicit
   re-exports of anything not covered by `*`. No logic moves; no
   existing import breaks.
2. **A later minor version**: the actual implementation moves to
   `src/whitepact/`, and `responsibleai` becomes the alias (reversed
   direction), once the bulk of new development already targets the new
   path.
3. **A future major version**: the `responsibleai` alias is removed,
   with a full minor-version cycle of `DeprecationWarning`s preceding
   it.

This mirrors the pattern this project already uses successfully — the
existing `biasbuster`/`responsibleai`/`privacylabel` three-package
structure inside one distribution.

---

## 4. CLI migration

**Current** (`pyproject.toml` `[project.scripts]`, verified):

```
biasbuster        = "biasbuster.cli:main"
responsibleai     = "biasbuster.cli:main"
responsibleai-mcp = "responsibleai.mcp.server:main"
responsibleai-mcp-http = "responsibleai.mcp.server:main_http"
```

**Target**: add, do not replace:

```
whitepact         = "biasbuster.cli:main"          # new preferred name
whitepact-mcp     = "responsibleai.mcp.server:main"
whitepact-mcp-http = "responsibleai.mcp.server:main_http"
```

`biasbuster`, `responsibleai`, `responsibleai-mcp`, and
`responsibleai-mcp-http` all keep working, unchanged, pointing at the
identical entry-point functions. This is additive — five new lines in
`[project.scripts]`, zero removed. `whitepact-mcp`'s process, once
started, should log a one-line notice (to stderr/structured logging,
**never to stdout**, since stdout is the stdio MCP transport itself and
writing to it corrupts the protocol — see Phase 26 of the parent
migration plan) confirming which name it was invoked as, for
observability during the transition.

---

## 5. Environment variable migration

**Current**: `Settings` (`src/responsibleai/dashboard/config.py`) uses
`pydantic-settings` with `env_prefix="RAI_"` applied uniformly across
all 40 configuration fields — there is no per-field `env=` override list
to enumerate; every field `foo_bar: str` automatically reads from
`RAI_FOO_BAR`. Representative examples actually in source:
`RAI_DATABASE_URL`, `RAI_API_KEYS`, `RAI_AUTH_ENABLED`, `RAI_REDIS_URL`,
`RAI_FIELD_ENCRYPTION_KEY`, `RAI_LEADERBOARD_AZURE_OPENAI_ENDPOINT`.

**Target**: `WHITEPACT_*` becomes the preferred prefix. Because the
prefix is applied uniformly by `pydantic-settings` rather than
per-field, the migration is a mechanism change, not a 40-line rename:

- Add a second `pydantic-settings` source that reads `WHITEPACT_*`
  variables and maps them onto the same field names.
- **Precedence rule** (matching the worked example in the parent
  migration spec): if both `WHITEPACT_DATABASE_URL` and
  `RAI_DATABASE_URL` are set, the `WHITEPACT_` value wins, unambiguously,
  for every field — not a per-field negotiation.
- `RAI_*` continues to be read whenever `WHITEPACT_*` is absent for that
  field — full backward compatibility, no deployment's existing
  `.env`/Helm `values.yaml`/Docker Compose file breaks on upgrade.
- On startup, if any `RAI_*` variable was used to satisfy a setting
  (i.e. its `WHITEPACT_*` counterpart was absent), log one structured
  `deprecated_env_var_used` warning per variable, not per request —
  loud enough to be seen in a deploy log, not so noisy it drowns out
  real warnings.

This is implemented via `pydantic-settings`' documented support for
multiple settings sources (`Settings.settings_customise_sources`), not a
hand-rolled `os.environ` scan — reusing the library's own precedence
mechanism rather than building a parallel one.

**Deferred to a dedicated follow-up, not part of this document's
scope**: the actual code change to `config.py` implementing this dual-
prefix resolution, plus tests proving the precedence rule (`WHITEPACT_*`
set + `RAI_*` set → `WHITEPACT_*` wins; only `RAI_*` set → it's used and
warns; only `WHITEPACT_*` set → no warning). That is real functional
code requiring its own test suite per this project's rule that every
functional change requires tests — tracked as the next concrete
implementation step after this document.

---

## 6. MCP server identity migration

**Current** (verified in `src/responsibleai/mcp/server.py` and
`compliance/MCP_DISTRIBUTION_GUIDE.md`): the server identifies itself as
`responsibleai-mcp` in its MCP `Server` metadata, is published under
that name in directory-submission copy, and exposes 27 tools + 10
resources.

**Target**: the server's advertised MCP identity becomes `whitepact`
(the `name` field in the `Server(...)` construction), while:

- The `responsibleai-mcp` / `responsibleai-mcp-http` console scripts
  keep launching the exact same server process (Section 4) — only the
  *protocol-level* self-identification string changes, which any MCP
  client already handles as an opaque display name, not a hardcoded
  dependency.
- Directory-listing copy (`compliance/MCP_DISTRIBUTION_GUIDE.md`,
  `compliance/outreach/PHASE_A_LAUNCH_KIT.md`) is updated to the new
  identity as part of this migration, since none of it has been
  submitted anywhere yet (per the standing founder-action item) — there
  is no live external listing under the old name to keep consistent
  with.

**Resource URI scheme**: current scheme is `rai://` (6 files, e.g.
`rai://health`, `rai://models/catalog` — verified in
`src/responsibleai/mcp/resources.py`). Target scheme is `whitepact://`.
Because MCP resource URIs are opaque identifiers a client reads from
`RESOURCE_DEFS` rather than constructs itself, this is safe to change
directly in a version bump **with both schemes served** for one
transition window: register every resource under both `rai://foo` and
`whitepact://foo`, pointing at the identical handler, then remove the
`rai://` registrations in the major version that also removes the
`responsibleai` import alias (Section 3).

---

## 7. MCP transport modernization (Streamable HTTP)

**Current** (verified in `src/responsibleai/mcp/server.py` before this
section's implementation): the hosted MCP HTTP app (`main_http()` /
`responsibleai-mcp-http`) served exactly one transport — HTTP+SSE, the
MCP spec's 2024-11-05 transport, on `/sse` (event stream) + `/messages/`
(client-to-server POSTs), both Bearer-authenticated and plan-gated
against the calling org (`mcp/licensing.py`).

**Target** (implemented): a second, additive endpoint, `/mcp`, serving
**Streamable HTTP** — the MCP spec's 2025-03-26+ transport, a single path
handling both directions instead of two. Implementation notes:

- Built on `mcp.server.streamable_http_manager.StreamableHTTPSessionManager`
  (already vendored by the pinned `mcp<2.0.0` SDK — no new dependency).
- Registered as `stateless=True`: every request to `/mcp` is
  authenticated and dispatched independently, matching the existing
  `/sse` transport's per-connection Bearer-auth model rather than adding
  cross-request session affinity the current deployment topology (see
  Section on HA readiness) doesn't yet support.
- Shares the exact same `_authenticate()` Bearer-token check and the
  same `_current_org`/`_current_usage_repo` contextvars that
  `_call_tool` reads for plan-gating and quota metering (Section on
  runtime governance) — a request over `/mcp` is billed and gated
  identically to one over `/sse`.
- Registered via Starlette `Route`, not `Mount` — `/mcp` matches the
  exact path with no trailing-slash redirect, since MCP clients
  connecting to `/mcp` don't expect a 307.

**Client configuration** — both transports point at the same
`responsibleai-mcp-http` / `whitepact-mcp-http` process, on the same
port; a client selects its transport by which path it connects to:

```jsonc
// Streamable HTTP (preferred for new clients)
{ "mcpServers": { "whitepact": {
    "url": "https://<host>/mcp",
    "headers": { "Authorization": "Bearer <api-key>" }
} } }

// HTTP+SSE (legacy, unchanged, still supported)
{ "mcpServers": { "whitepact": {
    "url": "https://<host>/sse",
    "headers": { "Authorization": "Bearer <api-key>" }
} } }
```

**Deprecation posture for `/sse`**: not deprecated in the sense of a
removal date — it keeps running, byte-for-byte unmodified by this
change (verified by `tests/test_mcp_http_transport.py`'s
`TestLegacySseTransportUnaffected`). `/mcp` is simply the transport new
integrations should prefer, per the same "additive, not a replacement"
posture as every other alias in this document. No removal date is
committed here, consistent with Section 14's timeline for every other
legacy name.

**Tests**: `tests/test_mcp_http_transport.py` runs a real MCP client
(`mcp.client.streamable_http.streamable_http_client`) against the real
Starlette app in-process (`httpx.ASGITransport`, no socket) — covering
unauthenticated/invalid-token rejection, `initialize` + `list_tools` +
`call_tool` round trips over `/mcp`, and that `/sse` still requires and
enforces the same auth. This also closed a pre-existing test gap: the
hosted HTTP app had no transport-level integration test before this
change, only the plan-gating unit tests in
`tests/test_mcp_server_gating.py` that call `_call_tool` directly.

**Not in scope for this section** (tracked separately, per the "no
refactor beyond what's required" rule): structured tool-output contracts
(`structuredContent`, output schemas) — a later phase of the WhitePact
Enterprise Foundation v2 program, not required to add a second transport
alongside the first. OAuth/OIDC-based authorization, originally deferred
here too, is now covered by Section 7.2 below.

### 7.1 Transport security hardening

Two gaps existed in both hosted transports before this addendum, found
by inspecting what the pinned MCP SDK actually provides versus what the
server was passing it (`mcp.server.transport_security.TransportSecurityMiddleware`'s
own docstring: DNS rebinding protection is **disabled by default** when
no `security_settings` is passed — which is what both transports had
been doing since Section 7 landed).

**DNS rebinding protection** (Host/Origin header validation): now wired
via `_build_transport_security()`, shared by both `/mcp` and `/sse`.

- `RAI_MCP_HTTP_ALLOWED_HOSTS` / `RAI_MCP_HTTP_ALLOWED_ORIGINS`
  (comma-separated allowlists) and `RAI_MCP_HTTP_DNS_REBINDING_PROTECTION`
  (explicit force on/off).
- Stays **disabled by default** even though this is a "security
  hardening" change — enabling it with an empty allowlist would reject
  every request against the SDK's own validation logic
  (`_validate_host`/`_validate_origin` require an exact or wildcard
  match against a non-empty list), which would silently break every
  existing hosted deployment on upgrade. Per the standing rule to
  preserve backward compatibility unless there's a strong technical
  reason not to: there isn't one strong enough to justify breaking
  deployments that haven't opted in. Once either allowlist is
  configured, protection auto-enables; the explicit flag can still force
  it either way.
- Deployers fronting the hosted MCP process with a known set of
  hostnames (the common case) should set `RAI_MCP_HTTP_ALLOWED_HOSTS` —
  this is the single most impactful hardening step available here and
  costs nothing functionally once the allowlist matches the real
  deployment.

**Bearer-auth brute-force rate limiting**: `_AuthFailureLimiter`, an
in-memory sliding-window limiter keyed by client IP, gates
`OrgRepository.authenticate()` on both transports — a client that
exhausts `RAI_MCP_HTTP_AUTH_MAX_FAILURES` (default 10) failed attempts
within `RAI_MCP_HTTP_AUTH_WINDOW_SECONDS` (default 60) gets `429`s
without touching the database, and the failure budget is shared between
`/mcp` and `/sse` so switching transports doesn't reset it. This is
explicitly **not** the same thing as `PlanRateLimiter`
(`dashboard/plan_rate_limiter.py`), which meters successful,
authenticated tool calls against a billing plan and is backed by Redis
for cluster-wide accuracy — `_AuthFailureLimiter` guards the auth
boundary itself and is in-memory, so it's per-process, not cluster-wide.
Stated plainly per the non-negotiable rule against overclaiming: this is
a real speed bump against the common single-source brute-force case, not
distributed rate limiting across replicas.

**Tests**: `tests/test_mcp_transport_security.py` — unit tests for the
env-var parsing helpers and `_AuthFailureLimiter`'s window/threshold/
per-key-independence behavior, plus integration tests proving a
mismatched `Host` header gets `421` once an allowlist is configured, a
matching host passes through to the existing auth check, and repeated
auth failures against either transport produce `429`s that share one
budget.

### 7.2 MCP authorization / OAuth modernization

Before this addendum, both hosted transports accepted exactly one
credential kind: a static, opaque API key (`rai_...`, `OrgRepository`-
issued, revocable but never expiring on its own). That's a real gap
against the MCP Authorization spec's expectation that a server can act
as an OAuth 2.1 resource server.

**What this does *not* do**: stand up a new OAuth Authorization Server
(client dynamic registration, `/authorize` + `/token` endpoints, consent
screens, refresh-token issuance). Building one from scratch, for a
product whose dashboard API already has a working SSO integration
point, would be reinventing infrastructure that already exists in this
codebase — and per the standing rule against unnecessary new
dependencies/features, there's no requirement here that calls for it.

**What this does**: makes the hosted MCP server an OAuth/OIDC
**resource server** against whichever Authorization Server an org's SSO
already trusts.

- Reuses `Settings.oidc_issuer` / `oidc_client_id` / `oidc_jwks_uri` /
  `oidc_skip_verification` — the exact same config
  `dashboard/app.py`'s `_oidc_provider` already reads for
  `/api/auth/login/oidc`. No new MCP-specific OIDC env vars: one IdP
  configuration serves both the dashboard API and the MCP server.
- `_resolve_oidc_context()` in `mcp/server.py` mirrors
  `dashboard/app.py`'s `_resolve_oidc_context()` claims-to-`OrgContext`
  mapping line for line, so a JWT behaves identically against both
  surfaces.
- Credential resolution order (both transports): `rai_`-prefixed →
  always a static key, DB lookup. Anything else → tried as an OIDC JWT
  first when a provider is configured, DB lookup otherwise. The `rai_`
  prefix (`_generate_raw_key()`, `org_repository.py`) makes the two
  credential kinds structurally unambiguous, never guessed.
- **RFC 9728** Protected Resource Metadata is served at
  `/.well-known/oauth-protected-resource` — `{"resource": ".../mcp",
  "authorization_servers": [oidc_issuer], ...}` — when OIDC is
  configured, `404` otherwise (there's no Authorization Server to point
  a client at). A `401` response also carries `WWW-Authenticate: Bearer
  resource_metadata="..."` pointing at that same document, per the spec,
  again only when OIDC is actually configured — an unconditional hint
  would tell every client "this deployment supports OAuth" even for
  ones that only ever will support static keys.
- A JWT with an `org_id` claim the DB doesn't recognize still
  authenticates (the JWT's signature/issuer is the trust boundary, not
  DB membership) but resolves to `Plan.FREE` — the existing plan-gating
  in `_call_tool` then applies normally, same as any other FREE-plan
  context.

**Tests**: `tests/test_mcp_oauth.py` — JWT auth succeeding on both
`/mcp` and `/sse`, static keys still working when OIDC is configured,
malformed/JWT-shaped-but-no-provider tokens rejected, the unknown-org-id
FREE-plan fallback, the `WWW-Authenticate` hint appearing only when
configured, and the metadata endpoint's `200`/`404` split.

### 7.3 Structured tool-output contracts

Spec 2025-06-18 added `structuredContent` to `CallToolResult`: a tool's
result as a real JSON object a client can consume directly, instead of
every client parsing the legacy `content[0].text` JSON-string blob.
Every one of the 27 tools' handlers in `mcp/tools.py` already returns
`dict[str, Any]` (`dispatch_tool`'s own return type) — the gap was
purely in `mcp/server.py`'s `_call_tool`, which discarded that structure
and serialized straight to `TextContent`.

**What changed**: `_call_tool` now returns `(content, structuredContent)`
tuples via a small `_text_and_structured()` helper — a shape the pinned
MCP SDK's `@server.call_tool()` decorator already recognizes natively
(`CombinationContent` in its own type signature) and turns into a
`CallToolResult` with **both** fields populated. The legacy
`content[0].text` blob is unchanged byte-for-byte (same
`json.dumps(result, indent=2, default=str)` call as before, just moved
into the helper) — pre-2025-06-18 clients that only ever read `content`
keep working exactly as before.

**What deliberately did *not* change**: `TOOL_DEFS`' `outputSchema`
field is left unset for all 27 tools. Per-tool output schemas would
need to be derived accurately from each handler's actual return shape
in `mcp/tools.py` (27 handlers, several with conditional/optional
fields) — writing them by hand without that derivation risks exactly
the kind of fabricated-but-wrong implementation detail the standing
rules prohibit, and the SDK enforces `outputSchema` strictly (a
declared-but-inaccurate schema would make previously-working calls fail
jsonschema validation). `structuredContent` is valid and useful without
a declared `outputSchema` — clients can still consume it, they just
don't get server-side schema validation on it yet. Adding accurate
schemas is real, separate, enumerable work, not implied by this change.

**Breaking change, internal-only**: `_call_tool`'s own return type
changed from `list[TextContent | ...]` to
`tuple[list[TextContent], dict[str, Any]]`. This function is not part
of the public MCP protocol surface (the protocol-level `tools/call`
response shape is unaffected — the SDK's decorator normalizes either
return shape into the same wire format) but it *is* called directly by
`tests/test_mcp_server_gating.py`, which was updated: `result[0].text`
(parse the JSON string) became `result[1]` (already the dict).

**Tests**: `test_mcp_http_transport.py`'s `test_call_tool_over_streamable_http`
now asserts `result.structuredContent is not None` and that it matches
`content[0].text`'s parsed JSON, over the real wire protocol. New
`TestStructuredToolOutput` in `test_mcp_server.py` covers the
`_text_and_structured` helper and `_call_tool`'s tuple shape directly.

---

## 8. Runtime governance core (Phase 8)

**Current** (before this section's work): SPEC.md Section 2 described a
five-stage decision pipeline — Agent → Action → Policy/Trust/Risk →
Decision → Execution → Evidence — entirely as **[TARGET]** architecture.
Every existing decision-shaped output in the codebase was binary
(`GuardrailsEngine.scan()` → `is_blocked: bool`), and there was no
single component that took "an agent proposes an action" as input and
returned one of a real decision model as output.

**Target** (implemented): `src/responsibleai/governance/` —

- `GovernanceDecision`: the real, five-member `StrEnum`
  (`ALLOW` / `ALLOW_WITH_REDACTION` / `REQUIRE_APPROVAL` / `DENY` /
  `QUARANTINE`) SPEC.md Section 3.6 defines.
- `IdentityContext`, `AgentContext`, `AuthorityContext`, `ActionRequest`:
  the core entities from SPEC.md Section 3.1-3.4, as tested dataclasses.
  `IdentityContext.from_org_context()` generalizes the existing
  `OrgContext` (human/API-key/OIDC identity, unchanged) into the new
  vocabulary without modifying it — the same additive, non-breaking
  pattern as every other alias in this document, applied to a data
  model instead of a package/env-var/CLI name.
- `WhitePactRuntimeGateway.evaluate(action, authority, policy=None) -> DecisionResult`:
  the actual missing component. Deterministic checks, no LLM call: does
  `AuthorityContext` grant this `action_type` at all; does a
  caller-declared `require_approval_for` set on `AuthorityContext` name
  this action type (→ `REQUIRE_APPROVAL`, a caller-supplied trigger,
  distinct from automatic risk-based routing — see Section 8.1); does
  an optional `Policy` match a rule (Section 8.2); and does the
  existing, tested `GuardrailsEngine` find PII (→
  `ALLOW_WITH_REDACTION`, reusing its own redaction) or
  toxicity/custom-pattern matches (→ `DENY`) in any string-valued
  argument.

**Tests**: `tests/test_governance_core.py` — the entity dataclasses
(`IdentityContext.from_org_context`'s api_key/oidc kind detection,
`AgentContext`'s `organization_id` defaulting), and the gateway's full
decision matrix: authority denial, the approval trigger (and that
authority denial still wins over it), PII redaction (non-PII fields
left untouched, reason codes field-qualified), toxicity hard-denying
even when PII is also present in the same argument, risk-tier
population, and policy short-circuit/fall-through behavior (see 8.1/8.2
below for the pieces those last two exercise).

### 8.1 Risk-tiered routing (Phase 9)

SPEC.md Section 4 recorded a **proposed** tiering for the 27 MCP tools
"so the tiering decision is made once, deliberately, and reviewably,
rather than invented ad hoc when Phase 9 starts." This makes it real:

- `governance/risk.py`: `RiskTier` (`MINIMAL`/`LOW`/`MEDIUM`/`HIGH`) and
  `TOOL_RISK_TIERS`, a hardcoded table implementing SPEC.md Section 4's
  categories exactly — not re-derived or re-decided here, per that
  section's own instruction. `classify_action_risk(action_type, target)`
  is the router: MCP tool calls look up `target` in the table;
  non-MCP action types and unrecognized tool names both get `MEDIUM`
  (never a silent `MINIMAL` default for something unclassified).
- Deliberately dependency-free from `mcp.tools` — the table is hardcoded
  rather than derived from `TOOL_DEFS` at runtime, keeping the
  architectural dependency direction SPEC.md Section 4 describes (MCP
  tools are intelligence the governance pipeline calls *into*, not the
  reverse). `tests/test_governance_risk.py` instead verifies the table
  stays in sync with the live `TOOL_DEFS` list as its own drift check.
- Wired into `WhitePactRuntimeGateway`: every action that reaches the
  risk-classification step gets a `RiskTier` recorded on
  `DecisionResult.risk_tier` — always, whether or not a `Policy` is
  supplied. An action denied at the authority-check stage never reaches
  risk classification (`risk_tier` stays `None` on that path — Phase 9
  computing a tier for an action that was already going to be denied
  outright would be wasted, meaningless work).
- **What tiering does *not* do by itself**: classification alone causes
  no behavioral difference between tiers. A `HIGH`-tier action isn't
  automatically held for approval — that only happens if a `Policy`
  rule reads the tier and says so (Section 8.2). No default policy ships
  that does this, since that would be an opinionated governance stance
  imposed on every deployment rather than a neutral, available signal.

### 8.2 Policy engine (Phase 10)

SPEC.md Section 3.5 called for "a small, strongly typed internal model
first — not an LLM, not necessarily OPA/Rego on day one." First version:

- `governance/policy.py`: `PolicyRule` (`risk_tiers`/`action_types`/
  `targets` match filters, each `None` meaning "any"; an `effect` of
  `ALLOW`/`DENY`/`REQUIRE_APPROVAL` — `ALLOW_WITH_REDACTION` and
  `QUARANTINE` are rejected at construction, since redaction needs a
  matched span only `GuardrailsEngine` has and `QUARANTINE` needs
  cross-request state no rule here has access to) and `Policy` (an
  ordered `list[PolicyRule]`, evaluated first-match-wins — the entire
  conflict-resolution model is "read the rules top to bottom," not a
  priority/specificity scoring system needing its own explanation).
- Gateway integration: `policy` is an optional parameter to `evaluate()`,
  defaulting to `None` — omitting it reproduces Phase 8's exact original
  behavior byte-for-byte (`tests/test_governance_core.py`'s
  `test_no_policy_behaves_exactly_as_phase_8`). When supplied and a rule
  matches: `DENY`/`REQUIRE_APPROVAL` short-circuits immediately with
  `reason_codes=["policy:<rule_id>:<reason_code>"]`; `ALLOW` is recorded
  but does **not** skip the guardrails content scan that follows —
  defense in depth, an org allowing an action type isn't a statement
  about what's safe to leave unscanned.
- **What this explicitly is not**: rule *persistence*. A `Policy` is
  constructed in code and passed to `evaluate()` per call — there is no
  `policies` database table, no API to author or store one, and no UI.
  Also not OPA/Rego or any expression language — `PolicyRule`'s filters
  are plain set-membership checks, nothing that needs its own parser.

**Tests**: `tests/test_governance_risk.py` (tier-table coverage against
the live `TOOL_DEFS` list, classification defaults) and
`tests/test_governance_policy.py` (rule-filter matching, effect
validation, first-match-wins/fall-through evaluation) — plus the
gateway-integration tests noted in the main section above.

### 8.3 Evidence persistence (Phase 12)

SPEC.md Section 3.7 defines an `EvidenceRecord` — immutable, tamper-evident
structured evidence for every decision. Before this section: `DecisionResult`
was in-memory and unpersisted; nothing generalized the existing, proven
hash-chaining pattern (`db/public_incident_repository.py`) to governance
decisions.

- `governance/evidence.py`: `EvidenceRecord` (a pure, unhashed shape) and
  `build_evidence_record(action, agent, authority, decision)` (a pure
  assembly function — no I/O, no hashing). Deliberately **never stores
  raw argument values** — `argument_keys: list[str]` captures only the
  field *names* an action carried, not their contents, since field names
  alone can't leak a secret the way even a truncated value sometimes can.
- `db/evidence_repository.py`: `EvidenceRepository.record()` persists an
  `EvidenceRecord`, computing its hash chained onto that **organization's**
  last entry — chained per-org, not globally like the public incident
  registry, since an org's evidence trail must be independently
  verifiable without needing any other org's records.
  `verify_chain(org_id)` re-walks the chain from scratch and recomputes
  every hash, catching both a directly-tampered field and a broken
  `prev_hash` link (`tests/test_governance_persistence.py` proves both).
  Write-once: no `update`/`delete` method exists.
- Exposed via `GET /api/governance/evidence` (list, org-scoped,
  `ANALYST`+) and `GET /api/governance/evidence/verify` (chain integrity
  check, org-scoped).
- **What's honestly not captured**, against SPEC.md's full
  `EvidenceRecord` shape (`governance/evidence.py`'s module docstring has
  the complete accounting): `trust_signals` (nothing computes a live
  `TrustCheckResult` automatically), `deterministic_checks`/
  `probabilistic_checks` as separate structured fields (folded into
  `reason_codes` instead), `execution_result_metadata` (this package
  can't see whether an allowed action was actually executed).

### 8.4 Approval workflow (Phase 11)

SPEC.md Section 3.6: `REQUIRE_APPROVAL` was a real decision the gateway
could return, but nothing queued it, notified anyone, or exposed a
resolution API — a decision with no mechanism to act on it.

- `governance/approval.py`: `ApprovalRequest` + `ApprovalStatus`
  (`PENDING`/`APPROVED`/`DENIED`) and `build_approval_request(action, decision)`,
  pure assembly matching `governance/evidence.py`'s pattern.
- `db/approval_repository.py`: `ApprovalRepository.create()` persists a
  `PENDING` request and, if a `WebhookManager` is supplied (optional,
  keyword-only), fires the new `WebhookEvent.APPROVAL_REQUESTED` through
  the existing, tested webhook infrastructure — real notification, not a
  new notification system. `resolve()` is a one-way state transition
  (`PENDING -> APPROVED`/`DENIED`) guarded two ways: an in-Python check
  before the write, and a `WHERE status = 'PENDING'` clause on the
  `UPDATE` itself, so a race between two concurrent resolvers can't both
  succeed — the loser gets `ApprovalAlreadyResolvedError`, never a
  silently overwritten decision. `ApprovalNotFoundError` for an unknown
  ID.
- Exposed via `GET /api/governance/approvals` (list pending, org-scoped,
  `ANALYST`+) and `POST /api/governance/approvals/{id}/resolve`
  (org-scoped, **`ADMIN`+** — resolving is a materially more privileged
  action than viewing). A resolve request for another org's approval ID
  returns `404`, never `403`, so the endpoint never confirms *anything*
  about another org's approval IDs existing.
- **What's honestly not built**: any notification beyond the optional
  webhook fire (no email/Slack-app-specific integration, no in-app UI,
  no SLA/expiry timers), and no automatic re-evaluation or execution of
  the original action once approved — resolving records a human
  decision; acting on it is the caller's responsibility, same as an
  `ALLOW` decision always was.

**Also explicitly not built anywhere in Phases 8-12** (real gaps,
tracked as their own later work — SPEC.md's per-section status markers
say this too, not just here):

- **`QUARANTINE`** — a real, tested enum member, but nothing anywhere
  in this package ever produces it: that needs cross-request pattern
  tracking (e.g. "this agent has had 3 policy violations this week")
  no phase so far builds.
- **MCP tool dispatch integration** — `dispatch_tool()` in `mcp/tools.py`
  is completely unchanged; nothing routes an actual MCP tool call
  through `WhitePactRuntimeGateway`, `EvidenceRepository`, or
  `ApprovalRepository` before dispatching it. All three exist and are
  tested standalone; wiring them into the live request path is real,
  separate, own-tested work.
- **Trust Index signal integration** — `AgentContext.trust_state` exists
  as a field; nothing populates it from a live Trust Index lookup or
  reads it in a decision or a piece of evidence.
- **Evidence export beyond JSON** (e.g. a signed PDF/CSV bundle for an
  auditor) — `EvidenceRecord.to_dict()` and the list API are the only
  export path today.

**Tests**: `tests/test_governance_persistence.py` (hash chain
record/get/list, tamper detection on both a mutated field and a broken
`prev_hash` link, per-org chain independence, approval creation/listing/
resolution including the double-resolve and not-found error paths) and
`tests/test_governance_api.py` (the four HTTP endpoints end-to-end
against a real auth-enabled app instance: org-scoping, the `ANALYST` vs
`ADMIN` role split, cross-org access returning `404` not `403`,
double-resolve returning `409`). 85 tests total across
`test_governance_core.py` + `test_governance_risk.py` +
`test_governance_policy.py` + `test_governance_persistence.py` +
`test_governance_api.py`.

### 8.5 MCP Trust/Supply-Chain Scanner (Phase 13)

**Current** (before this section's work): nothing in this codebase
evaluated the trustworthiness of a *third-party* MCP server before an
org grants an agent authority to use it — a real gap distinct from the
rest of the governance core, which governs actions against *this*
server's own tools.

**Target** (implemented): `src/responsibleai/supplychain/` —
`SupplyChainScanner.scan(manifest, incident_repo=...)` returns a
`SupplyChainReport`: a list of per-check `Finding`s, each a
`VERIFIED_FACT` / `INFERRED_SIGNAL` / `UNKNOWN` verdict — SPEC.md
Section 4.1's one hard requirement, never a single opaque score.

- **Confusable-character check** — `VERIFIED_FACT` either way, a
  bounded Cyrillic/Greek lookalike lookup table (not full Unicode TR39
  confusables — a stated, bounded subset) against server and tool
  names, the classic typosquat trick.
- **Tool description content scan** — always `INFERRED_SIGNAL`, reuses
  the existing, tested `GuardrailsEngine` rather than inventing new
  pattern-matching for this.
- **Known public incident cross-reference** — `VERIFIED_FACT` if the
  existing AI Incident Database's `check()` returns filed reports,
  `UNKNOWN` (not "safe") if it returns none — optional, only runs if a
  `PublicIncidentRepository` is supplied.
- Exposed via `POST /api/governance/supplychain/scan` (`ANALYST`+, not
  org-scoped — the checks are either pure or query the public,
  org-agnostic incident database).
- **Deliberately does not connect to a remote MCP server itself** — it
  analyzes a caller-supplied manifest. Actually speaking the MCP
  protocol to an arbitrary third-party server (handshake, `tools/list`,
  following redirects) is real, separate transport-layer work with its
  own security questions (SSRF risk in fetching an arbitrary
  server-supplied URL from the backend, for one) — out of scope here,
  not implied by this scanner's existence.

**Tests**: `tests/test_supplychain_scanner.py` (13 tests — each check's
verdict logic, including that the description scan can never claim
`VERIFIED_FACT` in either direction) and a new `TestSupplyChainScanEndpoint`
class in `tests/test_governance_api.py` (5 tests — auth required, the
findings list shape with no score/rating field present, the incident
check's default-on behavior, confusable-name detection, request
validation).

---

## 9. Deployment migration

**Docker**: `Dockerfile`'s `LABEL org.opencontainers.image.*` fields
currently describe `ResponsibleAI`/`responsibleai`. These are metadata,
not functional — updated directly to `WhitePact`/`whitepact` with no
compatibility concern (nothing parses these labels expecting the old
values, verified by grepping for any consumer of the label values in CI
or deploy scripts — there is none).

**Helm**: the chart directory is `helm/rai-governance/`
(`Chart.yaml` `name: rai-governance`). Renaming a Helm chart's `name`
changes its release history addressing for anyone who's already
`helm install`ed it. Target approach:

- Publish a new `helm/whitepact/` chart (copy, renamed, same templates)
  for new installs.
- Keep `helm/rai-governance/` in the repository, marked deprecated in
  its own `README`/`NOTES.txt`, for existing installs to upgrade from —
  do not delete a chart out from under a live Helm release.
- Both charts' `values.yaml` should default to the same container image,
  so switching charts is a `helm install` of the new chart followed by
  decommissioning the old release, not a forced simultaneous cutover.

**docker-compose**: service names and network names in
`docker-compose.yml`/`docker-compose.prod.yml` are internal to the
compose project and not part of any external contract — renamed
directly.

### 9.1 High-availability deployment defaults (Phase 14)

**Current** (before this section's work): `helm/rai-governance/` already
had solid within-region HA defaults for the dashboard —
`replicaCount: 2`, a `PodDisruptionBudget`, an `HorizontalPodAutoscaler`,
preferred pod anti-affinity, a zero-downtime `RollingUpdate` strategy,
and liveness/readiness probes — this predates this migration and wasn't
touched. What was missing: the hosted MCP transport process
(`responsibleai-mcp-http`, Section 7) had a `docker-compose.prod.yml`
service (`mcp-http`) but **no Helm representation at all** — a Kubernetes
deployer following this chart could run the dashboard with real HA and
had no equivalent path for the actual MCP governance layer, the core
deliverable of this whole migration.

**Target** (implemented): four new templates in `helm/rai-governance/templates/`
— `mcp-deployment.yaml`, `mcp-service.yaml`, `mcp-hpa.yaml`,
`mcp-pdb.yaml` — plus a new `mcp:` block in `values.yaml`, giving the
hosted MCP transport the identical HA posture as the dashboard:

- Its own `Deployment`, distinct name/selector from the dashboard's
  (`{{ fullname }}-mcp`) so the two never collide — a Deployment's
  selector is immutable after creation, same constraint the dashboard's
  already respects.
- `replicaCount: 2` by default, an `HorizontalPodAutoscaler` (2-10
  replicas on CPU/memory), a `PodDisruptionBudget` (`minAvailable: 1`),
  and preferred pod anti-affinity keyed to its own label — copied
  patterns, not new ones invented for this.
- Liveness/readiness probes against `GET /health` on port 8766 (the
  real health endpoint `mcp/server.py`'s `_build_http_app()` serves,
  verified against source, not assumed).
- Shares the dashboard's `ConfigMap`/`Secret` via `envFrom` (both
  processes read the same `Settings` class, so `RAI_DATABASE_URL` etc.
  only need to be defined once) but sets `RAI_MCP_HTTP_HOST`/
  `RAI_MCP_HTTP_PORT` directly in the Deployment spec, since those are
  specific to this process and irrelevant to the dashboard.
- **Deliberately does not reuse `.Values.podAnnotations`** for
  Prometheus scraping — that block hardcodes `prometheus.io/port:
  "8765"`, the dashboard's port. Copying it verbatim onto the MCP
  Deployment would tell Prometheus to scrape a port these pods don't
  even listen on. `mcp.podAnnotations` is a separate, empty-by-default
  value instead, since this process has no `/metrics` endpoint today —
  an honest gap, not something to paper over with copy-pasted
  annotations that happen to render without error.
- `mcp.enabled: false` skips deploying it entirely, for self-hosted
  stdio-only deployments that never run the hosted transport.

**Verified**: `helm lint helm/rai-governance/` (clean) and
`helm template rai-governance helm/rai-governance/ --set image.tag=ci-test
--debug` (renders without error, checked by hand for the exact image/
port/env values expected) — both also run in CI's `helm-lint` job.
`mcp.enabled=false` was verified to produce zero MCP resources.

---

## 10. Supply chain, release, registry, and OSS governance (Phases 15-18)

### 10.1 Supply chain security (Phase 15)

- **SBOM generation** (`.github/workflows/ci.yml`'s `build` job and
  `publish.yml`) — a CycloneDX 1.6 SBOM generated with `cyclonedx-py
  environment` against a clean venv with the *actual built wheel*
  installed into it, not a static read of `pyproject.toml` — verified
  locally before this landed: a real build produced a 66-component SBOM.
  Uploaded as a CI artifact on every build; attached to every GitHub
  Release.
- **Build provenance attestation** (`publish.yml`) —
  `actions/attest-build-provenance@v2` signs the published wheel/sdist
  via Sigstore, verifiable with `gh attestation verify <file> --owner
  Guruprasath-Annadurai`. Requires the new `attestations: write`
  permission and `contents: write` (for the GitHub Release, Section 10.2).
- **Dependency review on PRs** (`.github/workflows/dependency-review.yml`,
  new) — `actions/dependency-review-action@v4`, distinct from `pip-audit`
  in `ci.yml`: `pip-audit` scans what this repo's dependencies *already
  are* on every push; this workflow reviews what a *PR is proposing to
  change* (new/bumped dependencies and their licenses) before merge.
  License allowlist verified against this project's actual dependency
  tree (`pip-licenses`) at the time it was written, not guessed.
- **Not built**: a pinned lockfile (`pyproject.toml` uses range
  constraints only — no `uv.lock`/`poetry.lock`/pinned
  `requirements.txt`). A real gap for fully reproducible builds, not
  invented away here; choosing a lockfile tool is an architecture
  decision this migration doesn't impose unilaterally.

### 10.2 Release engineering (Phase 16)

- **`CHANGELOG.md`** gained an `[Unreleased]` section summarizing every
  WhitePact-migration change from Phase 3 through Phase 15 in one place
  — previously the last real entry was `[1.2.0]`, dated before any of
  this migration's work started.
- **`RELEASING.md`** (new) — the actual mechanical release process
  (bump version in two places, move the changelog entry, tag, push),
  and what it deliberately does *not* automate (version-bump judgment
  calls, changelog generation from commits, Docker image publishing,
  pre-release channels) — stated plainly rather than silently absent.
- **`publish.yml`** gained a `Create GitHub Release` step
  (`softprops/action-gh-release@v2`) — previously a tag push built and
  published to PyPI but created no GitHub Release at all; now one gets
  created with the built artifacts, the SBOM, and a pointer back to the
  `CHANGELOG.md` entry.
- **Real, verified fact this section surfaced**: as of this writing,
  PyPI's actual latest published `rai-governance-platform` release is
  **1.1.0** (checked against `pypi.org/pypi/rai-governance-platform/json`)
  — `pyproject.toml`'s `1.2.0` has never actually been released. This
  matters directly for Section 10.3 below.

### 10.3 MCP registry readiness (Phase 17)

- **`server.json`** (repo root, new) — the manifest the official MCP
  registry (`github.com/modelcontextprotocol/registry`) requires,
  validated with `jsonschema` against the real, current schema
  (`https://static.modelcontextprotocol.io/schemas/2025-12-11/server.schema.json`,
  fetched at the time this was written, not guessed at) —
  `tests/test_server_json.py` keeps its `version` and tool/resource
  counts in sync with `pyproject.toml`/`TOOL_DEFS`/`RESOURCE_DEFS` the
  same way `governance/risk.py`'s tier table is checked against
  `TOOL_DEFS`.
- **`packages`** describes the PyPI install path (`rai-governance-platform`,
  invoked via `uvx --from rai-governance-platform whitepact-mcp`).
  **`remotes` (the hosted `/mcp`/`/sse` transports) was deliberately
  left out** — there is no verified, publicly reachable URL for the
  hosted MCP transport today (Section 13 below); a placeholder
  `example.com` URL would be exactly the kind of fabricated-but-plausible
  detail this project's rules prohibit. `tests/test_server_json.py`
  guards against one being added without updating this reasoning.
- **Not done, and can't be from here** (`compliance/MCP_DISTRIBUTION_GUIDE.md`
  has the full checklist): the `1.2.0` version in `server.json` must
  actually exist on PyPI before the registry accepts it (see 10.2's
  1.1.0-vs-1.2.0 finding — cut the release first); namespace ownership
  of `io.github.guruprasath-annadurai` requires a GitHub OAuth device
  flow this session has no access to; actually running `mcp-publisher
  validate`/`publish` is a founder action.

### 10.4 Open source governance (Phase 18)

- **`CODE_OF_CONDUCT.md`** (new) — Contributor Covenant 2.1, real
  contact email, enforcement responsibility stated as the founder's
  (matching `GOVERNANCE.md`, not inventing a moderation team).
- **`GOVERNANCE.md`** (already existed — a risk-oversight cadence
  document from earlier work; extended here, not replaced) — gained a
  new Section 6 covering day-to-day contribution/code-change
  decision-making, stating plainly that this is a founder-led project
  (Guruprasath Annadurai) with no steering committee or maintainer
  council today, per the standing rule against fabricating team roles
  that don't exist. An early draft of this change mistakenly
  overwrote the file wholesale instead of extending it — caught before
  commit by checking `git status`/`git diff` before staging, and fixed
  by restoring the original content and adding Section 6 alongside it.
- **`.github/CODEOWNERS`** (new) — one name, on purpose, same reasoning.
- **`SECURITY.md`** — fixed a real staleness bug found while touching
  this area: the "Supported versions" table still listed `0.4.x`/`0.3.x`
  while `pyproject.toml` has been at `1.2.0`; replaced with a policy
  that doesn't hardcode a version number that will just go stale again.
  Also fixed the disclosure email's subject-line branding
  (`[ResponsibleAI Security]` → `[WhitePact Security]`) and the "affected
  component" list (was BiasBuster/PrivacyLabel/Guardrails/RedTeam only —
  didn't mention the MCP governance engine or runtime governance core
  at all).
- **`CONTRIBUTING.md`** gained a one-line pointer to both new documents
  — a full rewrite of that file is its own later phase, not done here.

---

## 11. Documentation, threat model, and benchmarking (Phases 19-25)

### 11.1 CONTRIBUTING.md and README.md rewrites (Phases 19-20)

Both were still substantially BiasBuster/ResponsibleAI-branded and didn't
reflect anything built across Phases 3-18 (the governance core, MCP
transports, supply-chain scanner, evidence/approval workflow). Rewritten to:
describe the current repository layout and the governance core's role,
add an "Engineering Principles" section restating the 23 non-negotiable
rules this whole migration operates under, document the risk-tiering /
policy / evidence / approval subsystems for contributors touching them,
and replace stale facts in README.md (test count, resource count, tool
table) with real, verified-at-write-time numbers: **1,538 tests passing,
85% coverage** (`pytest`, this session), **27 MCP tools / 20 resources**
(`len(TOOL_DEFS)` / `len(RESOURCE_DEFS)`, this session — resources count
was previously documented as "10," which was the canonical count before
the dual `whitepact://`/`rai://` scheme made the advertised count 20).

### 11.2 SLA/enterprise claims review (Phase 21)

Audited `SLA.md`, `ENTERPRISE_SECURITY.md`, and `README.md` for
unsubstantiated claims (SOC 2/ISO 27001 self-certification, guarantees,
"enterprise-grade" marketing language). Found none — prior phases had
already kept this honest (every certification claim found is correctly
attributed to a sub-processor's *own* published certification, e.g.
Supabase's SOC 2 Type II, never claimed as WhitePact's own). What the
review did fix: both documents' titles and internal references still said
"ResponsibleAI Platform" while every other document had moved to
"WhitePact" — corrected for consistency, not a claims fix.

### 11.3 THREAT_MODEL.md (Phase 22)

New document — a STRIDE-structured threat model against the actual current
attack surface (MCP transports, OAuth/OIDC, the governance decision
pipeline, evidence hash chain, approval workflow, dashboard REST API, DB
layer, Helm/K8s deployment). Every mitigation cited points at real code;
every gap is stated as a gap. Explicitly scoped as a solo-founder
self-assessment, not independent red-team output — same honesty standard
`GOVERNANCE.md` holds itself to.

One entry was corrected mid-draft: a first pass claimed webhook SSRF was
an open gap, before finding `webhooks/manager.py`'s
`validate_webhook_url()` already mitigates it (private/loopback/
link-local/reserved/multicast/unspecified address rejection, checked at
registration and delivery, tested in `tests/test_webhooks.py`) — corrected
before this document was ever committed, consistent with the standing
"never fabricate implementation status" rule applying to documenting a
false gap just as much as a false capability.

### 11.4 Security test suite expansion (Phase 23) — a real bug found and fixed

Writing cross-org isolation tests for `/api/models`, `/api/cost/summary`,
and `/api/audit` (new file `tests/test_tenant_isolation.py`) surfaced a
genuine, previously-unknown defect: **every audit log entry was recorded
with `org_id: null` regardless of who actually made the request.**

Root cause: `AuditLogMiddleware` is a `BaseHTTPMiddleware`. Starlette runs
the downstream app — including `get_org_context`, the auth dependency that
resolves which org a request belongs to — inside a separate task via its
own internal task group (needed for `StreamingResponse`/background-task
support). A `ContextVar` mutated inside that inner task does not propagate
back to the middleware's own scope once `call_next()` returns — a
well-known Starlette gotcha this codebase had not hit before because
nothing had previously written an end-to-end test asserting audit-entry
*content* for an authenticated, org-scoped request (existing tests only
asserted response shape/status, e.g. `test_redteam_audit_billing_api.py`).

Fixed by moving org/key attribution from the `_audit_ctx` `ContextVar`
onto `request.state.audit_org_id`/`audit_key_id` — `request.state` is an
attribute on the same `Request` object instance shared across that task
boundary, so it survives where a `ContextVar` didn't. Fixed in
`src/responsibleai/dashboard/app.py` (`get_org_context`,
`AuditLogMiddleware.dispatch`); regression-tested in
`tests/test_tenant_isolation.py`; documented in `THREAT_MODEL.md`'s
Dashboard REST API section and `CHANGELOG.md`'s Unreleased/Fixed list.
Full suite re-run clean after the fix: **1,542 tests passing** (the
previous 1,538 plus 4 new tenant-isolation tests).

This is the clearest evidence so far that "expand the security test
suite" is worth doing as real, executed test-writing rather than a
documentation pass — the bug was invisible to code review (the code
*looked* correct; the ContextVar/BaseHTTPMiddleware interaction is a
runtime property, not a static one) and only surfaced by actually
asserting on response content end-to-end.

### 11.5 Deterministic vs. probabilistic controls (Phase 24)

New document `DETERMINISTIC_VS_PROBABILISTIC.md`, expanding SPEC.md
Section 6's existing principle into a full inventory of which current
components are deterministic (risk tiering, policy matching, the evidence
hash chain, approval resolution, RBAC checks, PII regex detection,
typosquat detection) versus probabilistic (hallucination detection, bias
probes, toxicity scanning, the supply-chain scanner's description-content
check) — plus the reasoning for why this distinction matters more for a
governance layer than ordinary application code (reproducibility, prompt-
injection surface, false assurance), and a contributor checklist for
classifying new checks correctly.

### 11.6 Real performance benchmarks (Phase 25)

New `scripts/run_benchmarks.py` and `BENCHMARKS.md`. Every number in
`BENCHMARKS.md` came from an actual execution of that script in this
environment (Python 3.14.6, macOS arm64, single-threaded, in-process) —
not an estimate. Benchmarked: `GuardrailsEngine.scan()` (clean and
PII-bearing text), `TrustScoreEngine.compute()`, `WhitePactRuntimeGateway.
evaluate()` (allowed, PII-redaction, and authority-DENY-short-circuit
paths), and an MCP `TOOL_DEFS` lookup. Explicitly documented what these
numbers do *not* measure: concurrency/load, database-backed paths,
MCP transport-level overhead, and LLM-provider-dependent modules
(hallucination detection, bias probes) — stated honestly rather than
implied as covered.

---

## 12. Closing the four flagged gaps: QUARANTINE, trust_state, dispatch wiring, policy persistence

Four specific gaps were called out by name against the already-built
governance core: `GovernanceDecision.QUARANTINE` was a real enum member
nothing ever produced; `AgentContext.trust_state` existed but nothing
populated it; `dispatch_tool()` was unchanged — no live MCP tool call
routed through `WhitePactRuntimeGateway`; and policy rules existed only
as in-code `PolicyRule`/`Policy` objects a call site constructed fresh
each time, never persisted or editable without a deploy. All four are
now closed, real, and tested.

### 12.1 QUARANTINE is now reachable

`governance/quarantine.py` adds `recent_violation_count()` — an async
query (`EvidenceRepository.count_recent()`, a `COUNT(*)` against the
persisted evidence chain, not a fetch-then-filter) counting a caller's
`DENY` decisions within a rolling window (default 60 minutes).
`WhitePactRuntimeGateway.evaluate()` gained an optional
`recent_violation_count: int = 0` parameter; at or above
`QUARANTINE_VIOLATION_THRESHOLD` (5), it returns `QUARANTINE` before
even checking authority — a quarantined identity is blocked even with a
valid authority grant, which is the point of the decision. The gateway
itself stays synchronous and DB-free (the async count is computed by
the caller and passed in as a plain int), preserving the "deterministic
controls, no I/O in the decision path" property the rest of the gateway
already had.

### 12.2 AgentContext.trust_state is populated and consulted

`governance/trust_integration.py`'s `enrich_agent_trust_state()` calls
the existing `TrustClient` (the same HTTP client the LangChain/
LangGraph/ADK trust-gate integrations already use — no second way to
call the Trust Index API) when an action names a `provider`/`model`.
`WhitePactRuntimeGateway` now consults the result: a known model
scoring below `LOW_TRUST_SCORE_THRESHOLD` (40.0) downgrades an
otherwise-`ALLOW` decision to `REQUIRE_APPROVAL`. Fails open on an
unknown/unscored model or a network error (never escalates), and never
overrides an existing `DENY`/`ALLOW_WITH_REDACTION` — only the plain
`ALLOW` path is affected, keeping this an additive signal, not a
change to any other decision branch's behavior.

### 12.3 Policy rules are persisted per-org

New `governance_policies` table (migration `0012`) and
`db/policy_repository.py`'s `PolicyRepository` — full CRUD (`add_rule`,
`remove_rule`, `reorder`), first-match-wins order preserved as a
`position` column. Exposed via `GET /api/governance/policy`,
`POST /api/governance/policy/rules`,
`DELETE /api/governance/policy/rules/{rule_id}`, and
`POST /api/governance/policy/reorder` — mutations are ADMIN-gated
(changing what future actions an org's own pipeline allows is a
materially different responsibility than viewing past decisions, same
reasoning `/api/governance/approvals/{id}/resolve` already used), reads
are ANALYST+, everything is org-isolated. A richer rule language
(OPA/Rego) remains explicitly out of scope, per `governance/policy.py`'s
own long-standing docstring — this closes the persistence gap, not the
expressiveness one, which was never claimed as a target for this phase.

### 12.4 The MCP dispatch path is wired — opt-in

`mcp/governance_integration.py`'s `apply_governance()` builds an
`ActionRequest`/`AuthorityContext` from an incoming MCP tool call,
enriches `trust_state` when the call's arguments name a provider+model,
queries the quarantine violation count, loads the org's persisted
`Policy`, evaluates, records evidence, and — on `REQUIRE_APPROVAL` —
queues a real `ApprovalRequest` instead of executing.
`DENY`/`QUARANTINE` block execution outright and return a structured
error instead of the tool's normal response;
`ALLOW_WITH_REDACTION` substitutes the redacted arguments before
`dispatch_tool()` ever sees the originals.

**Deliberately opt-in**: `Settings.mcp_governance_enabled` defaults to
`False`. Turning this on for an already-running hosted deployment is a
real behavior change — a call that used to always execute can now come
back `DENY`/`QUARANTINE`/queued-for-approval, and PII-bearing arguments
can get silently redacted before the underlying tool sees them. Making
that the silent default for existing installs would violate this
project's own backward-compatibility rule; making it opt-in instead
means the gap is genuinely closed (the wiring exists, is real, and is
tested end-to-end) without breaking anyone who hasn't asked for it. Only
applies to org-scoped calls over Streamable HTTP/SSE — the self-hosted
stdio transport has no organizational identity to build an
`AuthorityContext`/`Policy` against and is unaffected either way,
regardless of the flag.

`AgentContext.agent_id` is deliberately set to the caller's API key ID
for MCP-dispatched calls, not left as the dataclass's random per-call
default — quarantine tracking needs a *stable* identity across repeated
calls from the same key to accumulate a violation count against; a
fresh random UUID every call would make `recent_violation_count()`
never see more than zero.

### 12.5 A real bug found while writing this section's tests

Writing `tests/test_governance_quarantine.py` and
`tests/test_mcp_governance_dispatch.py` required computing risk tier
before the authority check (so the `QUARANTINE` short-circuit has a
`risk_tier` to attach to its own result) — which changed
`test_governance_core.py::test_risk_tier_none_on_authority_denial`'s
previously-documented invariant ("an ungranted action never reaches
risk classification"). Updated that test to assert the new, more useful
behavior (a denied action's evidence now records what risk tier it
would have been) rather than silently letting the assertion rot or
reverting a deliberate improvement — consistent with the standing rule
that a functional change updates its own tests in the same commit, not
a follow-up.

### 12.6 Two more gaps closed the same day, plus what's still genuinely out of scope

Two items this section originally listed as open gaps were closed
before this document's first version was even committed:

- **Webhook notification on a dispatch-path `REQUIRE_APPROVAL`** —
  `_build_http_app()` now constructs its own `WebhookManager` (wired to
  `WebhookConfigRepository`/`WebhookDeliveryRepository`, configs loaded
  and the retry worker started/stopped in the app's lifespan) when
  `mcp_governance_enabled` is on, and passes it into
  `ApprovalRepository.create()`'s `webhook_manager` parameter — the
  hosted MCP transport previously had no webhook subsystem at all.
  Tested end-to-end: `test_mcp_governance_dispatch.py::
  TestRequireApprovalFiresWebhook` registers a real webhook, makes a
  governed call that resolves to `REQUIRE_APPROVAL`, and asserts the
  webhook's HTTP delivery actually fired (via a captured
  `WebhookManager` instance and a respx-mocked delivery endpoint).
- **Graceful degradation on an `EvidenceRepository.record()` failure**
  — now fails *closed*: an exception during evidence persistence is
  caught, logged, and the call is blocked with a
  `governance_evidence_unavailable` error instead of either crashing
  with an unhandled exception or (worse) silently letting the action
  proceed with no audit record. Deliberately asymmetric with the Trust
  Index lookup's fail-*open* behavior (Section 12.2) — an unreachable
  trust check shouldn't block routine calls, but an unrecorded decision
  always should, since evidence is this platform's entire audit-trail
  guarantee. Tested — `test_mcp_governance_dispatch.py::
  TestEvidenceWriteFailsClosed` monkeypatches `EvidenceRepository.record`
  to raise and confirms the underlying tool never runs.

**Still genuinely out of scope**: a richer policy rule language
(OPA/Rego) — confirmed as a deliberate non-goal, not revisited, after
asking the user directly whether to build it; and governing the
self-hosted stdio transport at all, which has no organizational
identity to evaluate against by design.

---

## 13. What is explicitly *not* claimed by this migration

Per the standing rule against fabricating implementation status:

- `responsibleai.dev` (3 references in docs) is not a domain this
  project has ever deployed anything to. This migration did not
  register a domain itself — that requires a real purchase and DNS
  control no session can perform. **Update, 2026-08-17**: the founder
  registered `whitepact.com` directly and wired it to the hosted
  dashboard the same day — `A` record (apex) and `CNAME` (`www`) added
  at Namecheap per Render's custom-domain instructions, both verified
  by Render, TLS certificate issued. Confirmed live by this session via
  a real HTTPS request to `https://whitepact.com` (200 response,
  correct CSP/HSTS headers, `x-api-version: 1.2.3` matching this
  deployment) — not just trusting the Render dashboard's own status
  badge. `https://responsibleai-dashboard.onrender.com` keeps resolving
  to the identical service, unchanged. One correction to the plan
  stated here previously: this app has **no cookie-domain
  configuration to update** — auth is bearer-token-based, not
  cookie-session-based (`Settings.allowed_origins` is the only
  domain-relevant setting, and it's an environment variable, not a
  hardcoded value in this repo — the founder sets it at deploy time,
  not something a doc sweep touches). Docs naming
  `responsibleai-dashboard.onrender.com` as the canonical URL have been
  updated to `whitepact.com` where safe to (`DEPLOY_RUNBOOK.md`,
  `DEFINITION_OF_DONE.md`, `CHANGELOG.md`, `VERSION_ROADMAP.md`) —
  `PRIVACY_POLICY.md`/`SLA.md`/`TERMS_OF_SERVICE.md` deliberately left
  untouched, since they name the Service's address as part of a legal
  notice and that's the founder's call, not a mechanical doc-sweep
  edit. `whitepact-mcp-http.onrender.com` (the separate MCP server
  deployment) is untouched by any of this — it's a different service,
  not affected by today's DNS work.
- No claim is made here that the MCP server identity change, the
  resource-URI dual-scheme serving, or the env-var precedence logic are
  implemented yet — Sections 5 and 6 describe the design; the code
  changes are separate, testable units of work that follow this
  document, each verified against the full test suite before being
  considered done.

---

## 14. Backward compatibility timeline

| Version | State |
|---|---|
| **v1.2.0** (current, shipped) | `responsibleai`/`rai-governance-platform`/`RAI_*`/`responsibleai-mcp`/`rai://` only. |
| **v2.0.0** (this migration) | `whitepact` package/CLI/env-prefix/MCP-identity/resource-scheme introduced as preferred, additive. `/mcp` (Streamable HTTP) introduced alongside the existing `/sse`+`/messages/` (HTTP+SSE) transport, unmodified. Every v1.2.0 name and endpoint keeps working identically, with deprecation warnings (stderr/logs, never stdout on stdio transport) where a legacy name is actually used. |
| **v2.x** (subsequent minors) | New feature development targets `whitepact` naming primarily; legacy names remain supported, unchanged. |
| **v3.0.0** (future major, not scheduled) | `responsibleai` import alias, `RAI_*` env vars, `responsibleai-mcp` console scripts, and `rai://` resource URIs may be removed, only after a full v2.x cycle of visible deprecation warnings and only if usage telemetry/issue reports suggest it's safe to do so. No specific date is committed here — per the rule against inventing commitments the project can't back.

### 13.1 CI requirements review (Phase 28)

Read directly from `.github/workflows/` and the live repository, not
restated from memory:

- **`ci.yml`** — `test` job matrix on Python 3.11/3.12: `ruff check`,
  `mypy src/responsibleai`, `pip-audit` (one documented, justified
  ignore: `PYSEC-2026-597`, an nltk path-traversal CVE not reachable by
  this codebase's one hardcoded `nltk.download()` call), then the full
  suite with `--cov-fail-under=80` (currently running at 85%, so real
  margin exists, not a threshold sitting exactly at the line). `build`
  job compiles the wheel/sdist, generates a CycloneDX SBOM, uploads
  both as artifacts. `helm-lint` job lints and template-renders the
  Helm chart. All three ran and passed on every push this session made.
- **`dependency-review.yml`** — gates pull requests on new/changed
  dependencies' licenses and severity, distinct from `pip-audit`'s
  scan of what's already installed.
- **`publish.yml`** — tag-triggered PyPI publish with Sigstore build
  provenance attestation and automated GitHub Release creation
  (Phases 15-16).
- **mypy scope**: only `src/responsibleai`, not `tests/` or
  `src/biasbuster`/`src/privacylabel` — consistent with this session's
  own local verification commands throughout, not a new gap introduced
  here, but worth stating plainly rather than implying full-repo type
  coverage.

**Real gap found, then closed the same day**: `gh api
repos/Guruprasath-Annadurai/Whitepact/branches/main/protection` first
returned `404 Branch not protected` — `main` had no branch protection
rule at all. Fixed via `PUT .../branches/main/protection`: all four CI
checks (`Lint · Type-check · Test (3.11)`/`(3.12)`, `Build
distribution`, `Helm chart lint`) are now required status checks
(`strict: true` — a branch must be up to date before a PR merges),
force-pushes and branch deletion are disabled. `enforce_admins` is
deliberately left `false` — this session's own workflow (push directly
to `main`, then watch CI) and the founder's own solo-maintainer
workflow both still work exactly as before; what changes is that a
future contributor's *pull request* can no longer merge past a failing
or incomplete check. Verified after the fact by re-querying the same
API endpoint, not just trusting the `PUT` response.

### 14.1 Discipline audit (Phases 26-27)

Backward compatibility here is ongoing discipline enforced by every
phase's own tests, not a one-time deliverable — this is a checkpoint
audit against real, currently-checked-out source, not a re-statement of
intent:

- **CLI entry points** — all four legacy names
  (`biasbuster`/`responsibleai`/`responsibleai-mcp`/
  `responsibleai-mcp-http`) still present in `pyproject.toml`'s
  `[project.scripts]`, pointing at the identical entry-point functions
  as their `whitepact*` preferred counterparts. Verified by direct
  read, not memory.
- **Env var precedence** — `Settings.settings_customise_sources`
  still gives `WHITEPACT_*` priority over `RAI_*` per Section 5's rule;
  `warn_deprecated_env_vars()` still fires the stderr-only
  (never-stdout) deprecation warning when a legacy name is what
  actually resolved a setting.
- **Version sync** — `pyproject.toml`'s `version` and
  `responsibleai/__init__.py`'s `__version__` both read `1.2.0`,
  enforced by `tests/test_whitepact_alias.py`'s
  `test_matches_pyproject_version` (not just eyeballed here).
- **MCP resource dual-scheme** — `rai://` URIs still served alongside
  `whitepact://`; neither this batch of work nor the gap-closure phase
  (Section 12) touched `mcp/resources.py`.
- **New work in this batch stayed additive** — the four gap closures
  (Section 12) added new tables/columns/endpoints/parameters; none
  renamed or removed an existing field, endpoint, or config option.
  The one genuine behavior-affecting addition
  (`Settings.mcp_governance_enabled`) is opt-in, default `False`, per
  Section 12.4 — the one place this phase deliberately chose "opt-in
  toggle" over "purely additive," and said so plainly rather than
  understating it as risk-free.
- **No global replace occurred** — `git grep -c "responsibleai\."` and
  `git grep -c "RAI_"` counts were not driven toward zero by this
  phase; every rename in this document remains alias-based, not a
  find-and-replace.

---

## 15. What this document does not cover

Docker/Helm/CLI/package/env-var/MCP-identity/transport migration, plus
now the runtime governance core through all six of its phases so
far — the gateway itself (Section 8), risk-tiered routing
(Section 8.1), a first policy engine (Section 8.2), evidence
persistence (Section 8.3), a first approval workflow (Section 8.4),
and the MCP Trust/Supply-Chain Scanner (Section 8.5) — MCP OAuth/OIDC
authorization (Section 7.2), structured tool-output contracts
(Section 7.3), and HA deployment defaults for the hosted MCP transport
(Section 9.1). Section 12 closes four of what were previously listed
here as gaps — `QUARANTINE` production, `AgentContext.trust_state`
population/consultation, persisted policy rules, and wiring the
governance gateway into the live MCP tool-dispatch path (opt-in via
`Settings.mcp_governance_enabled`) — see that section for what's real
now versus what within it is still deliberately unbuilt (webhook
notification on a dispatch-path `REQUIRE_APPROVAL`, graceful
degradation on an evidence-write failure, governing the stdio
transport). What remains genuinely out of scope here: a **richer
policy rule language** than plain risk-tier/action-type/target matching
(OPA/Rego or similar, if ever needed — a deliberate, stated non-goal
of `governance/policy.py`, not an oversight), a **richer approval
lifecycle** than `PENDING -> APPROVED`/`DENIED` (expiry/timeout,
multi-approver quorum, delegation-chain approval), **evidence export
beyond JSON**, **true multi-region HA** (Section 9.1 is
within-region only — no cross-region replication, no global load
balancer, that's infrastructure the deployer builds, see
`DEPLOY_RUNBOOK.md`), **`/metrics` on the MCP transport** (it has
none today, so `mcp.podAnnotations` defaults to no Prometheus scrape
config rather than a wrong one), and **the supply-chain scanner
actually connecting to a remote MCP server** (it analyzes a
caller-supplied manifest only — full Unicode TR39 confusables
detection and publisher/domain identity verification are also
undesigned). Section 10 adds supply chain security (Phase 15),
release engineering (Phase 16), MCP registry readiness (Phase 17),
and open source governance (Phase 18) — but explicitly does not
include: a **pinned dependency lockfile** (range constraints only),
**Docker image publishing** (no CI workflow builds/pushes the image
Helm/compose reference), **actually submitting to the MCP registry**
(namespace ownership needs a GitHub OAuth device flow this session
has no access to, and `1.2.0` isn't on PyPI yet — see Section 10.2's
finding), and a **distributed maintainer model** (`GOVERNANCE.md`
states plainly this is founder-led, not a claim of a team that
doesn't exist). These are tracked separately and are
not blocked on this document — they can proceed against the current
`responsibleai` code paths and be renamed in step with whichever phase
above actually executes the package migration.

---

## 16. Closing the 14-item gap list opened by Section 12's report (2026-08-17)

Section 12's gap-closure work produced a follow-up 14-item list, tracked
outside this document until now. All 14 are closed as of this date;
`MACHINE_AUTHORITY_V1.md` and `ENFORCEMENT_BOUNDARY.md` are the
authoritative, itemized record of what each one covers and where it
honestly stops — this section is the pointer, not a restatement:

- **Reason codes, policy versioning, approval expiry, authority value
  limits/target patterns, the fail-closed test, `whitepact_*`
  observability, the MCP Upstream Gateway, resume-after-approval, the
  risk router, multi-approver quorum, delegation chains, and the
  upstream discovery endpoint** — the twelve technical items, verified
  in this session by direct code/test inspection (not restated from
  memory): `format_reason()` has 31 live call sites and no bare
  `reason_codes=["..."]` literals remain; `Policy.version` is a real
  monotonic int; `ApprovalRequest.is_expired`/`ApprovalExpiredError`
  are enforced in `ApprovalRepository.consume()`;
  `governance/upstream_executor.py` and `governance/upstream_discovery.py`
  sit at 96-98% test coverage; `tests/test_approval_execution_binding.py`
  and `tests/test_mcp_governance_dispatch.py` both assert fail-closed
  behavior on subsystem failure.
- **The SOC2-alternative writeup and the CAIQ v4.0.3 questionnaire** —
  `compliance/SOC2_ALTERNATIVE_PATH.md` and
  `compliance/CAIQ_SELF_ASSESSMENT.md` (+ the completed `.xlsx`) exist
  as real files, not claims.
- **Real performance benchmarks, extended to the v3 authority layer** —
  `BENCHMARKS.md`/`scripts/run_benchmarks.py` now cover
  `validate_attenuation`, `constraint_violation`,
  `check_composition_violation`, `scan_memory_write`,
  `build_evidence_bundle`/`verify_evidence_bundle`, and the gateway with
  an Autonomy Budget engaged — every number measured, not estimated.
- **Concurrency/race tests** (`tests/test_concurrency.py`) — verified,
  under real `asyncio.gather()` concurrency, that
  `ApprovalRepository.consume()`'s conditional UPDATE,
  `resolve()`'s unique-vote constraint, and `EvidenceRepository`'s
  hash-chain lock all hold as claimed. Also found and documented a
  real, reliably-reproducing gap: Autonomy Budget's
  count-then-decide-then-record window has no lock, and a concurrent
  burst can fully bypass the configured cap (10 of 10 concurrent calls
  allowed against a budget of 3) — recorded in
  `ENFORCEMENT_BOUNDARY.md`'s Autonomy Budget entry, not fixed in that
  pass; still open as of this writing.
- **The reference enterprise demo**
  (`examples/08_whitepact_enterprise_scenario.py`) — walks all eight
  machine-authority invariants through one real, live scenario against
  real code, no API keys required.
- **Identity Bridge adapters** (`integrations/identity_bridge.py`) —
  claims-mapping for Entra ID, Google Workspace, Okta, and AWS
  (Cognito/IAM Identity Center), verified against each provider's
  publicly documented token shape (not a live tenant of any of them,
  which this project has no access to) — see the module's own
  docstring and `MACHINE_AUTHORITY_V1.md`'s Identity Bridge section for
  the three named gaps (Entra group-name resolution, Google Workspace
  group membership, AWS's non-JWT SigV4 path — none implemented, none
  claimed).

**Domain**: `whitepact.com` was registered by the founder on 2026-08-17
(confirmed by this session via a live DNS lookup — real nameservers, a
real `A` record). It is not yet wired to the hosted instance; see
Section 13's updated bullet for exactly what that still requires and
why it needs the founder's own Render/Namecheap account access.

## 17. Tool Trust Network and Execution Permit v2 (Authority Everywhere Phases 8-9, 2026-08-19)

The first implementation phases of `docs/architecture/AUTHORITY_EVERYWHERE.md`
(the target-architecture doc, itself Phases 1-2 of that plan) to touch
real code — chosen ahead of strict numeric order per that document's
own Phase 2 verdict, prioritizing revenue-relevant destination-trust and
permit-integrity work over further principal-identity generalization
(which already has a working enterprise-grade OIDC/SAML/MFA
implementation).

- **Tool Trust Network** (`governance/tool_trust.py`,
  `db/tool_trust_repository.py`, migration `0024`) — see SPEC.md
  Section 4.2 for the full design. In one sentence: a deterministic
  0-100 trust score per registered upstream MCP server, computed from
  the existing supply-chain scanner's findings plus incident history,
  with an audited admin-override escape hatch, gating calls to a
  `BLOCKED` server before governance is even consulted
  (`mcp/upstream_dispatch.py`).
- **Execution Permit v2** (`governance/execution.py`,
  `governance/upstream_executor.py`) — `ExecutionAuthorization` gained
  an optional `target_fingerprint`, closing a real gap: `action_digest`
  never captured what an upstream target string (`server_id::tool_name`)
  currently *resolves to* (URL, enabled state, credential presence), so
  a server's registration drifting between decision and execution
  couldn't previously be caught by the permit itself.
  `AuthorizationTargetDriftError` refuses execution on a mismatch. The
  drift check runs as an explicit step after `_validate_authorization()`
  and after the target is resolved — deliberately not folded into
  `_validate_authorization()` itself, since that function's four
  existing checks must keep their original precedence over a
  target-specific check that needs a lookup the function doesn't do.
  `InternalToolExecutor` is unaffected (no external target to resolve).
- Naming: `ReasonCode.UNTRUSTED_MCP_SERVER` was already reserved in
  `reason_codes.py` from earlier work and unused until this phase — no
  new reason code was needed.
- Not built in this phase (explicitly, per the plan's own phase-gating):
  JIT Credential Broker (Phase 10), Causal Influence Firewall
  generalization (Phase 7), risk-tier modulation by trust tier (a
  natural extension of the Tool Trust gate, deferred as a separate
  future increment), any UI page for viewing/managing trust scores
  (REST API only).
- Verification: 24 new tests (`tests/test_tool_trust.py`) plus the full
  existing `test_upstream_gateway.py`/`test_executor_bypass_invariant.py`
  suites re-run clean (69 passed together); full repo suite 2332 passed;
  `mypy`/`ruff` clean on every touched file.

## 18. JIT Credential Broker (Authority Everywhere Phase 10, 2026-08-19)

- **JIT Credential Broker** (`governance/jit_credential.py`,
  `db/credential_issuance_repository.py`, migration `0025`) — see
  SPEC.md Section 3.4 (immediately after the Execution Permit v2 entry)
  for the full design. In one sentence: `UpstreamMCPExecutor` no longer
  reads `UpstreamServer.auth_token` directly; it must obtain a
  single-use, time-boxed `JITCredential` bound to the exact,
  already-validated `ExecutionAuthorization` for this call, with every
  issuance and consumption recorded to an audit trail that never stores
  the secret value itself.
- **Honest scope, stated plainly** (also in the module's own
  docstring, since this is easy to overclaim): this is not OAuth token
  exchange and does not ask any upstream server to mint a new, narrower
  credential — most third-party MCP servers have no such protocol.
  What's real: the standing credential an org already configured is no
  longer handed to the executor wholesale; access to it is mediated,
  time-boxed (default 15s, capped by the permit's own remaining TTL —
  `min(authorization.expires_at, now + ttl_seconds)`), single-use, and
  logged. That is a genuine narrowing of "how" the credential is
  accessed, not a claim that the credential itself became scoped-down.
- A real ordering bug was caught and fixed during development, not
  after: the first implementation marked the `ExecutionAuthorization`
  consumed *before* calling `issue_jit_credential()`, which itself
  correctly refuses to issue against an already-consumed authorization
  — a self-inflicted contradiction caught by the existing
  `test_upstream_gateway.py` suite failing immediately. Fixed by
  issuing the credential first, then marking the authorization
  consumed. `tests/test_jit_credential.py` has a named regression test
  for this exact ordering.
- Not built in this phase: real upstream token-exchange support (would
  require a specific upstream server protocol to exist first — no
  speculative groundwork laid for one); any change to how a standing
  credential is originally registered (`UpstreamServerRegisterRequest`
  is unchanged); a UI for viewing the credential-issuance audit log
  (data model and persistence only, per this project's established
  "REST first, UI later if warranted" pattern for governance internals).
- Verification: 17 new tests (`tests/test_jit_credential.py`), including
  a real end-to-end REST round trip (real in-process second MCP server,
  real credential, real authenticated call) proving both that the
  credential actually authenticates the proxied call and that the
  resulting audit row never contains the token value. Full existing
  `test_upstream_gateway.py`/`test_tool_trust.py`/
  `test_executor_bypass_invariant.py` suites re-run clean (86 passed
  together); full repo suite 2349 passed; `mypy`/`ruff` clean on every
  touched file.

## 19. Causal Influence Firewall (Authority Everywhere Phase 7, 2026-08-19)

- **Causal Influence Firewall** (`governance/causal_influence.py`) —
  see SPEC.md Section 4.3 for the full design. In one sentence:
  generalizes `governance/memory_firewall.py`'s persistent-memory-only
  injection-pattern scan to any upstream content a caller declares
  causally shaped the current action (a prior tool's output, a
  sub-agent's result, external content) via a reserved `_provenance`
  argument key — the same argument-driven convention
  `AuthorityContext.constraints`' `memory_scope` already established.
- **`memory_firewall.py` absorbed, not replaced** — Phase 0's own
  classification of that module. Its public API
  (`scan_memory_write`/`MemoryFirewallResult`) is byte-for-byte
  unchanged; the pattern table and matching logic moved to
  `causal_influence.py` as the canonical location, and
  `memory_firewall.py` now delegates. Every existing caller
  (`mcp/tools.py`'s `rai_memory_write_check`, `gateway.py`'s
  memory-write hard-block check) keeps working with zero code changes
  on their end — proven by the full pre-existing
  `test_memory_firewall.py` suite passing unmodified.
- **Two distinct signals, not one** — a matched injection pattern in
  any provenance entry is a hard `DENY`
  (`ReasonCode.CAUSAL_INFLUENCE_VIOLATION`); untrusted/unknown
  provenance with no pattern match is a softer, non-blocking,
  evidence-visible marker (`ReasonCode.CAUSAL_INFLUENCE_UNTRUSTED_SOURCE`)
  attached to whatever decision the action otherwise receives —
  deliberately not collapsed into one signal, and deliberately not
  escalating risk tier or blocking on untrusted-influence alone in this
  first increment, matching the Tool Trust Network's own bounded-scope
  precedent (Section 17).
- New MCP tool `rai_causal_influence_check` (30th tool — every
  hardcoded tool-count assertion across the test suite and `server.json`
  updated from 29 to 30: `test_mcp_server.py`, `test_mcp_http_transport.py`,
  `test_mcp_oauth.py`, `test_server_json.py`, `test_governance_risk.py`).
- **Honestly scoped, stated in the module's own docstring**: this
  platform cannot observe, on its own, what upstream content actually
  influenced a given tool call — there is no runtime hook to intercept
  an LLM's context window. Provenance must be declared by the caller;
  not a claim of automatic taint tracking.
- Not built in this phase: risk-tier modulation by untrusted-influence
  presence (deferred, same reasoning as Tool Trust's own deferred
  increment); any UI for provenance/causal-influence data (REST/MCP
  tool only); real taint *propagation* across multiple hops (a caller
  declares provenance once, per action — chaining "this action's output
  becomes the next action's provenance" is the caller's own
  responsibility, not tracked automatically).
- Verification: 26 new tests (`tests/test_causal_influence.py`) plus
  the full pre-existing `test_memory_firewall.py` suite (12 tests)
  re-run clean and unmodified; full repo suite 2375 passed; `mypy`/`ruff`
  clean on every touched file.

## 20. Outcome Observation, Reconciliation, and Attestation (Authority Everywhere Phases 12-14, 2026-08-20)

The final three stages of the Authority Everywhere lifecycle doc's
canonical pipeline (`docs/architecture/AUTHORITY_EVERYWHERE.md`) that
had no implementation at all — closes the honestly-stated gap
`governance/evidence.py`'s own module docstring names: "this package
has no visibility into whether/how an allowed action was actually
executed."

- **Outcome Observation** (`governance/outcome.py`,
  `db/outcome_repository.py`, migration `0026`) — `OutcomeRecord`
  (`SUCCEEDED`/`FAILED`/`ERRORED`, optional minimal `result_summary`,
  never a raw result dump) linked to its authorizing `EvidenceRecord`.
  Auto-recorded, fail-open, at every governed-execution call site:
  `apply_governance()`, `resume_approval()` (both
  `mcp/governance_integration.py`), and `apply_upstream_governance()`
  (`mcp/upstream_dispatch.py`) — `_record_evidence()` in the latter now
  returns the persisted `EvidenceRecord` (was previously a bare `bool`)
  so callers can link an outcome to it via `evidence.evidence_id`. A
  manual-reporting REST endpoint
  (`POST /api/governance/evidence/{id}/outcome`) covers callers whose
  execution happens outside a governed dispatch call entirely.
- **Reconciliation** (`governance/reconciliation.py`) —
  `reconcile_outcome()` is deliberately narrower than the name might
  suggest: the strongest mutation invariant is already enforced
  *synchronously* before execution
  (`ExecutionAuthorization.matches_action()`/`check_target_fingerprint()`
  from Phase 9) — this module doesn't re-check that. What it adds:
  detecting when a decision that authorized execution never got an
  outcome reported at all (`MISSING_OUTCOME` — a real anomaly signal
  nothing else in this codebase currently surfaces), a defensive
  action-id-mismatch check, and correctly excluding
  DENY/QUARANTINE/REQUIRE_APPROVAL from ever being flagged as missing
  an outcome (`NOT_APPLICABLE` — nothing executed for those).
- **Attestation** (`governance/attestation.py`,
  `GET /api/governance/evidence/{id}/attestation`) — packages one
  evidence entry's decision + outcome + reconciliation status into one
  exportable record. **Not cryptographically signed**, stated in the
  module's own docstring: the identical "don't invent cryptography for
  a threat model that doesn't exist yet" reasoning `execution.py`
  already established for `ExecutionAuthorization` (Section 8),
  generalized — an automated per-action signing key sitting in the
  server process is a real secret-management burden with no
  infrastructure built for it yet, and integrity today is by linkage to
  the already-real `EvidenceRecord` hash chain instead, made explicit in
  every response via an `integrity_note` field rather than left
  implicit or overclaimed.
- **Two real, non-obvious test-isolation bugs found and fixed while
  building this phase's tests** (recorded here since they're a real
  gotcha, not this feature's own logic bug): (1) `dashboard/app.py`
  imports `create_engine` at module load time
  (`from responsibleai.db import create_engine`), binding an
  independent name into its own namespace — monkeypatching
  `responsibleai.db.create_engine` alone (the pattern
  `test_mcp_governance_dispatch.py` established, which works because
  `mcp/server.py` imports it lazily *inside* `_build_http_app()`) never
  reaches that already-bound reference, so a test running both a
  governed-MCP app and the dashboard app against "the same" engine
  silently got two disconnected empty databases instead. (2)
  `dashboard/config.get_settings()` lazily caches a module-level
  `_settings` singleton — patching an already-imported `settings`
  object works only as long as nothing resets that cache in between; a
  test combining `_build_http_app()` (which calls `get_settings()`
  fresh) with the dashboard app needs to pin
  `config_module._settings = settings` explicitly, not just patch
  attributes on the imported name, or full-suite run order can silently
  desync the two. Both fixed in
  `tests/test_outcome_reconciliation_attestation.py`'s `governed_mcp`
  fixture; documented here in case a future test hits the same class of
  bug.
- Not built in this phase: outcome-content verification (checking that
  a tool's result plausibly matches its risk tier or arguments — real,
  separate, per-tool-domain work); any UI for outcome/attestation data
  (REST only); published external chain-checkpoint commitments (the
  concrete next step that would make attestation verification meaningful
  even against a fully compromised DB, not attempted here).
- Verification: 20 new tests
  (`tests/test_outcome_reconciliation_attestation.py`), including a
  real MCP protocol round trip proving auto-recording end-to-end and a
  real REST round trip proving the attestation/manual-report endpoints;
  full repo suite 2395 passed (up from 2375, net of the 20 new plus
  migration-count assertion updates); `mypy`/`ruff` clean on every
  touched file.

## 21. Verified Principal (Authority Everywhere Phase 3, 2026-08-20)

The first Authority Everywhere phase to touch a lifecycle stage
unrelated to what Phases 7-14 already built: `docs/architecture/AUTHORITY_EVERYWHERE.md`'s
row 1 ("Verified Principal") gap — `auth/oidc.py`/`auth/saml.py` verify
*human* identities via an enterprise IdP, with no path for a *non-human*
principal (a service account, or another organization's attested
agent) to present its own cryptographic credential.

- **VC-JWT verification** (`auth/verifiable_credential.py`) —
  `VerifiableCredentialProvider.validate_presentation()` reuses
  `auth/oidc.py`'s exact `AsyncJWKSClient` / `kid`-resolution /
  private-key-rejection / weak-RSA-key-rejection machinery
  (`validate_rsa_key_size`), generalized from one configured OIDC
  issuer to an admin-configured trusted-issuer allowlist
  (`Settings.vc_trusted_issuers`) — a credential's issuer is just
  another entity publishing a JWKS at
  `<issuer>/.well-known/jwks.json`. An unlisted `iss` is rejected
  before any network call or crypto verification happens. Deliberately
  scoped to JWT-VC only: no DID resolution (`did:key`/`did:web`), no
  JSON-LD proof formats, no revocation-list checking, and not the full
  OpenID4VP presentation-exchange protocol — none of those libraries
  are dependencies of this codebase today, and each is real, separate
  work. `looks_like_vc_jwt()` is an unverified peek at a token's
  payload used only to decide *which* verifier to try (does it carry a
  `vc` claim) — mirrors the same "peek header for `kid`, verify
  everything afterward" posture `OIDCProvider.validate_token()` already
  uses; nothing about routing is ever trusted as verification.
- **Governance-layer representation** (`governance/principal.py`) —
  `PrincipalClaim` is deliberately a different object from
  `VerifiableCredentialClaims`, mirroring the existing `auth/*` vs.
  `governance/*` split in this codebase: it discards the raw JWT
  payload and keeps only `claim_keys` (field names the presented
  credential's `credentialSubject` carried, never their values) — same
  "never raw values" discipline `EvidenceRecord.argument_keys` and
  `OutcomeRecord.result_summary` already apply, chosen because this
  record may be queried long after the credential itself expires.
  `IdentityContext.from_principal_claim()` (`governance/models.py`)
  produces `kind="vc"`, a new value in the same vocabulary
  `from_org_context()` already established — no existing kind changes.
  Confirmed no existing `governance/*.py` file imports from `auth/*`
  before adding this one import (`governance/models.py` -> `governance/principal.py`,
  both governance-layer), keeping the category boundary real rather
  than just asserted.
- **DB layer** (`db/principal_repository.py`, migration `0027`) — an
  append-only `verified_principals` audit log, the same role
  `OutcomeRepository` plays for execution outcomes: by the time a
  `PrincipalClaim` exists, the credential is already fully
  cryptographically verified, so this table is an audit trail, not a
  security gate, and its write is fail-open (logged via
  `_logger.exception(...)`, never blocks an otherwise-valid
  authentication).
- **Wiring** (`mcp/server.py`) — `_resolve_vc_context()` sits alongside
  the existing `_resolve_oidc_context()` in `_authenticate()`, tried
  second (after OIDC, before falling through to a static API key), and
  produces the same `OrgContext` shape so every downstream governance
  call site (`IdentityContext.from_org_context`, RBAC, plan/quota
  gating, rate limiting) works completely unchanged — `key_id` is
  prefixed `vc:` rather than `oidc:`, the same disambiguation
  `_resolve_oidc_context` already uses. `Settings.vc_trusted_issuers`
  empty (the default) disables the entire path, same "unset config ->
  feature off" posture the OIDC provider already uses. Scoped to the
  hosted MCP server (`mcp/server.py`) only in this phase, not the
  dashboard REST API's own OIDC login path
  (`dashboard/app.py`) — the MCP surface is the actual agent-facing
  adapter (Phase 1's category lock names this as *the* adapter
  boundary), while the dashboard REST API is a human/org login surface
  where "non-human principal" doesn't apply; wiring it there too is
  possible but out of scope here.
- Not built in this phase: DID resolution, JSON-LD proof formats,
  OpenID4VP presentation exchange, revocation-list checking (see
  `auth/verifiable_credential.py`'s module docstring for the full
  list), dashboard REST API wiring, and any verification-method-aware
  branching in `governance/ceiling.py`/`governance/delegation.py` (a
  verified principal resolves to a plain `identity_id` string today,
  identical to an API-key or OIDC identity for delegation/ceiling
  purposes — whether it *should* get a different authority ceiling is
  a real, separate policy question, not answered here).
- Verification: 21 new tests across
  `tests/test_verifiable_credential.py` (unit: JWKS/JWT verification
  paths, weak-key and private-key rejection reusing the existing
  `test_crypto_policy.py` pattern, `PrincipalClaim` construction,
  `IdentityContext.from_principal_claim`) and
  `tests/test_mcp_verified_principal.py` (a real MCP protocol round
  trip authenticating via a VC-JWT bearer token, proving the audit
  trail is written, untrusted-issuer rejection, and that a plain
  OIDC-shaped JWT is never misrouted to the VC path); full repo suite
  2416 passed (up from 2395); `mypy`/`ruff` clean on every touched
  file.

## 22. Intent Contract (Authority Everywhere Phase 4, 2026-08-20)

Closes `docs/architecture/AUTHORITY_EVERYWHERE.md`'s lifecycle row 2
gap: `ActionRequest` states what's being done, not what was *promised*
up front — nothing let an agent declare a goal and its bounds before
starting a task, so nothing could check "does this action still match
what this task was supposed to be," only "is this action individually
allowed" (the org-delegated-authority question §3.3/Phase 8 already
answers).

- **Domain model** (`governance/intent.py`) — `IntentContract` (`goal`,
  optional `max_value_usd`/`allowed_targets`/`denied_targets`/
  `allowed_action_types`, `valid_from`/`expires_at`).
  `intent_violation(action)` mirrors `AuthorityContext.constraint_violation()`'s
  exact ordering (denied -> allowed -> action-type -> value), deliberately
  reusing that convention rather than inventing a new one, and is checked
  independently — an agent's own declared intent is a narrower,
  per-task promise, distinct from what the *organization* delegated to
  its authority grant. New `ReasonCode.INTENT_VIOLATED`.
- **Gateway wiring** (`governance/gateway.py`) — `evaluate()` gained an
  optional `intent: IntentContract | None = None` parameter, checked
  immediately after the existing parent-authority attenuation check
  (step 0) and before `authority.permits()` (step 1) — a violation is a
  `DENY` before the org's own delegated-authority checks even run,
  following the exact same additive, backward-compatible pattern
  `parent_authority`/`workflow_rules`/`autonomy_budget` already
  established. No `intent` supplied (every caller before this existed)
  — skipped entirely, identical to prior behavior.
- **DB layer** (`db/intent_repository.py`, migration `0028`) —
  `IntentContractRepository.declare()`/`get_active_for_agent()`/`get()`.
  "Latest declared, still-active contract wins" per agent, the same
  resolution `DelegationRepository.get_latest_delegation()` already
  uses for "what does this identity currently hold" — a new
  declaration doesn't delete or overwrite an older one (both persist as
  an audit trail of what an agent committed to over time).
- **Dispatch-path wiring** (`mcp/governance_integration.py`) —
  `apply_governance()` fetches the calling agent's active contract (if
  `GovernanceServices.intent_repo` is configured) alongside the
  existing ceiling/workflow-rule/autonomy-budget fetches, and passes it
  into `gateway.evaluate()`. `mcp/server.py` wires
  `IntentContractRepository(_db_engine)` into `GovernanceServices`
  construction when `mcp_governance_enabled` is on.
- **REST endpoints** (`dashboard/app.py`) —
  `POST /api/governance/intent-contracts` (ANALYST+ — declaring intent
  only ever narrows what an agent can do, never expands it, unlike a
  delegation grant which is ADMIN+) and
  `GET /api/governance/intent-contracts/{agent_id}/active` (`200` with
  `has_active_contract: false` when none is declared or the latest has
  expired — a normal state, not an error).
- Not built in this phase: goal *understanding* (semantically checking
  an action's target/arguments against the free-text `goal` string —
  real, separate, model-assisted work); wiring into the dashboard's own
  human-login REST-driven governed operations (only the MCP dispatch
  path consults an `IntentContract` today, matching Phase 1's
  category-lock naming of the MCP adapter as the actual agent-facing
  surface); any verification-method-aware interaction with `ceiling.py`
  or `delegation.py` (an Intent Contract is an independent gate, not
  merged into either).
- Verification: 35 new tests across `tests/test_intent_contract.py`
  (unit: `is_active()`/`intent_violation()` branches, gateway wiring,
  DB repository), `tests/test_mcp_intent_contract.py` (a real MCP
  protocol round trip proving a declared contract blocks/allows a
  governed tool call, and that an expired contract stops being
  enforced), and a `TestIntentContractEndpoints` class added to
  `tests/test_governance_api.py` (declare, fetch active, cross-org
  isolation); full repo suite 2451 passed (up from 2416); `mypy`/`ruff`
  clean on every touched file.

## 23. Authority Passport (Authority Everywhere Phase 5, 2026-08-20)

Closes `docs/architecture/AUTHORITY_EVERYWHERE.md`'s lifecycle row 3
gap: `governance/ceiling.py`'s `OrgAuthorityCeiling` is a real subset
of a full portable credential, but it's an in-process object with no
export/issuance/revocation/verification story of its own. The Phase 2
naming-collision resolution reserved "Authority Passport" for this
concept specifically to avoid colliding with the already-shipped
`trust/passport.py` (`AIPassport` — a *model's* Trust Index
certification, unrelated to principal authority).

- **Domain model** (`governance/authority_passport.py`) —
  `AuthorityPassport`: a snapshot of a principal's authorized bounds at
  issuance, exported from either the org's current `OrgAuthorityCeiling`
  (`build_authority_passport_from_ceiling()`) or an active
  `DelegationRecord` (`build_authority_passport_from_delegation()`).
  Revocation (`revoked_at`/`revoked_by`/`revoke_reason`) is tracked on
  the passport itself, independent of its source — an org can revoke
  one exported passport without touching the underlying ceiling or
  delegation.
- **Verification without signing** — `verify_passport()` re-fetches the
  live source (the caller passes a freshly-fetched `ceiling` or
  `delegation` object) and compares every claimed field, returning
  `VALID`/`DRIFTED`/`SOURCE_NOT_FOUND`/`REVOKED`/`EXPIRED`. Same
  "integrity by linkage to an already-real, DB-backed source" pattern
  `attestation.py` established against `EvidenceRecord`'s hash chain,
  generalized to a ceiling/delegation row. **Deliberately not
  cryptographically signed** — identical reasoning to
  `attestation.py`/`execution.py`: no live signing-key infrastructure
  exists, and a forged passport would need the same DB write access
  that could also rewrite its own source row, so an in-process
  signature wouldn't verify anything a forger couldn't already fake.
- **DB layer** (`db/authority_passport_repository.py`, migration
  `0029`) — `issue()`/`get()`/`get_active_for_principal()`/`revoke()`.
  "Latest issued, still-active passport wins" per principal, matching
  `DelegationRepository`/`IntentContractRepository`'s own resolution.
  Index names `idx_ap_org`/`idx_ap_principal` — two candidate prefixes
  (`idx_gap_*`, then `idx_pass_*`) were already taken by
  `governance_approvals`' own indexes from migration `0011`, caught
  both times by the migration test suite (`sqlite3.OperationalError:
  index ... already exists`) during development, not left as a silent
  collision.
- **REST endpoints** (`dashboard/app.py`) —
  `POST /api/governance/authority-passports` (ADMIN+, same tier as a
  delegation grant since exporting a portable credential exports real
  usable authority, unlike Intent Contract's narrowing-only ANALYST+),
  `GET /api/governance/authority-passports/{id}` (fetches + verifies
  against the live source in one response), and
  `POST .../{id}/revoke` (ADMIN+).
- Not built in this phase: wiring a *presented* passport into
  `WhitePactRuntimeGateway.evaluate()`'s live per-call authority
  resolution as an alternative to the fresh ceiling/delegation lookup
  `mcp/governance_integration.py` already performs on every call —
  deciding how much to trust an externally-presented credential versus
  re-deriving authority fresh is real, separate integration work with
  its own threat model. `AuthorityPassport.to_authority_context()`
  exists and is tested, but nothing in the hot dispatch path calls it
  yet.
- Verification: 35 new tests across `tests/test_authority_passport.py`
  (unit: `is_active()`, both builder functions, all five
  `verify_passport()` branches, DB repository) and a
  `TestAuthorityPassportEndpoints` class added to
  `tests/test_governance_api.py` (issue from ceiling/delegation, role
  checks, drift detection after a live ceiling change, revocation,
  cross-org isolation); full repo suite 2486 passed (up from 2451);
  `mypy`/`ruff check`/`ruff format --check` clean on every touched
  file.

## 24. Delegation Graph as a first-class object (Authority Everywhere Phase 6, 2026-08-25)

Closes `docs/architecture/AUTHORITY_EVERYWHERE.md`'s lifecycle row 4
gap — already credited as "a working delegation graph today," this
phase packages it into something queryable independent of a single
decision, per the row's own framing, rather than rebuilding anything.

- **Domain model** (`governance/delegation_graph.py`) —
  `DelegationGraphNode` (recursive tree node: `identity_id`, its own
  current `DelegationRecord` if any, `children`) and `DelegationGraph`
  (the org-wide forest: `roots`, `all_identity_ids()`, `find()`,
  `to_dict()`). A snapshot at build time, not a live/cached view —
  matches every other authority-layer read in this codebase's
  "recompute, don't cache" posture.
- **Repository additions** (`db/delegation_repository.py`) —
  `get_org_graph(org_id)` (the full forest) and
  `get_descendants(org_id, identity_id)` (the public, read-only,
  forward-direction counterpart to `revoke_branch()`'s internal BFS).
  Both built from `_current_parent_map()`, which resolves each
  identity's *current* `get_latest_delegation()` rather than walking
  raw historical rows (`_direct_children()`, used internally by
  `revoke_branch()` for cascading revocation, keeps its existing
  historical-row behavior unchanged — a re-delegated identity showing
  up under its new parent only, not duplicated, is a correctness
  property only the read-path graph builder needs). Verified
  empirically with a real 3-level, 2-root tree, cascading revocation,
  and a re-delegation-under-a-new-parent scenario before writing the
  test suite.
- **REST endpoints** (`dashboard/app.py`) —
  `GET /api/governance/delegations/{identity_id}/descendants` and
  `GET /api/governance/delegations/graph` (both ANALYST+, matching the
  existing `.../chain` endpoint's tier — these are reads, not grants).
- Not built in this phase: no new invariant, no new migration, no
  change to `grant()`/`revoke_branch()`/`validate_attenuation()` — pure
  read-only export of state already reconstructable from the existing
  `governance_delegations` table.
- Verification: 18 new tests — `tests/test_delegation_org_graph.py` (13:
  node/graph unit tests, multi-level multi-root forest construction,
  empty-org, cascading-revocation reflection, re-delegation-under-new-
  parent) and 5 new cases appended to `TestDelegationEndpoints` in
  `tests/test_governance_api.py` (descendants of a multi-level tree,
  leaf-identity empty descendants, full-forest graph shape, empty-org
  graph, cross-org isolation); `mypy`/`ruff check`/`ruff format --check`
  clean on every touched file.
- **A real self-caught mistake during development, documented as a
  gotcha**: `tests/test_delegation_graph.py` already existed (31 tests,
  covering the *base* delegation graph from the original v3
  authority-layer work — `grant()`, attenuation enforcement,
  `get_authority_chain()`, `revoke_branch()`, `explain_authority()`).
  The first draft of this phase's new test file reused that exact
  filename without checking first, silently overwriting all 31
  original tests. Caught by comparing `pytest --collect-only` counts
  between this branch and `main` before committing (2502 collected vs.
  an expected 2533, not the 2515+18 math) rather than trusting the
  "N passed" summary alone — a full-suite pass count going *down*
  after *adding* tests is the tell. Fixed by restoring the original
  file from git history (`git show HEAD:tests/test_delegation_graph.py`)
  and placing the new tests in `tests/test_delegation_org_graph.py`
  instead. Recorded here as a standing reminder: always check whether
  a test filename is already taken before writing to it, the same
  "Read before Write" discipline this whole codebase already expects
  for source files.
