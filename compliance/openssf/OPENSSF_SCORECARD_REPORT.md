# OpenSSF Scorecard — Manual Checklist Review

**Date:** 2026-08-29
**Method:** the `scorecard` CLI is **not installed and not runnable in this sandbox** (`which scorecard` → not found; no outbound network access to run it against the live GitHub repo, and no local scoring binary available to install). Confirmed, not assumed. Instead: a manual, criterion-by-criterion review against the actual repository state, security-first — not chasing a blind 10/10.

**Existing automation:** `.github/workflows/scorecard.yml` already runs the official `ossf/scorecard-action` weekly and on every push to `main`, uploading SARIF to code scanning and publishing to the public Scorecard API. That is the authoritative live score; this document is a supplementary manual read of the same checks, not a replacement for actually running it. Neither this session nor this document has that workflow's real numeric output — no fabricated score is stated anywhere below.

---

| Check | Manual assessment | What would raise it |
|---|---|---|
| **Binary-Artifacts** | Likely clean — `find . -name "*.exe" -o -name "*.dll" -o -name "*.so" -o -name "*.jar"` not run exhaustively this session, but the project is a pure Python package (`pyproject.toml`, `src/`) with no vendored binaries observed in normal browsing. Not independently re-verified with a full binary scan this session. | A real Scorecard run confirms/denies this precisely; low priority to chase manually given the project shape. |
| **Branch-Protection** | Strong | `compliance/OSPS_BASELINE_BRANCH_PROTECTION.md` — PR required, force-push/deletion blocked, `enforce_admins: true`, 8 required status checks, verified via `gh api` `GET`. `required_approving_review_count: 0` is the one real gap, and it's a security-first, honest 0 (see rationale in that doc), not something to fake to 1. |
| **CI-Tests** | Met | `.github/workflows/ci.yml` runs lint, type-check, tests with coverage on every PR; 3187 tests pass, re-verified this session. |
| **CII-Best-Practices** (i.e. OpenSSF Best Practices Badge) | Passing + Baseline Level 1 confirmed live (per `README.md:807`, `compliance/OPENSSF_SILVER_GAP_ANALYSIS.md`'s prerequisite check); Silver technically ready but not yet submitted/awarded (see `OPENSSF_MASTER_MATRIX.md`). | Submit the Silver form (founder action, see `OPENSSF_HUMAN_REQUIREMENTS.md`). |
| **Code-Review** | Partial | `docs/CODE_REVIEW.md` exists only on unmerged PR #52. Review *standard* aside, actual required-approval enforcement is 0 today by necessity (solo maintainer). Scorecard's Code-Review check specifically measures whether changesets went through review before merge — with one maintainer and `required_approving_review_count: 0`, this check will score low honestly, and should. | Merge PR #52 (owner decision) for the standard doc; a real second reviewer (human requirement) to actually raise the substantive score. |
| **Contributors** | Low, honestly | `git log --format='%ae' \| sort -u` → 3 emails, evidence points to effectively one person. Scorecard measures contributor diversity from organizations; this project doesn't have that yet. | Real, independent contributors over time — not fixable by configuration. |
| **Dangerous-Workflow** | Likely clean | No `pull_request_target` misuse or script-injection-prone `${{ }}` interpolation observed in the workflows read this session (`ci.yml`, `security-scan.yml`, `scorecard.yml`). Not exhaustively scanned across every workflow file this session. | A full Scorecard run is the authoritative check; worth a follow-up grep for `pull_request_target` + untrusted-input interpolation across all of `.github/workflows/`. |
| **Dependency-Update-Tool** | Partial | Dependabot config (`.github/dependabot.yml`) exists only on unmerged PR #52. Not present on this branch/`main` today. | Merge PR #52, or add an equivalent Dependabot/Renovate config directly (low-risk, purely additive — a reasonable near-term follow-up even independent of PR #52). |
| **Fuzzing** | Not present | No `oss-fuzz` integration or fuzz-testing harness found in this codebase (governance/policy/crypto logic is the highest-value fuzz target if this is ever pursued). | Genuine engineering investment — property-based tests (e.g. `hypothesis`) on the crypto/policy modules would be a reasonable, scoped starting point, not attempted in this pass. |
| **License** | Met | `LICENSE` (MIT) present at repo root, OSI-approved, machine-detectable. |
| **Maintained** | Met | Active commit history through 2026-08-2x per `git log`; this is not a dormant repository. |
| **Packaging** | Met | `pyproject.toml`, hatchling backend, builds a real wheel/sdist — verified by actually building it twice this session for the reproducibility check. |
| **Pinned-Dependencies** | Partial, real gap acknowledged | Workflow Action SHA pinning exists only on unmerged PR #52. `security-scan.yml`'s own `pip install bandit pip-audit` step (read this session) is an unpinned pip install, matching PR #52's own hardening report's stated caveat ("some pip install commands remain visible to Scorecard without `--require-hashes`... intentionally not papered over"). | Merge PR #52 for Action pinning; a hash-locked Python bootstrap workflow to close the pip-install gap fully — real, scoped follow-up work, not done here per the "don't touch workflows" constraint. |
| **SAST** | Met | Bandit runs in `.github/workflows/security-scan.yml`, re-run this session (`uvx bandit -r src/responsibleai -ll`): 0 Medium/High findings, 21 Low (asserts, try/except/pass, 2 format-string false positives). CodeQL also configured (`.github/workflows/codeql.yml`). |
| **Security-Policy** | Met | `SECURITY.md` at repo root. |
| **Signed-Releases** | Unknown — not re-verified this session | `compliance/SIGNED_VERSION_TAGS.md` exists on this branch (title suggests signed-tag practice); not re-read in full this session due to time budget. Flagged, not claimed. |
| **Token-Permissions** | Partial | Least-privilege `GITHUB_TOKEN` scoping (moving release/OIDC write permissions to the publish job only) exists only on unmerged PR #52. Current `main`-lineage workflows were not individually re-audited line-by-line for `permissions:` blocks this session beyond `security-scan.yml` (`permissions: contents: read`, correctly scoped) and `scorecard.yml` (correctly scoped, `security-events: write`/`id-token: write` only where needed). | Merge PR #52, or apply the same least-privilege pattern directly to remaining workflows as a scoped follow-up. |
| **Vulnerabilities** | Met (as of this session) | `uv run --with pip-audit -- pip-audit` against the real project environment (~163 packages): **no known vulnerabilities found**, re-run this session, not copied from a prior date. |

---

## Security-first framing, not score-chasing

Two checks (`Code-Review`, `Contributors`) will score low on a real Scorecard run **honestly and correctly** given WhitePact's current solo-maintainer reality — and this document does not recommend gaming them (e.g., self-approving PRs through a bot, or fabricating contributor identities). Those stay low until items 1 and 4 in `OPENSSF_HUMAN_REQUIREMENTS.md` are genuinely true. `Pinned-Dependencies` and `Token-Permissions` have a real, ready fix sitting in unmerged PR #52 — merging it (an owner decision, not this pass's call) would raise both without any new work.

## Recommended next step

Once `scorecard` CLI access or a GitHub Actions run against this branch's PR is available, run the real tool (`scorecard --repo=github.com/Guruprasath-Annadurai/Whitepact` or let the existing weekly workflow do it) and replace this manual checklist's assessments with actual numeric sub-scores. This document should be treated as a bridge, not a permanent substitute for the real tool.
