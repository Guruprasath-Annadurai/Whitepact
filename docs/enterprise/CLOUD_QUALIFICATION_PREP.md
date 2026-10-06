# Cloud qualification prep package (static)

**Status:** PLAN / DOCUMENTATION ONLY — not deployed cloud readiness.

## Scope

| Component | Repo path | Static action |
|-----------|-----------|---------------|
| Hetzner / compute | `infra/terraform/**` | `terraform validate`, fmt |
| Cloudflare / DNS | modules + docs | No DNS mutation |
| R2 / object storage | terraform stubs | Plan-only |
| GCP staging/DR | documented assumptions | No provision |
| LB / firewall / origin | `test_m4_cloud_origin_static.py` | Policy tests |
| Backup / restore | runbooks + `test_restore_*` | Engineering evidence |
| IAM / secrets / egress | terraform variables docs | No prod secrets |
| State / env separation | `infra/terraform/README.md` | Review |

## Deliverables for future Antigravity cloud audit

- Architecture diagram (in README / ws5 docs)
- Trust boundaries (public edge vs origin vs data plane)
- Threat model summary (link from `FINAL_AUTHORITY_PATH_PROOF.md`)
- Secret model (env vars, no committed secrets — Gitleaks CI)
- DR assumptions (RPO/RTO placeholders — measure before claim)

## Forbidden

`terraform apply`, production DNS, paid provisioning, production secret rotation.
