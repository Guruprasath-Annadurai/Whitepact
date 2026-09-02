# WhitePact Heart Production Closure + Enforcement Chokepoint Closure — Handoff Summary

**For**: external review (ChatGPT or any other reviewer)
**Repo**: `Guruprasath-Annadurai/Whitepact`
**Branch/PR**: `security/heart-production-closure` — [PR #55](https://github.com/Guruprasath-Annadurai/Whitepact/pull/55)
**Base**: stacked on PR #54's exact tested head (`32eb2a6b`), against `security/enterprise-neural-remediation`. Does not merge, modify, or touch PR #50 or PR #54.
**Status**: Open, unmerged. Full suite green (3422 passed, 0 failed, 0 errors — independently reproduced at commit `e1b1ddf`, see [`docs/security-review/FROZEN_REVIEW_VERIFICATION.md`](../security-review/FROZEN_REVIEW_VERIFICATION.md)). **Independent human security review has not occurred.**

> **Stage 2 correction (2026-09-02):** the "3339 passed, 1 skipped" figure below (§ Current verified state) is superseded by the freshly reproduced Stage 1 result. Also newly discovered during the freeze/verification process: no GitHub Actions CI or CodeQL run has ever executed against this branch or PR #55 — its base branch (`security/enterprise-neural-remediation`) doesn't match the workflow's `pull_request: branches: ["main"]` trigger. See `FROZEN_REVIEW_VERIFICATION.md` §11 for the full root-cause.

---

## What this was

Two initiatives, run back to back, both from the same governing directive style (audit before code, fail-closed by default, never manipulate wording to hit a target answer).

**Initiative 1 — Heart Production Closure.** PR #54's own remediation work was accepted as complete at the implementation/test level, but left four real gaps between "the Heart primitives exist and are tested" and "Heart-backed authority is an actual production invariant." Closed one at a time, audit-first (`docs/heart-production-closure/00_CLOSURE_AUDIT.md` written before any code changed).

**Initiative 2 — Heart Enforcement Chokepoint Closure.** After the four gaps closed, a follow-up review correctly flagged that closing the gaps wasn't the same as making Heart *unavoidable* — four possible bypass paths (stdio, legacy keys, a demo-auth flag, direct in-process function calls) were named as the remaining risk. A full execution-path audit (Phase E0) was run before touching any code, which found six real issues — the four named, plus two more the audit itself surfaced.

## Initiative 1 — the four gaps, final status

| Gap | What it closes | Status |
|---|---|---|
| A | Consent never consulted by legitimacy resolution | `resolve_authority_grant()` now looks up, integrity-verifies, and scope-matches a persisted `ConsentProof` before granting authority — resolved against the consent's own root, not the acting identity's. 13 negative/positive tests. |
| B | Revocation state in-memory/process-local | `RevocationEpoch` persisted (new table, migration 0035), race-safe `bump()` — a real deadlock was found and fixed during testing (querying a second DB connection from inside an already-open transaction, against a pool with none spare). Multi-instance propagation tested directly. |
| C | Heart production wiring opt-in/default-off | `enterprise_mode=true` now also requires `mcp_governance_enabled=true` and reachable root-authority/revocation-epoch stores, or the process refuses to start. |
| D | No real durable external audit-anchor provider | `S3ObjectLockAnchorProvider` — idempotent via S3's `IfNoneMatch` conditional writes. **Live AWS verification is explicitly reported as BLOCKED** (no credentials/infra in this environment) — 14 tests against a fake client reproducing AWS's real documented API behavior, not claimed as live-verified. |

Plus: an end-to-end production authority gauntlet (full chain → revoke → deny, and the ~14 named attack variants — two honestly marked as known, unenforced limitations: purpose isn't structurally checked, there's no execution-replay/nonce primitive), and `docs/security-review/PR50_PR54_INDEPENDENT_REVIEW_PACKET.md`, explicitly labeled "Independent review status: NOT YET PERFORMED."

## Initiative 2 — the E0 audit and what it found

`docs/heart-production-closure/ENFORCEMENT_PATH_MATRIX.md` — every path capable of reaching real tool/action execution, grounded in file:line reads, not inference. Two findings beyond the four originally named turned out to matter more:

1. **Headline finding**: Gap A's consent-backed legitimacy (above) had **zero live call sites**. Both places `resolve_authority_grant()` is actually called in production (`mcp/governance_integration.py`, `mcp/upstream_dispatch.py`) omitted the `consent_repo` parameter — fully wired and tested, but structurally unreachable. Consent was never actually consulted in production, only in tests.
2. **Critical wiring bug**: Gap C's fail-closed startup gate (`verify_heart_production_enforcement()`) was only ever called from the dashboard process's own startup. The separate `whitepact-mcp-http` process — where stdio, legacy-key, and demo-auth bypasses actually live — never called it at all. The invariant this gate exists to guarantee never protected the process that needed it.

One of the four originally-named bypasses also turned out to be a factual error, corrected inline in the audit doc rather than silently fixed: "legacy DB-backed API key reaches ungoverned dispatch with no org" doesn't happen — `OrgRepository.authenticate()` always returns a real org on a match. The real issue in that category was the unauthenticated demo-auth flag, which was real.

## Fixes, in the order they landed

| Fix | What changed | Status |
|---|---|---|
| Consent wiring | `consent_repo` threaded through `GovernanceServices`, `apply_upstream_governance()`, and `resume_approval()`; wired at both real construction sites | **Fixed** — regression test through the real HTTP dispatch path, not just the resolver in isolation |
| E2 — stdio | `enterprise_mode=true` now blocks stdio entirely (previously allowed MINIMAL/LOW-risk tools with zero check) | **Fixed** |
| E4 — demo-auth + process wiring | `enterprise_mode=true` refuses to start if the demo flag is also set; the startup gate itself now runs in both processes | **Fixed** |
| E3 — legacy keys | Audit corrected — no such path exists on the hosted MCP transports | **Corrected, not a bug** |
| E6 — approval-resume | `resume_approval()` re-checks Heart legitimacy fresh at execution time, not just at the original decision time — closes a real revoke-while-queued window | **Fixed** |
| E5 — direct dispatch | `dispatch_tool()` renamed to `_dispatch_tool_unchecked()`; a drift-guard test fails the suite if a third call site, a package re-export, or a public alias ever appears | **Mitigated, not fully closeable** — a caller with repo access can still import a private Python function directly; no language mechanism or wrapper prevents that |

## Honest final verdict

```
stdio bypass:              CLOSED
legacy-key bypass:         CLOSED (corrected — never real)
demo-auth bypass:          CLOSED
direct-dispatch bypass:    MITIGATED, not closeable (structural, in-process only)

Can any supported governed production execution bypass Heart?
YES — narrowly, via direct in-process import of a now explicitly-named,
audited, non-re-exported private function. Not reachable over any network path.

VERDICT: NOT CLOSED
```

Not rounded up. Every network-reachable path genuinely requires Heart legitimacy when `enterprise_mode` is on. What's left is a property of Python, not a missed wiring or a configuration gap.

## Current verified state

- Full suite: **3422 passed, 0 failed, 0 errors** (freshly reproduced at commit `e1b1ddf`, see `FROZEN_REVIEW_VERIFICATION.md` §1 — this supersedes the "3339 passed, 1 skipped" figure this line previously carried)
- `ruff check`: 2 minor errors, `mypy`: 4 errors in 2 unrelated files (`biasbuster`/`privacylabel`, confirmed pre-existing and outside this PR's touched code) — `ruff format --check`: 53 files not yet conforming, never previously enforced. See `FROZEN_REVIEW_VERIFICATION.md` §2-4 for exact detail; none of this is silently dropped.
- All 37 migrations (0001-0037) verified with a real `alembic upgrade head` / `downgrade base` round-trip against a real local PostgreSQL 17 database (not SQLite, not simulated) — see `FROZEN_REVIEW_VERIFICATION.md` §12.
- 68 commits (merge-base to current HEAD), each DCO-signed — 100% verified, not sampled.
- Everything pushed to GitHub; PR #55 open. **No GitHub Actions CI or CodeQL check has ever run against this branch** — see `FROZEN_REVIEW_VERIFICATION.md` §11 for why.

## What's explicitly deferred (named, not hidden)

- Independent human security review of PR #50, PR #54, or this branch has not occurred.
- Live AWS S3 Object Lock verification for the audit-anchor provider has not occurred (no credentials in this environment).
- `ExecutionAuthorization` is not cryptographically bound to Heart's legitimacy-verdict digest — the check runs synchronously immediately before execution on every path (including the newly-fixed approval-resume), so there's no live window for divergence, but this is a different, already-argued mechanism than literal binding, not the same thing.
- Purpose compatibility and execution-replay protection are not structurally enforced anywhere in this codebase's authority model — both named explicitly in the gauntlet's own test docstrings.
- The direct-dispatch bypass (above) remains open by construction, not oversight.

## Where to look

- [PR #55](https://github.com/Guruprasath-Annadurai/Whitepact/pull/55) — the cumulative diff and CI status
- `docs/heart-production-closure/00_CLOSURE_AUDIT.md` — Initiative 1's Rule 0 audit
- `docs/heart-production-closure/ENFORCEMENT_PATH_MATRIX.md` — Initiative 2's Phase E0 audit, plus a live "post-E0 status" table tracking every finding's current fix status
- `docs/security-review/PR50_PR54_INDEPENDENT_REVIEW_PACKET.md` — prepared for a real human reviewer, explicitly not claiming to be one
- `tests/test_heart_production_gauntlet.py` — the end-to-end chain + attack-variant test
- `tests/test_dispatch_tool_unchecked_call_sites.py` — the E5 drift guard

## Separately, found and reported but not fixable in-repo

A GitHub Dependabot high-severity alert (`extract-zip` symlink path traversal, CVE-2026-56876) on the default branch was investigated: it's a transitive dependency of `pa11y-ci` → `puppeteer` → `@puppeteer/browsers`, used only in CI to extract Puppeteer's own trusted Chromium download from Google's CDN — never processes user-supplied files. No patched version of `extract-zip` exists anywhere upstream yet (2.0.1 is the latest npm release, still vulnerable); confirmed by dry-running `npm audit fix --force` against every version in the chain, none resolve it. No code fix exists to make. Reported to the repo owner with the recommendation to dismiss the alert with that documented rationale, pending their decision — not dismissed unilaterally.
