# Cloud cost model and credits (source-linked)

**Status:** VERIFIED (pricing pages referenced); **OWNER_APPROVAL_REQUIRED** for monthly ceiling.

All figures are **estimates** from public pricing at documentation time. Re-verify before spend.

## Hetzner Cloud (primary recurring)

| Item | Dev (example) | Initial prod (example) | Source |
|------|---------------|------------------------|--------|
| CX22 server ×1 saas | ~€5.83/mo | — | https://www.hetzner.com/cloud |
| CX22 ×2 saas + CX32 authority + CX22×2 exec | — | ~€45–55/mo compute | same |
| LB11 load balancer | ~€5.39/mo | ~€5.39/mo | Hetzner LB pricing |
| Private network | €0 | €0 | Included |
| Volume backup (optional) | per GB | per GB | Hetzner volume pricing |

**Development-only:** single-node module count in `environments/development` — label `cost_tier = dev-minimum`.  
**Production:** `environments/production` uses larger types; isolation adequate for security claims only when owner approves sizing.

## Cloudflare

| Item | Notes | Source |
|------|--------|--------|
| Free / Pro / Business | WAF and rate limits vary by plan | https://www.cloudflare.com/plans/ |
| R2 storage | $0.015/GB-month (verify current) | https://developers.cloudflare.com/r2/pricing/ |
| Egress from R2 | Often free to Cloudflare; verify | R2 docs |

Backup operator credentials must be **separate** from application admin.

## Google Cloud (optional, credit-funded)

| Item | Notes |
|------|--------|
| GCE staging | Shut down without Hetzner impact |
| GCS secondary backup | Optional bucket in `gcp-staging-optional` module |
| Egress cross-cloud | Hetzner → GCS transfer fees apply |

**Credits:** Do not treat advertised startup credits as available. Verify in billing console via `scripts/infrastructure/gcp-account-readonly-check.sh` (**OWNER_APPROVAL_REQUIRED** for account access).

### Budget alerts (not universal hard caps)

Terraform module documents budgets at 50% / 80% / 100% of owner-approved USD limit. GCP billing disable automation is **not** enabled by default — use labeled disposable resources + documented shutdown runbook.

## Scenarios

| Profile | Monthly recurring (ex-GCP) | GCP |
|---------|---------------------------|-----|
| Minimum dev IaC | ~€15–25 | $0 |
| Initial production | ~€60–90 + CF plan + R2 | Credits only if verified |
| Scaled production | + larger CX/CPX, more exec nodes | Staging only |

## FinOps controls implemented

- Environment labels on all Terraform resources  
- Separate dev/prod tfvars examples  
- `DRY_RUN=1` default on backup example script  
- No paid resources created by this repository pass
