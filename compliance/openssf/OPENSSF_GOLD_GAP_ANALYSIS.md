# OpenSSF Best Practices Gold — Gap Analysis (re-verified)

**Date verified:** 2026-08-29
**Branch:** `security/openssf-readiness-matrix`
**Relationship to prior work:** `security/openssf-hardening` (PR #52, unmerged) wrote `compliance/OPENSSF_GOLD_GAP_ANALYSIS.md` on 2026-08-17-ish with its own Gold analysis. This document does not contradict that analysis's already-correct human-blocked markings — it re-verifies each claim against this branch's *current* state (12+ days newer, more tests, more code) and reports what changed. Where this document's finding differs numerically from PR #52's, that's stated explicitly as drift, not as PR #52 having been wrong.

---

## Organizational blockers — unchanged, still correctly Unmet/blocked

These three cannot be closed by any repository change. See `OPENSSF_HUMAN_REQUIREMENTS.md` for exactly what a human owner must do.

| Criterion | Status | Why |
|---|---|---|
| `bus_factor` ≥ 2 | `BLOCKED_BY_HUMAN_REQUIREMENT` | Re-checked this session: `git log --format='%ae' \| sort -u` shows 3 distinct commit-author emails, all plausibly the same founder (no second identifiable maintainer with standing). One primary maintainer today. |
| `contributors_unassociated` ≥ 2 | `BLOCKED_BY_HUMAN_REQUIREMENT` | No independent-contributor history exists to check. |
| `two_person_review` ≥ 50% | `BLOCKED_BY_HUMAN_REQUIREMENT` | `required_approving_review_count: 0` on `main` today, by necessity — see `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`. A solo maintainer cannot generate genuine two-person review history. |

## Technical Gold criteria — re-verified this session

| Criterion | Status | Evidence / what changed since PR #52's analysis |
|---|---|---|
| `achieve_silver` | Partial | Silver's technical/documentary evidence is essentially complete per `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md` (14/18 Met), but the live bestpractices.dev Silver form still has unanswered fields per that same document's own finding, and Silver has not been separately confirmed awarded on the live badge page during this session (no network access to re-check). Treated as **not yet claimed Met** here, consistent with the master directive's "never mark Met without concrete evidence you can point to." |
| `copyright_per_file` | **Unmet** (re-confirmed) | `grep -rl "SPDX-License-Identifier" src/ \| wc -l` → **0** of 205 `.py` files under `src/`. Same as PR #52's finding; no drift. A licensing pass to add per-file SPDX + copyright headers across `src/` remains real, undone work — see recommendation below. |
| `license_per_file` | **Unmet** (re-confirmed) | Same grep, same result. |
| `test_statement_coverage90` | **Met — newly verified this session, was "Not yet claimed" in PR #52** | PR #52's own analysis explicitly said: "does not contain a current independently captured pure statement-coverage value at or above 90%... Measure first." This session measured it: fresh full-suite run (`uv run pytest -q`, 3187 passed/1 skipped/1 flaky-timeout-that-passed-in-isolation), `coverage.json` totals give **92.75% pure statement coverage** (11494/12392 `covered_lines`/`num_statements`), computed the same way PR #52's own (unmerged) `scripts/check_statement_coverage.py` computes it (`covered_lines / num_statements`, not the blended `percent_covered`). This is the single most material update this document makes over PR #52's Gold analysis. |
| `test_branch_coverage80` | Met (re-verified, numbers drifted) | Prior figure (`compliance/OPENSSF_DYNAMIC_ANALYSIS.md`, 2026-08-17): 80.19% (1469/1832 branches). This session's fresh run: **83.32%** (2093/2512 branches) — both statement and branch counts grew (12392 vs. prior statement total, 2512 vs. 1832 branch total) because real feature code (`governance/`, `governance/neural/`) landed between 2026-08-17 and now. Coverage held above the 80% threshold through that growth; this is a genuine re-verification, not a copy-forward. |
| `build_reproducible` | Met — re-verified by actually running it, not just reading the workflow file | The instruction explicitly said not to assume PR #52's `reproducible-build.yml` would produce matching digests. This session replayed its exact logic locally: `SOURCE_DATE_EPOCH=$(git log -1 --format=%ct)`, `PYTHONHASHSEED=0`, `python -m build` run twice via `uv run --with build -- python -m build`, `shasum -a 256` on both output directories, `diff -u`. **Result: identical SHA-256 digests** for `rai_governance_platform-1.2.3-py3-none-any.whl` and the matching `.tar.gz` across both builds. The workflow's approach is technically sound for this repository as configured (hatchling backend). |
| `code_review_standards` | Met, but only on PR #52, not on this branch | `docs/CODE_REVIEW.md` exists on `security/openssf-hardening` and was read via `git show`. It does **not** exist on this branch or on `main` — PR #52 has not merged. This document cross-references it rather than duplicating it; do not read this row as claiming the file is present here. |
| `small_tasks` | Met (per PR #52's `.bestpractices.json`, not independently re-verified) | PR #52 cites issue #53 as a real scoped starter task. This session did not re-fetch GitHub Issues (no network access) to confirm #53 is still open/well-scoped, so this is carried forward as PR #52 reported it, with that caveat stated rather than silently re-asserted as freshly Met. |
| `crypto_used_network`, `crypto_tls12` | Met | `DEPLOYMENT.md`; TLS 1.3 was empirically verified against `whitepact.com:443` per `compliance/OPENSSF_SECURITY_EVIDENCE.md`'s `crypto_pfs` entry (dated 2026-08-17; not re-checked live this session, no network access). |
| `hardened_site` | Unmet — needs live-site evidence | Same reason: no outbound network access this session to `curl -I https://whitepact.com` and check CSP/HSTS/X-Content-Type-Options/X-Frame-Options as actually served. Documented in code (`src/responsibleai/dashboard/middleware.py`) but not re-confirmed live. Listed as a founder/operator action in `OPENSSF_HUMAN_REQUIREMENTS.md` — it's a 30-second check for anyone with a browser, just not something this sandboxed session could do. |
| `security_review` | Met, self-review, stated as such | `compliance/INTERNAL_SECURITY_REVIEW.md`. Not represented as an independent penetration test — matches the master directive's prohibited-claims rule. |
| `hardening` | Met | `src/responsibleai/dashboard/middleware.py` and related — defense-in-depth controls exist and are exercised by the passing test suite. |
| `dynamic_analysis` | Met | Automated pytest suite, ≥80% pure branch coverage, re-verified this session. |
| `dynamic_analysis_enable_assertions` | Met | Pytest `assert` usage is extensive across the 3187-test suite (also flagged twice by Bandit's `B101` at Low severity, which is expected and not a defect — see `OPENSSF_SCORECARD_REPORT.md`'s SAST section). |
| `require_2FA`, `secure_2FA` | Unmet — needs account-level evidence | Cannot be established from repository files; `BLOCKED_BY_HUMAN_REQUIREMENT`, see `OPENSSF_HUMAN_REQUIREMENTS.md` item 5. |

---

## What this document adds beyond PR #52's Gold analysis

1. **`test_statement_coverage90` moves from "not yet claimed" to genuinely Met**, with a real number (92.75%) from a run executed for this document, using the same pure-statement-coverage formula PR #52's own (unmerged) checker script uses.
2. **`test_branch_coverage80`'s number is refreshed** from 80.19% to 83.32%, confirming the threshold held as the codebase grew.
3. **`build_reproducible` is verified by execution**, not by reading the YAML and assuming it would work.
4. **Bus-factor/contributor evidence is re-checked** against current `git log`, not merely re-asserted from the prior date.

## What this document does not change

The three organizational blockers, `copyright_per_file`/`license_per_file` (still 0/205), and the two live-site-dependent criteria (`hardened_site`, and re-confirming `crypto_pfs`) are unchanged because either no new engineering happened in those areas, or this sandboxed session had no network access to re-check a live endpoint. Both limitations are stated plainly rather than papered over.

## Recommendation (not implemented in this pass — out of scope per the "purely additive, low-risk" hardening rule and this pass's time budget)

A dedicated SPDX/copyright pass across all 205 `src/` files (`SPDX-License-Identifier: MIT` + a copyright line per file) would close `license_per_file` and `copyright_per_file`. This is mechanical but touches every source file, so it risks merge conflicts with the concurrently-running `security/enterprise-neural-remediation` work if done here — deliberately left as a separate, explicitly scoped follow-up rather than rushed into this branch, consistent with PR #52's own stated reasoning for not having done it either.

**Gold is not claimed as achieved anywhere in this document.**
