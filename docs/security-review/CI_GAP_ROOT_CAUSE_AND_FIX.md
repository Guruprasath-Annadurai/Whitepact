# CI-Never-Ran Gap — Root Cause and Fix

PM decision (this session): close the CI-never-ran gap for PR #55 only.
No API-key rotation, no structural-bypass work, no new enterprise phase,
no merge of PR #50/#54/#55. This document is the required audit trail:
why CI didn't run, exactly what was changed, and nothing more.

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
| Workflow syntax | `python3 -c "yaml.safe_load(...)"` and `actionlint` run against all 5 affected files, both before and after the fix — valid before, valid after, with the exact same single pre-existing `shellcheck` warning in `ci.yml` (an unrelated, unused loop variable in an existing script, line number only shifted by the added comment lines — not introduced by this fix, not touched). |
| GitHub Actions enablement/restrictions | Repo is not a fork (`fork: false`), Actions enabled, `allowed_actions: "all"` — no organizational or repo-level restriction is blocking execution. |
| Concurrency rules | No `concurrency:` block in any of the 5 affected workflow files — ruled out. |
| Event conditions | No `if:` conditions at the workflow or job level narrowing execution beyond the `on:` trigger itself in any of the 5 files. |
| Changed-file conditions | None exist (same as path/path-ignore finding above). |
| Whether the PR's current base prevents expected workflows from firing | **Yes — this is the root cause.** Every `pull_request` trigger's `branches:` filter excluded `security/enterprise-neural-remediation`, so GitHub never even evaluated whether to run these workflows for PR #55 — the event's base branch never matched the filter. |

## Root cause (single sentence)

**Every `pull_request`-triggered workflow in this repository filters on `branches: ["main"]` only, and PR #55's base branch is `security/enterprise-neural-remediation` (PR #54's head branch), not `main` — so five workflows (`ci.yml`, `codeql.yml`, `dco.yml`, `dependency-review.yml`, `gitleaks.yml`) have never once evaluated a trigger match for this PR, let alone run.**

This is not a broken pipeline, a GitHub infrastructure restriction, an
Actions-enablement problem, or a required-status-check misconfiguration —
it is a trigger-filter scoping gap, and it is fixed by widening that
filter, nothing else.

## The fix

Added `security/enterprise-neural-remediation` to the `pull_request:
branches:` list in exactly these 5 files, and nowhere else:

- `.github/workflows/ci.yml`
- `.github/workflows/codeql.yml`
- `.github/workflows/dco.yml`
- `.github/workflows/dependency-review.yml`
- `.github/workflows/gitleaks.yml`

`scorecard.yml`, `security-scan.yml`, and `publish.yml` were deliberately
**not** touched: `scorecard.yml` evaluates the repository as a whole on a
schedule/push-to-main basis (not meaningful as a per-PR diff check),
`security-scan.yml` is a scheduled/push-to-main Bandit sweep (ci.yml's own
`pip-audit` step already covers PR-level dependency scanning), and
`publish.yml` is tag-triggered release automation, unrelated to PR
verification. Extending any of those would be scope creep beyond "fix the
real CI execution problem."

No job logic, no `uses:` reference (all remain SHA-pinned, independently
re-verified after this change), no required-status-check configuration on
`main`, and no permission/concurrency setting was touched. This is a pure
trigger-filter widening, five one-line-comment-plus-one-line-change edits.

## Why this specific branch name, not a wildcard

`security/enterprise-neural-remediation` is added by exact name, not a
glob like `security/**`. A wildcard would silently enable these workflows
for every future branch matching that pattern, which is broader than what
this PM decision authorized ("close the CI-never-ran gap for PR #55" —
singular, scoped). If a future PR stacks on yet another new intermediate
branch, that will need its own explicit, reviewed addition — not covered
here, and not assumed.
