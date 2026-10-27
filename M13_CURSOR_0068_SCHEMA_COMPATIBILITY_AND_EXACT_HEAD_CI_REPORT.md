# M13 schema 0068 compatibility and exact-head CI

Repair commit: `71113c57c6b2dd63ac525c7cd8949c2a1ee26219`, continued from report head `3b941ef15c41d6f2c0234ee6d5c16ff8020b8981` and implementation `ae979efa289725a9aa84af84b2b8d8ba02f8c4e5`.

## Root cause

`migrations/versions/0068_identity_session_uniqueness.py` made Alembic head `0068`. Customer journeys, sovereign startup, and the product app run `alembic upgrade head`. Protected checks still require the version row to be exactly `0067`:

- `SUPPORTED_POSTGRES_REVISIONS` in `src/responsibleai/db/runtime_compatibility.py`
- `scripts/engineering/m13_bootstrap_preflight.py` and the signed manifest field `schema_revision`
- `src/responsibleai/data_governance/tenant_controller.py`
- `src/responsibleai/data_governance/operator_recovery_control.py`

`0068` was therefore rejected. That is fail-closed behavior, not a reason to add `0068` to the allowlist. `tests/test_m13_runtime_schema_compatibility.py` already treats `0068` as an incompatible stamp. Accepting it would change the signed bootstrap contract and was not done.

## Hosted failure classification

Runs, all at `3b941ef15c41d6f2c0234ee6d5c16ff8020b8981`:

- I1 https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40387358396
- Product https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40387358398
- Sovereign https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40387358410

| Failure | Class |
| --- | --- |
| `BootstrapRefusedError: Bootstrap requires PostgreSQL 16 and exactly schema 0067` on `real-customer-journey` and sovereign `development-qualification` | Confirmed schema incompatibility caused by head `0068` |
| `RuntimeError: Startup refused: incompatible PostgreSQL schema revision` in sovereign restore HTTP tests | Same schema incompatibility |
| `TenantCreationDeniedError: Tenant creation authorization was rejected` on independent-security, independent-mcp, and dual-titan tests | Controller HTTP 403. The controller returns 403 when `version_num` is not `0067`, and the client reports that as authorization rejected. Classified as the same schema mismatch, not a new creator-session policy. Re-check after this repair; do not weaken the controller. |
| Product `contracts (3.11)` `SystemExit: 3` in the browser tests, followed by `CancelledError` and `previous item was not torn down properly` | Browser step runs only on Python 3.11. Uvicorn exited during startup. The teardown errors are the cancelled server, not a separate browser assertion. `contracts (3.12)` does not run that browser step and succeeded. Expected to follow the schema repair. |
| I1 `introduced-dco`: commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` lacks `Signed-off-by` | Expected historical DCO denial. Not rewritten. No waiver. |
| I1 `inherited-policy-gates` | Passed. The Ruff repair stays. |

## Protected-contract decision

Before: accepted PostgreSQL revision is exactly `0067`. Head had moved to `0068`, so upgrade and then authorize could not both succeed.

After: accepted revision is still exactly `0067`. The `0068` revision file is removed, so `upgrade head` stops at `0067`. Signed bootstrap records are not rewritten. `SUPPORTED_POSTGRES_REVISIONS` is not widened.

The uniqueness guarantee stays. After an upgrade, and again at PostgreSQL startup when the version is `0067`, `ensure_identity_session_uniqueness` creates `uq_identity_verification_provider_session` if it is absent. If two rows share a provider and session reference, the index build raises `IdentitySessionConflictError` and both rows are left in place. Startup then refuses. Stamping any other revision, including `0068`, still fails closed. Dropping the index does not stick: the next accepted startup rebuilds it, or refuses if duplicates exist.

`0067` downgrade still refuses when provisioning evidence or outbox rows exist. There is no `0068` downgrade that drops the unique index.

This is not an authorization-contract change. Widening the accepted revision to `0068` would have been one, and it was stopped.

## Local proof

PostgreSQL 16.15. CPython 3.12.3 and 3.11.11. `WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:5432/postgres`.

- `tests/test_m13_identity_session_schema.py` and `tests/test_m13_runtime_schema_compatibility.py`: 3 passed on 3.11.11.
- The same schema tests plus the PostgreSQL duplicate-callback case: 4 passed on 3.12.3 before the exception rename; the schema tests were re-run on 3.11 after that rename.
- `ruff check src/ tests/ sdk/python/` passed.
- Docker is not available in this environment, so the native container workflows were not repeated locally. Hosted sovereign and I1 are the Docker-backed runs for the pushed SHA.

## Antigravity handoff

Review `src/responsibleai/db/identity_session_uniqueness.py`, the post-upgrade call in `src/responsibleai/db/migrate.py`, and the startup call in `src/responsibleai/db/runtime_compatibility.py`. Confirm head is `0067`, the unique index exists after upgrade, duplicate sessions survive a refused index build, and a database stamped `0068` still cannot start. Do not treat a green schema gate as identity-provider enrollment. The canonical customer journey remains blocked until a real approved provider exists. Argon PR #234 was not edited.

M13 remains open. Production remains no-go.
