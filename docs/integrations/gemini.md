# Google Gemini

**Status**: PARTIALLY_VERIFIED — protocol/schema confirmed live against
the real API; full success blocked on Google account billing, not on
WhitePact or the example code. See `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-14.

## Important constraint

Gemini's Remote MCP path is the **Interactions API**
(`client.interactions.create`, not `client.models.generate_content` —
confirmed live 2026-08-14: `generate_content` with `gemini-2.5-pro`
returns a real 404 even though that model is still listed in the SDK's
own type hints, because the SDK's static types are stale relative to
what the live server actually accepts). Two more constraints:

- **Streamable HTTP only** — do not configure SSE for Gemini.
- **No hyphens in the registered MCP server name.** Register it as
  `whitepact`, not `white-pact` or `whitepact-mcp`.

## Endpoint

```
https://YOUR_WHITEPACT_HOST/mcp
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

**Run live 2026-08-14** against the real Interactions API
(`google-genai` SDK v2.14.0): the tool-config schema was accepted by
the live server (no validation error) using a rolling model alias,
`gemini-pro-latest`, which resolves server-side to `gemini-3.1-pro`.
The call then failed with a `429` — *"Quota exceeded ... free_tier
limit: 0, model: gemini-3.1-pro"* — meaning this specific model
requires a billing-enabled Google Cloud project; a bare free-tier API
key key isn't enough on its own. That's a real, live-confirmed finding,
not a guess: the schema itself works, the account doesn't have quota.

## Verification steps (what the example checks)

1. Server registers under the name `whitepact` (no hyphen).
2. `tools/list` returns 27 tools.
3. One `allowed_tools`-scoped call to `rai_scan` succeeds — `allowed_tools`
   is a real field on the Interactions API's MCP tool type
   (`[{"tools": [...]}]`, confirmed by reading the installed SDK's
   generated types), unlike the older `models.generate_content` path's
   `Tool.mcp_servers`, which has no such scoping field.
4. One call to a policy-checking tool (`rai_policy_check`) returns a DENY
   outcome for a deliberately non-compliant input, proving DENY paths
   reach the model unmodified.

Steps 3-4 are not yet exercised end-to-end — blocked on billing, per above.

## Safe test prompt

> "Using the whitepact tool, run rai_trust_score on: 'Our system is 100%
> bias-free.'"

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| Registration rejected | Server name has a hyphen | Use `whitepact` exactly |
| `Unsupported transport` | SSE configured | Switch to Streamable HTTP |
| `401` | Bad API key | Re-check `WHITEPACT_API_KEY` |
| `404` calling `client.models.generate_content(model="gemini-2.5-pro", ...)` | Wrong API path — that model is deprecated for new users despite still appearing in the SDK's type hints | Use `client.interactions.create(model="gemini-pro-latest", ...)` instead, per the example |
| `429` "Quota exceeded ... free_tier ... limit: 0" | The resolved model requires a billing-enabled Google Cloud project | Enable billing on the project tied to your `GEMINI_API_KEY` in Google AI Studio / Cloud Console |

## Founder action

Enable billing on the Google Cloud project behind your `GEMINI_API_KEY`
to clear the `429` above and get a full end-to-end run — the schema and
auth are already confirmed working.
