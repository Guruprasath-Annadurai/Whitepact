# Backup and disaster recovery

**Status:** IMPLEMENTED_NOT_DEPLOYED (tooling + runbooks); Cell B DR **VERIFIED** on disposable PostgreSQL only.

## Backup strategy

| Tier | Method | Encryption | Privilege |
|------|--------|------------|-----------|
| Primary | PostgreSQL logical (`pg_dump`) on authority node | `age` to recipient key | DB backup role only |
| Off-site A | Cloudflare R2 | Client-side before upload | R2 token: `backups/` prefix only |
| Off-site B (optional) | GCS bucket `gcp-staging-optional` | GCS default + CMEK optional | Separate GCP SA |

Integrity: `sha256sum` sidecar per object. Restore verifies hash before `psql`.

## R2 limitations

- Same vendor as edge — document **correlated outage** risk; keep independent GCS copy when credits allow.
- Retention locks: configure per Cloudflare R2 lifecycle rules after owner review.

## Recovery exercises

| Exercise | Status |
|----------|--------|
| 100k+ row logical restore + audit chain | VERIFIED @ Cell B `6210358` (disposable PG) |
| Security-state post-restore | VERIFIED (`b4-enterprise-dr-security-state.json`) |
| Restore to isolated Hetzner recovery VPC | NOT_TESTED — OWNER_APPROVAL |
| RTO/RPO measured on Hetzner | **Not invented** — record after real drill |

## Quarantine after snapshot restore

If backup predates revocations/consumed nonces, **consequential execution must remain fail-closed** until reconciliation (application invariant; Phase 7A tests).

## Commands (engineering)

```bash
# Logical backup (on authority host — not committed)
pg_dump "$DATABASE_URL" | gzip -c > backup.sql.gz

# Example encrypt + dry-run upload
DRY_RUN=1 PGDUMP_URL=... AGE_RECIPIENT=... ./scripts/infrastructure/backup-encrypt-r2.sh.example
```
