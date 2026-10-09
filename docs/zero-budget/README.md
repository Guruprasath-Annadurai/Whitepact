# Zero-budget development environment

**Status: authorization gate CLOSED.** Nothing in this package was provisioned.
This is not staging GO and it is not production readiness.

Owner approval covered preparation only: no paid provisioning, no production
deployment, no DNS modification, and no launch. `infra/zero-budget/oci/apply.sh`
exits 2 on every invocation. Terraform's authorization precondition stays
`HOLD`.

Enterprise cloud staging remains **BLOCKED — UNSAFE TO PROVISION**
(`docs/phase0/ANTIGRAVITY_CLOUD_PRESTAGING_AUDIT_REGISTER.md`, findings
CLOUD-AG-01 through CLOUD-AG-07). This package does not remediate those
findings. Pull requests **#173** and **#174** continue as separate security
reconciliation and are not modified here.

## Budget

Documented out-of-pocket budget: **$0**.

Budget alerts, credit balances, and free-tier labels do **not** guarantee
zero charges. A card on file, an upgraded billing account, a shape outside
the allowlist, or a resource left running after a trial can still bill.
The controls below reduce that chance. They are not a promise.

## What was verified from this repository

| Fact | Evidence |
|---|---|
| Public GitHub repository | `gh repo view` reports `visibility: PUBLIC` for `Guruprasath-Annadurai/Whitepact` |
| CI already runs PostgreSQL 16 | `.github/workflows/ci.yml` service `postgres:16-alpine` on port 55432 |
| CI does not require a persistent cloud | test, wheel, helm, scan, and accessibility jobs use GitHub-hosted `ubuntu-latest` |
| Single-VM floor | `DEPLOY_RUNBOOK.md`: 2+ vCPU and 4 GB RAM for Postgres, Redis, dashboard, and MCP at low traffic. That is below `SLA.md`'s hosted recommendation |
| Dashboard / MCP requests | `helm/rai-governance/values.yaml`: dashboard 250m/256Mi request, 1 CPU/1Gi limit; MCP 100m/128Mi request, 500m/512Mi limit. Chart defaults are 2 replicas each |
| Isolation sandbox | `src/responsibleai/isolation/models.py`: 256 MB, 0.5 CPU, 32 PIDs, `--network=none`. Compliance profile: 512 MB, 1 CPU, 64 PIDs |
| Production database | PostgreSQL via `WHITEPACT_DATABASE_URL` / `DATABASE_URL` / `RAI_DATABASE_URL`. SQLite is refused when production mode is on. Alembic head is 0061. No `CREATE EXTENSION` in migrations |
| Redis | Optional for one replica. Required to exercise multi-replica rate limits. Not an authority store |
| Pinned images include arm64 | Index digests in `Dockerfile` and `docker-compose.prod.yml` advertise `linux/arm64/v8` (inspected 2026-10-09). The WhitePact image was not built on ARM in this pass |

## Documents

1. [Provider eligibility checklist](./01-provider-eligibility-checklist.md)
2. [Infrastructure architecture](./02-infrastructure-architecture.md)
3. [Exact free-tier resource allocation](./03-free-tier-resource-allocation.md)
4. [Security boundary analysis](./04-security-boundary-analysis.md)
5. [Deployment and rollback](./05-deployment-and-rollback.md) — procedures only; not authorized to execute
6. [Cost and expiry risk register](./06-cost-and-expiry-risk-register.md)
7. [Antigravity review handoff](./07-antigravity-review-handoff.md)

Infrastructure code: `infra/zero-budget/`.

## Gate

Do not run `terraform apply`, `terraform destroy`, or an OCI/GCP/AWS/Neon/Cloudflare create API against this design until all of the following exist:

- Owner authorization that explicitly names this package and the $0 budget
- Independent Antigravity review of this handoff, with a recorded verdict
- A reviewed change that replaces the hard failure in `apply.sh`
- A recorded free-tier eligibility check for the actual account (home region, remaining credits, billing-account type)
- Confirmation that no production DNS name is being changed

Until then the only supported commands are `preflight.py --self-test`, `terraform fmt -check`, `terraform init -backend=false`, and `terraform validate`.
