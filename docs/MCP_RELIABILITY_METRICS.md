# MCP reliability metrics (development-owned)

## Probe tiers

### Public liveness (no credentials)

- DNS resolution
- TLS certificate validity
- `GET /health` → expect HTTP 200 and `status: ok`
- Latency percentiles on `/health`

### Authenticated MCP functional check (scoped CI secret only)

- Bearer token with **minimal** org scope
- Streamable HTTP: `initialize` → `tools/list`
- Optional: call `rai_health` (read-only)
- **Never** call `test.counter.increment` or other consequential tools from monitors

Monitor credentials must not be published or reused as customer API keys.

## Canonical endpoint

`https://whitepact-mcp-http.onrender.com/mcp`

## Root-cause confidence

See `docs/MCP_UPTIME_INVESTIGATION.md`. Uptime narrative remains **LEADING_HYPOTHESIS** until MCPBeat/raw handshake logs are correlated.
