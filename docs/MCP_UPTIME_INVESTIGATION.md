# MCP uptime investigation (2026-09-21)

## Canonical endpoint

`https://whitepact-mcp-http.onrender.com/mcp` (Streamable HTTP, Bearer required)

## External probe results

| Check | Result |
|-------|--------|
| DNS A | `216.24.57.16`, `216.24.57.18` (via Cloudflare → Render) |
| DNS AAAA | CNAME chain only in sample |
| TLS | Valid Google Trust Services cert for `onrender.com` |
| GET `/health` | **200** ~60–85ms (5/5) |
| POST `/mcp` (no auth) | **401** ~62–88ms (5/5) |
| Cold start | Not observed in sample (warm instance) |

## Classification

**Primary:** `AUTH_EXPECTATION_MISMATCH` + `PROBE_INCOMPATIBILITY`  
Automated directory scanners that treat `/mcp` as an unauthenticated health URL will mark the service "down" despite a healthy host.

**Not observed:** DNS/TLS failure, 5xx storms, or hosting sleep in this sample.

## Mitigation (code)

- Enrich GET `/health` with `service`, `protocol_version`, `server_version`, `tools_public`, `tools_registered`, `resources` (no tenant/policy data).
- Document probes in `docs/MCP_RELIABILITY_METRICS.md`.

**Deployment required:** yes, to refresh hosted `/health` beyond legacy `{status, tools}`.
