# Anthropic Claude

**Status**: PARTIALLY_VERIFIED — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-13.

## Prerequisites

- Claude Team/Enterprise (or a plan that supports custom remote MCP
  connectors — Claude Pro does not, confirmed earlier in this project).
- A WhitePact API key.

## Endpoint

```
https://whitepact-mcp-http.onrender.com/mcp
```

## Authentication

Bearer API key. Claude's custom-connector UI accepts a static header value
at setup time — no OAuth flow is required since WhitePact doesn't run an
Authorization Server.

## Setup (manual, in Claude's UI)

1. Claude → **Settings** → **Connectors** → **Add custom connector**.
2. URL: `https://whitepact-mcp-http.onrender.com/mcp`.
3. Add header: `Authorization: Bearer <YOUR_WHITEPACT_API_KEY>`.
4. Save. Claude will fetch `tools/list` immediately — 30 tools should
   appear.

This flow requires an interactive browser session and was **not**
exercised in this pass (no such session available here). It was
previously verified live in this project for the OpenAI submission's demo
recording, using the same underlying `/mcp` endpoint and auth pattern —
see `FOUNDER_ACTION_CHECKLIST.md`.

## Verification steps

- MCP Inspector (`npx @modelcontextprotocol/inspector`) can validate the
  endpoint independent of Claude's own UI — point it at the same URL and
  header and confirm `initialize`, `tools/list`, and one `tools/call`
  succeed.
- In Claude itself, after adding the connector, ask it to list available
WhitePact tools and confirm the count matches 30 for v1.2.6.

## Safe test prompt

> "Using the whitepact connector, run rai_trust_score on the claim: 'This
> model achieves 99.9% accuracy in all conditions.'"

Expected: one tool call, a trust score with rationale, no writes, no
approval prompt needed (read-only tool).

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| Connector greyed out / can't add | Claude plan doesn't support custom connectors | Requires Team/Enterprise |
| "Cold start" 502 on first call | Render free-tier idle sleep | Retry after ~10-20s |
| Tools list empty after add | Header typo | Re-check `Authorization: Bearer <key>` exactly, re-save |

## Security notes

No credentials are stored by this integration effort — the header value
lives only in Claude's own connector config, entered directly by the
account owner.

## Founder action

**FOUNDER UI VALIDATION REQUIRED** — confirm the "Add custom connector"
flow still matches the steps above (Claude's UI has changed layout before)
and that all 30 tools render for v1.2.6, using your own Claude session.
