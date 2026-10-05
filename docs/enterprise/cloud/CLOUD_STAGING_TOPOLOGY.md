# Cloud staging topology

## Final network topology (Gate 1)

```
                    [ Internet ]
                         |
                 Cloudflare Edge
           (staging.whitepact.com — DNS NOT created yet)
           SSL: Full (strict) + WAF/rate limits (planned)
                         |
              Hetzner LB11 (public IPv4+IPv6)
              TCP :443 → private targets :443
                         |
         +---------------+----------------+
         |               |                |
    SaaS CX33       Authority CX33    Exec CX23
    10.42.1.x       10.42.2.x         10.42.3.x
    Caddy/Nginx     PostgreSQL 16     worker/MCP egress
    AOP + TLS       :5432 private     allowlist egress
    app :8765/:8766
```

## Staging hostname (recommendation only)

**`staging.whitepact.com`** — orange-cloud `A`/`AAAA` → LB IPv4/IPv6 when **Owner Gate 2 (DNS)** approves. **No DNS created in this phase.**

## Artifact pinning

| Field | Value |
|-------|--------|
| Source SHA | `ee6e4a26becf7e89a933202651fba3b4e7a8176d` |
| Tree | `cbd8ba8678448a4164681ac47e31dc582c5c7947` |
| Image | `whitepact@sha256:…` built from Dockerfile at this SHA |

## Administrative SSH

- Variable `admin_cidr_allowlist` in `terraform.tfvars` — **operator `/32` only** (example placeholder `203.0.113.10/32` in `terraform.tfvars.example`).
- **Never** `0.0.0.0/0` for SSH.
- Alternative: WireGuard on SaaS bastion (document if operator IP is dynamic) — not provisioned until Gate 1.
