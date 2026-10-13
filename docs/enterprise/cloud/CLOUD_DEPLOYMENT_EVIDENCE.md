# Cloud deployment evidence

## Pre-flight audit (2026-10-05)

| Area | Repo state | Gap |
|------|------------|-----|
| Terraform Hetzner | `whitepact-hetzner-foundation` + NAT route | Private nodes: **host nftables**; **hcloud_firewall only on NAT**; **not applied** |
| Terraform Cloudflare | `infra/terraform/modules/cloudflare-edge` | DNS stub; no apply |
| GCP optional | `gcp-staging-optional` | Out of scope per architecture lock |
| Docker prod stack | `docker-compose.prod.yml` | Postgres+Redis not host-exposed |
| Backup | `scripts/backup-postgres.sh` | No R2 upload until credentials |
| Restore | `scripts/restore-postgres.sh` | Live drill pending |
| CI deploy | `.github/workflows/deploy-staging-manual.yml` | Manual SHA dispatch |
| Origin static tests | `tests/test_m4_cloud_origin_static.py` | Live bypass pending |
| Migrations | Alembic/SQL in repo | Run on staging DB post-provision |
| Helm | `helm/rai-governance/` | CI lint only; not default staging |

## Owner Gate 1 — pre-apply plan summary (2026-10-05)

**Branch:** `cursor/whitepact-production-cloud-staging-f7a9`  
**Terraform root:** `infra/terraform/environments/staging` (module `whitepact-hetzner-foundation`, `enable_nat_gateway=true`, `saas_public_ipv4=false`)

| # | Planned `CREATE` (15 resources) |
|---|----------------------------------|
| 1 | `hcloud_network.private` |
| 2–5 | `hcloud_network_subnet` ×4 (saas, authority, execution, mgmt) |
| 6 | `hcloud_network_route.default_via_nat` (`0.0.0.0/0` → NAT private IP) |
| 7 | `hcloud_firewall.nat_gateway` (SSH :22 from `admin_cidr_allowlist` only) |
| 8–11 | `hcloud_server` ×4: `wp-staging-nat-1` (public IPv4), `wp-staging-saas-1`, `wp-staging-authority-1`, `wp-staging-exec-1` (no public IPv4) |
| 12–15 | `hcloud_load_balancer` + network + target + TCP :443 service (HTTP `/livez` :8765 health check) |

**Not in plan:** Cloudflare DNS/R2, `hcloud_firewall.saas_public` (count 0), extra servers/volumes/backups, GCP modules.

**Projected Hetzner subtotal:** **€35.95/mo ex VAT** (mandatory SKUs per `CLOUD_STAGING_COST_AND_RESOURCE_PLAN.md`). LB11 public IPv4 is included in LB pricing; no extra server Primary IPv4 beyond NAT.

### Pre-apply owner checks (code + verifier; live `terraform plan` pending API token)

| Check | Result |
|-------|--------|
| 1. No unexpected resources | **PASS (static)** — only rows above; no Cloudflare/terraform DNS |
| 2. Monthly cost within €35.95 (cap €45) | **PASS (static)** — mandatory subtotal €35.95; no optional backups/volumes in TF |
| 3. SaaS / PostgreSQL / execution: no public IPs | **PASS (static)** — `ipv4_enabled=false` on authority, execution, staging SaaS |
| 4. Only NAT server has Primary IPv4 | **PASS (static)** — NAT `ipv4_enabled=true`; other servers false |
| 5. PostgreSQL private-only | **PASS (static)** — authority tier private network only; no DB listener in TF public path |
| 6. Production `whitepact.com` DNS untouched | **PASS** — no Cloudflare provider in staging root; no DNS resources applied |

Automated verifier (run after `terraform plan -out=tfplan && terraform show -json tfplan > plan.json`): `scripts/cloud/staging-preapply-verify.sh plan.json`.

### Provisioning status

| Item | Status |
|------|--------|
| `HCLOUD_TOKEN` / operator `/32` in agent environment | **Not present** — `terraform apply` not executed |
| Hetzner resources created | **None** |
| Production DNS | **Unchanged** |
| Engineering status | **Gate 1 approved — provisioning blocked on secure credentials** (not `CLOUD_STAGING_INFRASTRUCTURE_PROVISIONED`) |

Configure `HCLOUD_TOKEN` and `TF_VAR_admin_cidr_allowlist` (and local `terraform.tfvars` from example) via environment secrets, then re-run agent to execute plan → verify → apply → bootstrap.

## Build record (to fill at deploy)

| Field | Value |
|-------|--------|
| Git SHA | `ee6e4a26becf7e89a933202651fba3b4e7a8176d` |
| Container digest | Local build `sha256:2f496e0b1b62c5be3a746f5627cf03bbb487071b7d0a9f058b7d66721702e69e` (not yet pushed to staging registry; set at deploy) |
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
