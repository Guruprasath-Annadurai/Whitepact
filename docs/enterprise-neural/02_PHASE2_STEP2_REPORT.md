# Phase 2 — Cryptographic Foundation + Key Management: Step 2 Report

STATUS: **PASS** (Step 2 of the design doc's implementation sequencing,
Sec 7 — the persistent `crypto_keys`-table-backed `WrappedKeyStore`.
Steps 3-5 — wiring existing call sites onto the provider, the
generalized rotation script — remain. Phase 2 as a whole is not yet
complete.)

## Objective

Add a real, persistent `WrappedKeyStore` backing store, replacing Step
1's explicitly non-persistent `InMemoryWrappedKeyStore` for any real
deployment, per `docs/enterprise-neural/02_PHASE2_DESIGN.md` Sec 7 Step 2.

## Current state before phase

`InMemoryWrappedKeyStore` was the only `WrappedKeyStore` implementation —
every process restart lost all key state, silently generating fresh DEKs
on next use and making anything encrypted under the lost DEK permanently
undecryptable. No DB table, no migration, no repository existed for this
data.

## Architecture implemented

- `migrations/versions/0030_add_crypto_keys.py` — additive migration,
  `governance_crypto_keys` table: `key_id` (the canonical
  `KeyId.to_string()` encoding, primary key — collision-free by
  construction, no separate synthetic id needed), `purpose`, `tenant_id`
  (`""` reserved for "no tenant", the same wire encoding `KeyId` itself
  already uses — avoids a nullable primary-key-adjacent column), `version`,
  `wrapped_dek` (base64 text, matching `db/encryption.py`'s existing
  ciphertext-storage convention), `status`, `created_at`. Composite
  lookup index on `(purpose, tenant_id, environment, status, version)`.
- `src/responsibleai/db/engine.py` — `governance_crypto_keys` Table
  definition, adjacent to `governance_authority_passports`.
- `src/responsibleai/db/crypto_key_repository.py` — `CryptoKeyRepository`,
  structurally satisfying the `WrappedKeyStore` Protocol (`get`,
  `get_current`, `get_max_version`, `put`, `set_status`). `put()` catches
  `IntegrityError` (the DB's own primary-key uniqueness constraint on
  `key_id`) and re-raises as the new, typed `KeyVersionConflictError` —
  turning a concurrent-rotation race into a hard, typed error instead of
  a silent overwrite.
- `governance/crypto/types.py` — new `KeyVersionConflictError(CryptoError)`.

## Files created

- `migrations/versions/0030_add_crypto_keys.py`
- `src/responsibleai/db/crypto_key_repository.py`
- `tests/test_crypto_key_repository.py`
- `docs/enterprise-neural/02_PHASE2_STEP2_REPORT.md` (this file)

## Files modified

- `src/responsibleai/db/engine.py` — new table definition.
- `src/responsibleai/db/__init__.py` — exports `CryptoKeyRepository`.
- `src/responsibleai/governance/crypto/types.py` — new
  `KeyVersionConflictError`.
- `src/responsibleai/governance/crypto/__init__.py` — exports it; module
  docstring extended explaining why `CryptoKeyRepository` lives in `db/`
  rather than `governance/crypto/` (no circular dependency: `db/` already
  imports from `governance/`, not the reverse).
- `src/responsibleai/governance/crypto/local_envelope.py` — **bug fix**,
  see below.
- `CHANGELOG.md` — new entry at the top of `[Unreleased]`/`### Added`.
- `tests/test_db_migrate.py` — updated three hardcoded expected-head-
  revision assertions from `"0029"` to `"0030"` (the same routine update
  every prior migration that became the new head required — not a
  weakened test, the value it asserts against genuinely changed).

## Database migrations

`0030_add_crypto_keys`, additive. Verified via a real
`alembic upgrade head` / `downgrade -1` / `upgrade head` cycle against a
fresh SQLite database (not just the test suite's
`DatabaseEngine.init()` → `metadata.create_all()` path, which bypasses
Alembic entirely) — all 30 migrations from `0001` apply cleanly in
sequence, `governance_crypto_keys` downgrades and re-upgrades cleanly,
final schema inspected directly via `sqlite3`/`PRAGMA table_info`.

## Security properties added

- Persistent key state — a wrapped DEK survives process restart, closing
  the data-loss risk `InMemoryWrappedKeyStore`'s own docstring warns
  about.
- Real concurrency safety at the storage layer: a primary-key uniqueness
  violation on simultaneous `put()` calls for the same `KeyId` now raises
  `KeyVersionConflictError` rather than silently overwriting — this is
  strictly stronger than the in-memory store's dict-based `put()`, which
  cannot detect or prevent this class of race at all.

## Privacy properties added

None directly (still no PII flowing through this package — unchanged
from Step 1, pending call-site wiring in a later step).

## Trust boundaries changed

None — this repository is not called from any existing application code
path yet (only from its own tests and, structurally, by
`LocalEnvelopeKeyProvider` when explicitly constructed with it). Still
additive, unreachable-in-production code until a later step wires a real
call site onto it.

## Threats mitigated

Data loss on process restart (closed by persistence). Concurrent-write
key overwrite (closed by the DB uniqueness constraint +
`KeyVersionConflictError`, strictly better than Step 1's in-memory store).

## Threats not yet mitigated

Everything Step 1's report already listed as unchanged (webhook/SAML
secret rotation, no call site wired) remains unchanged. No row-level
locking/transaction-isolation analysis has been done for the
`get_max_version` → `put()` sequence under true concurrent load (SQLite's
own file-level locking and the async engine's connection pooling behavior
under Postgres are both untested here) — the uniqueness constraint
guarantees *no silent corruption*, but a concurrent caller that loses the
race gets a `KeyVersionConflictError` it must handle (retry, or surface
as a real error) — no retry logic exists yet anywhere that calls this
repository, since nothing calls it yet.

## Known limitations

Same as Step 1's `LocalEnvelopeKeyProvider` limitations, now with a real
store: root key custody/injection (`RAI_ROOT_KEY` or equivalent) is still
not wired to any deployment configuration — this step ships the
persistence primitive, not the deployment integration.

## Unit test results

15 new tests in `tests/test_crypto_key_repository.py`:
`TestCryptoKeyRepositoryCrud` (12 — CRUD, version-conflict, current/
max-version queries, tenant/environment isolation, `None`-tenant
round-trip through the reserved empty-string column), plus
`TestLocalEnvelopeKeyProviderOverDbBackedStore` (3 — persistence across
separate repository instances against the same DB, rotation/revocation
over the DB-backed store, the retire→re-generate regression guard at the
DB layer). All passing.

## Integration test results

`TestLocalEnvelopeKeyProviderOverDbBackedStore` above is genuinely
integration-level: real `LocalEnvelopeKeyProvider` wired onto real
`CryptoKeyRepository` against a real (in-memory SQLite) `DatabaseEngine`,
not a mock.

## Property test results

None new this step (the property tests from Step 1 already cover the
provider logic this repository plugs into; this step's own tests are
example-based, appropriate for a thin persistence-layer contract).

## Fuzz results

Not run — same reasoning as Step 1.

## Adversarial test results

Concurrent-write collision explicitly tested
(`test_put_duplicate_key_id_raises_version_conflict`) and confirmed to
raise a typed error rather than corrupt state — the specific adversarial
property this step's design was meant to add over Step 1's in-memory
store.

## Regression results

Full suite: **2937 passed, 0 failed**, 81.95s
(`/tmp/full_run_phase2_step2b.log`). One genuine pre-existing-test-value
update was required (see Errors found below) before this was reached.

## Static analysis

`ruff check` and `ruff format --check`: clean on all new/modified files.
`mypy`: `Success: no issues found` — this run is what caught the
`LocalEnvelopeKeyProvider.store` type-narrowing bug (see Errors below)
before any test even ran.

## Dependency audit

No new dependency — `sqlalchemy`, `alembic` already project dependencies.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this step (no dependency change).

## Performance results

Not benchmarked — same reasoning as Step 1 (no hot-path call site yet).

## Backward-compatibility result

Fully backward compatible — new table (additive migration), new export,
zero existing call site touched. The `test_db_migrate.py` value updates
are test-suite-internal, not a behavior change for any consumer.

## Migration result

Verified clean, both directions, real Alembic (see Database migrations
above), and via the full regression suite's own migration tests
(`test_db_migrate.py`, 14/14 passing after the expected-head-revision
update).

## Rollback procedure

`alembic downgrade -1` reverses the migration (verified). Code rollback:
delete `db/crypto_key_repository.py`, revert `db/engine.py`'s table
definition, `db/__init__.py`'s export, `governance/crypto/types.py`'s
`KeyVersionConflictError` and its export, revert
`local_envelope.py`'s `store` type annotation back to
`InMemoryWrappedKeyStore | None` (though there's no reason to — see
Errors below, that was a bug, not a feature to roll back), delete
`tests/test_crypto_key_repository.py`. `tests/test_db_migrate.py`'s
`"0030"` assertions would need reverting to `"0029"` only if the
migration itself is rolled back too.

## Documentation updated

`CHANGELOG.md`, this report, `PROGRESS_LEDGER.md` (updated alongside).

## Claims now supported by evidence

"WhitePact's key-management layer has a persistent, DB-backed store with
real concurrency-safety guarantees (typed error on collision, not silent
overwrite), verified through a real Alembic migration cycle" — true,
evidenced above.

## Claims still unsupported

Same as Step 1 (no call site wired), plus: "concurrent rotation races are
handled gracefully" is not true yet — they're detected and rejected
loudly (`KeyVersionConflictError`), which is correct fail-safe behavior,
but no retry/backoff logic exists to handle that error gracefully for a
caller, because no caller exists yet.

## Errors found and fixed this phase

1. **`LocalEnvelopeKeyProvider.store` type over-narrowing (Step 1's own
   bug, caught this step)** — `mypy` failed while type-checking this
   step's new test file: the constructor's `store` parameter was
   annotated `InMemoryWrappedKeyStore | None` instead of the
   `WrappedKeyStore` Protocol it was actually designed against (Step 1's
   design doc, Sec 3.7, explicitly says every call site should depend on
   the Protocol). This would have made it a **type error** to pass
   `CryptoKeyRepository` — the exact production-capable persistent store
   this step exists to build — to `LocalEnvelopeKeyProvider`, defeating
   the entire abstraction Step 1 built. **Fix**: changed the annotation
   to `WrappedKeyStore | None` and added the (non-circular) import.
   Caught by static analysis before any test ran, not by a failing test —
   worth noting as a case where "run mypy before pytest" earned its
   keep.
2. **`tests/test_db_migrate.py` stale expected-head-revision** — three
   assertions hardcoded `"0029"` as the expected `alembic_version` after
   a fresh migration run. This is expected staleness every time a new
   migration becomes the new head (the same update `0029`'s own addition
   presumably required for whatever was head before it), not a defect in
   this step's migration — confirmed by manually running the real
   Alembic migration and observing it correctly reaches `"0030"`.
   **Fix**: updated all three assertions to `"0030"`.

## Residual risks

- No retry/backoff pattern designed yet for `KeyVersionConflictError` —
  deferred until a real caller exists that could actually race (nothing
  concurrent calls this repository today).
- Postgres-specific behavior (vs. SQLite) for the uniqueness-constraint
  race path is untested — the empirical/integration tests here all ran
  against SQLite (`:memory:`), consistent with this project's existing
  test-suite convention, but worth a note for whoever eventually load-
  tests this under Postgres in production.

## Next-phase dependencies

Step 3 (per design doc Sec 7): wire `db/encryption.py` onto
`LocalEnvelopeKeyProvider` + `CryptoKeyRepository`, with the legacy-
Fernet-fallback path described in the design doc Sec 3.14. This is the
step where this package's code finally becomes reachable from a real
request path, and where the residual risks above (concurrent-write
handling, cross-database behavior) start to matter in practice rather
than in the abstract.
