# Amazon Q Developer

**Status**: CONFIG_READY / NOT_PROVIDER_VERIFIED — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-13.

## Prerequisites

- Amazon Q Developer (CLI or IDE extension) installed and signed in.
- A WhitePact API key.

## Endpoint

```
https://whitepact-mcp-http.onrender.com/mcp
```

## Authentication

WhitePact does not require OAuth — a static Bearer API key is sufficient
and is what the example below uses. (Amazon Q's MCP config format
supports an OAuth block for servers that need it; WhitePact simply
doesn't populate one.)

## Setup

See [`../../examples/amazon-q/mcp-config.json`](../../examples/amazon-q/mcp-config.json)
for the config block. Add its `whitepact` entry to your own Amazon Q MCP
config file (commonly `~/.aws/amazonq/mcp.json` — confirm the exact path
against your installed Amazon Q version's docs, since Claude did not
modify any global user configuration as part of this task).

## Verification steps

Amazon Q CLI's own MCP inspection commands (naming varies by version) —
run whichever your installed CLI documents, e.g. a servers-list command,
and confirm `whitepact` shows connected with 27 tools.

Not run in this pass — Amazon Q CLI is not installed in this environment.

## Safe test prompt

> "Use the whitepact rai_compliance tool to check this claim against
> EU AI Act requirements: 'Our hiring model requires no human oversight.'"

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `401` | Missing/incorrect Bearer header | Re-check API key |
| Server not found | Config not in the path Amazon Q actually reads | Confirm the config file path for your installed version |

## Security notes

The example config sets no default tool restrictions beyond what
WhitePact itself enforces (all 27 tools are read-only) — Amazon Q's own
per-call approval UI still applies.

## Founder action

Install/confirm Amazon Q Developer tooling and add the config to your own
environment — Claude does not have access to a live Amazon Q installation.
