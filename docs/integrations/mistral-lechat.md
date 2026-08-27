# Mistral Le Chat

**Status**: BLOCKED_BY_CLIENT_TRANSPORT (blocked on submission channel, not
actually on transport — see the ADR) — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-13.

## Engineering decision

See [`../adr/ADR-MISTRAL-MCP-TRANSPORT.md`](../adr/ADR-MISTRAL-MCP-TRANSPORT.md).
Summary: WhitePact already serves both Streamable HTTP (`/mcp`) and
legacy SSE (`/sse`), so whichever transport Le Chat's MCP client actually
requires is already covered. No new code was written for this platform.

## What's actually blocking

Not the transport — the submission channel. Research this session found
only a third-party community repository
(`github.com/rdmgator12/awesome-mistral-connectors`) describing a
PR-based submission process; no confirmed official Mistral-run channel
was found. This doc will not tell you to submit a PR to an unverified
repository as though it were Mistral's own process.

## Endpoint (if/when a real submission path is confirmed)

```
Streamable HTTP: https://YOUR_WHITEPACT_HOST/mcp
Legacy SSE:       https://YOUR_WHITEPACT_HOST/sse
```

## Authentication

Bearer API key, same as every other platform in this set.

## Safe test prompt (for manual bring-your-own testing in Le Chat, if
custom MCP connectors are available in your account)

> "Use whitepact's rai_scan tool on: 'Employee SSN: 123-45-6789.'"

## Founder action

Confirm Mistral's actual, official MCP Connectors submission process
directly (developer relations, official docs, or your own Mistral
account) — see `docs/integrations/FOUNDER_ACTIONS.md`. Do not use the
unofficial `awesome-mistral-connectors` repo as a stand-in for a real
vendor relationship.
