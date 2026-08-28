# OpenSSF Supply-Chain Hardening Report

**Date:** 2026-08-29
**Branch:** `security/openssf-readiness-matrix`
**Scope:** what supply-chain hardening exists today (this branch, and cross-referenced from PR #52 which is unmerged), vs. what's genuinely still missing, vs. what this pass added.

---

## Already real, on this branch (`security/enterprise-neural-remediation` lineage)

Not from PR #52 — this is what the parallel "gap by gap" remediation already built, confirmed present by reading the files directly:

- `SECURITY.md` (root) — vulnerability reporting process.
- `.github/CODEOWNERS` — single-owner, deliberately not fabricated with fake sub-maintainers (see the file's own comment).
- `.github/workflows/dco.yml` — DCO sign-off enforcement, required status check.
- `.github/workflows/gitleaks.yml` — secret scanning, required status check.
- `.github/workflows/security-scan.yml` — weekly + on-push Bandit SAST and pip-audit dependency scan, uploaded as CI artifacts.
- `.github/workflows/codeql.yml`, `.github/workflows/scorecard.yml`, `.github/workflows/dependency-review.yml` — present (dependency-review is intentionally not a required check yet; see `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`'s stated reason: the repo's Dependency graph setting isn't enabled, a separate pre-existing gap).
- Branch protection on `main`: PR required, force-push and deletion blocked, `enforce_admins: true`, 8 required status checks — verified via `gh api` `GET` in `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`.
- `compliance/OPENSSF_SECRET_SCAN.md` — a documented one-time secret-scan pass (Gitleaks CI job above is the ongoing, repeatable version).

## Real hardening in PR #52 (`security/openssf-hardening`, unmerged) — cross-referenced, not duplicated

Confirmed by `git show origin/security/openssf-hardening:<path>` and `git diff --stat main...origin/security/openssf-hardening` (18 files changed):

- GitHub Actions pinned to full 40-character immutable commit SHAs (all workflow files).
- Workflow token permissions reduced to least privilege; release/OIDC write permissions moved to the publishing job only (`.github/workflows/publish.yml`).
- `.github/dependabot.yml` — weekly Dependabot coverage for GitHub Actions, Python (pip), and Docker.
- Docker base/service images pinned to immutable digests while keeping readable tags (`Dockerfile`, `docker-compose.prod.yml`).
- `scripts/check_pinned_actions.py` + `.github/workflows/openssf-policy.yml` — a CI policy guard rejecting any future movable (non-SHA) Action reference.
- `.github/workflows/reproducible-build.yml` — build-twice-and-diff reproducibility gate. **This session locally replayed its exact logic** (see `OPENSSF_GOLD_GAP_ANALYSIS.md`) and confirmed it produces identical SHA-256 digests for this repo's wheel/sdist today.
- `docs/CODE_REVIEW.md` — review-standard document.
- `scripts/check_statement_coverage.py` — pure statement-coverage gate script (this session used its formula, not the file itself, since it isn't on this branch).
- `.bestpractices.json` — Best Practices Badge automation evidence file.

**None of this was merged, cherry-picked, or reproduced file-for-file onto this branch.** It's cited by path so a reviewer can diff PR #52 directly rather than trusting a second copy.

## Genuinely still missing (real gaps, not yet closed by either branch)

| Gap | Status | Why not fixed in this pass |
|---|---|---|
| Per-file SPDX license identifiers | Missing (0/205 `src/` files) | Mechanical but touches every source file — deliberately deferred as a separate pass to avoid merge conflicts with concurrent work on `security/enterprise-neural-remediation` (per this task's own instructions and PR #52's own stated reasoning). |
| Per-file copyright headers | Missing | Same as above; typically done in the same pass as SPDX headers. |
| `dependency-review` as a required status check | Not required | Blocked on a repository *setting* (Dependency graph), not a workflow bug — see `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`. This is a `Settings → Code security` toggle, listed in `FOUNDER_FINAL_ACTIONS.md`. |
| GitHub Action SHA pinning, Dependabot, token-permission scoping, reproducible-build workflow | Exist only on unmerged PR #52 | Not this pass's job to merge PR #52 — the master directive is explicit that this pass should not duplicate or merge that work, only cross-reference it. Once PR #52 merges, these become real on `main`/this lineage too. |
| Hard CI gate on branch coverage (`--fail` flag) | Informational-only today | `scripts/check_branch_coverage.py --fail` exists and could be flipped on now that 83.32% is confirmed above the 80% threshold — flagged as a low-risk, easy follow-up, **not done in this pass** because touching `.github/workflows/*` in a way that changes CI pass/fail behavior is explicitly out of scope for this pass ("do NOT touch any `.github/workflows/*` file in a way that could break CI; if unsure, document as recommendation instead"). |
| Hard CI gate on statement coverage | Doesn't exist yet at all (`check_statement_coverage.py` is PR #52-only, unmerged) | Same reasoning — recommend merging PR #52's script and wiring it in as a follow-up, not doing it here. |

## What this pass did NOT add to `.github/workflows/*`

Per the explicit instruction not to touch workflow files in a way that could break CI, and to document rather than implement anything uncertain: **no workflow file was modified in this pass.** The two coverage-gate flips above are recommendations, not changes.

## What this pass did add

Five new documents under `compliance/openssf/` (this matrix, gap analysis, human-requirements list, this hardening report, the Scorecard checklist, and `FOUNDER_FINAL_ACTIONS.md`) — all purely additive markdown, zero risk to CI or runtime behavior. No `SECURITY.md` or `CODEOWNERS` were added because both already exist on this branch (see "Already real" above) — nothing to add there.

## Net assessment

Between the parallel remediation branch's real work and PR #52's real (unmerged) work, WhitePact's supply-chain posture is materially stronger than a "just pinned some Actions" pass — Dependabot, SHA pinning, and reproducible builds exist in a reviewable PR; DCO, Gitleaks, and branch protection are already live on this lineage. The genuinely open items are per-file license metadata (mechanical, deferred deliberately) and merging PR #52 itself (a decision for the repository owner, not this pass).
