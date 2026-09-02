# Disaster-Recovery Restore Drill — Evidence

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 16. `SLA.md` states RPO/RTO targets and
`scripts/backup-postgres.sh`/`restore-postgres.sh` exist, but no one had
actually run a restore drill — this document is that drill's real
evidence, not a description of the scripts' intended behavior.

**Date run**: 2026-09-01
**Environment**: local disposable PostgreSQL 17.10 (Homebrew), NOT the
`docker-compose.prod.yml` stack — Docker was not available in this
environment (`docker info` failed: daemon not running). The drill
therefore exercises the exact same underlying mechanism the scripts
wrap (`pg_dump`/`psql` against a real Postgres server, gzip-compressed
plain-format dump) directly, not through the docker-compose wrapper
layer. This is named honestly: the compression, dump format, and
restore commands are identical to what `backup-postgres.sh`/
`restore-postgres.sh` run; the docker-orchestration wrapper (stopping/
starting the `dashboard`/`mcp-http` containers around the restore) was
not itself exercised.

## What was actually done, step by step

1. Created a disposable database (`whitepact_migration_test`) and
   migrated it to head (`alembic upgrade head`, revision `0037`) —
   see `PHASE17_POSTGRES_MIGRATION_VERIFICATION.md` for that step's own
   evidence.
2. Seeded real data through the actual application code (not raw SQL):
   created an organization, an API key, a `REQUIRE_APPROVAL` governed
   action with `purpose="ops.check"` (Phase 5), approved it, and
   consumed it — via `OrgRepository`/`ApprovalRepository`/
   `WhitePactRuntimeGateway`, the same code paths the real app uses.
3. Captured pre-drill row counts: 1 organization, 1 approval
   (`purpose="ops.check"`).
4. Ran a real `pg_dump --format=plain | gzip` — the exact command
   `backup-postgres.sh` runs — producing an 8,156-byte non-empty
   compressed dump.
5. **Simulated the disaster**: `DROP DATABASE whitepact_migration_test`,
   then `CREATE DATABASE whitepact_migration_test OWNER $USER` — a
   genuinely empty, freshly created database, not a copy.
6. Restored via `gunzip -c backup.sql.gz | psql -d whitepact_migration_test`
   — the exact command `restore-postgres.sh` runs (`psql` invocation
   only; the docker-exec wrapper around it was not exercised, per the
   Environment note above).
7. Verified post-restore state:
   - Row counts: 1 organization, 1 approval — identical to pre-drill.
   - The `purpose` column value (`"ops.check"`) survived the round trip
     exactly — proves the Phase 5 migration's new column is covered by
     ordinary `pg_dump`, not something that needs special handling.
   - `alembic_version` still reads `0037` post-restore (schema-tracking
     metadata is itself part of the dump, so a restored database is
     immediately usable without re-running migrations).
   - **Application-level check**: reconnected with the real
     `DatabaseEngine`/`create_engine()` code path (not just raw `psql`)
     and queried the restored organization through it — confirms the
     restored database is not just byte-identical at the SQL level but
     actually usable by the application's own connection/pooling code.
8. Cleaned up the disposable database (`DROP DATABASE`) — nothing from
   this drill persists.

## Result

**PASS.** The backup → simulated total data loss → restore → verify
cycle completed successfully, with zero data loss and zero manual
schema repair needed. The restored database was immediately queryable
by the real application code, not just by raw SQL.

## What this drill does NOT prove (named honestly)

- **Not run against the actual production/staging infrastructure**
  (`docker-compose.prod.yml`, Render-hosted Postgres) — a local
  disposable instance stands in for it. The underlying `pg_dump`/`psql`
  mechanism is identical; the deployment-specific orchestration
  (stopping/restarting `dashboard`/`mcp-http` containers, `.env.prod`
  variable resolution) was not exercised.
- **Not a timed RTO measurement.** `SLA.md` states RTO targets (4h PRO,
  1h ENTERPRISE); this drill did not time itself against those targets
  under realistic data volume or network conditions — it proves the
  mechanism *works*, not that it meets the stated RTO at production
  scale.
- **Single-table-scale data volume.** The seeded dataset (1 org, 1
  approval) is trivially small; dump/restore duration at real
  production data volumes was not measured here.
- **No point-in-time recovery (PITR) tested** — `SLA.md` and
  `backup-postgres.sh`'s own comments already state this honestly
  (nightly `pg_dump`, not continuous replication); this drill matches
  that same scope, a full-snapshot restore, not a PITR-to-a-specific-
  timestamp drill.

## Recommended follow-up (not done here, scoping the next drill honestly)

- Run this same drill against the real `docker-compose.prod.yml` stack
  once Docker is available in whatever environment performs it, to
  additionally verify the orchestration wrapper (service stop/start)
  works as scripted.
- Time the drill against realistic data volume to produce a real RTO
  measurement comparable to `SLA.md`'s stated targets.
- Schedule this drill to repeat periodically (e.g. quarterly) rather
  than being a one-time artifact — a script that hasn't been run in a
  year is not meaningfully different from one that's never been run.
