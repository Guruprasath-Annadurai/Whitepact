# OpenSSF Best Practices Silver — Gap Analysis

**Date**: 2026-08-18
**Scope**: audit only. No code, docs, or repository settings were changed to produce this document — it inspects the current state of the repository (`Guruprasath-Annadurai/Whitepact`, `main` @ `8cb8e0c`) and the live BadgeApp project entry against what Silver actually requires.
**Prerequisite verified independently** (via the live [bestpractices.dev project 14112](https://www.bestpractices.dev/en/projects/14112) page, not assumed): **Passing badge = achieved**, **OSPS Baseline Level 1 = achieved**. Both real, both confirmed by fetching the pages directly rather than trusting a prior claim.

## An important finding about how Silver actually works

Silver criteria on bestpractices.dev live on a **self-service web form** tied to the founder's own account. Spot-checking several criteria on the live Silver page (`dco`, `implement_secure_design`, `coding_standards`, `vulnerability_report_credit`, `crypto_algorithm_agility`) showed them still at **`?` (unanswered)** on the form itself — separate from whether the underlying repository evidence exists. This means: even once every technical/documentary gap below is closed, **someone has to sit down and answer the BadgeApp form** — that step is not something achievable by editing files in this repository, and not something this session can do on your behalf (it requires your GitHub-authenticated bestpractices.dev session). Every remediation below closes the underlying gap; filling in the form itself is listed as a standing founder action, not repeated per-criterion.

---

## Update log (2026-08-18)

This document's item-by-item bodies below are left as originally written —
they're the audit's evidence trail and shouldn't be silently rewritten.
This log records what actually changed afterward, item by item, each
closing the gap that item's original body described:

- **Item 1 (DCO)**: now **MET**. `CONTRIBUTING.md` got a DCO section,
  `.github/workflows/dco.yml` enforces sign-off on every PR, and it's
  now a required branch-protection check (see item 18's update below).
- **Item 5 (Access continuity)**: the plan-writing half is now **MET** —
  `compliance/PROJECT_CONTINUITY_PLAN.md` exists. The underlying
  bus-factor gap (items 6–7) is unchanged; see "What genuinely requires
  you, specifically" at the end of this document.
- **Item 8 (12-month roadmap)**: now **MET** — a canonical root
  `ROADMAP.md` exists, linked from `README.md`.
- **Item 9 (Architecture documentation)**: now **MET** — `ARCHITECTURE.md`
  was fixed to reference current WhitePact architecture/`SPEC.md` rather
  than stale pre-rename `ResponsibleAI`/`BiasBuster` branding.
- **Item 10 (Security requirements documentation)**: now **MET** —
  `ENTERPRISE_SECURITY.md` got an explicit "Summary: what you can expect
  vs. what you cannot assume" section synthesizing the whole document
  into Silver's two-list structure, including an explicit "no
  independent penetration test has been performed" statement that
  wasn't previously stated as its own claim.
- **Item 12 (Documentation currentness)**: now **MET** — stale test
  counts fixed, `scripts/check_doc_consistency.py` built and wired into
  CI as a hard gate.
- **Item 13 (Achievements displayed)**: now **MET** — both real earned
  badges (Passing, OSPS Baseline Level 1) display in `README.md`.
- **Item 14 (Accessibility)**: now **MET** — real WCAG2AA infrastructure,
  `pa11y-ci` wired into CI, `docs/ACCESSIBILITY.md` written, a real
  light-mode contrast bug found and fixed along the way. See
  `docs/ACCESSIBILITY.md`.
- **Item 15 (Internationalization)**: now **MET** — real message-catalog
  i18n architecture (`en`/`es`), 27 passing tests, CI-gated. See
  `docs/INTERNATIONALIZATION.md`.
- **Item 17 (Contribution quality)**: now **MET** — `CONTRIBUTING.md`'s
  Accessibility and Internationalization sections (added alongside items
  14/15) were re-checked and confirmed accurate, current, and correctly
  linked to real CI jobs; no further changes needed.
- **Item 18 (CI hardening)**: now **MET** — Gitleaks, DCO, doc-consistency,
  accessibility, and i18n CI jobs all exist (per items 1/12/14/15 above),
  **and**, as of this update, all four are now actually enforced as
  required branch-protection status checks alongside the original four
  — previously they ran and reported pass/fail but a PR could still
  merge regardless of their result, which defeats the point of a "hard
  gate." See `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`'s
  "2026-08-18 update" section for the exact command and verification.
  `dependency-review` remains deliberately non-required — it fails on
  every PR today due to a separate, pre-existing repository-setting gap
  (Dependency graph not enabled), and making it required would block
  every PR unconditionally rather than surface a real finding.

Items 6–7 (a real second person, bus factor ≥ 2) are unchanged —
founder action required, not something this update closes.

---

## 1. Developer Certificate of Origin (DCO)

**CURRENT STATUS: MET** (updated 2026-08-18 — see below; original UNMET finding preserved for record)

**EVIDENCE**: `grep -ril "signed-off-by\|developer certificate"` across the whole repo returns nothing. `CONTRIBUTING.md` has no DCO section. `.github/PULL_REQUEST_TEMPLATE.md` has no sign-off checkbox. No CI job validates commit sign-offs. `git commit -s` is not mentioned or required anywhere.

**GAP**: No DCO policy, no contributor instructions, no automated enforcement — all three required elements are absent.

**REMEDIATION**: Add a DCO section to `CONTRIBUTING.md` (what it is, the `git commit -s` command, the `Signed-off-by` trailer, a link to the official DCO 1.1 text). Add a sign-off checkbox to the PR template. Add a DCO-checking GitHub Action (the maintained `dcoapp/app` GitHub App, or the FLOSS `github.com/dcoapp/probot` equivalent that runs as a status check) so it's enforced going forward — not retroactively rewriting existing history.

**VERIFICATION METHOD**: Open a test PR with an unsigned commit and confirm the DCO check fails; sign it and confirm the check passes.

---

## 2. Governance model

**CURRENT STATUS: MET**

**EVIDENCE**: `GOVERNANCE.md` explicitly states the model (founder-led), current maintainer (Guruprasath Annadurai, linked GitHub handle), final decision/merge/release authority, security and incident responsibilities (Section 2), roadmap/architecture decision-making (Section 6 — `SPEC.md`/`MIGRATION_WHITEPACT_V2.md`), contributor rights (anyone can contribute; contributing doesn't confer commit access), how roles may change (Section 4: "the moment a second person joins... update this document the same day"), and current limitations (Sections 2 and 4, stated without hedging).

**GAP**: None material. A dedicated "conflict/escalation handling" subsection doesn't exist as a named heading, but the document is honest that all decisions currently route through one person, which is itself the answer.

**REMEDIATION**: None required. Optional: add one sentence naming the founder's email/GitHub as the escalation contact for governance disputes, purely for completeness.

**VERIFICATION METHOD**: Read `GOVERNANCE.md` end to end; cross-check named maintainer against `.github/CODEOWNERS` and GitHub repo collaborator list — they agree (single name, no invented team).

---

## 3. Code of Conduct

**CURRENT STATUS: MET**

**EVIDENCE**: `CODE_OF_CONDUCT.md` is Contributor Covenant 2.1 with correct attribution and link. Contains pledge, standards, enforcement responsibilities (honestly scoped to the founder, per `GOVERNANCE.md`), scope, a real reporting email, and privacy commitment. Linked from `CONTRIBUTING.md`'s opening paragraph.

**GAP**: None.

**REMEDIATION**: None required.

**VERIFICATION METHOD**: Diff against the canonical Contributor Covenant 2.1 text at contributor-covenant.org to confirm no silent alterations beyond the enforcement-contact substitution.

---

## 4. Project roles & responsibilities

**CURRENT STATUS: MET**

**EVIDENCE**: `GOVERNANCE.md` Section 2 maps every role (founder/maintainer, security contact, incident commander, risk owner) to the same real named person, explicitly, in a table — not a vague claim.

**GAP**: The specific role labels the Silver directive suggested (Release Manager, Continuity Maintainer) aren't named separately, but inventing separate labels for the same one person would be exactly the kind of fabricated process `GOVERNANCE.md` itself refuses to do (see its own text: "no steering committee... would be exactly the kind of fabricated process this project's own engineering rules prohibit," echoed in `.github/CODEOWNERS`'s comment).

**REMEDIATION**: None required — the honest single-row mapping is the correct answer at this project stage, not a gap to paper over with invented titles.

**VERIFICATION METHOD**: Cross-check `GOVERNANCE.md` Section 2's table against `SECURITY.md`'s named contact and `.github/CODEOWNERS` — all three agree on the same person.

---

## 5. Access continuity

**CURRENT STATUS: PARTIAL — plan-writing MET, founder action still required for items 6-7** (updated 2026-08-18, see Update log above)

**EVIDENCE**: `GOVERNANCE.md` Section 4 states plainly: "A named advisor, fractional CISO, or co-founder with actual standing to push back... is a decision for the founder to make... Until that person exists, treat every review above as self-assessment, not independent oversight." No `compliance/PROJECT_CONTINUITY_PLAN.md` exists.

**GAP**: No continuity plan document exists at all (recovery objectives, account-continuity checklist, off-repo vault reference). This is buildable without a second person existing yet — the plan can be written now and activated once someone real fills the role.

**REMEDIATION**: Write `compliance/PROJECT_CONTINUITY_PLAN.md` covering GitHub/domain/DNS/PyPI/MCP-Registry/Render/database/Redis/security-contact/release-signing/incident-response/billing continuity and the 7-day recovery-objective checklist, explicitly not storing any real credential in git. This is pure documentation work achievable today.

**VERIFICATION METHOD**: A second, independent person (once one exists) attempts the drill described in the plan and confirms each listed capability is actually reachable.

---

## 6. Real second-person continuity

**CURRENT STATUS: FOUNDER ACTION REQUIRED**

**EVIDENCE**: Same as above — `.github/CODEOWNERS` deliberately lists one name; `GOVERNANCE.md` confirms no second person holds any operational or advisory role today.

**GAP**: No real second person exists with GitHub access, release capability, or infrastructure recovery access.

**REMEDIATION**: `compliance/FOUNDER_ACTION_CONTINUITY.md` — a document listing the exact steps (choose a trusted person, grant GitHub access, PyPI publisher access, domain/DNS recovery, encrypted vault access, legal-authority documentation, run a drill). This document can be written now; the actions in it cannot be performed by anyone but the founder.

**VERIFICATION METHOD**: N/A until a real second person exists — status must stay `FOUNDER ACTION REQUIRED` until then, not silently upgraded to MET.

---

## 7. Bus factor ≥ 2

**CURRENT STATUS: FOUNDER ACTION REQUIRED**

**EVIDENCE**: One real maintainer, confirmed via `.github/CODEOWNERS`, `GOVERNANCE.md`, and the repository's actual collaborator list (not independently re-checked via API this pass, but nothing in the repo suggests otherwise, and `GOVERNANCE.md` states it directly).

**GAP**: Same underlying gap as items 5–6. Not separately fixable by more documentation — this criterion measures a real fact about the world, not a document.

**REMEDIATION**: Once a real second person exists with the six recommended capabilities (repo access, architecture understanding, CI familiarity, release capability, vulnerability response capability, deployment recovery understanding), update `GOVERNANCE.md` and the continuity documents the same day, per `GOVERNANCE.md`'s own stated rule.

**VERIFICATION METHOD**: The second person independently performs at least one of: merges a real PR, cuts a release, or responds to a security report — with evidence (PR, release tag, email thread) that they did it, not that they were merely granted permission to.

---

## 8. 12-month roadmap

**CURRENT STATUS: MET** (updated 2026-08-18, see Update log above)

**EVIDENCE**: README's `## Roadmap` section exists, but it's mostly a retrospective changelog of v0.1→v1.2 with `[ ] v2.0 onward — see VERSION_ROADMAP.md`. Two more roadmap-shaped documents exist at the root: `STRATEGY_ROADMAP.md` (last touched Jul 23, predates the WhitePact rename) and `GAME_CHANGER_STRATEGY.md`/`GAME_CHANGER_BUILD_PLAN.md`. `VERSION_ROADMAP.md` is current (Aug 17) and does cover a phase-by-phase plan through v6.0.

**GAP**: No single canonical `ROADMAP.md` exists at the repo root with an explicit NOW/NEXT/LATER structure and WILL BUILD / WILL NOT BUILD YET / DEFERRED / DEPENDENCIES / EXIT CRITERIA framing. Four documents currently claim roadmap territory (`README.md`'s section, `STRATEGY_ROADMAP.md`, `VERSION_ROADMAP.md`, `GAME_CHANGER_STRATEGY.md`) with real risk of drifting out of sync — `STRATEGY_ROADMAP.md` in particular predates the WhitePact rename and hasn't been touched since.

**REMEDIATION**: Create one canonical root `ROADMAP.md` synthesizing `VERSION_ROADMAP.md` (the most current) into the NOW/NEXT/LATER + WILL/WON'T/DEFERRED/EXIT-CRITERIA structure Silver expects, spanning ≥12 months forward. Either fold `STRATEGY_ROADMAP.md`'s still-relevant content into it and mark the old file superseded, or add a one-line pointer at its top. Link `ROADMAP.md` from `README.md`.

**VERIFICATION METHOD**: Confirm exactly one document answers "what is WhitePact building in the next 12 months" without contradiction; every other roadmap-shaped doc either points to it or is explicitly marked historical/strategic-context-only.

---

## 9. Architecture documentation

**CURRENT STATUS: MET** (updated 2026-08-18, see Update log above)

**EVIDENCE**: `GOVERNANCE.md` itself states "`SPEC.md` is the current architecture contract." Root `ARCHITECTURE.md` (last touched Jun 13, before this session's WhitePact work began) opens with "This document describes the internal design of the three components that make up **ResponsibleAI**: BiasBuster, PrivacyLabel, and DeepfakeDetector" — 5 mentions of the old `ResponsibleAI`/`BiasBuster` branding, 0 mentions of WhitePact, no coverage of Identity→Authority→Policy→Risk→Workflow→Decision→Execution Permit→Execution→Evidence at all.

**GAP**: Exactly the stale-architecture-doc risk Silver's own guidance warns about. A newcomer or reviewer who opens `ARCHITECTURE.md` first (the conventionally-named file) gets a materially incomplete, pre-governance-core picture of the system, while the real current architecture lives in `SPEC.md`.

**REMEDIATION**: Either (a) rewrite `ARCHITECTURE.md` to be a short pointer to `SPEC.md` as canonical, explicitly deprecating itself, or (b) merge its still-accurate BiasBuster/PrivacyLabel component-level content into `SPEC.md` and delete/redirect `ARCHITECTURE.md`. Prefer (a) — smaller, lower-risk change — unless `SPEC.md` is missing the probe-level detail `ARCHITECTURE.md` has, in which case fold that section in first.

**VERIFICATION METHOD**: `grep -c whitepact ARCHITECTURE.md` returns > 0 and the file's first paragraph correctly names `SPEC.md` as canonical, or the file no longer exists and links resolve to `SPEC.md` instead.

---

## 10. Security requirements documentation

**CURRENT STATUS: MET** (updated 2026-08-18, see Update log above)

**EVIDENCE**: `ENTERPRISE_SECURITY.md`, `SECURITY.md`, and `THREAT_MODEL.md` collectively cover most of what's asked (tenant isolation, fail-closed behavior, auth/authz, crypto requirements, secret handling, auditability, replay prevention, revocation). `ENTERPRISE_SECURITY.md` was extended this session with a real, verified PFS paragraph (not assumed).

**GAP**: Not independently re-verified this pass whether a single canonical document explicitly separates "what users CAN expect" from "what users CANNOT assume" in the specific structure Silver's guidance asks for (no SOC 2 claim, no ISO claim, no independent-pentest claim, hash-chain limitations, external-provider dependencies) — this needs a dedicated read-through of `ENTERPRISE_SECURITY.md` end-to-end rather than the excerpt-level familiarity this session has.

**REMEDIATION**: Read `ENTERPRISE_SECURITY.md` in full against the CAN-expect/CANNOT-assume checklist; add any missing explicit disclaimers (no independent pentest performed, hash-chain integrity limitations, third-party LLM provider dependency risk) rather than creating a new competing document.

**VERIFICATION METHOD**: A checklist pass confirming every item in Silver Section 10's two lists (CAN expect / CANNOT assume) has an explicit sentence in `ENTERPRISE_SECURITY.md`, not an inferred absence.

---

## 11. Quick start

**CURRENT STATUS: MET**

**EVIDENCE**: README's `## 30-second quickstart` gives a real `pip install`, a real `uvicorn` invocation, and a working `curl` example against `/api/evaluate` with a complete JSON body — no LLM key required for that path. A dedicated `## MCP Server` section and `## Python SDK` section follow with their own runnable examples.

**GAP**: Commands weren't re-executed fresh in this pass (would require a clean venv + running server) — reasonable confidence from architecture familiarity and the fact this exact dashboard was live-verified via Render deploy checks earlier in this session, but not re-verified command-by-command today.

**REMEDIATION**: None required for Silver's substantive bar; optional follow-up is a scripted smoke test (`scripts/check_readme_quickstart.sh`) that actually runs the documented commands in CI against a fresh checkout, catching future drift automatically.

**VERIFICATION METHOD**: Fresh `venv`, run the exact three quickstart commands verbatim, confirm the curl call returns a 200 with a trust score.

---

## 12. Documentation currentness

**CURRENT STATUS: MET** (updated 2026-08-18, see Update log above)

**EVIDENCE — concrete drift found, not assumed**:
- README's badge: `tests-1725_passing` — the actual current count is **2249** (confirmed this session via a fresh `pytest` run).
- `CONTRIBUTING.md`: "As of this writing the suite is **1,538 tests** at 85% coverage" — a third, different stale number in a second location.
- `ARCHITECTURE.md`: pre-WhitePact branding throughout (see item 9).
- No `scripts/check_doc_consistency.py` exists to catch this kind of drift automatically.

**GAP**: At least three independently-stale numbers across two files, exactly the failure mode Silver's guidance anticipates ("prefer a CI badge or generated status... instead of repeatedly writing '2249 tests'"). No automated doc-consistency check exists.

**REMEDIATION**: Fix the two stale test-count mentions now with a real current number or (better) switch the README badge to a dynamically-generated one (e.g., a GitHub Actions job that regenerates a badge JSON from the actual `pytest` run, or simply drop the hardcoded count and rely on the CI-passing badge instead, since a passing badge already implies "tests pass" without needing an exact count that goes stale every session). Fix `ARCHITECTURE.md` per item 9. Build `scripts/check_doc_consistency.py` validating package version, official domain, repo identity, and canonical project name against `pyproject.toml`/`git remote`, add to CI once stable.

**VERIFICATION METHOD**: `scripts/check_doc_consistency.py` run in CI on every PR; a deliberately-introduced stale version number in README fails the check.

---

## 13. OpenSSF achievements displayed

**CURRENT STATUS: MET** (updated 2026-08-18, see Update log above)

**EVIDENCE**: Independently verified via live fetch of `bestpractices.dev/en/projects/14112` and `.../baseline-1`: **Passing badge = genuinely achieved**, **OSPS Baseline Level 1 = genuinely achieved**. README currently shows only the OpenSSF **Scorecard** badge (`scorecard.dev`) — the Passing and Baseline Level 1 badges are both real and both missing from README.

**GAP**: Two real, earned badges aren't displayed.

**REMEDIATION**: Add both badge images to README's badge row using bestpractices.dev's own supplied embed markup:
```
[![OpenSSF Best Practices](https://www.bestpractices.dev/projects/14112/badge)](https://www.bestpractices.dev/projects/14112)
[![OpenSSF Baseline](https://www.bestpractices.dev/projects/14112/baseline)](https://www.bestpractices.dev/projects/14112)
```
Add a short, accurately-worded "Security & Open Source Assurance" section distinguishing these self-certified badges from independent certification (SOC 2, ISO, pentest) — none of which are claimed.

**VERIFICATION METHOD**: Badge images render on the live GitHub README and link to the correct project 14112 pages; wording nowhere implies independent certification.

---

## 14. Accessibility

**CURRENT STATUS: MET** (updated 2026-08-18, see Update log above)

**EVIDENCE**: No `docs/ACCESSIBILITY.md` exists. No accessibility tooling (`axe-core`, `pa11y`, Lighthouse CI) found in `pyproject.toml` or any `package.json` (none exists at the repo root). No automated accessibility test in CI. Dashboard has ~29 HTML pages under `src/responsibleai/dashboard/static/` — not audited page-by-page this pass.

**GAP**: Nothing automated exists to substantiate an accessibility claim one way or the other. This is a real, non-trivial engineering task (audit ~29 pages, fix real issues, wire a FLOSS scanner into CI), not a documentation-only fix.

**REMEDIATION**: Pick a FLOSS scanner (`pa11y-ci` is lightweight and Node-based, or `axe-core` via Playwright since Playwright may already be usable for the existing dashboard). Run it against the live/local dashboard pages, fix real findings (missing labels, contrast, focus states — whatever the scan actually surfaces), wire it into CI for the stable pages, write `docs/ACCESSIBILITY.md` describing approach/known limitations/reporting process. Budget this as its own multi-hour pass, not a quick add-on.

**VERIFICATION METHOD**: CI job runs the scanner against a built/served dashboard and fails on new critical/serious findings; `docs/ACCESSIBILITY.md` links to the last scan's real output, not a claim without evidence.

---

## 15. Internationalization

**CURRENT STATUS: MET** (updated 2026-08-18, see Update log above)

**EVIDENCE**: `grep -rl "i18n\|gettext\|locale"` across `src/responsibleai/dashboard/static/` returns nothing. No message-catalog architecture, no locale abstraction, no pluralization/date-formatting abstraction anywhere in the frontend or backend user-facing strings.

**GAP**: Zero i18n infrastructure exists. This is real engineering work: introducing a message-catalog pattern across ~29 static HTML pages plus whatever user-facing strings the FastAPI backend emits (error messages, webhook notification text), without translating everything — just making the architecture real and provably functional with one non-English or pseudo-locale.

**REMEDIATION**: For a vanilla-JS/server-rendered-HTML frontend, the lightest real approach is a small client-side message-catalog loader (JSON per locale, a `t(key)` helper, `<html lang="...">` reflecting the active locale) rather than pulling in a heavy framework-coupled i18n library. Ship `en` as default plus one pseudo-locale or real second locale to prove the mechanism works end-to-end (locale selection, fallback, at least one pluralized string). Write `docs/INTERNATIONALIZATION.md` explaining how a contributor adds a locale. Add tests for locale selection/fallback.

**VERIFICATION METHOD**: Switching the configured/selected locale changes at least one rendered string on a real page, verified by an automated test, not a manual screenshot.

---

## 16. Password storage

**CURRENT STATUS: N/A**

**EVIDENCE**: WhitePact does not authenticate end users via passwords. `src/responsibleai/db/org_repository.py` confirms: raw API keys are never stored, only `hashlib.sha256(raw.encode()).hexdigest()` is persisted (`_hash_key`), with `authenticate()` re-hashing the presented key and comparing against the stored hash. OIDC/SSO is the second supported auth path (`src/responsibleai/auth/oidc.py`), which also involves no password storage by this project (delegated to the external IdP).

**GAP**: None — correctly N/A, not something to force into MET by inventing password auth.

**REMEDIATION**: None. Keep documenting this as N/A with the reasoning above, not silently omitted — an auditor should be able to find this exact justification.

**VERIFICATION METHOD**: `grep -r "password" src/responsibleai/db/` shows no plaintext password column or comparison; SHA-256 API-key hashing is the actual mechanism in use, confirmed by reading the repository code directly.

---

## 17. Contribution quality

**CURRENT STATUS: MET** (updated 2026-08-18, see Update log above)

**EVIDENCE**: `CONTRIBUTING.md` is comprehensive and current (14.5KB, last touched Aug 17): setup, repo layout, running tests, engineering principles, PR guidelines, code style, a real "common vulnerability classes to avoid" security section, a questions/discussions pointer, and links to `CODE_OF_CONDUCT.md`/`GOVERNANCE.md`/`SECURITY.md`.

**GAP**: Missing sections for capabilities that don't exist yet elsewhere in the repo: DCO (item 1), accessibility expectations (item 14), internationalization expectations (item 15). Everything else Silver Section 17 asks for is already present.

**REMEDIATION**: Add DCO/accessibility/i18n subsections to `CONTRIBUTING.md` as those underlying capabilities are built (items 1, 14, 15) — don't add contributor-facing instructions for a capability that doesn't exist yet, that would itself be a fabricated-process problem.

**VERIFICATION METHOD**: Re-read `CONTRIBUTING.md`'s table of contents once items 1/14/15 land; confirm each links to real, working CI checks, not aspirational text.

---

## 18. CI hardening

**CURRENT STATUS: MET** (updated 2026-08-18, see Update log above)

**EVIDENCE**: `.github/workflows/ci.yml` runs `ruff check`, `mypy`, dependency vulnerability scanning, the full `pytest` suite with coverage, and (as of this session's prior work) a hard `--fail` branch-coverage gate at 80%. `.github/workflows/security-scan.yml` runs Bandit and pip-audit separately. `.github/workflows/dependency-review.yml` exists but currently fails on every PR because the repo's Dependency graph setting isn't enabled (pre-existing, unrelated to Silver, noted in `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md`).

**GAP**: No Gitleaks step in CI (this session's secret scan was a manual one-off run, documented in `compliance/OPENSSF_SECRET_SCAN.md`, not a repeatable CI gate). No DCO check (item 1). No documentation-consistency check (item 12). No accessibility or i18n tests (items 14, 15, since those capabilities don't exist yet).

**REMEDIATION**: Add a Gitleaks GitHub Action step (informational first, then hard-gate once confirmed clean on a few runs) for real, ongoing secret-scan coverage instead of a one-time manual pass. Add the other CI gates (DCO, doc-consistency, accessibility, i18n) as their underlying capabilities land, matching items 1/12/14/15 above — don't add a CI job for a check that has nothing real to verify yet.

**VERIFICATION METHOD**: `.github/workflows/ci.yml` diff shows a new Gitleaks step; a deliberately-introduced fake high-entropy string in a test commit trips it in a scratch PR before being reverted.

---

## Summary table

| # | Criterion | Status |
|---|---|---|
| 1 | DCO | MET (was UNMET) |
| 2 | Governance model | MET |
| 3 | Code of Conduct | MET |
| 4 | Roles & responsibilities | MET |
| 5 | Access continuity | PARTIAL — plan MET, founder action still needed for 6-7 |
| 6 | Real second-person continuity | **FOUNDER ACTION REQUIRED** |
| 7 | Bus factor ≥ 2 | **FOUNDER ACTION REQUIRED** |
| 8 | 12-month roadmap | MET (was PARTIAL) |
| 9 | Architecture documentation | MET (was PARTIAL) |
| 10 | Security requirements | MET (was PARTIAL) |
| 11 | Quick start | MET |
| 12 | Documentation currentness | MET (was UNMET) |
| 13 | Achievements displayed | MET (was UNMET) |
| 14 | Accessibility | MET (was UNMET, real engineering work) |
| 15 | Internationalization | MET (was UNMET, real engineering work) |
| 16 | Password storage | N/A (correctly) |
| 17 | Contribution quality | MET (was PARTIAL) |
| 18 | CI hardening | MET (was PARTIAL) |

**14 MET, 1 N/A, 1 PARTIAL (access continuity — plan done, bus factor pending), 2 FOUNDER ACTION REQUIRED (of 18 reviewed), as of the 2026-08-18 update log above.**

## What's genuinely buildable by engineering work alone (no second human needed)

Items 1, 8, 9, 10 (verification), 12, 13, 17, 18 — DCO enforcement, canonical roadmap, architecture-doc consolidation, security-requirements checklist pass, doc-currency fixes + drift-check tooling, badge display, and CI hardening. Items 14–15 (accessibility, internationalization) are real, substantial engineering work, not quick fixes — each deserves its own focused pass.

**Update (2026-08-18): all of the above are now done** — see the Update log at the top of this document for what changed and where. What's left in this category is item 5's remaining half (the plan itself is written; nobody holds the access it describes yet) — that boundary is exactly where "buildable by engineering work alone" ends and "founder action required" (items 6-7) begins.

## What genuinely requires you, specifically

Items 5–7: a real second person with real access and standing. No amount of documentation manufactures that. The plan documents (item 5's `PROJECT_CONTINUITY_PLAN.md`, item 6's `FOUNDER_ACTION_CONTINUITY.md`) are buildable now and should be, so the moment a real second person exists, activation is fast — but the badge criteria themselves stay UNMET until that person is real.

Plus, regardless of every item above: **filling in the actual bestpractices.dev Silver form** for this project is a manual step only you can do, tied to your account.
