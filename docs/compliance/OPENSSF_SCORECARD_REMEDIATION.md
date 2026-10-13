# OpenSSF Scorecard — Comprehensive Remediation & Check Audit

**Tool:** OpenSSF Scorecard (v5.5.0)
**Project:** WhitePact (`Guruprasath-Annadurai/Whitepact`)  
**Current Public Score:** **8.1 / 10** (API result dated 2026-09-27, commit `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec`)
**Evaluation Date:** 2026-09-28  

---

## 1. Scorecard Overview

OpenSSF Scorecard performs automated heuristic checks against open-source repositories to measure supply-chain security practices. The current public API result is **8.1/10**, superseding the historical 6.0/10 result.

Scorecard checks fall into three distinct categories:
1. **Directly Remediable Technical Practices:** Workflow permissions, dependency pinning, license compliance, binary exclusion, security policies, automated CI, and continuous fuzzing. These must be reported at the scanner's actual current score, not described as universally complete.
2. **Scanner / Heuristic Limitations:** Where WhitePact has implemented strong security controls (such as SSH signed tags, Sigstore artifact attestations, CodeQL/Bandit SAST, and GitHub branch protection), but Scorecard's automated heuristics or API token permissions do not recognize them.
3. **Human & Organizational Governance Metrics:** Metrics that measure community longevity, contributor diversity, and multi-party code reviews. (These cannot and will not be artificially inflated).

---

## 2. Exhaustive Check-by-Check Audit

| Scorecard Check | Score | Classification | Verifiable Repository Reality & Remediation Status |
|---|---:|---|---|
| **Binary-Artifacts** | 10/10 | `ALREADY SATISFIED` | Verified zero generated or unreviewable executable binaries checked into Git. |
| **Branch-Protection** | -1/10 | `PLATFORM LIMITATION` | Scorecard returned `Resource not accessible by integration` because the read-only GITHUB_TOKEN cannot query repository branch protection rules via the GitHub API. Branch protection is strictly active on `main`. |
| **CI-Tests** | 10/10 | `ALREADY SATISFIED` | 4 of 4 merged PRs sampled by the current result executed CI tests. |
| **CII-Best-Practices** | 7/10 | `PARTIALLY SATISFIED` | OpenSSF Best Practices Silver badge earned (Project ID 14112). Gold is pending human governance criteria. |
| **Code-Review** | 10/10 | `SCANNER-VERIFIED` | The current scanner reports all sampled changesets reviewed. This is an automated heuristic result and does not satisfy the distinct OSPS non-author-human requirement. |
| **Contributors** | 0/10 | `HUMAN_BLOCKED` | 0 independent organizations detected among commit authors. Reflects historical reality; will naturally improve with community adoption. |
| **Dangerous-Workflow** | 10/10 | `ALREADY SATISFIED` | Zero dangerous workflow triggers (such as unvalidated `pull_request_target` checkouts or arbitrary script execution). |
| **Dependency-Update-Tool** | 10/10 | `ALREADY SATISFIED` | Dependabot actively configured for GitHub Actions, Python pip, and Docker container ecosystems (`.github/dependabot.yml`). |
| **Fuzzing** | 0/10 | `TECHNICAL REQUIREMENT` | Hypothesis property-based testing is heavily utilized across core modules, but continuous fuzzing engines (e.g. OSS-Fuzz or ClusterFuzzLite) are not yet integrated. |
| **License** | 10/10 | `ALREADY SATISFIED` | Recognized root MIT license file and SPDX headers enforced across all first-party files. |
| **Maintained** | 10/10 | `SCANNER-VERIFIED` | Current result reports 30 commits and 9 issue activities in the preceding 90 days. |
| **Packaging** | 10/10 | `ALREADY SATISFIED` | Automated GitHub Actions release packaging workflows present and operational. |
| **Pinned-Dependencies** | 5/10 | `PARTIALLY SATISFIED` | GitHub Actions and security-sensitive infrastructure are pinned, but the scanner still detects dependencies not pinned by hash. |
| **SAST** | 10/10 | `ALREADY SATISFIED` | Current Scorecard detects SAST on all commits. |
| **Security-Policy** | 10/10 | `ALREADY SATISFIED` | Comprehensive, actionable `SECURITY.md` detailing vulnerability disclosure, scope, and encryption channels. |
| **Signed-Releases** | 0/10 | `SCANNER GAP` | Releases use SSH tag signatures verified against an allowed-signers file and Sigstore SLSA attestations. Scorecard's heuristic looks specifically for GPG keys and does not parse GitHub CLI / Sigstore attestations. |
| **Token-Permissions** | 10/10 | `ALREADY SATISFIED` | Top-level workflow permissions set to `permissions: contents: read` across all workflows; write permissions strictly scoped to dedicated jobs. |
| **Vulnerabilities** | 9/10 | `REQUIRES TRIAGE` | Current Scorecard reports one existing vulnerability. The affected component and disposition must be verified before claiming zero known vulnerabilities. |

---

## 3. Remediation Analysis & Anti-Gaming Position

1. **Why Scorecard is 8.1 and Not 10.0:**
   - `Contributors` remains 0 because the scanner finds no contributing company or organization.
   - `Fuzzing` remains 0 because no continuous fuzzing service is detected.
   - `Signed-Releases` remains 0 despite independently verifiable GitHub attestations; the public result must still be reported as 0.
   - `Vulnerabilities` is 9 because the scanner reports one existing vulnerability requiring triage.
   - 1 check (`Branch-Protection`) is blocked from the scanner by GitHub API token isolation.
   - `Pinned-Dependencies` is 5 because some dependencies are not hash-pinned.
2. **Honest Score Ceiling:**
   - No maximum claim is made. Continuous fuzzing, dependency pinning, and vulnerability disposition remain legitimate technical improvement areas.
