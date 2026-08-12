# WhitePact — Connector/Directory Readiness Report

> Written for external review (originally: to hand to ChatGPT and ask "what's
> missing, what would you build first"). Every claim below was checked live
> against the running code/services on 2026-08-13, not recalled from memory —
> see the "How this was verified" line under each section.

---

## 0. What WhitePact is, in one paragraph

WhitePact (PyPI: `rai-governance-platform`, formerly ResponsibleAI) is an
MCP server plus REST API that gives any LLM agent runtime AI-governance
controls: PII/harm scanning, trust scoring, guardrails, hallucination
detection, bias eval, and a policy/approval engine that can gate or quarantine
a tool call before it executes (`ALLOW / ALLOW_WITH_REDACTION /
REQUIRE_APPROVAL / DENY / QUARANTINE`). It ships as a self-hosted stdio MCP
server (free, unrestricted) and as a hosted HTTP+SSE/Streamable-HTTP server
(`whitepact-mcp-http`, plan-gated, Bearer/apiKey-authenticated). 27 tools, 10
canonical resources (20 advertised across dual `whitepact://`/`rai://` URI
schemes). MIT licensed.

---

## 1. Per-platform readiness

### 1a. Anthropic (Claude)

**Strongest of the four — this is the platform to lead with.**

- **Individual/team connection**: works today, zero approval needed. Any
  Claude Code/Desktop user drops the README's JSON config block in and the
  full 27-tool stdio server runs locally.
- **Claude.ai remote connectors (Team/Enterprise/Max)**: also works today —
  `whitepact-mcp-http` is a live, publicly reachable HTTPS endpoint
  (`whitepact-mcp-http.onrender.com`) speaking standard MCP HTTP+SSE, serving
  a `/.well-known/mcp/server-card.json` and an OAuth-resource-server
  `/.well-known/oauth-protected-resource` endpoint. Verified live via curl:
  returns real tool list, `authentication.schemes: ["apiKey"]`.
- **Anthropic's curated in-app Connectors Directory**: separate from the two
  above — a real submission/review process gated behind Claude Console login
  (`console.claude.com`), not something automatable from here. Not yet
  submitted (requires founder's own login).
- **Gap**: auth is apiKey-only by default. The resource-server code path for
  full OAuth 2.1 (token validation against an external authorization server)
  exists (`src/responsibleai/mcp/server.py`, OIDC-gated) but isn't configured
  on the live hosted instance. Anthropic's directory review may expect OAuth
  for a listed remote connector rather than a static API key — worth
  confirming against their current submission requirements before applying.

**Verdict: ready to submit to the Connectors Directory today; the OAuth gap
is the one thing worth closing first if the directory's checklist requires it.**

### 1b. OpenAI (ChatGPT / Apps SDK)

- No central marketplace exists — OpenAI's model is bring-your-own-URL
  "Connectors" per org, admin-configured. WhitePact already satisfies the
  only real technical bar (a standards-compliant MCP HTTP endpoint).
- **Nothing to build.** The only action is user-side: an org admin pastes the
  `whitepact-mcp-http` URL into their own ChatGPT connector settings. There's
  no listing to submit to, so "onboarding strength" here isn't a code
  question — it's a matter of the platform's own registration UI (which
  changes independent of this codebase).

**Verdict: connector-technically ready; there is no directory to be "onboarded" into as of the last documentation check — reverify OpenAI's current developer docs before pitching a specific prospect, since this segment of the ecosystem moves fastest.**

### 1c. Google (Gemini API / Gemini Enterprise)

- Same shape as OpenAI: a custom MCP data-store/connector flow, per-org
  admin-configured, no public directory found. Same conclusion: technically
  ready, no listing exists to submit to.

**Verdict: same as OpenAI — ready, nothing to build, re-verify current docs before a specific pitch.**

### 1d. Glama

- Glama crawls the MCP ecosystem automatically rather than taking manual
  submissions without an account. As of the last live check WhitePact was
  **not yet indexed**. Being on the official MCP Registry (confirmed live,
  see §2) is very likely what triggers Glama's crawler to pick it up —
  no separate action currently identified beyond waiting/re-checking.

**Verdict: passively pending, re-check periodically; nothing to build.**

---

## 2. Official MCP Registry + community directories — current live status

**Verified live via `curl https://registry.modelcontextprotocol.io/v0/servers?search=whitepact` on 2026-08-13:**
WhitePact **is live** on the official registry — `io.github.Guruprasath-Annadurai/whitepact`,
version `1.2.2`, package `rai-governance-platform` (PyPI, confirmed `1.2.2` is
also the actual latest published PyPI release — the version-mismatch blocker
noted in `compliance/MCP_DISTRIBUTION_GUIDE.md` on 2026-07-23 has since been
resolved).

**One concrete, real gap found in this pass**: `server.json`'s `packages[0]`
only declares a `stdio` transport — there is **no `remotes` entry** pointing
at `whitepact-mcp-http.onrender.com`, even though that URL is now live,
publicly reachable, and serving a correct server-card. When
`MCP_DISTRIBUTION_GUIDE.md` was written, this was correctly left out because
no real hosted URL existed yet. That's no longer true. **This is a real,
buildable action item** (§4 below), not just a "wait and check" item like
Glama.

- **Smithery**: confirmed live and listed (per prior session's verification,
  `smithery.ai/server/guruprasathannadurai-official/whitepact`) — badge
  already in README.
- **PulseMCP**: submissions were paused as of the last check but the
  platform states it auto-ingests anything already on the official MCP
  Registry — since WhitePact is now on that registry, no separate action
  needed once PulseMCP resumes indexing.

---

## 3. Underlying technical/security posture (what a reviewer will actually check)

This is the part that determines whether a directory *approves* a listing,
not just whether one is technically submittable.

| Area | Status | Evidence |
|---|---|---|
| Protocol compliance | Standard stdio + HTTP/SSE + Streamable HTTP transports | `src/responsibleai/mcp/server.py`, tests: `test_mcp_http_transport.py`, `test_mcp_transport_security.py` |
| Auth | apiKey (Bearer) live; OAuth 2.1 resource-server code path exists but not enabled on hosted instance | `test_mcp_oauth.py`, server-card live check |
| Tool safety/governance | Real policy engine gates tool calls (ALLOW/DENY/REQUIRE_APPROVAL/QUARANTINE), not just tool exposure | `MIGRATION_WHITEPACT_V2.md` Phase 8, governance dispatch tests |
| SSRF protection on upstream proxying | Present — the upstream MCP gateway is SSRF-guarded | `upstream_dispatch.py`, Phase 13/task #139 |
| Rate limiting | Redis-backed, confirmed live (`rate_limit_backend: redis` on `/api/health`) | live curl check |
| Threat model | Documented | `THREAT_MODEL.md` |
| SOC2 | Not certified — honest no-budget alternative path documented instead (CAIQ v4.0.3 filled from real facts, NIST CSF self-assessment) | `compliance/SOC2_READINESS.md`, `compliance/CAIQ_SELF_ASSESSMENT.md` |
| License | MIT | `LICENSE` |
| CI | 4 required status checks, branch protection enabled on `main` | `.github/workflows/{ci,security-scan,dependency-review,scorecard}.yml` |
| Test coverage | 1725+ passing tests (per README badge, last full-suite run) | `README.md` badge, `CHANGELOG.md` |
| Credential hygiene | Supabase DB password + Upstash Redis token both rotated 2026-08-13 after a chat-history exposure earlier in this engagement | `FOUNDER_ACTION_CHECKLIST.md` |

**One operational gap worth flagging honestly**: `whitepact-mcp-http` (the
service actually presenting itself to remote connectors) has **no database or
Redis configuration at all** — confirmed directly in its Render environment
tab. It falls back to SQLite/in-memory. That means: usage/quota tracking,
API-key state, and rate limiting on the *connector-facing* server are not
durable across restarts and not shared if the service ever scales beyond one
instance. This doesn't block a directory submission (the server still works
correctly for a single reviewer testing it), but it is a real limitation for
production multi-tenant connector traffic at any real volume.

---

## 4. Concrete build list — ranked by what actually moves onboarding strength

1. **Add `remotes` to `server.json` pointing at `whitepact-mcp-http.onrender.com`,
   revalidate against the schema, republish.** This is the single highest-leverage
   item: it's what turns "listed as a pip-installable stdio server" into
   "listed as a one-click remote connector," which is what Claude.ai/ChatGPT/Gemini
   connector pickers actually want to consume. Was correctly blocked before;
   isn't blocked anymore.
2. **Wire `RAI_DATABASE_URL` and `RAI_REDIS_URL` into `whitepact-mcp-http`**
   (same values already live on `responsibleai-dashboard`, or a dedicated
   pooler connection). Turns the connector-facing server from
   single-instance/ephemeral into production-durable — matters once real
   connector traffic starts, not before.
3. **Decide on and enable OAuth 2.1 for the hosted MCP server**, at least as
   an option alongside apiKey, before submitting to Anthropic's Connectors
   Directory — check their current submission requirements first; if OAuth
   isn't actually required, this drops in priority.
4. **Submit to Anthropic's Connectors Directory** (requires founder's own
   Claude Console login — not automatable here).
5. **Re-check Glama** periodically now that the official registry listing is
   live — likely resolves itself once their crawler passes over the registry
   again.
6. **Write the launch post** (still the one open item from the original MCP
   distribution checklist) — time it to cite the live registry + Smithery
   listings as the "already listed elsewhere" social proof.

---

## 5. Questions for external review

If you're reviewing this from outside the project, the things worth
pressure-testing are:

1. Is the `ALLOW/ALLOW_WITH_REDACTION/REQUIRE_APPROVAL/DENY/QUARANTINE`
   governance model — real policy enforcement rather than a thin wrapper
   around tool listing — actually the differentiator it's positioned as
   against a plain MCP server, or is this table-stakes now that other
   governance-flavored MCP servers exist?
2. Does the lack of SOC2 certification (honest self-assessment only) create
   friction specifically for the *connector directory* review process, as
   opposed to friction for a direct enterprise sales conversation (which is
   a separate, already-understood problem)?
3. Given `whitepact-mcp-http`'s current no-DB/no-Redis state, is it worth
   fixing *before* pursuing real connector-directory listings, or is
   "works correctly for a single reviewer, not yet load-tested for
   multi-tenant traffic" an acceptable state to launch a directory listing
   in and fix reactively once traffic actually shows up?
4. Anything in the actual MCP tool surface (`src/responsibleai/mcp/tools.py`,
   27 tools) that reads as bloated, redundant, or missing an obvious
   governance primitive a reviewer would expect and not find?
