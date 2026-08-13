# WhitePact platform integrations

WhitePact is one MCP server with one authority model. Every AI platform
listed here connects to the **same** hosted endpoint through a
standards-compliant MCP client — there is no per-platform fork, no
per-platform governance logic, and no platform that can bypass a DENY.

```
OpenAI / Claude / Gemini / Grok / Copilot / Amazon Q / Mistral / Cursor
                              ↓
                   Client's own MCP adapter
                              ↓
                    WhitePact MCP surface
                 (transport, auth, tool schema)
                              ↓
                     WhitePact Core
        (Identity → Authority → Policy → Risk → Decision → Evidence)
```

Start here:

- [`PLATFORM_COMPATIBILITY.md`](PLATFORM_COMPATIBILITY.md) — the canonical
  status matrix. Read this first; it is the single source of truth for
  what is actually verified per platform.
- [`FOUNDER_ACTIONS.md`](FOUNDER_ACTIONS.md) — everything that needs a human
  (account, legal identity, payment, UI confirmation), grouped by what kind
  of action it needs.

Per-platform setup docs (prerequisites, exact config, safe test prompts,
common errors):

- [`github-copilot.md`](github-copilot.md)
- [`microsoft-copilot.md`](microsoft-copilot.md)
- [`claude.md`](claude.md)
- [`grok.md`](grok.md)
- [`gemini.md`](gemini.md)
- [`amazon-q.md`](amazon-q.md)
- [`aws-agentcore.md`](aws-agentcore.md)
- [`mistral-lechat.md`](mistral-lechat.md)
- [`cursor.md`](cursor.md)

OpenAI's Plugins Directory submission is tracked separately in
`compliance/OPENAI_PLUGIN_SUBMISSION_PREP.md` and
`FOUNDER_ACTION_CHECKLIST.md` — not duplicated here.

## Shared facts (do not repeat per-platform)

- **Endpoint**: `https://whitepact-mcp-http.onrender.com/mcp` (Streamable
  HTTP, preferred). Legacy SSE at `.../sse` — still served today, but new
  integrations should use Streamable HTTP.
- **Auth**: every remote connection uses a Bearer API key
  (`Authorization: Bearer <key>`), obtained from the WhitePact dashboard
  (Settings → API Keys) after creating a free org. WhitePact does not run
  an OAuth Authorization Server — clients that *require* OAuth (rather
  than accepting a static bearer token) cannot complete a fully automated
  setup today; see each platform's page for how that's handled.
  Self-hosting via `stdio` (no network, no key) is also available — see
  `server.json`'s `packages` entry.
- **Tool count**: 27, all read-only (no destructive or state-mutating
  tools exist in WhitePact today, so onboarding tests never risk real
  side effects).
- **Security posture that applies everywhere**: HTTPS only, Origin
  validation via `RAI_MCP_HTTP_ALLOWED_ORIGINS`, tenant isolation enforced
  in WhitePact Core (not the transport layer), no platform-specific logic
  is permitted to override a DENY or self-approve — see
  `THREAT_MODEL.md` and `compliance/INTERNAL_SECURITY_REVIEW.md`.

## Automated preflight

`python scripts/integration_smoke.py` runs the protocol-level checks
(`initialize`, `tools/list`, auth failure, malformed request, etc.)
against the live endpoint and prints a per-check pass/fail table. It does
**not** simulate any specific provider's client — see the script's header
for the distinction between `LOCAL_PROTOCOL_TEST` and `REAL_PROVIDER_TEST`.
