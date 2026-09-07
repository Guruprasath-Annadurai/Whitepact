# Phase 1 execution evidence

Baseline: `6f030a3e0bcece0e68f9ec5f18c9b28a2a42904d`.
Branch: `integration/enterprise-phase1`. No push or merge authorized.

## Checkpoint 1

Verified clean frozen baseline and created branch at the exact SHA. Inspected
PR55 migrations and authority resolver. Its empty-target matching, optional
purpose and missing-consent self-root fallback do not meet the current directive;
they are explicitly excluded from canonical behavior. PR55 migration 0031 is
legacy neural storage, not a Heart runtime dependency: preserve only the explicitly
requested storage compatibility, no deferred neural runtime features.

Read-only helper failed at account usage limit; no helper result is evidence.
Continuing inline. Design and plan saved in DCO commit `18e740d`.

## Checkpoint 2 — canonical migrations

Added forward revisions 0033–0040 from individually inspected PR55 schema intent.
Website 0030–0032 remain unchanged. Added tenant FKs, same-tenant root/consent
references, evidence fork/ownership preflight, scoped nonce/epoch storage and
deny-by-default empty consent scope. Startup and direct online Alembic both reject
unversioned nonempty or incompatible legacy schemas without stamping/deleting data.

Fresh evidence:

- Before implementation: new tests produced 6 expected failures and 3 environment
  skips (missing head 0040 and unsafe unversioned/legacy acceptance).
- SQLite migration/legacy/history tests: 22 passed, 3 PostgreSQL environment skips,
  1 existing Alembic path-separator deprecation warning.
- Separate real PostgreSQL 17 invocation: 3 passed (fresh, 0029, website 0032),
  including repeated head upgrade, empty consent defaults and cross-tenant FK
  rejection. The three databases were created fresh; none reset or stamped.
- Governance API/evidence consumer regressions: 110 passed.
- Alembic: exactly one head, 0040. Scoped Ruff and doc consistency passed.
- Corrected an intermediate metadata ordering error before the passing runs.
  Installed repository-locked asyncpg 0.31.0 in local venv for PostgreSQL tests.

PostgreSQL test container: `whitepact-phase1-postgres`, loopback port 55439,
disposable data only. Image digest:
`sha256:18cfe3ef5e6815560c98237d6216d1e5119702fb0f3894c8785dd58b8bbe5d73`.
This digest identifies test infrastructure, not a WhitePact release artifact.

Legacy PR55 bridge: not implemented or verified. No deployed legacy database was
provided; incompatible revision/schema combinations are rejected with data intact.
This remains an explicit customer-transition gap if such a deployment exists.

Checkpoint 2 committed as `c4e5426`. DB mypy: 31 files, no issues.

## Checkpoint 3 — trusted context and explicit authority

Added a canonical normalized context and tenant-scoped root/consent repositories.
The resolver reads explicit persisted delegation chains and consent, verifies
tenant/subject/target/purpose/integrity/expiry, checks attenuation and composes
Heart root, consent, purpose and delegation results. It never creates roots from
logins or supplies wildcard fallback authority. Authority versions bind the
resolved records. Root and consent digests now bind validity and evidence refs;
legacy unsigned record digests are not silently upgraded.

Focused authority/Heart/consent/root/grant/purpose suites: 184 passed. Added tests
cover trusted context mismatch, empty scopes with valid digests, revoked consent,
root revocation, expiry tampering, wrong purpose and cross-tenant hidden reads.
This is the canonical resolver foundation; live transport adoption remains
checkpoint 6, and revocation/nonce coordination remains checkpoint 4.

## Checkpoint 4 — partial: durable admission foundation

Added database-backed nonce consumption serialized on a tenant revocation epoch
row. Root and consent creation/revocation advance that epoch inside their own
mutation transactions. Permit matching now binds the authenticated principal;
action/approval digests bind explicit purpose. Approval storage and reconstruction
preserve purpose without rewriting historical purpose-less digests. Corrected a
stale root repository docstring that incorrectly described automatic bootstrap.

Fresh evidence (Python 3.12):

- Initial test collection demonstrated the missing nonce repository. After the
  first implementation, four tests exposed an incorrect identity attribute name;
  corrected to `identity_id` before passing verification.
- Purpose round-trip test initially failed with `None` instead of `reconcile`;
  now passes through real approval persistence and reconstruction.
- Execution, authority, approval, bypass and upstream combined suite: **99 passed,
  1 skipped** (`WHITEPACT_TEST_POSTGRES_EXECUTION` absent in that invocation).
- Separate real PostgreSQL 17 run: **1 passed, 6 deselected**. Both database
  variants exercise 16 competing consumes across two engines (one admitted,
  fifteen rejected), stale epoch rejection, 16 concurrent bumps without lost
  increments, rollback, and replay rejection after connection pools reopen.
- Scoped Ruff passed; mypy passed for 7 affected source files; documentation
  consistency, tracked-source SPDX and `git diff --check` passed.
- An earlier combined run recorded **53 passed, 1 skipped, 1 setup error**:
  the existing five-second ASGI startup timeout. The failing case then passed
  individually (1 passed), and the expanded combined run passed in 16.58 seconds.
  Cause of that transient timeout is unconfirmed; no timeout was relaxed and no
  test removed. It remains a reliability observation for full verification.

Security boundary still **PARTIAL**: nonce consumption is not wired into live
executors yet. Delegation/policy/credential mutation epoch wiring, full permit
version binding, fresh approval authorization and the shared guarded execution
chokepoint remain required before checkpoint 4 can close. These tests prove
database admission behavior, not exactly-once external side effects, process
isolation, full replica deployment or production readiness. Epoch comparison
linearizes admission; revocation cannot undo an operation already dispatched.
