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
| `responsibleai.dev` | 3 | A domain referenced in docs that has never been registered/deployed — see Section 10 |

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
committed here, consistent with Section 11's timeline for every other
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

---

## 10. What is explicitly *not* claimed by this migration

Per the standing rule against fabricating implementation status:

- `responsibleai.dev` (3 references in docs) is not a domain this
  project has ever deployed anything to. This migration does not
  register `whitepact.dev` or any other domain — that requires a real
  purchase and DNS control this session cannot perform. References to
  it in docs are corrected to say what's actually true (the real hosted
  instance is `responsibleai-dashboard.onrender.com`, itself pending its
  own rename decision, tracked separately).
- No claim is made here that the MCP server identity change, the
  resource-URI dual-scheme serving, or the env-var precedence logic are
  implemented yet — Sections 5 and 6 describe the design; the code
  changes are separate, testable units of work that follow this
  document, each verified against the full test suite before being
  considered done.

---

## 11. Backward compatibility timeline

| Version | State |
|---|---|
| **v1.2.0** (current, shipped) | `responsibleai`/`rai-governance-platform`/`RAI_*`/`responsibleai-mcp`/`rai://` only. |
| **v2.0.0** (this migration) | `whitepact` package/CLI/env-prefix/MCP-identity/resource-scheme introduced as preferred, additive. `/mcp` (Streamable HTTP) introduced alongside the existing `/sse`+`/messages/` (HTTP+SSE) transport, unmodified. Every v1.2.0 name and endpoint keeps working identically, with deprecation warnings (stderr/logs, never stdout on stdio transport) where a legacy name is actually used. |
| **v2.x** (subsequent minors) | New feature development targets `whitepact` naming primarily; legacy names remain supported, unchanged. |
| **v3.0.0** (future major, not scheduled) | `responsibleai` import alias, `RAI_*` env vars, `responsibleai-mcp` console scripts, and `rai://` resource URIs may be removed, only after a full v2.x cycle of visible deprecation warnings and only if usage telemetry/issue reports suggest it's safe to do so. No specific date is committed here — per the rule against inventing commitments the project can't back.

---

## 12. What this document does not cover

Docker/Helm/CLI/package/env-var/MCP-identity/transport migration, plus
now the runtime governance core through all five of its phases so
far — the gateway itself (Section 8), risk-tiered routing
(Section 8.1), a first policy engine (Section 8.2), evidence
persistence (Section 8.3), and a first approval workflow
(Section 8.4) — MCP OAuth/OIDC authorization (Section 7.2), and
structured tool-output contracts (Section 7.3). What remains genuinely
out of scope here: **`QUARANTINE`** actually being produced by anything
(needs cross-request pattern tracking not built here), a **richer
policy rule language** than plain risk-tier/action-type/target matching
(OPA/Rego or similar, if ever needed), a **richer approval lifecycle**
than `PENDING -> APPROVED`/`DENIED` (expiry/timeout, multi-approver
quorum, delegation-chain approval), **Trust Index signal integration**
(`AgentContext.trust_state` exists as a field, nothing populates or
reads it), **evidence export beyond JSON**, and **wiring the governance
gateway/evidence/approval layers into the live MCP tool-dispatch path**
(`dispatch_tool()` is unchanged; nothing routes an actual tool call
through any of them yet). These are tracked separately and are not
blocked on this document — they can proceed against the current
`responsibleai` code paths and be renamed in step with whichever phase
above actually executes the package migration.
