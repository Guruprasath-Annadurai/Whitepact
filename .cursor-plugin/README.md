# WhitePact — Cursor Plugin

AI governance for agent tool calls: trust scoring, PII/harmful-content
guardrails, hallucination detection, and compliance checks (NIST AI RMF,
EU AI Act, ISO 42001) via 27 read-only MCP tools.

## Setup

1. Install this plugin from the Cursor Marketplace.
2. When prompted, enter your **WhitePact API key** (`WHITEPACT_API_KEY`).
   Get a free key at your WhitePact org's dashboard under
   **Settings -> API Keys**.
3. Cursor connects to `https://whitepact-mcp-http.onrender.com/mcp`
   (Streamable HTTP) using that key as a Bearer token.

## What it does

All 27 tools are read-only and non-destructive (`readOnlyHint=True`,
`destructiveHint=False`) — WhitePact never writes to your code or
project. It evaluates text you pass it (agent outputs, claims, prompts)
and returns structured trust/risk signals.

## Safe test prompt

> "Use whitepact's rai_scan tool to check this text for PII: 'Contact
> John at john@example.com or 555-123-4567.'"

Expected: one tool call to `rai_scan`, a redacted copy returned, no
writes.

## Links

- Source: https://github.com/Guruprasath-Annadurai/Whitepact
- Full docs: https://github.com/Guruprasath-Annadurai/Whitepact/blob/main/docs/integrations/cursor.md
- License: MIT
