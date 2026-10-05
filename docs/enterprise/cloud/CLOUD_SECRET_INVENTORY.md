# Cloud secret inventory (types only)

## Application / data plane

| Type | Where |
|------|--------|
| `POSTGRES_PASSWORD` | Authority host env |
| `REDIS_PASSWORD` | SaaS host |
| App signing / session / CSRF | SaaS host |

## Origin TLS (reverse proxy on SaaS)

| Type | Holder |
|------|--------|
| Origin **server certificate** (leaf) | SaaS Caddy/Nginx |
| Origin **server private key** | SaaS Caddy/Nginx only |

## Cloudflare Authenticated Origin Pull (custom per-hostname)

| Type | Holder |
|------|--------|
| AOP **client certificate + private key** (Cloudflare presents to origin) | **Cloudflare** (uploaded in zone/hostname AOP settings) — **not** on origin |
| AOP **trusted CA / root** to validate client cert | **Origin reverse proxy** only (verify client certificate chain) |

Do **not** place the Cloudflare AOP client private key on the WhitePact origin unless a specific integration explicitly requires it (standard AOP does not).

## Infrastructure

| Type | Holder |
|------|--------|
| `HCLOUD_TOKEN` | CI / operator |
| `CLOUDFLARE_API_TOKEN` | CI (zone-scoped) |
| R2 access key / secret | Authority or SaaS backup job env |
| Operator SSH private key | Operator workstation |
| NAT gateway host keys | Gateway VM |
