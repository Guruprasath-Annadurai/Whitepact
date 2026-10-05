# Cloud staging — cost and resource plan (Owner Gate 1)

**M6 qualified SHA:** `ee6e4a26becf7e89a933202651fba3b4e7a8176d`  
**Status:** PLAN ONLY — **no billable resources created** by this document.  
**Pricing effective date:** Hetzner **15 June 2026** adjustment for new orders/rescales ([official table](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/)).

All Hetzner figures below are **EUR, excl. 19% VAT** unless noted. German VAT example uses **19%** ([Primary IP pricing](https://docs.hetzner.com/cloud/servers/primary-ips/overview/) notes excl. VAT).

---

## Official unit prices (staging SKUs)

| Product | Official source | EUR/mo (ex VAT) |
|---------|-----------------|-----------------|
| **CX33** cloud server | [Price adjustment — Germany/Finland cloud](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) | **8.49** |
| **CX23** cloud server | Same | **5.49** |
| **LB11** load balancer | Same document, Load Balancers section | **7.49** |
| **Primary IPv4** (if attached to a server) | [Primary IPs overview](https://docs.hetzner.com/cloud/servers/primary-ips/overview/) | **0.50** each |
| **LB public IPv4** | [Load Balancer overview](https://docs.hetzner.com/networking/load-balancers/overview/) | **Included in LB price** (not billed separately today) |
| **Backups** (optional per server) | [Billing FAQ — Backups](https://docs.hetzner.com/cloud/billing/faq/) | **20%** of that server’s monthly price |
| **Snapshots** (optional) | [Billing FAQ — Snapshots](https://docs.hetzner.com/cloud/billing/faq/) | Per compressed GB-month (see Hetzner cloud pricing / price adjustment **Snapshots** row) |
| **Volumes** (optional) | [Volumes overview](https://docs.hetzner.com/cloud/volumes/overview/) + price adjustment **Volumes** row | Per GB-month (e.g. **€0.0572/GB-mo** post–15 Jun 2026 in official adjustment table) |
| Private network / Hetzner firewalls | [Firewalls overview](https://docs.hetzner.com/cloud/firewalls/overview/) | **0.00** |
| Cloudflare R2 Standard storage | [R2 pricing](https://developers.cloudflare.com/r2/pricing/) | **$0.015/GB-month** (10 GB-month free tier) |

---

## A. Minimum serious staging topology (unchanged shape)

| Resource | Qty | SKU | EUR/mo (ex VAT) | Notes |
|----------|-----|-----|-----------------|-------|
| SaaS + reverse proxy | 1 | CX33 | 8.49 | No public server IPv4 (`saas_public_ipv4=false`) |
| PostgreSQL authority | 1 | CX33 | 8.49 | No public IPv4 |
| Execution | 1 | CX23 | 5.49 | No public IPv4 |
| Load balancer | 1 | LB11 | 7.49 | **TCP :443 passthrough** (see `CLOUD_ORIGIN_PROTECTION.md`) |
| Private network | 1 | — | 0.00 | |
| Firewalls | 3 | — | 0.00 | Server-scoped only |
| Hetzner backups (optional) | 3 | 20% × server | **4.49** | 0.2×(8.49+8.49+5.49) |
| Postgres volume (optional) | 20 GB | Volume | **~1.14** | 20 × €0.0572 (official adjustment) |
| Cloudflare zone | 1 | Free | **0.00** | Pro **~€20/mo** if advanced WAF rulesets required (list price on [cloudflare.com/plans](https://www.cloudflare.com/plans/)) |
| R2 backups | — | — | **~€0–2** | Within free tier for small staging backups |

### Monthly totals (Hetzner + edge)

| Scenario | EUR/mo ex VAT | EUR/mo incl. 19% VAT (DE) |
|----------|---------------|---------------------------|
| **Minimum** (3 servers + LB11, no backups/volumes) | **29.96** | **35.65** |
| **Recommended staging** (+ Hetzner backups on all 3 nodes) | **34.45** | **41.00** |
| **Upper band** (+ 20 GB volume, Cloudflare Pro ~€20) | **~55–58** | **~65–69** |

Cloudflare R2 and USD-priced items excluded from EUR band; typically **&lt;€2** at staging scale.

---

## B. Recommended production topology (launch)

| Resource | Qty | SKU (indicative) | EUR/mo ex VAT |
|----------|-----|------------------|---------------|
| SaaS | 2 | CX33 or CPX32 (13.99) | 16.98–27.98 |
| Authority | 1 | CX43 (15.99) | 15.99+ |
| Execution | 2 | CX23 | 10.98 |
| LB11 | 1 | — | 7.49 |
| Backups + R2 retention | — | — | variable |

Production adds **HA**, larger DB disk, and stricter retention — not required for first staging qualification.

---

## Exact API actions (Gate 1)

Unchanged — no `terraform apply`, no DNS, no R2 bucket until **APPROVE STAGING CLOUD PROVISIONING**.

---

## OWNER GATE 1 — STOP

> **APPROVE STAGING CLOUD PROVISIONING**
