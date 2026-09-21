# MCP reliability metrics (development-owned)

See `docs/MCP_UPTIME_INVESTIGATION.md` for the 2026-09-21 external probe record.

## Probes without credentials

- GET `/health` → expect 200, fields `service`, `status`, `protocol_version`, `server_version`
- POST `/mcp` without Bearer → expect **401** (not 5xx)

## Authenticated handshake (CI secret only)

- Initialize + `tools/list` over Streamable HTTP with org API key
