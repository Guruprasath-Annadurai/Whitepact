# GitHub Copilot

**Status**: VERIFIED — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-15.

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
copilot mcp add --transport http --header "Authorization: Bearer <YOUR_WHITEPACT_API_KEY>" whitepact \
  https://whitepact-mcp-http.onrender.com/mcp
```

**Verified live 2026-08-15** against GitHub Copilot CLI v1.0.80
(installed via `npm install -g @github/copilot`): `copilot mcp add`
registered the server correctly (`copilot mcp get whitepact` showed
`Type: http`, correct URL, header present, `Tools: * (all)`), and in an
interactive session the prompt "Use whitepact's rai_scan tool to check
this text for PII: 'Contact John at john@example.com or 555-123-4567.'"
triggered a real `rai_scan` tool call that correctly identified both PII
elements and returned the redacted text.

## Verification steps

```bash
copilot mcp list
copilot mcp get whitepact
```

Expected: `whitepact` listed, status connected, 27 tools discoverable.

## Registry visibility

WhitePact is live on the official MCP Registry
(`io.github.Guruprasath-Annadurai/whitepact`, confirmed queryable). That is
**not** the same as being in GitHub's own curated registry at
`github.com/mcp` (219 servers as of 2026-08-14, editorially curated —
confirmed live that WhitePact has no page there yet:
`github.com/mcp/Guruprasath-Annadurai/whitepact` returns 404 despite the
official-registry listing already being live).

```
OPEN_REGISTRY_LIVE
GITHUB_CURATED_REGISTRY_PENDING
```

**Real submission path found 2026-08-14**, confirmed directly from
GitHub's own blog
([How to find, install, and manage MCP servers with the GitHub MCP
Registry](https://github.blog/ai-and-ml/generative-ai/how-to-find-install-and-manage-mcp-servers-with-the-github-mcp-registry/)):
after publishing to the official OSS registry (already done for
WhitePact), email **partnerships@github.com** and request inclusion,
referencing the live registry listing. Not a self-serve form, but a
real, documented, named channel — not "no path found." Draft email in
`compliance/outreach/READY_TO_SEND_EMAILS.md`.

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
registry inclusion has a real, confirmed path now (email
`partnerships@github.com`) — draft ready in
`compliance/outreach/READY_TO_SEND_EMAILS.md`, sending it is the founder
action (see `FOUNDER_ACTIONS.md`).
