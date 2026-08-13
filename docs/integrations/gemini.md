# Google Gemini

**Status**: CONFIG_READY / NOT_PROVIDER_VERIFIED — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-13.

## Important constraint

Gemini's Remote MCP path (Interactions API) currently documents:

- **Streamable HTTP only** — do not configure SSE for Gemini.
- **No hyphens in the registered MCP server name.** Register it as
  `whitepact`, not `white-pact` or `whitepact-mcp`.

## Endpoint

```
https://whitepact-mcp-http.onrender.com/mcp
```

## Authentication

Bearer API key passed via `headers` in the server registration.

## Setup

See [`../../examples/gemini/remote_mcp_example.py`](../../examples/gemini/remote_mcp_example.py).
Reads `GEMINI_API_KEY` from the environment only.

```bash
export GEMINI_API_KEY=...
export WHITEPACT_API_KEY=...
python examples/gemini/remote_mcp_example.py
```

Not run in this pass — `GEMINI_API_KEY` is not present in this
environment.

## Verification steps (what the example checks)

1. Server registers under the name `whitepact` (no hyphen).
2. `tools/list` returns 27 tools.
3. One `allowed_tools`-scoped call to `rai_scan` succeeds.
4. One call to a policy-checking tool (`rai_policy_check`) returns a DENY
   outcome for a deliberately non-compliant input, proving DENY paths
   reach the model unmodified.

## Safe test prompt

> "Using the whitepact tool, run rai_trust_score on: 'Our system is 100%
> bias-free.'"

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| Registration rejected | Server name has a hyphen | Use `whitepact` exactly |
| `Unsupported transport` | SSE configured | Switch to Streamable HTTP |
| `401` | Bad API key | Re-check `WHITEPACT_API_KEY` |

## Founder action

Supply `GEMINI_API_KEY` to run the example against the real Interactions
API — not available in this environment.
