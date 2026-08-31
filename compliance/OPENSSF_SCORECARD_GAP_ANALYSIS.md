# OpenSSF Scorecard Gap Analysis

Evidence boundary: official Scorecard v5.0.0 result dated 2026-08-31 for
`79f604bcd5162aca92419f2801cfad3903ad9874`; workflow run
`33359584927` completed successfully and the official API publishes **6.0/10**.
This supersedes the pre-hardening 4.2 result.

| Check | Score | Current evidence | Classification | Remaining action / limitation |
|---|---:|---|---|---|
| Binary-Artifacts | 10 | no binaries detected | VERIFIED | preserve review discipline |
| Branch-Protection | -1 | scanner API returned `Resource not accessible by integration`; authenticated repository audit separately found protections | PLATFORM LIMITATION | retain protection; retry official scan |
| CI-Tests | 10 | 30/30 merged PRs checked | VERIFIED | hosted CI availability |
| CII-Best-Practices | 7 | official Silver badge detected | ACHIEVED (Silver only) | Gold still has human/account criteria |
| Code-Review | 0 | 0/30 approved changesets | HUMAN MATURITY BLOCKER | real non-author reviews only |
| Contributors | 0 | no contributing companies/organizations detected | HUMAN MATURITY BLOCKER | genuine independent contributors |
| Dangerous-Workflow | 10 | no dangerous workflow pattern detected | VERIFIED | continue contextual review |
| Dependency-Update-Tool | 10 | Dependabot detected | VERIFIED | human review of updates remains necessary |
| Fuzzing | 0 | no recognized fuzzer integration | EXTERNAL-SERVICE / TECHNICAL GAP | Hypothesis is property testing, not a recognized continuous fuzzer |
| License | 10 | recognized MIT license | VERIFIED | per-file policy is separately enforced |
| Maintained | 0 | repository created within 90 days | HUMAN HISTORY / TIME | do not manufacture activity |
| Packaging | 10 | GitHub Actions release packaging detected | VERIFIED | preserve protected release path |
| Pinned-Dependencies | 4 | Actions and containers pinned; most pip/download commands not hash-pinned | PARTIALLY VERIFIED | remediate only where coherent and maintainable |
| SAST | 0 | Scorecard did not recognize SAST across recent commits | TECHNICALLY READY ON BRANCH / SCANNER GAP | merge PR-triggered Bandit gate and reassess recognition |
| Security-Policy | 10 | actionable policy detected | VERIFIED | response objectives are not contractual SLAs |
| Signed-Releases | 0 | Scorecard did not recognize v1.2.6 signature/provenance | SCANNER MISMATCH | independent tag and attestation checks pass; do not alter evidence to game heuristic |
| Token-Permissions | 10 | least-privilege workflow tokens detected | VERIFIED | preserve job-scoped writes |
| Vulnerabilities | 10 | zero existing vulnerabilities detected by Scorecard | VERIFIED FOR SCANNER SCOPE | retain SCA and OpenVEX review |

Scorecard v5.0.0 did not emit a separate Webhooks check in this result. The maximum honest
improvement is to address coherent dependency/SAST gaps, preserve legitimate controls,
and wait for genuine review/contributor/history evidence. Scorecard's Signed-Releases
heuristic does not override independently verified v1.2.6 release evidence.
