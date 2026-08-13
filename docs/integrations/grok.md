# xAI Grok

**Status**: CONFIG_READY / NOT_PROVIDER_VERIFIED — see `PLATFORM_COMPATIBILITY.md`.
**Source-of-truth date**: 2026-08-13.

Two independent paths exist. They reach the same WhitePact endpoint and
tools; pick whichever fits your workflow.

## Path A — Grok custom connector (grok.com)

1. `grok.com/connectors` → **New Connector** → **Custom**.
2. URL: `https://whitepact-mcp-http.onrender.com/mcp`.
3. Authentication: Bearer token, value = your WhitePact API key.

Not exercised — requires an interactive grok.com session.

## Path B — xAI API remote MCP

See [`../../examples/grok/remote_mcp_example.py`](../../examples/grok/remote_mcp_example.py).
Reads `XAI_API_KEY` from the environment only — never hardcode it. The
example scopes `allowed_tools` to a small read-only set rather than
enabling all 27 tools by default, since a security-sensitive example
should default to least privilege.

Run:

```bash
export XAI_API_KEY=...        # your own key, not committed anywhere
export WHITEPACT_API_KEY=...  # your own key
python examples/grok/remote_mcp_example.py
```

Not run in this pass — `XAI_API_KEY` is not present in this environment.

## Safe test prompt

> "Call whitepact's rai_scan on: 'SSN 123-45-6789, call me at 555-0100.'"

Expected: PII findings for SSN and phone, redacted copy returned.

## Common errors

| Symptom | Cause | Fix |
|---|---|---|
| `401` | Bad/missing Bearer key | Re-check `WHITEPACT_API_KEY` |
| Empty tool list | `allowed_tools` misconfigured to an empty set | Widen the allowlist, verify tool names against `rai_*` prefix |

## Security notes

`allowed_tools` is used deliberately in the example to avoid handing a
new integration blanket access on day one — expand it once the connector
is confirmed working.

## Founder action

Create the connector in `grok.com/connectors` (Path A) and/or supply
`XAI_API_KEY` to actually run Path B against the live xAI API — both
require an account Claude cannot create.
