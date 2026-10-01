# Resource and Cost Approval — Private Staging

**OWNER_APPROVAL_REQUIRED** before any apply or paid Cloudflare upgrade.

Baseline SHA: `caf539bcaa9893d346ce01f6fbc032cf9d1eabc4`

## 1. Hetzner (primary)

| Line item | Spec (staging qualification) | Unit €/mo (indicative) | Qty | Subtotal €/mo |
|-----------|------------------------------|------------------------|-----|----------------|
| SaaS server | CX22 | ~5.83 | 2 | ~11.66 |
| Authority + PostgreSQL | CX22 | ~5.83 | 1 | ~5.83 |
| Execution worker | CX22 | ~5.83 | 1 | ~5.83 |
| Load balancer | LB11 | ~5.39 | 1 | ~5.39 |
| Primary IPv4 (if enabled) | per server | ~0.50–1.00 | 0–4 | ~0–4 |
| Private network | — | 0 | 1 | 0 |
| Volume backup (optional) | per GB | variable | — | ~2–10 |

**Estimated Hetzner recurring (qualification BOM):** **€28–35/mo** at CX22 + LB11 (verify [Hetzner pricing](https://www.hetzner.com/cloud)).

**Short qualification window (14 days):** prorated **~€15–20** if destroyed on schedule.

## 2. Cloudflare

| Line item | Notes | Est. $/mo |
|-----------|--------|-----------|
| Zone (existing) | DNS only | $0–20 (plan) |
| Access | Per-seat pricing; WebAuthn via supported IdP | **verify plan** |
| Tunnel (optional) | Origin without public SaaS IP | $0 + seats |
| R2 storage | $0.015/GB-mo + Class A/B ops | ~$1–5 staging |
| R2 egress | Often free to CF edge; verify | variable |

**Do not assume Business/Enterprise features** until account is checked.

## 3. Google Cloud (optional — not on production critical path)

| Line item | Use | Status |
|-----------|-----|--------|
| GCE micro | DR drill target | **BLOCKED_PROVIDER_ACCESS** until credits verified |
| GCS bucket | Secondary backup | Optional |

Production must **not** depend on GCP credits.

## 4. Monitoring / secrets (staging)

| Item | Approach | Cost |
|------|----------|------|
| Auth / audit logs | App + PostgreSQL + CF Access logs | Included in compute |
| External secrets | GitHub Environment secrets + manual vault | $0 |
| Paid SIEM | Not required for staging | $0 |

## 5. Summary table for founder approval

| | Amount |
|---|--------|
| **Monthly recurring (staging qualification BOM)** | **~€30–45** + Cloudflare plan/seats + R2 usage |
| **14-day qualification burn (estimate)** | **~€20–35** + CF/R2 variable |
| **Variable risk** | Egress, R2 ops, extra IPv4, CF seat count |
| **Deletable after test** | All Hetzner servers, LB, staging DNS records, R2 objects |
| **May remain billable after shutdown** | CF zone (if kept), R2 minimum storage until purge |

## 6. Account permissions required (no credentials in repo)

| Provider | Scoped permission |
|----------|-------------------|
| Hetzner | Project API token: servers, networks, firewalls, LB |
| Cloudflare | Zone DNS edit; Access apps; R2 bucket (backup operator token separate) |
| GitHub | Environment secrets for staging workflow only |

## 7. Credit verification

- GCP: run `scripts/infrastructure/gcp-account-readonly-check.sh` with owner account — **not verified** in CI.
- Hetzner/Cloudflare: **no credits assumed**.

See `ROLLBACK_AND_RESOURCE_CLEANUP.md` for teardown verification.
