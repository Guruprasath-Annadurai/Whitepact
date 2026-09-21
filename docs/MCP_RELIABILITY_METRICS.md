# MCP reliability metrics (development-owned)

## Canonical endpoint

| Surface | URL |
|---------|-----|
| Streamable HTTP | `https://whitepact-mcp-http.onrender.com/mcp` |
| Health (unauthenticated) | `https://whitepact-mcp-http.onrender.com/health` |
| Server card | `https://whitepact-mcp-http.onrender.com/.well-known/mcp/server-card.json` |

## Synthetic probes (no credentials)

Run from CI or an external cron (recommended: weekly + post-deploy):

1. **DNS** — `A`/`AAAA` resolve for `whitepact-mcp-http.onrender.com`
2. **TLS** — certificate valid, hostname matches Render/Cloudflare chain
3. **HTTP GET /health** — expect `200`, `status=ok`, latency p95 < 5s
4. **HTTP POST /mcp** (no auth) — expect `401` with `unauthorized` (not 5xx)
5. **MCP handshake** — requires Bearer test key in secure CI secret store only

## Measurements (internal SLO inputs — not public claims)

| Metric | Definition |
|--------|------------|
| `mcp.health.availability` | % successful GET /health over 7d |
| `mcp.auth_reject_rate` | % POST /mcp no-auth → 401 (should be ~100%) |
| `mcp.handshake.success` | % authenticated initialize+list_tools in CI |
| `mcp.latency.health_p95` | p95 seconds for /health |

## 2026-09-21 external probe summary

- Five consecutive GET `/health`: **200**, ~60–85ms
- Five consecutive POST `/mcp` (no auth): **401**, ~62–88ms
- **No cold-start failure observed** in sample (service was warm)

Directory uptime complaints are often **probe incompatibility** (expecting 200 on `/mcp` without auth).
