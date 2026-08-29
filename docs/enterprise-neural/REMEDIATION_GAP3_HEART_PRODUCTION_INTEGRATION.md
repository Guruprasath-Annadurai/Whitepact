# Security Remediation Gap 3 — Heart Production Integration: Phase 3 (Persistence)

## Reproduction

Independently re-verified, not assumed from the earlier handoff docs:
the "Heart" (root authority / delegation / consent / revocation /
attenuation / constitutional-constraint logic named by constitutional
laws H1-H13) is **real, tested code** —
`src/responsibleai/governance/{root_authority,consent_proof,
delegation_kernel,revocation_kernel,authority_lattice,
sovereignty_kernel,legitimacy_envelope,heart_veto,
non_delegable_authority,purpose_binding,authority_lifetime,
constitution}.py`, ~2,800 lines, each phase documented in
`docs/heart/HEART_CURRENT_STATE.md`. **None of it is wired into any
live request path.** `mcp/governance_integration.py::apply_governance()`
— the sole place a real MCP tool call is governed — never imports any
Heart module; its `AuthorityContext` is synthesized fresh from the
caller's own authenticated identity every call
(`governance_integration.py:247-252`), not derived from a proof of
legitimate authority. This is exactly what
`docs/heart-production/00_CURRENT_RUNTIME_MAP.md` §12 already
documents, written honestly before any of this remediation began.

This is not a gap discovered from scratch by this remediation pass —
it is an **already-scoped, already-in-progress initiative**
("Heart Production Integration"), with two phases already merged
before this remediation branch existed:

- **Phase 0+1** (PR #45, commit `85abd0b`): runtime audit
  (`00_CURRENT_RUNTIME_MAP.md`) + the `AuthorityGrant` contract type
  (`01_AUTHORITY_CONTRACT.md`, `governance/authority_grant.py`).
- **Phase 2** (PR #46, commit `9dcdc1b`): real-identity → Heart-root
  mapping (`02_IDENTITY_RESOLUTION.md`,
  `governance/identity_authority_adapter.py`, 19 tests).

The initiative's own roadmap (stated in `01_AUTHORITY_CONTRACT.md` and
`02_IDENTITY_RESOLUTION.md`'s "what this phase does not do" sections)
names the remaining phases: **Phase 3 (persistence)**, Phase 4
(unscoped at time of writing), **Phase 5 (the Authority Resolver** —
turns live identity + DB state into a real `AuthorityGrant`), **Phase
6 (wiring** into `apply_governance()`/`apply_upstream_governance()`).

## What this session's work is, and is not

**Is**: Phase 3 — durable persistence for `RootAuthorityRecord` (Heart
Phase H3) and `ConsentProof` (Heart Phase H4), the two record types
`00_CURRENT_RUNTIME_MAP.md` §14 explicitly names as having **no
existing table** ("Nothing in the current schema is a
`RootAuthorityRecord`, `ConsentProof`, or true `LegitimacyEnvelope`").
Without this, no root-of-trust or consent act can outlive a single
process/request, which blocks every later phase.

**Is not**: this session does **not** claim Gap 3 (Heart Production
Integration) is closed. Phases 5 (Authority Resolver) and 6 (wiring
into the live decision path) remain, and are substantial,
multi-session-scale work in their own right — building a real resolver
that turns authenticated identity + these new tables into a legitimate
`AuthorityGrant`, then wiring its output into `apply_governance()` and
`apply_upstream_governance()` without weakening any existing
`gateway.evaluate()` behavior. Marking this "done" before that wiring
exists would repeat exactly the failure mode this whole remediation
directive exists to correct: claiming a security property that isn't
actually enforced on the live path.

## What was built

- **`migrations/versions/0032_add_heart_root_authority_and_consent.py`**
  — two new, additive tables: `governance_root_authority_records`,
  `governance_consent_proofs`. (Renumbered from an initial `0030` after
  discovering `0030`/`0031` were already claimed by the crypto-keys and
  neural-vault migrations from other in-flight phases — confirmed via
  `alembic upgrade head` / `downgrade -1` / `upgrade head` round-trip
  against a real on-disk SQLite file, not just `:memory:`.)
- **`src/responsibleai/db/engine.py`** — `governance_root_authority_records`
  and `governance_consent_proofs` `Table` definitions, mirroring the
  existing `governance_authority_passports` pattern exactly (same
  column-naming and indexing conventions).
- **`src/responsibleai/db/root_authority_repository.py`** —
  `RootAuthorityRepository.create()/get()/revoke()`. Pure storage; does
  not resolve chains or decide legitimacy (`root_authority.
  validate_root_chain()` is unchanged and untouched).
- **`src/responsibleai/db/consent_proof_repository.py`** —
  `ConsentProofRepository.create()/get()/revoke()`. Same discipline;
  `consent_proof.validate_consent_proof()` unchanged and untouched.
- **`tests/test_heart_persistence.py`** — 13 tests. Round-trip
  persistence and revocation for both repositories, plus four
  end-to-end tests proving the existing Heart validation logic still
  enforces its invariants against **persisted, retrieved-from-a-real-DB**
  records (not just in-memory-constructed ones) — directly answering
  the remediation directive's request for property coverage of
  revoked-grant reuse and identity substitution:
  - A two-hop chain (service principal → organization root) resolves
    to `VALID` once round-tripped through storage.
  - **Revoked-grant reuse**: revoking an organization root, then
    re-resolving a descendant service-principal root against the
    revoked (persisted) parent, correctly yields `REVOKED`, not
    silently `VALID`.
  - **Identity substitution**: a `ConsentProof` claiming a
    `consenting_root_id` that doesn't match the actually-validated
    root correctly yields `ROOT_MISMATCH`.
  - A revoked `ConsentProof`, even backed by an otherwise-legitimate
    root, correctly yields `REVOKED`.

## What this deliberately does not build (and why)

- **No sync/async resolver adapter in production code.** `validate_root_chain()`'s
  `RootResolver` Protocol is a plain synchronous callable; these
  repositories are async (matching every other repository in this
  codebase). Building the real bridge — prefetching a chain from the
  DB and presenting it as a sync callable, with real caching/depth
  bounds for production traffic — is Phase 5's Authority Resolver, not
  a persistence-phase concern. The test file's `store = {...}` +
  `lambda rid: store.get(rid)` pattern is a **test-only** adapter,
  proving the stored data is chain-walkable correctly; it is not
  offered as the production resolver.
- **No wiring into `apply_governance()`/`apply_upstream_governance()`.**
  Per Phase 6's own scope, and because wiring an unresolved,
  unvalidated concept (no resolver exists yet to populate these tables
  from live requests) into the live decision path would be premature
  and untestable end-to-end.
- **No `AuthorityGrant` persistence.** `governance/authority_grant.py`
  (Phase 1) is explicitly short-lived/derived per its own contract
  (`issued_at`/`expires_at` mirror `ExecutionAuthorization`'s 30-second
  TTL pattern) — it is not meant to be a long-lived, persisted
  credential, so it has no table by design, not by omission.

## Verification

- 13 new tests, all passing on first real run (no debugging needed —
  the round-trip pattern was copied from `authority_passport_repository.py`'s
  own already-proven shape).
- `alembic upgrade head` / `downgrade -1` / `upgrade head` verified
  against a real on-disk SQLite database (not `:memory:`), confirming
  the migration is syntactically and referentially correct against the
  true current head (`0031`, not the `0029` this branch's git history
  alone would suggest — `0030`/`0031` were consumed by concurrent
  crypto-foundation and neural-vault migrations already on this
  branch).
- `ruff check` / `ruff format --check` / `mypy` clean on every touched
  file.
- Full repository test suite: see commit for the exact pass count at
  time of commit — run fresh, not assumed from an earlier phase's run.
