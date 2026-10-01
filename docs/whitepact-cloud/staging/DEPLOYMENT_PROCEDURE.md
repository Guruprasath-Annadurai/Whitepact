# Deployment Procedure — Private Staging (plan only)

SHA: `caf539b` — **no `terraform apply` in this document’s execution.**

## Phase 9 — Deployment completeness audit

| Capability | Repository state | Status |
|------------|------------------|--------|
| Terraform foundation (network, firewalls, servers, LB) | `infra/terraform/modules/whitepact-hetzner-foundation` | **VERIFIED_SIMULATION** |
| `terraform validate` | `scripts/infrastructure/validate-terraform.sh` | **VERIFIED_AUTOMATED_TESTS** |
| PostgreSQL migrations (cloud tables 0062–0063) | Alembic | **VERIFIED_AUTOMATED_TESTS** |
| Application container / systemd deploy | Not fully automated in repo | **AWAITING_LIVE_STAGING** |
| Secrets injection at runtime | Documented; no K8s secret operator | **OWNER_APPROVAL_REQUIRED** |
| Host hardening (nftables cloud-init) | Template in module | **VERIFIED_AUTOMATED_TESTS** |
| Monitoring agents | Docs only (`08_SECURITY_MONITORING.md`) | **AWAITING_LIVE_STAGING** |
| Backup scheduling | `scripts/infrastructure/backup-encrypt-r2.sh.example` | **IMPLEMENTED** — **BLOCKED_PROVIDER_ACCESS** |
| Recovery automation | Runbooks in `10_DISASTER_RECOVERY.md` | **AWAITING_LIVE_STAGING** |
| Config validation | Terraform + pytest policy tests | **VERIFIED_AUTOMATED_TESTS** |
| Rollback | `ROLLBACK_AND_RESOURCE_CLEANUP.md` | **IMPLEMENTED** (procedure) |
| Health checks | Dashboard `/` in CI a11y; no staging probe job | **AWAITING_LIVE_STAGING** |

## Preconditions

1. Founder approval recorded (`OWNER_APPROVAL_GATE.md`).
2. `HCLOUD_TOKEN`, Cloudflare tokens, staging signing keys in GitHub **staging** environment only.
3. `admin_cidr_allowlist` set to founder egress / bastion CIDR.
4. Staging subdomain chosen (no production apex changes).

## Sequence (after approval)

1. **Plan:** `cd infra/terraform/environments/development && terraform init && terraform plan -out=staging.plan`
2. **Review plan** against `STAGING_ARCHITECTURE.md` BOM.
3. **Apply** (owner executes): `terraform apply staging.plan`
4. **Bootstrap:** SSH via allowlisted IP; verify cloud-init completed (`nftables` active).
5. **Database:** Run migrations against staging PostgreSQL (`run_migrations_or_raise`).
6. **Enroll founder** via `EmployeeEnrollmentService` (not grant issuance).
7. **Cloudflare Access:** Create staging app; JWKS URI in `AccessGatewayConfig`.
8. **Smoke:** JWT validation + one admin grant issue/consume in staging DB.
9. **Do not** set `PRIVILEGED_EXECUTOR_ENABLED = True` until `ADMIN_EXECUTION_TEST_PLAN.md` passes.

## Validation gates before live tests

```bash
bash scripts/infrastructure/validate-terraform.sh
pytest tests/whitepact_cloud tests/infrastructure/ -q
```

## Rollback

See `ROLLBACK_AND_RESOURCE_CLEANUP.md` — destroy order: LB → servers → network; revoke tokens.
