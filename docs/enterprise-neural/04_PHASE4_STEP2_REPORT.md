# Phase 4 — Neural Data Classification + Privacy Boundary: Step 2 Report

STATUS: **PASS**. Neural Vault persistence layer built. Retention/
export/purge automation and end-to-end leakage tests (design doc Sec
8, 10) remain — see Residual risks.

## Objective

Persist the per-category consent ledger and the Neural Vault index
(metadata/references, never raw N0/N1/N2 content by default), per
`docs/enterprise-neural/04_PHASE4_DESIGN.md` Sec 6-7, Sec 12 Step 2.

## Current state before phase

`governance/neural/`'s types existed (Step 1) but nothing persisted
them — no table, no repository.

## Architecture implemented

- `migrations/versions/0031_add_neural_vault_and_consent.py` —
  additive migration: `governance_neural_consent` (consent ledger,
  indexed on `(subject_id, category)`) and `governance_neural_vault_index`
  (Vault index, indexed on `subject_id` and `(subject_id, session_id)`,
  with a nullable `encrypted_sync_copy` column that defaults to unused —
  the opt-in cross-device-sync capability the design doc describes,
  not wired to any writer yet).
- `db/engine.py` — the two `Table` definitions.
- `db/neural_vault_repository.py` — `NeuralConsentRepository` (`grant`,
  `revoke` — inserts a new REVOKED record at the next version rather
  than mutating, preserving the audit trail, same pattern
  `AuthorityPassportRepository` established — `list_for_subject`,
  `get_active`) and `NeuralVaultRepository` (`create_entry`, `get`,
  `list_for_subject` with `include_deleted`, `soft_delete`).

## Files created

- `migrations/versions/0031_add_neural_vault_and_consent.py`
- `src/responsibleai/db/neural_vault_repository.py`
- `tests/test_neural_vault_repository.py`
- `docs/enterprise-neural/04_PHASE4_STEP2_REPORT.md` (this file)

## Files modified

- `src/responsibleai/db/engine.py` — two new table definitions.
- `src/responsibleai/db/__init__.py` — exports
  `NeuralConsentRepository`, `NeuralVaultRepository`,
  `NeuralVaultEntryNotFoundError`.
- `src/responsibleai/governance/neural/types.py` — added
  `NeuralVaultEntry`.
- `src/responsibleai/governance/neural/__init__.py` — exports it.
- `tests/test_db_migrate.py` — updated three stale hardcoded expected-
  head-revision assertions (`"0030"` → `"0031"`), the same routine
  update every new head migration requires.

## Database migrations

`0031_add_neural_vault_and_consent`, additive. Verified via a real
`alembic upgrade head` / `downgrade -1` / `upgrade head` cycle against a
fresh SQLite database.

## Security properties added

Consent audit trail is append-only (revocation never overwrites a
grant). Vault deletion is explicit and distinguishes soft-delete
(Vault index reference removed from default listing) from a
hypothetical hard-purge (not built — see design doc Sec 8's "deletion
semantics must be explicit" requirement, honored by *not* claiming more
than what `soft_delete` actually does).

## Privacy properties added

The Vault index structurally cannot hold raw N0/N1/N2 payload bytes —
`NeuralVaultEntry` has no `payload` field at all, only metadata and an
optional opt-in encrypted reference. This is an architectural
enforcement (the type doesn't have the field), not a policy convention.

## Trust boundaries changed

None — still no application code path reaches this repository.

## Threats mitigated

None newly mitigated in production (same "mechanism, not activation"
posture as every other Phase 2/4 step so far).

## Threats not yet mitigated

Retention-window expiry enforcement (a scheduled purge job) isn't
built. Export (design doc Sec 8) isn't built — `list_for_subject` is
the read path an export endpoint would use, but no such endpoint exists.

## Known limitations

`encrypted_sync_copy` is a real column with no writer — Phase 4 Step 3
or a later phase would need to wire `governance/crypto`'s
`KeyProvider`/envelope pattern (a new `KeyPurpose.NEURAL_VAULT_SYNC`
value, following the exact precedent Phase 2 Steps 3-4 established) to
actually populate it. Flagged, not silently implied to exist.

## Unit test results

17 tests in `tests/test_neural_vault_repository.py`:
`TestNeuralConsentRepository` (7 — grant/get_active round trip, empty-
store None, revoke-with-no-prior-grant, revoke-after-grant version
bump, audit-trail preservation, category filtering, subject isolation,
highest-version resolution), `TestNeuralVaultRepository` (10 — create/
get round trip, missing-entry None, subject isolation, soft-delete,
soft-delete-on-unknown raises, default exclusion of deleted entries,
explicit inclusion, `encrypted_sync_copy` defaults to `None`, all 6
`NeuralDataClass` values round-trip correctly). All passing.

## Integration test results

Every test in this suite is genuinely integration-level: real
repositories against a real (in-memory SQLite) `DatabaseEngine`, not
mocks — consistent with this project's established DB-repository test
convention.

## Property test results

None new — the version-numbering logic here reuses the same "latest
wins" pattern Phase 4 Step 1's `evaluate_neural_data_flow` already has
property-test coverage for at the policy-decision level; this step's
own tests are example-based, appropriate for a thin persistence-layer
contract (same reasoning Phase 2 Step 2's report gave for
`CryptoKeyRepository`).

## Fuzz results

Not run.

## Adversarial test results

Not applicable at this step's scope (no adversarial surface yet — no
untrusted input reaches this repository).

## Regression results

Full suite: **3009 passed, 0 failed**, 101.87s
(`/tmp/full_run_phase4_step2b.log`). One genuine pre-existing-test-value
update was required first (see Errors found below).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy`: clean.

## Dependency audit

No new dependency.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this step.

## Performance results

Not applicable — no hot path yet.

## Backward-compatibility result

Fully backward compatible — new tables (additive migration), new
export, zero existing call site touched.

## Migration result

Verified clean, both directions, real Alembic (see Database migrations
above), and via the full regression suite's own migration tests
(`test_db_migrate.py`, 14/14 passing after the expected-head-revision
update).

## Rollback procedure

`alembic downgrade -1` reverses the migration (verified). Code
rollback: delete `db/neural_vault_repository.py`, revert `db/engine.py`'s
table definitions, `db/__init__.py`'s exports,
`governance/neural/types.py`'s `NeuralVaultEntry` and its export, delete
`tests/test_neural_vault_repository.py`. `tests/test_db_migrate.py`'s
`"0031"` assertions would need reverting to `"0030"` only if the
migration itself is rolled back too.

## Documentation updated

`CHANGELOG.md`, this report, `PROGRESS_LEDGER.md` (updated alongside).

## Claims now supported by evidence

"WhitePact has a persistent, DB-backed Neural Vault index and consent
ledger, with an append-only audit trail for consent and explicit soft-
delete semantics for Vault entries" — true, evidenced above.

## Claims still unsupported

"WhitePact enforces neural data retention windows" — not yet; no
scheduled purge exists. "A subject can export their neural data" — not
yet; no export endpoint exists, though the read path (`list_for_subject`)
it would use is now in place.

## Errors found and fixed this phase

One routine, expected update: `tests/test_db_migrate.py`'s three
hardcoded expected-`alembic_version` assertions were stale after
`0031` became the new head — the same update every prior migration
that became head required (documented in Phase 2 Step 2's report as
well). Confirmed via the real Alembic migration reaching `"0031"`
correctly before updating the test.

## Residual risks

- No retention-expiry enforcement job.
- No export endpoint.
- `encrypted_sync_copy` has no writer yet (see Known limitations).
- Same application-code-path gap as every prior phase: nothing calls
  these repositories yet — that's Phase 5's job, once a real BCI device
  adapter exists to produce data worth storing.

## Next-phase dependencies

Phase 4's own remaining work (Sec 12 Steps 3-4: the neural privacy
policy engine is already built in Step 1's `evaluate_neural_data_flow`,
so what remains is genuinely just leakage tests once real N0/N1/N2
content exists) is now blocked on Phase 5 (BCI device adapter) —
there's no more scaffolding to build without real data flowing through
it. Recommend proceeding to Phase 5 next, treating Phase 4 as
functionally complete for what can be built without a device adapter,
and returning to close out leakage testing once Phase 5/6 produce real
payloads.
