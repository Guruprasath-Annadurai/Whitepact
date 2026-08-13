# WhitePact Platform Compatibility Matrix

Source of truth for what is actually verified, as of the date below — not
aspirational. Statuses are restricted to:

- **VERIFIED** — tested end-to-end against the real provider/client.
- **PARTIALLY_VERIFIED** — the WhitePact side (protocol/transport/auth) is
  confirmed working; the provider-specific surface (their UI, their CLI,
  their registry) was not independently exercised.
- **CONFIG_READY** — a correct configuration/example exists and follows the
  provider's documented format, but has not been run against the real
  provider (no credentials available, or the surface requires an account
  Claude cannot create — see `FOUNDER_ACTIONS.md`).
- **BLOCKED** — a concrete technical or policy incompatibility exists.
- **NOT_TESTED** — no verification attempted yet.

`APPROVED` is never used here unless a platform's own review process has
actually approved WhitePact's listing.

Last verified: 2026-08-13. WhitePact `1.2.2` (PyPI package) / `1.2.3`
(MCP Registry listing).

## Current WhitePact MCP surface (ground truth)

| Property | Value |
|---|---|
| Transports | `streamable-http` (primary), `sse` (legacy, still served), `stdio` (self-hosted, free) |
| Public endpoint | `https://whitepact-mcp-http.onrender.com/mcp` (streamable-http), `.../sse` (SSE) |
| Auth | Static Bearer API key only. No OAuth Authorization Server is deployed (`/.well-known/oauth-protected-resource` 404s — confirmed live, no OIDC issuer configured on the hosted instance) |
| Tools | 27, all `readOnlyHint=True, idempotentHint=True, openWorldHint=False, destructiveHint=False` |
| Resources | Supported — 10 canonical resources, 20 advertised (dual `whitepact://` / `rai://` URI scheme) |
| Prompts | **Not supported** — no `prompts/list` handler in `src/responsibleai/mcp/server.py` |
| Structured output | Tool results are JSON text content; no `structuredContent`/`outputSchema` wired into tool responses yet (gap, not platform-specific) |
| Origin validation | Enforced via `RAI_MCP_HTTP_ALLOWED_ORIGINS` / `TrustedHostMiddleware` |
| Health | `GET /health` → `{"status":"ok","tools":27,...}` (live-verified 2026-08-13) |
| Directory fallback card | `GET /.well-known/mcp/server-card.json` — static capability card for crawlers that can't complete an authenticated scan (e.g. Smithery) |
| Demo/unauthenticated bypass | `RAI_MCP_HTTP_ALLOW_UNAUTHENTICATED_DEMO` env var exists for recording demos only — **confirmed closed** (live 401 on unauthenticated `/mcp` initialize, 2026-08-13) |

## Compatibility matrix

| Platform | Surface | Transport | Auth | Tools | Resources | Prompts | Structured Results | Approval Model | Status | Test Evidence | Founder Action | Known Limitation |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| GitHub Copilot | CLI / IDE MCP (remote HTTP) | streamable-http | Bearer API key | Discoverable | N/A (Copilot MCP surface is tool-centric) | N/A | Text content only | Per-call tool approval in client | PARTIALLY_VERIFIED | Protocol-level `/mcp` init + `tools/list` verified live; `copilot mcp add/list/get` not run (Copilot CLI not installed in this environment) | None to reach current state; curated-registry inclusion is a separate outreach step | Open MCP Registry presence ≠ GitHub's curated registry |
| Microsoft Copilot / Copilot Studio | Custom connector (admin-added, MCP over Streamable HTTP) | streamable-http | Bearer API key (custom connector auth) | Discoverable | Supported by connector, untested by MS tooling | N/A | Text content only | Admin/tenant approval per connector | CONFIG_READY | Local protocol test only; no Microsoft tooling available to run | Partner Center account, business verification, Copilot enrollment — see `distribution/microsoft/FOUNDER_SUBMISSION_CHECKLIST.md` | Certification package prepared, not submitted |
| Anthropic Claude | Custom remote MCP connector | streamable-http | Bearer API key | Discoverable | Discoverable | N/A (Claude tolerates absent `prompts/list`) | Text content only | Per-tool user approval in Claude UI | PARTIALLY_VERIFIED | Protocol-level `/mcp` init verified live via curl; UI-level "Add custom connector" flow requires interactive browser session | Add connector via Settings → Connectors in an interactive Claude session; confirm tool list renders | Claude UI add-flow can't be scripted headlessly from this session |
| xAI Grok | Custom connector (grok.com) + xAI API remote MCP | streamable-http | Bearer API key | Discoverable | Discoverable | N/A | Text content only | Per-connector approval | CONFIG_READY | Local protocol test only; `XAI_API_KEY` not present in this environment | Configure connector in grok.com UI or supply `XAI_API_KEY` for API-path testing | Not provider-verified |
| Google Gemini | Remote MCP (Interactions API) | streamable-http only (Gemini does not support SSE for remote MCP) | Bearer API key via `headers` | Discoverable | Discoverable | N/A | Text content only | `allowed_tools` scoping | CONFIG_READY | Local protocol test only; `GEMINI_API_KEY` not present in this environment | Supply `GEMINI_API_KEY` to run the example script for real | Must register server name as `whitepact` (no hyphen) per Gemini's current restriction |
| Amazon Q Developer | Remote HTTP MCP config | streamable-http | Bearer API key (OAuth not required by WhitePact) | Discoverable | Discoverable | N/A | Text content only | Q Developer tool-approval prompts | CONFIG_READY | Local protocol test only; Amazon Q CLI not installed in this environment | Add config via Amazon Q CLI/IDE settings | Not provider-verified |
| AWS Bedrock AgentCore | External MCP target behind AgentCore Gateway | streamable-http | Bearer API key | Discoverable | Discoverable | N/A | Text content only | Gateway-level policy + WhitePact's own authority engine (unchanged) | CONFIG_READY | Local protocol test only; no AgentCore Gateway instance available | Provision an AgentCore Gateway and register WhitePact as a target | Reference architecture only — not a hosting migration |
| Mistral Le Chat | Featured/MCP Connectors directory or custom | **Blocked pending transport decision** | Bearer API key | Discoverable | Discoverable | N/A | Text content only | Per-connector approval | BLOCKED_BY_CLIENT_TRANSPORT | See `docs/adr/ADR-MISTRAL-MCP-TRANSPORT.md` | Confirm Le Chat's current transport requirement directly (no verified official submission channel found — see ADR) | If Le Chat requires legacy SSE only and WhitePact's SSE support is ever dropped, this breaks; currently SSE is still served, so no immediate break |
| Cursor | Remote MCP (project or global `mcp.json`) | streamable-http | Bearer API key | Discoverable | Discoverable | N/A | Text content only | Per-tool approval in Cursor UI | CONFIG_READY | Local protocol test only; not injected into any live Cursor install | Add `.cursor-example/mcp.json` contents to personal `~/.cursor/mcp.json` | "Add to Cursor" one-click deep link format not independently confirmed from current official docs — omitted rather than guessed |
| OpenAI | Plugins Directory | streamable-http | OAuth/No-Auth/Mixed only (WhitePact used a scoped demo-auth workaround) | Discoverable | Discoverable | N/A | Text content only | Per-tool approval + directory review | Handled separately (submitted, in Review) | See `compliance/OPENAI_PLUGIN_SUBMISSION_PREP.md` and `FOUNDER_ACTION_CHECKLIST.md` | None — submission complete | Out of scope for this document per task instructions |
