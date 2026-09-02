# CI-Never-Ran Gap — Root Cause, Fix, and Verified Result

PM decision (this session): close the CI-never-ran gap for PR #55 only.
No API-key rotation, no structural-bypass work, no new enterprise phase,
no merge of PR #50/#54/#55. This document is the required audit trail:
why CI didn't run, exactly what was changed, and the verified result
against the final SHA.

**Final verified SHA: `860c806c510d049ad53c94f8e3e449c0acf7265c`** — real
GitHub Actions CI executed against this exact commit, all 12 checks pass.

## Audit performed

Every item the PM's directive named was checked directly against the
live repository, not assumed:

| Item | Finding |
|---|---|
| Workflow triggers | 5 of 8 workflow files have a `pull_request:` trigger: `ci.yml`, `codeql.yml`, `dco.yml`, `dependency-review.yml`, `gitleaks.yml`. |
| `pull_request` branch filters | **All 5** were scoped to `branches: ["main"]` (or `[main]`) only — none included any other branch name. |
| `push` branch filters | `ci.yml`: `["main", "develop"]`; `codeql.yml`/`scorecard.yml`/`security-scan.yml`: `["main"]`. Irrelevant to PR-level checks (a `push` trigger doesn't populate a PR's own checks tab; the PR's `pull_request` event does, re-firing on every push to the PR branch). |
| Path/path-ignore rules | **None exist in any workflow file** (`grep -n "paths:\|paths-ignore:"` across `.github/workflows/*.yml` returned nothing) — ruled out as a contributing factor. |
| Stacked-PR base behavior | Confirmed via `gh pr view`: PR #55's base is `security/enterprise-neural-remediation` (PR #54's own head branch, not `main`). PR #54's base **is** `main` directly; PR #50's base is also `main` directly, on an unrelated branch (`security/enterprise-neural-phase-0-1`). So the stack is exactly one level: PR #55 → (branch) `security/enterprise-neural-remediation` → PR #54 → `main`. |
| Workflow permissions | `repos/.../actions/permissions`: `{"enabled": true, "allowed_actions": "all", "sha_pinning_required": false}` — Actions are fully enabled repo-wide; nothing here blocks execution. |
| Required status-check names | `branches/main/protection`'s `required_status_checks.contexts`: `Lint · Type-check · Test (3.11)`, `Lint · Type-check · Test (3.12)`, `Build distribution`, `Helm chart lint`, `dco-check`, `gitleaks`, `Accessibility (WCAG2AA)`, `i18n unit tests` — all 8 map directly to job names inside `ci.yml` (6 of the 8) plus `dco.yml` (`dco-check`) and `gitleaks.yml` (`gitleaks`). This confirms exactly which workflow files needed fixing to produce a review-relevant, GitHub-attested check set. **Note:** this protection rule only applies to merges into `main` — it does not gate PR #55 (which targets a different branch) and was not modified. |
| Workflow syntax | `python3 -c "yaml.safe_load(...)"` and `actionlint` run against all 5 affected files, both before and after the fix — valid before, valid after, with the exact same single pre-existing `shellcheck` warning in `ci.yml` (an unrelated, unused loop variable in an existing script — not introduced by this fix, not touched). |
| GitHub Actions enablement/restrictions | Repo is not a fork (`fork: false`), Actions enabled, `allowed_actions: "all"` — no organizational or repo-level restriction is blocking execution. |
| Concurrency rules | No `concurrency:` block in any of the 5 affected workflow files — ruled out. |
| Event conditions | No `if:` conditions at the workflow or job level narrowing execution beyond the `on:` trigger itself in any of the 5 files. |
| Changed-file conditions | None exist (same as path/path-ignore finding above). |
| Whether the PR's current base prevents expected workflows from firing | **Yes — this is the root cause.** Every `pull_request` trigger's `branches:` filter excluded `security/enterprise-neural-remediation`, so GitHub never even evaluated whether to run these workflows for PR #55 — the event's base branch never matched the filter. |

## Root cause (single sentence)

**Every `pull_request`-triggered workflow in this repository filters on `branches: ["main"]` only, and PR #55's base branch is `security/enterprise-neural-remediation` (PR #54's head branch), not `main` — so five workflows (`ci.yml`, `codeql.yml`, `dco.yml`, `dependency-review.yml`, `gitleaks.yml`) have never once evaluated a trigger match for this PR, let alone run.**

Not a broken pipeline, a GitHub infrastructure restriction, an
Actions-enablement problem, or a required-status-check misconfiguration —
a trigger-filter scoping gap, fixed by widening that filter, nothing else.

## The fix — commit 1: trigger widening (`adeb522`)

Added `security/enterprise-neural-remediation` to the `pull_request:
branches:` list in exactly these 5 files, and nowhere else: `ci.yml`,
`codeql.yml`, `dco.yml`, `dependency-review.yml`, `gitleaks.yml`.

`scorecard.yml`, `security-scan.yml`, and `publish.yml` were deliberately
**not** touched: `scorecard.yml` evaluates the repository as a whole on a
schedule/push-to-main basis (not meaningful as a per-PR diff check),
`security-scan.yml` is a scheduled/push-to-main Bandit sweep (ci.yml's own
`pip-audit` step already covers PR-level dependency scanning), and
`publish.yml` is tag-triggered release automation, unrelated to PR
verification.

No job logic, no `uses:` reference (all remain SHA-pinned, independently
re-verified after this change), no required-status-check configuration on
`main`, and no permission/concurrency setting was touched — a pure
trigger-filter widening.

## First real CI run — revealed a genuine, pre-existing failure

Commit `adeb522` was pushed and, for the first time ever, GitHub Actions
actually evaluated PR #55. Result: **9 of 10 checks passed immediately**
(`dco-check`, `gitleaks`, `dependency-review`, `Helm chart lint`,
`i18n unit tests`, `Accessibility (WCAG2AA)`, both CodeQL analyses). **Two
required checks failed**: `Lint · Type-check · Test (3.11)` and `(3.12)`,
both at the "Check formatting with ruff" step.

Investigated per the PM's "STOP on any required-job failure" instruction,
not assumed: both failures were `ruff format --check src/ tests/`
rejecting the exact 53-file formatting debt already disclosed in
`FROZEN_REVIEW_VERIFICATION.md` §3 back in Stage 1 ("never previously
enforced"). This is real, pre-existing debt CI correctly caught for the
first time — not a regression introduced by the trigger fix. Reported to
the PM with full evidence; explicit authorization received to apply the
mechanical formatting fix.

## The fix — commit 2: `ruff format` (`860c806`)

`ruff format src/ tests/` — 52 files reformatted (matching ci.yml's exact
`ruff format --check src/ tests/` invocation scope), whitespace/wrapping
only, no logic change. Re-verified before pushing:
- `ruff check src/ tests/`: clean
- `ruff format --check src/ tests/`: clean
- `mypy src/responsibleai`: clean (matches ci.yml's exact `mypy
  src/responsibleai` scope — the 2 pre-existing mypy errors flagged in
  earlier stages live in `src/privacylabel` and `src/biasbuster`, outside
  this scope, untouched, not CI-blocking)
- Full local suite: **3442 passed, 0 failed, 0 errors** — unchanged from
  before the reformat.

## Final verified result — all required checks pass

Pushed as `860c806c510d049ad53c94f8e3e449c0acf7265c`. GitHub Actions run
IDs: CI `33619134110`, CodeQL `33619134064` (+ overall `CodeQL` context
run `100212126309`), DCO `33619134066`, Dependency Review `33619134081`,
Gitleaks `33619134303`.

| Check | Result | Duration |
|---|---|---|
| dco-check | ✅ pass | 5s |
| gitleaks | ✅ pass | 8s |
| dependency-review | ✅ pass | 9s |
| Helm chart lint | ✅ pass | 5s |
| i18n unit tests | ✅ pass | 14s |
| Accessibility (WCAG2AA) | ✅ pass | 1m20s |
| CodeQL analysis (python) | ✅ pass | 1m28s |
| CodeQL analysis (javascript-typescript) | ✅ pass | 1m11s |
| CodeQL (overall context) | ✅ pass | 3s |
| Lint · Type-check · Test (3.11) | ✅ pass | 6m7s |
| Lint · Type-check · Test (3.12) | ✅ pass | 4m45s |
| Build distribution | ✅ pass | 51s |

**All 12 checks pass.** PR #55: `mergeable: MERGEABLE`,
`mergeStateStatus: CLEAN` (per `gh pr view`, unchanged fact, not itself
evidence of anything beyond GitHub's own merge-conflict computation).

## Reconciliation — local vs. GitHub CI

No discrepancy. Local verification (this session, `.venv` Python 3.11.15)
and GitHub's CI matrix (3.11 and 3.12) agree: full suite green, ruff
clean, mypy clean within its scoped path. GitHub CI additionally ran
CodeQL semantic analysis and Dependency Review, neither of which this
session's local tooling covers — both pass, first real evidence of either
ever having evaluated this branch's diff.

## Why this specific branch name, not a wildcard

`security/enterprise-neural-remediation` is added by exact name, not a
glob like `security/**`. A wildcard would silently enable these workflows
for every future branch matching that pattern, broader than what this PM
decision authorized ("close the CI-never-ran gap for PR #55" — singular,
scoped). A future PR stacking on yet another new intermediate branch will
need its own explicit, reviewed addition.

## Independent human security review: NOT YET PERFORMED

This CI fix produces GitHub-attested automated checks. It is not, and is
not claimed to be, a substitute for independent human security review.
