# Hosted MCP purpose (`_whitepact_purpose`)

WhitePact records **declared intent** in the governance evidence chain. Hosted MCP
execution (Streamable HTTP with tenant governance enabled) requires a
human-readable purpose on every governed tool call.

## Required argument

Pass a string field **`_whitepact_purpose`** alongside normal tool arguments:

```json
{
  "_whitepact_purpose": "Review and approve Q1 vendor invoice batch for ACME Corp",
  "text": "Scan this draft email before send"
}
```

## Invalid substitutes

Do **not** use:

- MCP session IDs or connection metadata
- Generic placeholders such as `mcp_session_context:<id>`
- Empty strings or single-word tokens without business context

The value is stored as governance **purpose**, not as transport metadata.

## Client integration

- **Cursor / Claude Desktop / Windsurf**: add `_whitepact_purpose` in the tool
  call payload your MCP client sends (or use a thin adapter that prompts the
  user once per task and injects the field).
- **Self-hosted stdio MCP**: purpose is optional unless your deployment enables
  hosted-style governance on HTTP transports.

If purpose is missing, the server returns `governance_purpose_required` with
this documentation link.
