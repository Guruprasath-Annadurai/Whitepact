# Independent Security Review Packet — PR #50, PR #54, and the Heart Production Closure branch

**Independent review status: NOT YET PERFORMED**, in the sense of a
formal, security-focused review of these specific PRs.

> **Update, 2026-09-02:** a separate external human technical review
> (reviewer: Keshavan) is recorded in
> [`EXTERNAL_REVIEW_KESHAVAN.md`](EXTERNAL_REVIEW_KESHAVAN.md) — gate
> status PARTIALLY CLOSED at the whole-project level. That review's
> scope was not confirmed against PR #50/#54 specifically.

This document is prepared *for* a human security reviewer. It does not itself
constitute review, and nothing in this repository should be represented as
independently reviewed until a qualified human has actually performed that
review and recorded findings. This packet was assembled by an AI agent
(Claude, via Claude Code) at the direction of the repository owner, following
an explicit "Heart Production Closure Initiative" directive that itself named
this requirement: *"do not 'complete' independent review yourself."*

---

## 1. What is being reviewed

Three pieces of work, layered:

1. **PR [#50](https://github.com/Guruprasath-Annadurai/Whitepact/pull/50)** — `security/enterprise-neural-phase-0-1`, titled "Enterprise Neural
   directive: frozen for Codex security review (unmerged)". 90 files changed,
   +14,970/−61. **Open, unmerged.**
2. **PR [#54](https://github.com/Guruprasath-Annadurai/Whitepact/pull/54)** — `security/enterprise-neural-remediation`, titled "Security
   remediation: crypto foundation activation (Gap 1 of 7)". 135 files changed,
   +20,926/−125. Base `9dcdc1bebe0ad856bd399dc627d17c35a2cc5828` (main), head
   `32eb2a6b1891fa751376bc8dbee8bd048256efb3`. **Open, unmerged.** CI green
   (12/12 checks passing as of last check: lint/type/test on 3.11 and 3.12,
   CodeQL python + javascript-typescript, DCO, dependency-review, gitleaks,
   Helm lint, accessibility, i18n, build).
3. **This branch, `security/heart-production-closure`** — stacked on PR #54's
   exact tested head (`32eb2a6b`...), NOT part of either PR above, not merged
   into either. Five commits, closing four specific gaps a follow-up audit
   found between PR #54's own claimed remediation and genuine production
   enforcement. See §4 below for the full list and rationale.

**Neither PR #50 nor PR #54 has been modified by this branch.** This branch
only adds new commits on top of PR #54's head.

## 2. Why this packet exists

The repository owner's own directive (reproduced in spirit, not verbatim, for
brevity) stated:

> PR #54 is accepted as the completed security-remediation branch... Do not
> merge PR #54. Do not modify PR #50. Do not represent either PR as
> independently security reviewed... Gap E: independent review of PR #50 has
> not occurred, and cannot be solved by Claude pretending to be an
> independent reviewer. Prepare a packet for a real reviewer instead.

This document is that packet.

## 3. Architecture summary (for a reviewer new to this codebase)

WhitePact/`responsibleai` is a governance/observability layer for AI agent
tool use, built around a "Heart" — a set of formally-specified legitimacy
primitives (Phases H1–H14, `src/responsibleai/governance/`) that answer "is
this agent's claimed authority to perform this action actually legitimate,"
independent of whether the request is technically well-formed.

Key vocabulary:

- **Root authority** (`root_authority.py`, H3): a `RootAuthorityRecord` traces
  an identity back to a human or organization root. `validate_root_chain()`
  walks `authority_source` pointers to a terminal (self-originating) root
  type, or reports why it can't.
- **Consent proof** (`consent_proof.py`, H4): a `ConsentProof` records that
  some root explicitly consented to a grantee acting on its behalf, with
  temporal validity and (as of this branch's Gap A) structured
  action-type/target scope.
- **Delegation** (`delegation.py`/`delegation_kernel.py`, H6): chains of
  authority handed down from a root, independently revocable.
- **Revocation epoch** (`revocation_kernel.py`, H9; persisted as of this
  branch's Gap B): a cheap monotonic counter per `(organization_id, scope)`
  for "has anything in this scope changed since I was issued."
- **Sovereignty kernel** (`sovereignty_kernel.py`, composes H3–H12):
  `evaluate()` runs whichever of the above checks its inputs make possible
  and returns a `LegitimacyEnvelope` with `is_legitimate`.
- **Authority Resolver** (`authority_resolver.py`, Phase 5): the ONLY code
  allowed to construct an `AuthorityGrant` — turns a live `IdentityContext` +
  real DB state into `sovereignty_kernel.evaluate()`'s inputs.
- **Evidence + audit anchor** (`evidence.py`/`evidence_bundle.py`/
  `audit_anchor.py`): an append-only, hash-chained decision log, with a
  signed, externally-anchorable checkpoint mechanism to detect full-database
  tamper (the primary DB's own hash chain alone cannot detect an attacker
  with DB write access who regenerates the chain forward).

## 4. What changed, PR by PR, then this branch's five commits

### PR #54's own scope (already CI-green, not touched by this branch)
Per its own title: crypto foundation activation (Security Remediation Gap 1)
plus, per the repository owner's earlier framing, six further remediation
gaps closed at implementation/test level across the same branch. Full suite:
3263 passed / 1 skipped / 0 failed at the time of the closure audit (see
`docs/heart-production-closure/00_CLOSURE_AUDIT.md`).

### This branch's five commits (all new, stacked on PR #54's head)

| Commit | Gap | Summary |
|---|---|---|
| `343871c` | A | Consent-backed legitimacy: `resolve_authority_grant()` now looks up, integrity-verifies, and scope-matches a persisted `ConsentProof` before granting authority, resolving against the CONSENT'S OWN root rather than the acting identity's. Migration 0034. 13 new negative/positive tests. |
| `4ee941c` | B | Durable, multi-instance-safe revocation epochs. New `governance_revocation_epochs` table (migration 0035), race-safe `RevocationEpochRepository.bump()`. Wired into consent/delegation revoke endpoints. |
| `0be7245` | C | `enterprise_mode=true` now also requires `mcp_governance_enabled=true` and reachable root-authority/revocation-epoch stores at startup, or the process refuses to start (`HeartEnforcementError`). |
| `847fe0e` | D | `S3ObjectLockAnchorProvider` — a real, deployable `AuditAnchorProvider` implementation backed by S3 Object Lock, idempotent via `IfNoneMatch` conditional writes. Optional `boto3` dependency. |
| `da77fdb` | — | End-to-end production authority gauntlet (full chain + revoke-then-deny + ~14 named attack variants) and fixes for two pre-existing tests broken by Gaps A/C's changes. |

## 5. Files with the highest security sensitivity in this branch

Ranked by how directly each affects whether an action executes with or
without genuine legitimacy:

1. **`src/responsibleai/governance/authority_resolver.py`** — the single
   place `AuthorityGrant`s are constructed. Gap A's `_resolve_applicable_consent()`
   and the root-substitution logic in `resolve_authority_grant()` are the
   highest-value review target in this entire branch: an error here could
   either (a) grant authority that shouldn't exist, or (b) deny legitimate
   authority. Review specifically: the fail-closed-by-omission empty-scope
   handling, the integrity check ordering, and the root-substitution
   (`consent.consenting_root_id` vs. the acting identity's own root).
2. **`src/responsibleai/governance/consent_proof.py`** — digest completeness
   for the two new fields (`allowed_action_types`/`allowed_targets`); the
   `verify_consent_proof_integrity()` function's correctness is what makes
   tamper-detection real rather than theatrical.
3. **`src/responsibleai/governance/heart_production_gate.py`** — the
   fail-closed startup invariant. A bug here fails in the SAFE direction
   (refuses to start) rather than the dangerous one, but review the exact
   conditions it checks against the six bypass paths named in the closure
   audit — it only closes two of them, named explicitly in its own
   docstring.
4. **`src/responsibleai/db/revocation_epoch_repository.py`** — `bump()`'s
   concurrency correctness. A real deadlock was found and fixed during this
   branch's own testing (documented in the module and in commit `4ee941c`'s
   message) — worth specific reviewer attention given that class of bug's
   history here.
5. **`src/responsibleai/governance/audit_anchor_s3.py`** — untested against
   real AWS infrastructure (see §8). Review the idempotency-vs-retry
   correctness argument in the module docstring particularly critically,
   since it cannot be empirically verified against real S3 in this
   environment.
6. **`migrations/versions/0034_*.py`, `0035_*.py`** — additive-only, verified
   with real `alembic upgrade head` / `downgrade -1` / `upgrade head`
   round-trips against on-disk SQLite (not just reasoned about).

## 6. Identity, authority, and execution-boundary changes

- **Identity → authority binding**: unchanged in this branch beyond Gap A's
  consent lookup — `resolve_root_for_identity()` (Phase 5, pre-existing) is
  untouched.
- **No new authentication mechanism, no new API key format, no new session
  handling.** This branch is entirely inside the governance/authority layer.
- **Execution boundary**: this branch does NOT touch `dispatch_tool()`,
  `_call_tool()`, or any MCP transport code. The closure audit's six traced
  bypass paths (see `docs/heart-production-closure/00_CLOSURE_AUDIT.md`) are
  therefore only partially addressed — Gap C closes two of the six
  (governance-flag-off, enterprise-mode-as-independent-opt-in); the other
  four (stdio's different trust model, legacy API keys,
  `mcp_http_allow_unauthenticated_demo`, and a direct Python import of
  `dispatch_tool()`) remain open and are named explicitly, not silently
  implied closed.

## 7. Database migrations in this branch

Two, both additive-only (new columns / new table, no data transformation, no
column drops on upgrade):

- `0034_add_consent_proof_scope_fields.py` — adds
  `allowed_action_types`/`allowed_targets` (JSON-encoded TEXT,
  `server_default='[]'`) to `governance_consent_proofs`.
- `0035_add_governance_revocation_epochs.py` — new table
  `governance_revocation_epochs`, composite PK `(organization_id, scope)`.

Both verified with a real `alembic upgrade head` → `downgrade -1` → `upgrade
head` round-trip against an on-disk SQLite file during development (not
merely reasoned about) — reproduction commands in §9.

## 8. Coverage evidence and known limitations

**Test evidence** (as recorded at this branch's head *at the time this
packet section was written* — since superseded by substantially more work;
see the Stage 2 correction below for the current figures):
- Full suite: 3300 passed, 1 skipped, 0 failed (after fixing two pre-existing
  tests this branch's own changes broke — see commit `da77fdb`).
- `ruff check src/ tests/`: clean.
- `ruff format --check src/ tests/`: clean, 394 files.
- `mypy src/`: clean except two pre-existing errors in unrelated
  `biasbuster`/`privacylabel` packages, confirmed present before this branch
  (not touched by it).

> **Stage 2 correction (2026-09-02):** the branch has advanced well past
> this snapshot (226 files changed vs. the merge-base as of the current
> frozen candidate). Current, freshly reproduced figures live in
> [`FROZEN_REVIEW_VERIFICATION.md`](FROZEN_REVIEW_VERIFICATION.md): 3422
> passed / 0 failed / 0 errors; `ruff check` 2 minor errors and `ruff
> format --check` 53 files outstanding (both outside this PR's own touched
> files); `mypy` 4 errors in 2 unrelated files (was 2, now 4 — a real
> increase, driven by the surrounding codebase moving, not by this
> security work). Also newly discovered: no CI/CodeQL has ever run against
> this branch (see that document's §11).

**Known, explicitly-named limitations** (not fabricated as closed):
1. **Purpose is not structurally enforced.** `ConsentProof.purpose` remains
   free text; no `ActionRequest` field represents "the purpose this specific
   action is being requested for" to compare against. See
   `tests/test_heart_production_gauntlet.py::TestAttackVariants::test_04_wrong_purpose_KNOWN_LIMITATION`.
2. **No execution-replay/nonce protection.** A legitimately-resolved
   `AuthorityGrant` has no single-use semantics; reusing it for a second
   identical execution is not denied. See
   `...::test_13_execution_replay_KNOWN_LIMITATION`.
3. **Four of six audit-traced bypass paths remain open** (§6 above).
4. **Gap D's S3 provider has zero live-infrastructure verification** — no
   AWS credentials or Object-Lock-enabled bucket exist in the environment
   this branch was developed in. All 14 of its tests run against a fake
   client reproducing AWS's documented API behavior, not real S3. **This is
   reported as BLOCKED, not as passing.**
5. **Delegation revocation cascading** (`revoke_branch()`) was found by the
   closure audit to already be DB-live with no caching layer — this branch
   did not need to change it, but a reviewer should independently confirm
   that finding rather than take it on trust.

## 9. Exact reproduction commands

```bash
# Full test suite
uv run pytest -q

# Lint / format / types
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy src/

# Migration round-trip verification (0034, 0035)
export DATABASE_URL="sqlite+aiosqlite:////tmp/heart_closure_verify.db"
rm -f /tmp/heart_closure_verify.db
uv run alembic upgrade head
uv run alembic downgrade -1
uv run alembic upgrade head
rm -f /tmp/heart_closure_verify.db

# The specific tests a reviewer should run first
uv run pytest tests/test_authority_resolver.py -v --no-cov          # Gap A
uv run pytest tests/test_revocation_epoch_repository.py tests/test_revocation_propagation.py -v --no-cov  # Gap B
uv run pytest tests/test_heart_production_gate.py -v --no-cov       # Gap C
uv run pytest tests/test_audit_anchor_s3.py -v --no-cov             # Gap D (guarded: pip install -e ".[aws]" first)
uv run pytest tests/test_heart_production_gauntlet.py -v --no-cov   # full gauntlet
```

## 10. Recommended reviewer attack paths

In priority order:

1. **Re-derive the "does empty `allowed_action_types` really deny
   everything" property yourself**, not from this document's claim of it.
   Read `consent_proof.py`'s `build_consent_proof()` default and
   `authority_resolver.py`'s `_resolve_applicable_consent()` together; try to
   construct a `ConsentProof` with an empty scope that still resolves as
   applicable.
2. **Attempt to defeat the root-substitution logic**: can a consent proof be
   crafted so `resolve_authority_grant()` validates it against a root the
   grantee (not the consenting party) controls? Trace `proof.consenting_root_id`
   end to end.
3. **Attempt the concurrency race `RevocationEpochRepository.bump()` was
   originally vulnerable to** (a deadlock, documented and fixed in this
   branch) against a real Postgres backend, not just the `:memory:` SQLite
   engine this branch's own tests use — the fix's correctness under
   Postgres's actual connection-pool behavior has not been independently
   verified.
4. **Attempt every path in §6** that remains open (stdio, legacy keys, demo
   flag, direct `dispatch_tool()` import) against a real running instance
   with `enterprise_mode=true` — confirm the closure audit's own
   characterization of each is still accurate.
5. **Review `heart_production_gate.py`'s readiness queries** — do they
   actually prove the store is *writable*, or only that a `SELECT` succeeds?
   (Currently: only read-checked, named as a possible gap for the reviewer's
   own judgment.)

## 11. Explicit disclaimer

This packet, the code it describes, and every test result cited above were
produced by an AI agent (Claude) working from the repository owner's written
directive, without any human security engineer's involvement in either the
implementation or this packet's own preparation. Treat every claim above as
requiring independent verification, not as pre-validated. **Independent
review status: NOT YET PERFORMED.**
