# Cloud staging — cost and resource plan (Owner Gate 1)

**M6 qualified SHA:** `ee6e4a26becf7e89a933202651fba3b4e7a8176d`  
**Status:** PLAN ONLY — **no billable resources created** by this document.

Pricing sources (verify before spend):

- Hetzner Cloud: [Hetzner price adjustment (official)](https://docs.hetzner.com/general/infrastructure-and-availability/price-adjustment/) — EUR monthly caps, excl. VAT.
- Cloudflare R2: [R2 pricing](https://developers.cloudflare.com/r2/pricing/) — USD.
- Cloudflare plan features: [Cloudflare plans](https://www.cloudflare.com/plans/).

> **Note:** Hetzner adjusted cloud prices effective **2026-04-01**. Figures below use **post-adjustment EUR** from the official table unless marked legacy.

---

## A. Minimum serious staging topology (recommended for qualification)

| Resource | Qty | Type / SKU | EUR/mo (ex VAT) | Purpose |
|----------|-----|------------|-----------------|---------|
| Hetzner Cloud server | 1 | CX33 (4 vCPU, 8 GB, 80 GB) | **6.49** | SaaS / API / MCP (docker-compose or systemd) |
| Hetzner Cloud server | 1 | CX33 | **6.49** | PostgreSQL (private NIC only) |
| Hetzner Cloud server | 1 | CX23 (2 vCPU, 4 GB) | **3.99** | Isolated execution tier |
| Load balancer | 1 | LB11 | **7.49** | Public origin; health checks → `/livez` |
| Private network | 1 | — | **0.00** | 10.42.0.0/16 |
| Firewalls | 3 | — | **0.00** | Tier separation (module defaults) |
| Primary IPv4 (LB) | 1 | — | **0.00** | Included with LB |
| Server backups (optional) | 3 | ~20% of server | **~3.60** | Automated Hetzner backups (optional) |
| Cloudflare | 1 | Free or Pro zone | **0–20** | DNS/WAF/TLS (Pro if advanced WAF rulesets required) |
| R2 bucket | 1 | Standard storage | **~0–2** | Off-site backups (10 GB-month free tier) |

**Estimated Hetzner subtotal:** **€24.46/mo** (+ optional backups **~€3.60**)  
**Estimated Cloudflare + R2:** **€0–22/mo** (usage-dependent)  
**Expected minimum monthly spend (staging):** **~€25–50/mo** ex VAT.

Terraform root: `infra/terraform/environments/staging/` (single SaaS + authority + execution + LB).

---

## B. Recommended production topology (launch)

| Resource | Qty | Type | EUR/mo (indicative) | vs staging |
|----------|-----|------|---------------------|------------|
| SaaS nodes | 2 | CX32 or CPX32 | **16.98–27.98** | HA app tier |
| Authority (Postgres) | 1 | CX42+ | **11.99+** | Larger disk/IOPS |
| Execution | 2 | CX23+ | **7.98+** | HA workers |
| LB11 | 1 | — | **7.49** | Same pattern |
| R2 + retention | — | 50–200 GB | **variable** | Longer retention |
| Cloudflare Pro/Business | 1 | — | **20–200** | WAF/rate limits |

**Failure domains:** staging accepts single-node SaaS; production requires LB + ≥2 SaaS, monitored backups, defined RPO/RTO.

---

## Cloudflare / R2 usage (staging)

| Item | Assumption | Cost |
|------|------------|------|
| R2 storage | 5–30 GB backup objects | First 10 GB-month free; then **$0.015/GB-month** |
| Class A ops | Daily backup upload | Usually within **1M/mo** free tier |
| Egress from R2 | Restore drills | **$0** egress per Cloudflare docs |

---

## Exact API actions requiring owner approval (Gate 1)

| Provider | Action | Billable |
|----------|--------|----------|
| Hetzner | `POST /servers`, networks, firewalls, load_balancers | Yes |
| Hetzner | Attach volumes, enable backup addon | Yes |
| Cloudflare | Create R2 bucket, API token, (optional) DNS record | R2/storage yes; DNS record only after Gate 2 |
| Cloudflare | Authenticated Origin Pull, WAF rulesets | Plan-dependent |

**Expected staging lifetime:** 30–90 days for Antigravity qualification, then resize or destroy.

---

## OWNER GATE 1 — STOP

> **APPROVE STAGING CLOUD PROVISIONING**

Cursor must **not** run `terraform apply`, create Hetzner servers, create R2 buckets, or mutate DNS until the owner explicitly approves this plan and provides API tokens via a secure channel (not Git).
