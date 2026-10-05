# Backup and restore evidence

**Status:** PENDING LIVE STAGING (Owner Gate 1 not yet approved).

## Intended pipeline

1. `scripts/backup-postgres.sh` → local `*.sql.gz` on authority host.
2. `scripts/cloud/upload-backup-to-r2.sh` → Cloudflare R2 bucket `whitepact-staging-backups-<account>` (private).
3. Checksum: `sha256sum` recorded in backup manifest JSON.
4. Retention: 30 days staging (configurable `RETENTION_DAYS`).

## Restore drill (required before Antigravity cloud PASS)

| Step | Evidence field |
|------|----------------|
| Download object from R2 | Object key, size, sha256 |
| Restore to disposable Postgres | `scripts/restore-postgres.sh` |
| Verify migration version | App `/readyz` + schema query |
| Row-count sanity | Synthetic tenant counts |
| App smoke | Login + governed read-only action |
| RTO/RTO measured | Wall-clock minutes |

## Pre-provision baseline

- Scripts exist in repo: `scripts/backup-postgres.sh`, `scripts/restore-postgres.sh`.
- R2 upload wrapper: `scripts/cloud/upload-backup-to-r2.sh` (requires credentials at runtime).
