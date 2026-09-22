# MCPBeat / directory probe investigation (2026-09-22)

**Classification:** `AUTHENTICATION_MISMATCH` (primary) with `MIXED_CAUSE` (cold start / timeout possible)

## Live evidence (whitepact-mcp-http.onrender.com)

| Check | Result |
|-------|--------|
| DNS / TLS | Resolves; TLS succeeds |
| `GET /health` | **200** ~90–100ms warm; JSON `tools: 30`, version line not in health body |
| `GET /.well-known/mcp/server-card.json` | **200**; `serverInfo.version` **1.2.6**; **30** tools; `test.counter.increment` **absent** |
| `POST /mcp` unauthenticated `initialize` | **401** JSON `{"error":"unauthorized",...}` — not JSON-RPC envelope |

## Why monitors may under-report uptime

1. **Auth expectation:** Production `/mcp` requires Bearer/OAuth. Probes that treat any non-JSON-RPC 401 as hard failure will score down even when the service is healthy behind auth.
2. **Protocol mismatch:** Unauthenticated `initialize` does not receive MCP-shaped JSON-RPC errors; directory tools expecting JSON-RPC success on `/mcp` without credentials will fail.
3. **Cold start:** Render free/low-tier spin-up can add latency; not measured as sustained outage in this pass.
4. **Historical measurements:** Prior ~24% uptime may include periods of real outage, auth mismatch, or both — **not proven solved** by this investigation.

## Security constraints (unchanged)

- Do **not** add unauthenticated MCP bypass for monitors.
- Do **not** weaken governance or tenant isolation for directory scores.

## Recommended follow-up (post combined RC)

- Scoped authenticated monitor credential (read-only, no mutation).
- Observe MCPBeat over 7–14 days after any deploy change.
- Optional: document that `/health` and server-card are the supported unauthenticated liveness/discovery surfaces.

**Uptime solved:** **NOT CLAIMED**
