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
| `responsibleai.dev` | 3 | A domain referenced in docs that has never been registered/deployed — see Section 9 |

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
committed here, consistent with Section 10's timeline for every other
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
refactor beyond what's required" rule): OAuth/OIDC-based authorization
for MCP (currently static Bearer API keys), and structured tool-output
contracts (`structuredContent`, output schemas) — both are later phases
of the WhitePact Enterprise Foundation v2 program, not required to add
a second transport alongside the first.

---

## 8. Deployment migration

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

## 9. What is explicitly *not* claimed by this migration

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

## 10. Backward compatibility timeline

| Version | State |
|---|---|
| **v1.2.0** (current, shipped) | `responsibleai`/`rai-governance-platform`/`RAI_*`/`responsibleai-mcp`/`rai://` only. |
| **v2.0.0** (this migration) | `whitepact` package/CLI/env-prefix/MCP-identity/resource-scheme introduced as preferred, additive. `/mcp` (Streamable HTTP) introduced alongside the existing `/sse`+`/messages/` (HTTP+SSE) transport, unmodified. Every v1.2.0 name and endpoint keeps working identically, with deprecation warnings (stderr/logs, never stdout on stdio transport) where a legacy name is actually used. |
| **v2.x** (subsequent minors) | New feature development targets `whitepact` naming primarily; legacy names remain supported, unchanged. |
| **v3.0.0** (future major, not scheduled) | `responsibleai` import alias, `RAI_*` env vars, `responsibleai-mcp` console scripts, and `rai://` resource URIs may be removed, only after a full v2.x cycle of visible deprecation warnings and only if usage telemetry/issue reports suggest it's safe to do so. No specific date is committed here — per the rule against inventing commitments the project can't back.

---

## 11. What this document does not cover

Docker/Helm/CLI/package/env-var/MCP-identity/transport migration only.
The runtime governance architecture (`SPEC.md`), OAuth/OIDC
authorization, modern structured tool-output contracts, the policy
engine, and the other phases of the WhitePact Enterprise Foundation v2
program are tracked separately and are not blocked on this document —
they can proceed against the current `responsibleai` code paths and be
renamed in step with whichever phase above actually executes the
package migration.
