# Phase 17 — PostgreSQL Migration Round-Trip Verification

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 17. Every migration this branch has
added (0034 through 0037) was previously verified only against
on-disk SQLite. `db/engine.py` uses `render_as_batch=True` specifically
for SQLite/Postgres cross-dialect compatibility, but that intent had
never been independently confirmed against a real PostgreSQL server.

## Environment

Real local PostgreSQL 17.10 (Homebrew, already running as a system
service — not Docker, not a mock). `asyncpg` (this project's async
Postgres driver, declared as the `postgres` extra in `pyproject.toml`)
installed into the virtualenv for this verification.

## What was run

```
$ createdb whitepact_migration_test
$ RAI_DATABASE_URL=postgresql://<user>@localhost/whitepact_migration_test \
    alembic upgrade head
```

All 37 migrations (0001 → 0037) ran cleanly against real Postgres, in
order, with no errors — full log preserved in this session's own
record. `alembic_version` correctly reads `0037` afterward.

```
$ alembic downgrade base
```

All 37 migrations reversed cleanly, in order, back to an empty schema
— no partial-downgrade failures, no orphaned constraints/indexes left
behind.

```
$ alembic upgrade head
```

Re-applied cleanly a second time, confirming the round trip
(upgrade → downgrade → upgrade) is fully reversible against Postgres,
not just idempotent-looking.

Final state directly inspected (not inferred):
- `SELECT version_num FROM alembic_version` → `0037`.
- `\d governance_approvals` confirms the Phase 5 `purpose` column
  exists with type `text`, nullable — matching the SQLite verification
  from `PHASE5_PURPOSE_BINDING.md` exactly.

## Functional smoke test (beyond DDL)

A schema-level round trip alone doesn't prove the application can
actually *use* a Postgres-backed database — the real
`responsibleai.db` code path was exercised directly against it:

- `create_engine(postgres_url)` → `DatabaseEngine.init()`
- `OrgRepository.create_org()` / `create_key()` — real org + API key
  persisted.
- `WhitePactRuntimeGateway.evaluate()` on a `REQUIRE_APPROVAL` action
  carrying `purpose="ops.check"` (Phase 5).
- `ApprovalRepository.create()` → `.resolve()` → `.consume()` — full
  approval lifecycle, including the Phase 5 `purpose` field, round-
  tripped through real `asyncpg` reads/writes.

Result: **PASS** — `approval.purpose == "ops.check"` read back
correctly after being written through the same repository code the
production app uses, against the same PostgreSQL server, not SQLite.

This database was also the seed data for the Phase 16 DR restore
drill (`DR_RESTORE_DRILL.md`) — the same org/approval/purpose data
survived a full `pg_dump`/restore cycle as well.

## Cleanup

The disposable `whitepact_migration_test` database was dropped after
verification. No persistent Postgres infrastructure was created or
left running as part of this phase.

## Result

**PASS.** `render_as_batch=True`'s cross-dialect intent is now
independently confirmed against a real PostgreSQL server, not only
asserted from SQLite behavior. All 37 migrations (0001–0037) are
verified reversible and forward-applicable against Postgres.

## What this does not cover

- Not run against a managed Postgres provider (RDS, Cloud SQL, Render,
  Supabase) — a local Homebrew-managed Postgres 17 instance stands in.
  Provider-specific extensions/permission models were not exercised.
- Not run under concurrent migration attempts (two processes racing to
  migrate the same database) — out of scope for this phase, a
  reasonable follow-up if multi-instance deploys ever run migrations
  from more than one process at once.
