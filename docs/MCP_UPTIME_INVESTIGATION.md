# MCP uptime investigation (2026-09-21)

## Canonical endpoint

`https://whitepact-mcp-http.onrender.com/mcp` (Streamable HTTP, Bearer required)

## External probe results (this environment)

| Check | Result |
|-------|--------|
| DNS A | Resolves via Cloudflare → Render |
| TLS | Valid |
| GET `/health` | **200**, ~60–85ms (5/5) |
| POST `/mcp` (no auth, non-MCP JSON body) | **401** JSON `{"error":"unauthorized",...}` |
| POST `/mcp` (no auth, MCP `initialize`) | **401** same non-JSON-RPC envelope |
| Warm latency | Sub-100ms in sample |

## MCPBeat / scanner behavior (public sources)

Per [mcpbeat.com/about](https://mcpbeat.com/about/) and [mcpbeat.com/bot](https://mcpbeat.com/bot/):

- Probes use a real MCP **`initialize`** handshake (not plain HTTP GET).
- May follow with **`tools/list`** when the server answers.
- **Does not authenticate** (no API keys).
- Documents that **401/403 can count as “alive, requires key”** — not necessarily downtime.

## Root-cause confidence

**LEADING_HYPOTHESIS (not proven):**

1. **AUTH_EXPECTATION_MISMATCH / non-MCP error shape** — unauthenticated requests receive a plain JSON error object, not a JSON-RPC error envelope; some monitors may classify that as a failed handshake even when HTTP status is 401.
2. **PROBE_INCOMPATIBILITY** — scanners that only check HTTP 200 on `/mcp` without MCP semantics will see failure.
3. **HOSTING_COLD_START / timeout** — not observed in this warm sample; remains possible for external monitors.

**UNKNOWN without WhitePact-specific MCPBeat raw rows:** whether this deployment is scored “down” vs “behind auth” in their dataset.

## Health endpoint

Minimal public liveness only (`service`, `status`, `protocol_version`, `transport`). Tool inventory belongs in authenticated MCP surfaces / server-card, not `/health`.

## Deployment

No deployment performed in this correction pass.
