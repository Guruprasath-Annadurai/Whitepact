# Backup & Restore Runbook

## Backup (Postgres)

```bash
# From repo root with docker-compose.prod.yml stack running
./scripts/backup-postgres.sh
```

Store artifacts off-system with encryption at rest. Record SHA-256 of backup file in change ticket.

## Restore (destructive)

```bash
./scripts/restore-postgres.sh /path/to/backup.sql.gz
```

**Warning:** drops and recreates the database.

## Post-restore (mandatory)

1. Confirm restore admission gate state: `GET /api/restore/status`
2. Run reconciliation: `POST /api/restore/reconcile` (operator auth required in hosted deployments)
3. Verify migration head matches application: Alembic `0061_*` for current main
4. Run smoke tests: health, auth, single governance evaluate, MCP handshake (staging)

## Evidence

Launch Cell B has **not** yet attached a machine-readable restore evidence file. When rehearsed, store under `docs/production/evidence/restore-YYYYMMDD.json` (gitignored secrets; commit only metadata).

## What NOT to do

- Do not serve production traffic while gate is `RESTORE_PENDING`
- Do not skip reconciliation to “save time”
- Do not restore production backups into unencrypted dev SQLite
