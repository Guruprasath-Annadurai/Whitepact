# Origin protection (addresses ORIGIN-LIVE-BYPASS)

**M6 defect:** `ORIGIN-LIVE-BYPASS` — live proof required after deploy.

## TLS / AOP architecture (verified)

Hetzner documents that **HTTPS on the load balancer terminates TLS at the LB** and speaks **HTTP to targets** ([Load Balancer FAQ — protocols](https://docs.hetzner.com/networking/load-balancers/faq/)). That mode **cannot** enforce [Cloudflare Authenticated Origin Pull (mTLS)](https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/) on the application host.

### Approved staging path

```
Internet
  → Cloudflare (proxied, SSL/TLS = Full (strict))
  → Hetzner LB11 public :443  [service protocol = TCP, not HTTPS]
  → SaaS private IP :443      [Caddy or Nginx — TLS termination]
  → validate Cloudflare AOP client certificate (per-hostname custom cert preferred)
  → reverse_proxy → WhitePact :8765 / :8766
```

| Hop | TLS | AOP |
|-----|-----|-----|
| Browser ↔ Cloudflare | Cloudflare edge cert | n/a |
| Cloudflare ↔ Origin | Re-encrypted to origin | Cloudflare presents **client cert** |
| Origin reverse proxy | Terminates TLS; **requires** valid CF client cert | **Enforced here** |
| LB ↔ Origin | **Opaque TCP** passthrough (encrypted blob) | Not visible to LB |

Terraform (staging): `lb_service_protocol = "tcp"`, `lb_listen_port = 443`, `lb_destination_port = 443`; health checks remain **HTTP** to `8765/livez` on the private app port ([FAQ: HTTPS health checks supported](https://docs.hetzner.com/networking/load-balancers/faq/)).

### Security invariant

> A direct TLS client to the Hetzner LB public IPv4 **without** Cloudflare’s authorized client certificate must **fail TLS** at the origin reverse proxy before WhitePact application handlers run.

Proof: `curl -vk https://<lb-ipv4>/` from arbitrary Internet host → handshake failure or 403 **without** reaching `/api/*` governance paths.

### What we do **not** rely on

- `CF-Connecting-IP` / `X-Forwarded-For` alone (spoofable if origin is reachable without network controls).
- Hetzner LB **HTTPS termination** + AOP at app (incompatible — LB strips TLS).

### Proxy Protocol

**Not required** for AOP. Enable Proxy Protocol on LB→target only if the reverse proxy needs original client IP **and** the stack supports it; prefer logging at Cloudflare + app correlation IDs. If enabled, configure only on **TCP** service and trust PROXY headers **only** from the LB private IP.

### Cloudflare AOP configuration

- Prefer **per-hostname** (or zone-level) **custom** AOP certificate for `staging.whitepact.com` (not global shared cert only).
- SSL mode: **Full (strict)** with valid origin certificate (Let’s Encrypt DNS-01 or Cloudflare origin cert on Caddy).
- AOP incompatible with **Cloudflare Tunnel** for the same hostname — do not mix tunnel + AOP on one origin path.

### Hetzner LB source-IP allowlisting — honest answer

- [Hetzner Cloud Firewalls](https://docs.hetzner.com/cloud/firewalls/overview/) apply to **Cloud Servers**, not to Load Balancer resources as a first-class attachment in our module.
- There is **no documented Cloudflare-IP allowlist on the LB product itself** in Hetzner docs; **do not claim** LB ingress filtering by Cloudflare CIDR unless verified in Console/API at apply time.
- Defense is **TLS + AOP at origin**, plus keeping SaaS nodes **without public IPv4** (only LB is Internet-facing).

### Optional hardening (post-staging)

- Restrict SaaS nftables/firewall: allow **443/tcp only from LB private IP** (`10.42.1.5` in default module layout).
- Cloudflare **WAF / rate limits** on `staging.whitepact.com` (edge), not origin IP headers.
