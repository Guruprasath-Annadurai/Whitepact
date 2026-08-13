# GitHub Copilot

**Status**: PARTIALLY_VERIFIED — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-13.

## Prerequisites

- GitHub Copilot CLI (or an IDE with Copilot's MCP support) installed and
  signed in.
- A WhitePact API key (Settings → API Keys on your WhitePact org).

## Endpoint

```
https://whitepact-mcp-http.onrender.com/mcp
```

Streamable HTTP. Use this over the legacy `/sse` endpoint for new setups.

## Authentication

Bearer API key in the `Authorization` header. Copilot CLI supports passing
custom headers on remote MCP server registration.

## Setup

```bash
copilot mcp add --transport http whitepact \
  https://whitepact-mcp-http.onrender.com/mcp \
  --header "Authorization: Bearer <YOUR_WHITEPACT_API_KEY>"
```

> The exact flag names above follow Copilot CLI's documented remote-MCP
> syntax as of this writing. Copilot CLI was not installed in the
> environment this doc was prepared in, so the command itself is
> **CONFIG_READY, not provider-verified** — run `copilot mcp add --help`
> first and adjust flags if your installed version differs before relying
> on this.

## Verification steps

```bash
copilot mcp list
copilot mcp get whitepact
```

Expected: `whitepact` listed, status connected, 27 tools discoverable.

## Registry visibility

WhitePact is live on the official MCP Registry
(`io.github.Guruprasath-Annadurai/whitepact`, confirmed queryable). That is
**not** the same as being in GitHub's own curated Copilot registry. If
`/mcp search whitepact` (Copilot CLI's experimental registry search) does
not surface WhitePact, treat that as:

```
OPEN_REGISTRY_LIVE
GITHUB_CURATED_REGISTRY_PENDING
```

Evidence ready for a future curation-outreach request: official MCP
Registry listing (live, `isLatest: true`), 27 read-only annotated tools,
published `server.json` with `remotes`, this compatibility matrix. No
outreach has been sent — that is a founder action (see `FOUNDER_ACTIONS.md`).

## Safe test prompt

> "Use whitepact's rai_scan tool to check this text for PII: 'Contact John
> at john@example.com or 555-123-4567.'"

Expected: one tool call to `rai_scan`, a redacted copy returned, no writes.

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `401 Unauthorized` | Missing/incorrect `Authorization` header | Confirm the header is exactly `Bearer <key>`, no extra whitespace |
| Tool list empty | Transport mismatch | Ensure `--transport http`, not `sse` or `stdio` |
| Timeout on first call | Render free-tier cold start | Retry after ~10-20s; the hosted instance sleeps when idle |

## Security notes

All 27 tools are read-only (`readOnlyHint=True`, `destructiveHint=False`).
Copilot's own per-call approval UI still applies — WhitePact does not
disable client-side approval prompts.

## Founder actions

None required to reach current (PARTIALLY_VERIFIED) state. GitHub curated
registry inclusion, if pursued, is a founder outreach action — see
`FOUNDER_ACTIONS.md`.
