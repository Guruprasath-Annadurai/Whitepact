# Frozen Review Verification — Stage 1

Every check below was freshly re-run against this exact commit — not carried
forward from a prior session's memory. Where a prior report claimed a
number (e.g. "3422 passed"), that number is treated as unverified until
reproduced here; this document records the reproduction, not the memory.

**Reviewed commit (frozen SHA):** `3011a01c7d107c93ce249c29f8caa4c215cc4bff`
(HEAD of `security/heart-production-closure` immediately after Stage 0's
baseline-doc commit; verified via `git rev-parse HEAD` at the start of this
pass — working tree otherwise clean except the two pre-existing untracked
local artifacts noted in [FROZEN_REVIEW_BASELINE.md](FROZEN_REVIEW_BASELINE.md)).

**Environment:** macOS (Darwin 25.6.0), project `.venv` Python 3.11.15
(Clang 22.1.3), Node v26.0.0, local PostgreSQL 17.10 (Homebrew, running as
a `brew services` LaunchAgent) plus PostgreSQL 16 client tools also on
`PATH`.

---

## 1. Full pytest suite

- **Command:** `.venv/bin/python -m pytest -q`
- **Result:** `3422 passed, 6 warnings` — **0 failed, 0 errors**
- **Duration:** 213.82s (3:33) test time; 3:38.51 wall including interpreter startup/collection
- **Coverage:** 91% overall (13,016 statements, 913 missed; branch coverage 2,638/2,912)
- **Evidence:** full log at `/tmp/stage1_verification/pytest_full.log` (not committed — local-only evidence artifact)
- **Warnings, all reviewed and benign:**
  - 2× `InsecureKeyLengthWarning` from `PyJWT` — both are **intentional**, from tests that verify weak keys (1024-bit RSA, 6-byte HMAC) are correctly *rejected* (`test_crypto_policy.py`, `test_verifiable_credential.py`, `test_oidc.py`).
  - 2× `UserWarning` from `test_deepfake_detector.py` — expected, notes the optional `torch`/`torchvision` extra isn't installed so the detector runs in heuristic-only mode; the tests are written to pass in that mode.
  - 1× `UserWarning` from `google-adk` marking an experimental feature flag — third-party library notice, not this project's code.
- **Limitation:** this reproduces the prior session's "3422 passed" figure exactly, but that agreement is *this run's own independent result*, not a carry-forward of the earlier claim.

## 2. Lint — `ruff check`

- **Command:** `.venv/bin/ruff check .`
- **Result:** **2 errors**, both `B007` (unused loop control variable) in `examples/05_cost_intelligence.py:30` (variables `provider`, `model` unused in an example script, outside `src/`/`tests/`)
- **Duration:** 0.175s
- **Evidence:** `/tmp/stage1_verification/ruff_check.log`
- **Assessment:** cosmetic, in an example/demo script, not in reviewed application or test code. Not fixed in this stage per the "no source changes outside evidence/blocker/dormant-control/deployment/integration-candidate work" rule — flagged here rather than silently dropped or silently fixed.

## 3. Format check — `ruff format --check`

- **Command:** `.venv/bin/ruff format --check .`
- **Result:** **53 files would be reformatted** (of 668 checked); 615 already formatted
- **Duration:** 0.227s
- **Evidence:** `/tmp/stage1_verification/ruff_format.log`
- **Assessment:** a mix of `.py` files and `.md` files with embedded Python code blocks (ruff formats fenced Python in Markdown too). None of these are new regressions introduced by this review — this is the first time `ruff format --check` has been run as part of this review process, so no baseline exists to diff against. Recorded as a known gap, not silently dropped.

## 4. Type-check — `mypy`

- **Command:** `.venv/bin/mypy src`
- **Result:** **4 errors in 2 files** (212 source files checked)
  - `src/privacylabel/federated/client.py:191-192` — two `arg-type` errors passing `object`-typed values where `str`/`float` expected
  - `src/biasbuster/providers/anthropic_provider.py:46` — `call-overload` errors: the call site passes a `temperature` kwarg the current Anthropic SDK's `AsyncMessages.create()` overloads don't accept, and doesn't match any overload's required-kwarg shape
- **Duration:** 1.9s
- **Evidence:** `/tmp/stage1_verification/mypy.log`
- **Assessment:** both files are in unrelated subsystems (`privacylabel`, `biasbuster`) — not the `responsibleai` governance/heart code this PR's security work touches. Genuine type errors, not previously known to this review process; recorded as-is rather than dropped.

## 5. Security lint — `bandit`

- **Command:** `.venv/bin/bandit -r src -ll -q`
- **Result:** **0 medium/high-severity findings**, exit code 0
- **Duration:** 2.53s
- **Evidence:** `/tmp/stage1_verification/bandit.log`
- **Note:** one informational line from bandit's own `nosec`-tracking machinery (a `# nosec B104` suppression comment in `mcp/server.py:938` that bandit notes didn't correspond to an actual B104 finding at `-ll` severity) — not a finding, a bandit housekeeping message.

## 6. Dependency vulnerabilities — `pip-audit`

- **Command:** `.venv/bin/pip-audit --strict`
- **Result:** **No known vulnerabilities found**
- **Duration:** 31.7s
- **Evidence:** `/tmp/stage1_verification/pip_audit.log`

## 7. npm audit

- **Command:** `npm audit --omit=dev`
- **Result:** **0 vulnerabilities**
- **Duration:** 2.06s
- **Evidence:** `/tmp/stage1_verification/npm_audit.log`

## 8. Secret scanning — `gitleaks`

- **Command:** `gitleaks detect --source .`
- **Result:** **no leaks found**, 68 commits scanned (~1.58 MB), exit code 0
- **Duration:** 0.6s
- **Evidence:** `/tmp/stage1_verification/gitleaks.log`
- **Scope note:** scanned the full local commit history reachable from `HEAD` (68 commits), not limited to the merge-base..HEAD range — broader than strictly required, kept as-is since it's a superset.

## 9. DCO sign-off

- **Command:** manual check of every commit from merge-base (`9dcdc1b`) to `HEAD` for a `Signed-off-by` trailer
- **Result:** **68/68 commits carry `Signed-off-by`** — zero missing
- **Duration:** <1s

## 10. GitHub Actions SHA-pinning

- **Command:** `grep -rn "uses:" .github/workflows/*.yml` filtered for any `uses:` not pinned to a 40-character commit SHA (local composite actions via `uses: ./` excluded as N/A)
- **Result:** **0 unpinned external actions found** — every `uses:` reference across all workflow files is pinned to a full commit SHA
- **Duration:** <1s

## 11. CodeQL / CI status on this branch

- **Command:** `gh api repos/.../commits/<sha>/check-runs`, `gh pr checks 55`, `gh run list`
- **Result:** **No CI runs, no CodeQL runs, and no check-runs of any kind exist for `security/heart-production-closure` or for PR #55**, at either the Stage-0 SHA (`6878cc7`) or the Stage-1 SHA (`3011a01`). `gh pr checks 55` reports: `no checks reported on the 'security/heart-production-closure' branch`.
- **Root cause, verified (not assumed):** `.github/workflows/ci.yml` triggers are `push: branches: ["main", "develop"]` and `pull_request: branches: ["main"]`. PR #55's base branch is `security/enterprise-neural-remediation`, **not** `main` — so the `pull_request` trigger never matches, and this branch is neither `main` nor `develop` for the `push` trigger either. This is confirmed structural (workflow trigger scoping given the PR's stacked base), not a broken or flaky CI system — other branches in this repo (e.g. `security/scorecard-max-hardening`, which targets `main` directly) do have full green CI runs including CodeQL.
- **Assessment:** this is a real gap that must be carried into the review packet and attack map: **this entire branch's diff has never been evaluated by CodeQL, by the repo's CI lint/type/test matrix, by Dependency Review, by the Gitleaks Action, by Scorecard, or by any other Actions-based check — only by this manual, local verification pass.** It is not disguised as CI-verified anywhere in this document.

## 12. PostgreSQL migration round-trip

- **Setup:** fresh local database via `createdb`, using PostgreSQL 17.10 (Homebrew), `RAI_DB_URL` pointed at it (the correct env var per `migrations/env.py`'s `_resolve_url()` — note an earlier attempt in this same pass using `DATABASE_URL` silently fell through to the SQLite default, which is itself worth flagging: `_resolve_url()` has no validation/warning when an unrecognized env var name is set, so a misconfigured deployment could silently migrate the wrong database)
- **Upgrade:** `alembic upgrade head` — all 37 migrations (`0001` → `0037`) applied cleanly in sequence, ending with 39 tables (37 app tables + `alembic_version` + 1) present in `information_schema.tables`
- **Downgrade:** `alembic downgrade base` — all 37 migrations reversed cleanly, back to 1 table (`alembic_version`) remaining
- **Result:** **clean round-trip in both directions against real PostgreSQL 17**, not simulated
- **Cleanup:** test database dropped after verification; no residual state left

## 13. SPDX / license headers

- **LICENSE file:** present at repo root.
- **Per-file SPDX headers:** **0 of 212 `src/**/*.py` files carry an `SPDX-License-Identifier` header.** This was checked against the project as a whole, not just reviewed files — it is evidently not a convention this project uses anywhere, not a gap introduced by this PR's diff. Recorded for completeness per the checklist, not flagged as a regression.

## 14. Diff integrity

- **Command:** `git diff --stat <merge-base>..HEAD`
- **Result:** 226 files changed, 31,484 insertions(+), 330 deletions(-) — matches the figure independently recorded in Stage 0's baseline doc, confirming no drift between the two capture points.

---

## Summary table

| Check | Result | Status |
|---|---|---|
| pytest (full suite) | 3422 passed, 0 failed, 0 errors | ✅ CLEAN |
| ruff check | 2 errors (examples/, non-reviewed code) | ⚠️ MINOR, OUT OF SCOPE |
| ruff format --check | 53 files unformatted | ⚠️ NOT PREVIOUSLY ENFORCED |
| mypy | 4 errors in 2 unrelated files | ⚠️ MINOR, OUT OF SCOPE |
| bandit | 0 findings | ✅ CLEAN |
| pip-audit | 0 vulnerabilities | ✅ CLEAN |
| npm audit | 0 vulnerabilities | ✅ CLEAN |
| gitleaks | 0 leaks (68 commits) | ✅ CLEAN |
| DCO | 68/68 signed | ✅ CLEAN |
| Actions SHA-pinning | 0 unpinned | ✅ CLEAN |
| CodeQL / repo CI | **never run on this branch** (base-branch trigger mismatch) | ❌ GAP — CARRY TO REVIEW PACKET |
| PostgreSQL migration round-trip | clean both directions, real Postgres 17 | ✅ CLEAN |
| SPDX headers | not used project-wide | ℹ️ INFORMATIONAL |
| Diff integrity | matches Stage 0 baseline | ✅ CLEAN |

**No failing check was silently dropped.** The two "minor, out of scope" rows and the one "not previously enforced" row are pre-existing conditions outside this PR's own touched files; the CodeQL/CI gap is the one finding in this stage that materially affects review readiness and must be surfaced prominently, not softened, in the Stage 3 review packet and Stage 5 gate decision.
