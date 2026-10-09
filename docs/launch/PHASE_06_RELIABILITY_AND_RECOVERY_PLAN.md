# Phase 6 — Reliability and recovery plan

**These targets are proposals for the founder. They are not measurements and not customer commitments.**

## Proposed targets (not approved, not measured)

| Target | Proposal | Why it is not a promise |
|--------|----------|-------------------------|
| Availability | Discuss 99.9% monthly for the API only after a staging soak | No soak was run |
| RPO | 24 hours until a restore drill passes, then reconsider 1 hour | No live backup was taken |
| RTO | 4 hours for staging restoration | No timed restore was performed |

Do not print these numbers on the website or in a contract.

## What already exists in source

- `scripts/backup-postgres.sh` and `scripts/restore-postgres.sh`
- Alembic migrations and historical upgrade tests
- Health and readiness behavior covered by dashboard and deployment docs
- `scripts/release_evidence_check.py`, which refuses GO when `backup.restore.live` has no accepted live evidence

## Incident severity proposal

| Severity | Meaning | Engineering action |
|----------|---------|--------------------|
| 1 | Authority bypass, cross-tenant read, or active data loss | Stop new execution grants. Page the owner. Do not publish a workaround that disables the gateway. |
| 2 | Staging or production unavailable, backups failing | Freeze deploys. Restore only with owner approval. |
| 3 | Single-tenant defect with a deny-safe workaround | Patch forward. Grants stay fail-closed. |
| 4 | Documentation or non-security defect | Schedule normally. |

## Recovery order

1. Revoke grants and agent credentials for the affected tenant.
2. Preserve evidence bundles and database snapshots before repair.
3. Restore into a scratch instance and compare digests.
4. Return traffic only on a pinned SHA whose gateway still denies missing authority.

## Gate

CONDITIONAL as a plan. Live recovery is NOT EXECUTED.
