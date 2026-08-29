# Security Remediation Gap 5, Phase 2 — Multi-Instance Evidence-Chain Sequencing Safety

Closes the one item `REMEDIATION_GAP5_AUDIT_ANCHOR.md` named as
deliberately out of scope for Phase 1: "multi-instance sequencing
safety... a real change to the hot evidence write path that this
phase did not attempt without the ability to test it under genuine
multi-replica concurrent load."

## Reproduction

Confirmed by reading `db/evidence_repository.py::EvidenceRepository`:
write serialization was provided by exactly two mechanisms, both
per-process — an `asyncio.Lock` (`self._chain_lock`) and an in-process
cache (`self._last_hash_by_org`, hydrated once per org from the DB's
latest row). Neither has any cross-process/cross-replica coordination.
Two application replicas, each with their own `EvidenceRepository`
instance, both writing to the same organization's evidence chain at
roughly the same time could each independently read the same "current
last hash," compute their own `entry_hash` against it, and both
insert — producing two rows that each claim the same `prev_hash`, a
forked chain. `verify_chain()` walks in `recorded_at` order and would
report a broken link the moment it hit the second of the two forked
rows (their `prev_hash` wouldn't match the immediately-preceding row's
`hash`), so the fork wouldn't stay silently undetected forever — but
by then the damage (a chain that no longer verifies, an audit trail
with an unresolvable branch) is already done. This is a genuine
correctness gap the multi-instance-focused sub-cell of the fail-closed
matrix named but this remediation hadn't fixed until now.

## The fix

Two new partial unique indexes on `governance_evidence`
(`migrations/versions/0033_add_evidence_chain_uniqueness.py`, and
mirrored in `db/engine.py`'s `Table` definition so `create_engine(":memory:")`'s
`metadata.create_all()` — what every test in this repository runs
against — enforces the identical constraint):

- `idx_gev_chain_link`: `UNIQUE(org_id, prev_hash) WHERE prev_hash IS NOT NULL`
  — at most one row per organization may claim any given hash as its
  parent. Covers every non-genesis append, the high-volume case.
- `idx_gev_chain_genesis`: `UNIQUE(org_id) WHERE prev_hash IS NULL` —
  at most one row per organization may be a genesis entry (no parent).

This is the exact same discipline `governance/crypto/types.py`'s
`KeyVersionConflictError` already established for wrapped-key
rotation: a database-enforced uniqueness constraint turns a race into
a hard, typed, catchable error instead of silent corruption.

`EvidenceRepository.record()` now catches the resulting
`IntegrityError`, discards its (now known-stale) in-process cache
entry for that org, re-hydrates fresh from the database, and retries
— up to `_MAX_CHAIN_CONFLICT_RETRIES` (5) times — before raising a new
`EvidenceChainConflictError`. The existing per-process `asyncio.Lock`
is unchanged and still useful (it avoids unnecessary DB round-trips
and conflict retries among same-process concurrent tasks); the unique
indexes are the actual cross-process safety net.

## What this does not cover, named honestly

A race between two `org_id=None` ("no org") genesis entries is not
caught — standard SQL treats each `NULL` as distinct for uniqueness
purposes, so `UNIQUE(org_id) WHERE prev_hash IS NULL` doesn't collide
when `org_id` itself is `NULL` in both rows. This is an accepted, deliberately-scoped
gap: `mcp/governance_integration.py::apply_governance()` already
asserts `ctx.org_id is not None` before any evidence write reaches
this path on the live governed call flow — an `org_id=None` evidence
row does not occur there today, making this a defensive-only edge
case rather than a live risk. Closing it fully would need a
sentinel non-NULL value standing in for "no organization" throughout
this table, a broader change than this phase's scope.

## Verification

`tests/test_evidence_chain_multi_instance_safety.py` reproduces the
race deterministically rather than relying on real timing/concurrency
(which would make the test flaky): two independent
`EvidenceRepository` instances share one DB engine, and the second
instance's in-process cache is deliberately poisoned with stale state
— exactly what a lagging replica would have — before it attempts a
write. Covers: the genesis-race case, a non-genesis (mid-chain) race,
that two different orgs' chains never interfere with each other's
conflict resolution, and that persistent conflict (every retry fails)
correctly raises `EvidenceChainConflictError` after exactly the
configured number of attempts rather than looping forever.

- 4 new tests, all passing on first run.
- Existing evidence-related test suites re-run clean: `test_evidence_chain_anchoring.py`,
  `test_governance_persistence.py`, `test_audit_anchor.py`,
  `test_mcp_governance_dispatch.py` — 69 tests, all passing, confirming
  the `record()` restructuring didn't regress any existing behavior.
- Migration verified with a real `upgrade head` / `downgrade -1` /
  `upgrade head` round-trip against an on-disk SQLite file.
- `ruff check` / `ruff format --check` clean.
- `mypy src/responsibleai`: clean, 169 source files.
- Full repository suite: see commit for the exact pass count at time
  of commit, run fresh.
