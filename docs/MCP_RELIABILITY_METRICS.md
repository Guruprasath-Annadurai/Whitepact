# MCP reliability metrics (development-owned)

## Public liveness (no credentials)

- DNS / TLS checks on `whitepact-mcp-http.onrender.com`
- `GET /health` → HTTP 200, `status: ok`
- Latency tracking on `/health`

## Authenticated functional check (CI secret only)

- Scoped Bearer token
- MCP `initialize` → `tools/list` on `/mcp`
- Optional read-only `rai_health`
- No consequential tools from monitors

## Root-cause confidence

**LEADING_HYPOTHESIS:** authentication/probe mismatch — see `docs/release/MCPBEAT_INVESTIGATION.md`.
Do not claim uptime issues are solved without independent observation.
