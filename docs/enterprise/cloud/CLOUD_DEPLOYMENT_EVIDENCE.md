# Cloud deployment evidence

## Pre-flight audit (2026-10-05)

| Area | Repo state | Gap |
|------|------------|-----|
| Terraform Hetzner | `infra/terraform/modules/whitepact-hetzner-foundation` | Staging root added; **not applied** |
| Terraform Cloudflare | `infra/terraform/modules/cloudflare-edge` | DNS stub; no apply |
| GCP optional | `gcp-staging-optional` | Out of scope per architecture lock |
| Docker prod stack | `docker-compose.prod.yml` | Postgres+Redis not host-exposed |
| Backup | `scripts/backup-postgres.sh` | No R2 upload until credentials |
| Restore | `scripts/restore-postgres.sh` | Live drill pending |
| CI deploy | `.github/workflows/deploy-staging-manual.yml` | Manual SHA dispatch |
| Origin static tests | `tests/test_m4_cloud_origin_static.py` | Live bypass pending |
| Migrations | Alembic/SQL in repo | Run on staging DB post-provision |
| Helm | `helm/rai-governance/` | CI lint only; not default staging |

## Build record (to fill at deploy)

| Field | Value |
|-------|--------|
| Git SHA | `ee6e4a26becf7e89a933202651fba3b4e7a8176d` |
| Container digest | TBD at build |
| Config version | staging tfvars hash TBD |
| Migration version | TBD after `alembic upgrade head` |

## Live tests (pending Gate 1)

- [ ] Governed action E2E
- [ ] MCP matrix on hosted endpoint
- [ ] Cross-tenant assault (2 orgs)
- [ ] Revocation on live keys
- [ ] DB failure scenarios
- [ ] Origin bypass negative test
- [ ] Restore from R2
