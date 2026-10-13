# Backup and Recovery — Staging Test Plan

SHA: `caf539b`

## Phase 6 — intended staging implementation

| Capability | Artifact | Status |
|------------|----------|--------|
| Encrypted off-site backup | `scripts/infrastructure/backup-encrypt-r2.sh.example` | **IMPLEMENTED** — `DRY_RUN=1` default |
| R2 target | Cloudflare R2 | **BLOCKED_PROVIDER_ACCESS** |
| Auth logging | App + PostgreSQL + CF Access | **AWAITING_LIVE_STAGING** |
| Privileged audit | Grant claims + offboarding steps tables | **VERIFIED_AUTOMATED_TESTS** |
| Firewall alerts | Hetzner / host monitoring | **AWAITING_LIVE_STAGING** |
| Backup deletion protection | Separate R2 API token without delete on app role | **OWNER_APPROVAL_REQUIRED** |

## Tests

| ID | Test | Expected | Status |
|----|------|----------|--------|
| B-01 | Nightly backup job (staging cron) | Object in R2 with age tag | **AWAITING_LIVE_STAGING** |
| B-02 | Backup encryption | Cannot read plaintext without key | **AWAITING_LIVE_STAGING** |
| B-03 | Integrity check (checksum) | Matches source dump | **AWAITING_LIVE_STAGING** |
| B-04 | Restore to **isolated** DB instance | Migrations + row counts match | **AWAITING_LIVE_STAGING** |
| B-05 | Recovery without admin UI | Break-glass SSH + restore script | **AWAITING_LIVE_STAGING** |
| B-06 | Measure RTO/RPO | Record actual times post-drill | **AWAITING_LIVE_STAGING** |
| B-07 | App role cannot delete R2 bucket | 403 on delete API | **AWAITING_LIVE_STAGING** |

## Recovery drill procedure (outline)

1. Take fresh backup with known marker row in `cloud_employees`.
2. Provision **second** temporary CX22 PostgreSQL (or local restore VM).
3. Restore dump; run `alembic current` == head.
4. Verify marker row and grant chain integrity.
5. Destroy restore VM; document elapsed time.

**Do not** run drill until owner approves R2 bucket creation.

## Evidence

Restore log, `pg_restore` exit code, before/after row counts, wall-clock timestamps.
