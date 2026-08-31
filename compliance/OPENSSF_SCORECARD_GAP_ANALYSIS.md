# OpenSSF Scorecard Gap Analysis

The authoritative dated baseline and complete per-check evidence are maintained
in [`OPENSSF_SCORECARD_CURRENT.md`](OPENSSF_SCORECARD_CURRENT.md). The official
2026-08-31 result for `a46980d4873ab614f462878903ee4389c51f0e8f` is **6.1/10**.
No branch-only improvement is represented as an achieved Scorecard result.

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
| Pinned-Dependencies | 5 | Actions and containers pinned; pip/download findings remain in the official baseline | IMPLEMENTED ON BRANCH / NOT RESCANNED | generated hash locks and detector findings remediated; merge and rescan |
| SAST | 0 | Scorecard did not recognize SAST across recent commits | IMPLEMENTED ON BRANCH / NOT RUN | merge and successfully run CodeQL, then rescan |
| Security-Policy | 10 | actionable policy detected | VERIFIED | response objectives are not contractual SLAs |
| Signed-Releases | 0 | v1.2.6 has verified online provenance but no recognized portable release asset | IMPLEMENTED FOR NEXT RELEASE | publish and verify the genuine `.sigstore` bundle on a new signed release |
| Token-Permissions | 10 | least-privilege workflow tokens detected | VERIFIED | preserve job-scoped writes |
| Vulnerabilities | 10 | zero existing vulnerabilities detected by Scorecard | VERIFIED FOR SCANNER SCOPE | retain SCA and OpenVEX review |

Scorecard v5.0.0 did not emit a separate Webhooks check in this result. The maximum honest
improvement is to address coherent dependency/SAST gaps, preserve legitimate controls,
and wait for genuine review/contributor/history evidence. Scorecard's Signed-Releases
heuristic does not override independently verified v1.2.6 release evidence.
