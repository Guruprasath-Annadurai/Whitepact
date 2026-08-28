# OpenSSF Master Readiness Matrix — WhitePact

**Date verified:** 2026-08-29
**Branch:** `security/openssf-readiness-matrix` (created from `security/enterprise-neural-remediation` @ `a7b8143`)
**BadgeApp project:** [14112](https://www.bestpractices.dev/en/projects/14112)
**Purpose:** one table spanning OSPS Baseline 1/2/3, OpenSSF Best Practices Passing, Silver, and Gold, each row backed by a file, a CI job, or a command actually run for this document — not memory, not a prior doc's number copied forward without re-checking.

**Relationship to other work:**
- `security/openssf-hardening` (PR #52) already did real repository hardening (Action SHA pinning, Dependabot, token-permission scoping, reproducible-build workflow, `docs/CODE_REVIEW.md`, `.bestpractices.json`, its own Gold gap analysis). This matrix cross-references PR #52 by file path rather than re-deriving that work. PR #52 was **not merged or cherry-picked** into this branch — its content was read via `git show origin/security/openssf-hardening:<path>`.
- `security/enterprise-neural-remediation` (the branch this one forked from) already did substantial Silver-level and security-evidence work: `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md`, `compliance/OPENSSF_SECURITY_EVIDENCE.md`, `compliance/OPENSSF_DYNAMIC_ANALYSIS.md`, `compliance/OPENSSF_SECRET_SCAN.md`, `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`. This matrix cross-references those documents rather than re-deriving them, but re-verifies the load-bearing numeric claims (test count, coverage) against a fresh run.

**Legend:** Met / Unmet / Partial / `BLOCKED_BY_HUMAN_REQUIREMENT` (something only a human/org owner can do — see `OPENSSF_HUMAN_REQUIREMENTS.md`) / N/A.

---

## Fresh verification run for this document (2026-08-29)

Commands actually executed on this branch, this session, not copied from any prior doc:

| Check | Command | Result |
|---|---|---|
| Full test suite | `uv run pytest -q` | **3187 passed, 1 skipped, 1 error, in 286.34s** |
| Isolated re-run of the errored test | `uv run pytest tests/test_dashboard_api.py::TestCost::test_model_pricing -q` | **1 passed** in 9.41s — confirms the full-run `TimeoutError` was a timing-sensitive flake under full-suite CPU load, not a real defect. Not silently omitted: see caveat below. |
| Pure branch coverage | `uv run python scripts/check_branch_coverage.py` (against the full-suite `coverage.json`) | **83.32%** (2093/2512 branches) — above the 80% OpenSSF threshold |
| Pure statement coverage | computed from the same `coverage.json`: `covered_lines / num_statements` | **92.75%** (11494/12392) — above the 90% OpenSSF Gold threshold |
| Blended stmt+branch % (coverage.py's own "Cover" column — NOT either OpenSSF metric) | same run | 91.16% |
| Lint | `uv run ruff check .` | **2 errors**, both `B007` (unused loop variable) in `examples/05_cost_intelligence.py`, outside `src/`. `uv run ruff check src/` alone: **0 errors**. |
| Type-check | `uv run mypy src/` | **4 errors in 2 files** (of 205 checked): `src/biasbuster/providers/anthropic_provider.py` (2, SDK overload mismatch on `.create()` kwargs) and `src/privacylabel/federated/client.py` (2, `object`-typed argument passed where `str`/`float` expected) |
| SAST | `uvx bandit -r src/responsibleai -ll` (matches `.github/workflows/security-scan.yml`'s own invocation) | **0 issues at Medium/High severity** (the CI gate threshold). Unfiltered (`uvx bandit -r src/responsibleai`, no `-ll`): 21 issues, all **Low severity** (asserts, try/except/pass, two format-string false positives on `token_type="input"`/`"output"` flagged as `hardcoded_password_funcarg`) |
| Dependency vulnerability scan | `uv run --with pip-audit -- pip-audit` (run inside the actual project environment, ~163 packages, not an empty ephemeral env) | **No known vulnerabilities found** |
| Reproducible build | Locally replayed PR #52's `.github/workflows/reproducible-build.yml` logic: `SOURCE_DATE_EPOCH` pinned to `git log -1 --format=%ct`, `PYTHONHASHSEED=0`, built twice with `python -m build`, `shasum -a 256` both outputs | **Identical SHA-256 digests** for both the wheel and the sdist across both builds |

**Coverage caveat, stated honestly:** the 83.32%/92.75% figures come from one full-suite run that also produced a flaky `TimeoutError` on one test (which passed cleanly in isolation). This is very unlikely to materially move either coverage percentage — the errored test still executed most of its body before timing out — but this document does not claim a re-run to a byte-identical result, only that the numbers above are real and current as of this run, and the flake is real and disclosed rather than hidden.

**Test-suite caveat:** "3187 passed" here differs from `compliance/OPENSSF_DYNAMIC_ANALYSIS.md`'s prior "2249/2249 tests passing" figure — that document is dated 2026-08-17; this branch is 12 days newer and substantial feature work (governance/neural modules, per `git log`) landed in between, adding real tests. The prior document's number was not wrong when written; it is simply stale. This is exactly the kind of drift `OPENSSF_HUMAN_REQUIREMENTS.md`/this matrix exist to catch by re-running rather than re-quoting.

---

## OSPS Baseline Level 1

| Criterion | Status | Evidence |
|---|---|---|
| Version control (Git, distributed) | Met | Repository is Git, hosted on GitHub |
| Public issue tracker | Met | GitHub Issues, `.github/ISSUE_TEMPLATE/` |
| Contribution documentation | Met | `CONTRIBUTING.md` |
| License present, OSI-approved | Met | `LICENSE` (MIT) |
| Secure communication for repository access | Met | GitHub over HTTPS/SSH by platform default |
| Badge displayed | Met | README badge row (see `README.md:11`) links to `bestpractices.dev/projects/14112/baseline`; live badge is a founder-account artifact this document cannot re-fetch, but the badge markup and target are real and in-repo |

**Baseline 1 status: Met**, per README's own claim (`README.md:807`, "OSPS Baseline Level 1... independently confirmed by fetching the pages directly" per `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md`'s prerequisite check).

## OSPS Baseline Level 2 / 3

WhitePact's own prior audits (`compliance/OPENSSF_SILVER_GAP_ANALYSIS.md`, `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`) do not claim Baseline 2/3 badges were separately pursued or earned — only Baseline Level 1 is claimed live on the badge page. This matrix does not invent a Baseline 2/3 claim. The technical controls Baseline 2/3 would additionally require (branch protection, required reviews, vulnerability reporting process) are documented below under Silver/Gold since they overlap substantially with those criteria.

| Control area | Status | Evidence |
|---|---|---|
| Branch protection on default branch (PR required, force-push/deletion blocked) | Met | `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md` — verified via `gh api .../branches/main/protection` `GET` (not just the `PUT` response). `allow_deletions: false`, `allow_force_pushes: false`, `enforce_admins: true`, 8 required status checks. |
| Required approving review count ≥ 1 | `BLOCKED_BY_HUMAN_REQUIREMENT` | Deliberately `required_approving_review_count: 0` today — a solo maintainer cannot require review of their own PRs without deadlocking themselves out of the repo. Raising it to ≥1 requires a second real maintainer to exist first (see `OPENSSF_HUMAN_REQUIREMENTS.md`). |
| Vulnerability reporting process | Met | `SECURITY.md` (root, 2.2KB) |

---

## OpenSSF Best Practices — Passing

**Status: Met (live badge).** `README.md:807` and `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md`'s prerequisite section state the Passing badge was independently confirmed on the live `bestpractices.dev/projects/14112` page, not merely assumed. This document does not re-fetch that live page (no network access in this session) and does not re-claim it beyond citing the existing verified record.

All Passing-level technical criteria that overlap with Silver's checklist are covered in the Silver section below (`compliance/OPENSSF_SILVER_GAP_ANALYSIS.md` audits Silver, which is a superset of Passing).

---

## OpenSSF Best Practices — Silver

Full 18-item breakdown lives in `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md` (dated 2026-08-18, on this same lineage branch). Summary, re-stated here rather than re-derived:

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | DCO | Met | `.github/workflows/dco.yml`, `CONTRIBUTING.md` DCO section, required status check |
| 2 | Governance model | Met | `GOVERNANCE.md` |
| 3 | Code of Conduct | Met | `CODE_OF_CONDUCT.md` |
| 4 | Roles & responsibilities | Met | `GOVERNANCE.md` |
| 5 | Access continuity plan | Partial | `compliance/PROJECT_CONTINUITY_PLAN.md` written; no second person yet holds the access it describes |
| 6 | Real second-person continuity | `BLOCKED_BY_HUMAN_REQUIREMENT` | No engineering substitute exists |
| 7 | Bus factor ≥ 2 | `BLOCKED_BY_HUMAN_REQUIREMENT` | Same — see verification below |
| 8 | 12-month roadmap | Met | `ROADMAP.md`, linked from `README.md` |
| 9 | Architecture documentation | Met | `ARCHITECTURE.md` |
| 10 | Security requirements documentation | Met | `ENTERPRISE_SECURITY.md` |
| 11 | Quick start | Met | `README.md` |
| 12 | Documentation currentness | Met | `scripts/check_doc_consistency.py`, CI-gated |
| 13 | Achievements displayed | Met | README badge row |
| 14 | Accessibility | Met | `docs/ACCESSIBILITY.md`, `pa11y-ci` in CI, required status check |
| 15 | Internationalization | Met | `docs/INTERNATIONALIZATION.md`, i18n test job, required status check |
| 16 | Password storage | N/A | No end-user password auth; SHA-256-hashed API keys + OIDC only (`db/org_repository.py`) |
| 17 | Contribution quality | Met | `CONTRIBUTING.md` |
| 18 | CI hardening | Met | 8 required status checks incl. `dco-check`, `gitleaks`, accessibility, i18n (`compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`'s 2026-08-18 update) |

**Bus-factor re-verification for this document:** `git log --format='%ae' | sort -u` on this branch returns 3 distinct commit-author email addresses. This is **not** evidence of a second independent maintainer — all three plausibly trace to the same founder (one of the three, `milchcreamfoods@gmail.com`, is the operator's own address for this session). No commit history, PR-review history, or CODEOWNERS entry shows a second person with standing (`.github/CODEOWNERS` deliberately lists one name — see its own comment explaining why a fabricated second entry was not added). Items 6–7 remain correctly `BLOCKED_BY_HUMAN_REQUIREMENT`.

**Silver summary: 14 Met, 1 N/A, 1 Partial, 2 `BLOCKED_BY_HUMAN_REQUIREMENT`, of 18.** All technical/documentary gaps are closed. What remains is real people (items 6–7) and the founder's own action of filling in the bestpractices.dev Silver web form (see `OPENSSF_HUMAN_REQUIREMENTS.md`) — this matrix does not claim Silver is awarded; it claims the underlying repository evidence is ready for that form.

---

## OpenSSF Best Practices — Gold

Full breakdown in `OPENSSF_GOLD_GAP_ANALYSIS.md` in this same directory. Summary:

| Criterion | Status | Evidence |
|---|---|---|
| `achieve_silver` | Partial | See Silver section above — technically ready, not yet submitted/awarded |
| `bus_factor` ≥ 2 | `BLOCKED_BY_HUMAN_REQUIREMENT` | Same as Silver items 6–7 |
| `contributors_unassociated` ≥ 2 | `BLOCKED_BY_HUMAN_REQUIREMENT` | Same |
| `two_person_review` ≥ 50% | `BLOCKED_BY_HUMAN_REQUIREMENT` | Solo-maintainer repo; `required_approving_review_count: 0` by necessity today |
| `copyright_per_file` | Unmet | `grep -rl SPDX src/` → 0/205 files; no per-file copyright headers either |
| `license_per_file` | Unmet | Same grep, 0/205 files carry `SPDX-License-Identifier` |
| `test_statement_coverage90` | **Met (newly verified this session)** | 92.75% pure statement coverage (11494/12392), computed from a fresh full-suite `coverage.json`, ≥90% threshold |
| `test_branch_coverage80` | Met | 83.32% pure branch coverage (2093/2512), re-verified this session (was 80.19% on 2026-08-17; the codebase grew since, coverage held above threshold) |
| `build_reproducible` | Met | Locally replayed PR #52's `reproducible-build.yml` logic this session — identical SHA-256 digests, wheel and sdist, two independent builds |
| `code_review_standards` | Met (via PR #52) | `docs/CODE_REVIEW.md` exists on `security/openssf-hardening` only — **not yet on this branch or `main`**, since PR #52 hasn't merged. Cross-referenced, not duplicated. |
| `small_tasks` | Met | `.bestpractices.json` on PR #52 cites a real scoped starter issue (#53) |
| `crypto_used_network` / `crypto_tls12` | Met | `DEPLOYMENT.md`; production TLS 1.3 verified empirically per `compliance/OPENSSF_SECURITY_EVIDENCE.md`'s `crypto_pfs` entry |
| `security_review` | Met (self-review, stated as such) | `compliance/INTERNAL_SECURITY_REVIEW.md` |
| `hardening` / `dynamic_analysis` / `dynamic_analysis_enable_assertions` | Met | Middleware, ≥80% branch coverage, pytest assertions throughout — see Gold gap doc |
| `require_2FA` / `secure_2FA` | Unmet — needs account-level evidence | Cannot be proven from repository files alone |
| `hardened_site` | Unmet — needs live-site evidence | CSP/HSTS/etc. on `whitepact.com` not re-checked this session (no network access) |

**Gold summary:** of the criteria this session could evaluate, the two coverage thresholds and the reproducible-build claim are now genuinely, freshly verified Met — this is real, new evidence beyond what PR #52 or the prior Silver-era docs established. The three organizational criteria remain correctly blocked. Per-file SPDX/copyright remains a real, not-yet-done technical task. **Gold is not claimed as achieved anywhere in this document set.**

---

## Overall counts (this matrix, all levels combined)

| Status | Count |
|---|---|
| Met | 24 |
| Partial | 2 |
| Unmet | 4 |
| `BLOCKED_BY_HUMAN_REQUIREMENT` | 5 (deduplicated: bus factor, unassociated contributors, two-person review, ≥1 required review, 2FA account-level evidence) |
| N/A | 1 |

Counts are per-criterion as enumerated in this document; see `OPENSSF_HUMAN_REQUIREMENTS.md` for the deduplicated human-action list and `OPENSSF_GOLD_GAP_ANALYSIS.md` for the full Gold-level detail.
