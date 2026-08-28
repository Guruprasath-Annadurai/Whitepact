# OpenSSF — Human/Owner Requirements

**Date:** 2026-08-29
**Purpose:** every criterion across Baseline, Passing, Silver, and Gold marked `BLOCKED_BY_HUMAN_REQUIREMENT` in `OPENSSF_MASTER_MATRIX.md` and `OPENSSF_GOLD_GAP_ANALYSIS.md`, deduplicated, with exactly what a human owner needs to do. Nothing here can be closed by further engineering work in this repository.

---

## 1. Recruit a real second maintainer

**Blocks:** Silver items 6–7 (real second-person continuity, bus factor ≥ 2), Gold `bus_factor`, Gold `contributors_unassociated`, Silver item 5's remaining half (someone has to actually hold the access `compliance/PROJECT_CONTINUITY_PLAN.md` describes).

**What to do:** Identify and onboard a second person with real, standing repository access and enough project knowledge to operate independently if the founder is unavailable — not a nominal co-maintainer added to satisfy a badge criterion. `compliance/PROJECT_CONTINUITY_PLAN.md` and `FOUNDER_ACTION_CONTINUITY.md` (if present) describe the access/handoff shape to give them once they exist. This is inherently not something an engineering pass can create.

## 2. Get two unassociated significant contributors

**Blocks:** Gold `contributors_unassociated`.

**What to do:** Grow real, independent (not employed by or otherwise affiliated with the founder) contributors who make significant contributions over time. This is a community-growth outcome, not a repository setting.

## 3. Enable ≥1 required approving review on the default branch

**Blocks:** OSPS Baseline 2/3-adjacent branch-protection maturity, Gold `two_person_review`.

**What to do:** Once a second maintainer (item 1) exists, in GitHub repo settings → Branches → branch protection rule for `main`, raise `required_approving_review_count` from 0 to 1 (or use `gh api -X PATCH repos/Guruprasath-Annadurai/Whitepact/branches/main/protection/required_pull_request_reviews -F required_approving_review_count=1`). Doing this today, with one maintainer, would lock that maintainer out of merging their own PRs — see `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`'s explicit rationale for why it's deliberately 0 now.

## 4. Establish and demonstrate two-person pre-release review history

**Blocks:** Gold `two_person_review` (≥50% of proposed modifications before release reviewed by someone other than the author).

**What to do:** After items 1 and 3 are real, accumulate an actual history of the second reviewer reviewing PRs before merge/release. This is a historical/behavioral criterion, not a one-time configuration change — it can only be satisfied by real review activity over time.

## 5. Provide account-level 2FA evidence

**Blocks:** Gold `require_2FA`, Gold `secure_2FA`.

**What to do:** Confirm (and, where relevant, screenshot/document) that the maintainer's GitHub account requires and uses cryptographic two-factor authentication (TOTP, a hardware security key, or a passkey — not SMS). GitHub's org-wide mandatory-2FA enforcement toggle applies to organizations, not personal-account repositories, so evidence here is account-settings evidence the founder must produce and attest to, not something a repository file can prove.

## 6. Verify live-site security headers

**Blocks:** Gold `hardened_site` (CSP, HSTS, X-Content-Type-Options, X-Frame-Options on the project's website/repository/download site).

**What to do:** With live network access to `whitepact.com`, check the actual response headers (e.g. `curl -sI https://whitepact.com` or `securityheaders.com`) and confirm CSP/HSTS/X-Content-Type-Options/X-Frame-Options are present as served, not just as documented in `middleware.py`. This session had no outbound network access to re-verify live headers, so this remains open pending that check — it is likely already true given the documented middleware, but "likely" is not "verified," and this document does not mark it Met on an assumption.

## 7. Submit the OpenSSF Best Practices Silver web form

**Blocks:** Silver badge actually being awarded (as distinct from the underlying repository evidence being ready).

**What to do:** Log into the founder's `bestpractices.dev` account, open project 14112's Silver criteria form, and answer each criterion (several are currently `?` unanswered on the live form per `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md`'s finding, independent of whether the underlying repository evidence exists). This is a manual, account-tied web form only the founder can complete — no repository change submits it.

## 8. (Not currently blocking, but note for later) Gold badge application

**Blocks:** Nothing yet — Gold cannot be meaningfully applied for until items 1–4 above are real, since those are hard Gold requirements. Listed here so it isn't forgotten once the organizational criteria are eventually satisfied.

---

## What is explicitly NOT on this list

Per-file SPDX/copyright headers (`license_per_file`, `copyright_per_file`) and the `docs/CODE_REVIEW.md`/`.bestpractices.json` merge from PR #52 are **not** human-only blockers — they are real, doable engineering/process work, tracked in `OPENSSF_GOLD_GAP_ANALYSIS.md` and `OPENSSF_HARDENING_REPORT.md` instead of here.
