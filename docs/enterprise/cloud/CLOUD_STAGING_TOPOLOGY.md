# Cloud staging topology (final Gate 1)

```text
                          ┌─ private PostgreSQL (CX33)
Internet → Cloudflare     │
         → LB11 TCP :443 → private SaaS (CX33, Caddy/Nginx + AOP)
                          │
                          └─ private execution (CX23)

Private SaaS / Postgres / Execution
        ↓  (hcloud_network_route 0.0.0.0/0)
Dedicated NAT/management (CX23 + Primary IPv4)
        ↓
Internet (updates, R2, registry, telemetry, email)

Operator /32
        ↓ SSH (or WireGuard — TBD if dynamic IP)
NAT/management gateway
        ↓ private SSH
Internal nodes
```

**Staging hostname (not created):** `staging.whitepact.com`

**NAT is not in the inbound app path** (Cloudflare → LB → SaaS only).
