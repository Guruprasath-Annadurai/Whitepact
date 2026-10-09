# Cloud network trust boundary

## Zones

| Zone | Trust | Ingress | Egress |
|------|-------|---------|--------|
| Cloudflare edge | Untrusted Internet | Public HTTPS | To origin (TLS, Full strict) |
| Hetzner LB | Public entry; **no TLS termination in staging** | TCP :443 from Internet | TCP passthrough → SaaS :443 |
| Origin reverse proxy (Caddy/Nginx) | Trust boundary for AOP | TLS :443 from LB private IP only (firewall) | HTTP to app :8765/:8766 |
| SaaS application | Trusted app tier | Not directly public | Postgres, Redis, telemetry |
| Authority / Postgres | High trust data | 5432 from SaaS + execution subnets only | Documented HTTPS (updates, R2 API) |
| Execution | Isolated | SSH admin only | Allowlisted upstream HTTPS + Postgres admission |

## Header trust

- Application must **not** treat `X-Forwarded-For` / `CF-Connecting-IP` as authoritative unless the **network path** already restricts clients to Cloudflare or the load balancer.
- MCP HTTP: `RAI_MCP_HTTP_TRUST_FORWARDED` / `trust_forwarded` defaults **off** (`src/responsibleai/mcp/server.py`).
- Enable forwarded trust only on interfaces bound to private LB listeners after origin hardening.

## Admin access

- SSH: key-based, `admin_cidr_allowlist` in Terraform (no password auth).
- Optional: WireGuard/Tailscale on SaaS bastion — justify if operator IP is dynamic.

## Ports (staging target)

| Port | Listener | Public |
|------|----------|--------|
| 443 | LB → origin | Via Cloudflare only |
| 8765 | Dashboard | Private only |
| 8766 | MCP HTTP | Private only |
| 5432 | PostgreSQL | **Never** public |
| 22 | SSH | Admin CIDR only |
