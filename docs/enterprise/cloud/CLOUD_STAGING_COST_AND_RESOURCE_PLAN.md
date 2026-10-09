# Cloud staging — cost and resource plan (Owner Gate 1)

**M6 SHA:** `ee6e4a26becf7e89a933202651fba3b4e7a8176d`  
**Pricing:** [Hetzner 15 Jun 2026 adjustment](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) — **EUR excl. VAT** unless noted.  
**Tax:** VAT/GST depends on billing account and region — **not assumed** below.

## Mandatory staging SKUs (official)

| Resource | SKU | EUR/mo ex VAT | Source |
|----------|-----|---------------|--------|
| SaaS | CX33 | 8.49 | Price adjustment table |
| PostgreSQL | CX33 | 8.49 | Same |
| Execution | CX23 | 5.49 | Same |
| NAT / management | **CX23** | 5.49 | Cheapest x86 tier with enough CPU for NAT + SSH; 2 vCPU / 4 GB sufficient for staging jump + masquerade |
| Primary IPv4 (NAT only) | — | **0.50** | [Primary IPs](https://docs.hetzner.com/cloud/servers/primary-ips/overview/) |
| Load balancer | LB11 | **7.49** | Price adjustment — Load Balancers |
| Private network / server firewalls on NAT | — | 0.00 | [Firewalls](https://docs.hetzner.com/cloud/firewalls/overview/) free |

**Mandatory Hetzner subtotal:** **35.95 EUR/mo ex VAT**

(CX33×2 + CX23×2 + Primary IPv4 + LB11 = 16.98 + 10.98 + 0.50 + 7.49)

## Optional

| Item | EUR/mo ex VAT | Notes |
|------|---------------|--------|
| Hetzner backups (×4 servers) | **5.592** | 20% of server SKUs only: 0.20 × (8.49+8.49+5.49+5.49). Not 20% of the 35.95 subtotal. |
| Volume 20 GB | ~1.14 | €0.0572/GB-mo (adjustment table) |
| Cloudflare **Pro** | ~€20 | **Optional only** — not required for AOP / Full (strict) / Universal SSL ([AOP docs](https://developers.cloudflare.com/ssl/origin-configuration/authenticated-origin-pull/)) |
| R2 | ~$0 staging | [R2 free tier](https://developers.cloudflare.com/r2/pricing/) |

## Cloudflare plan

- **Free:** sufficient for proxied DNS (Gate 2), **Full (strict)**, Universal SSL, **AOP** (global/zone/per-hostname).
- **Pro:** only if we adopt a **named** paid capability (e.g. specific advanced rate-limit ruleset) — document feature before upgrade.

---

## OWNER GATE 1 — STOP

> **APPROVE STAGING CLOUD PROVISIONING**

No `terraform apply` until approved.
