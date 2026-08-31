# OpenSSF Scorecard Gap Analysis

Evidence boundary: official Scorecard v5.0.0 result dated 2026-08-27 for
`9dcdc1bebe0ad856bd399dc627d17c35a2cc5828`; repository work assessed through
this hardening branch on 2026-08-31. Branch changes are not reflected in the official
score until merged and rescanned. Current official score: **4.2/10**.

| Check | Current evidence | Action taken | Status | Blocker | Remaining risk |
|---|---|---|---|---|---|
| Branch-Protection | Classic protection requires PRs, checks, conversation resolution; blocks force-push/deletion; Scorecard returned API error | Recorded API evidence and exact owner actions | VERIFIED, scanner unknown | PLATFORM LIMITATION | Required checks need refreshing after merge |
| Code-Review | 0/30 commits had non-author approval | Review standard exists; no synthetic reviewer added | HUMAN MATURITY BLOCKER | Genuine second reviewer/history | Sole-author blind spots |
| Contributors | Score 0; project has one maintainer | Honest roles and succession process documented | HUMAN MATURITY BLOCKER | Genuine independent contributors | Bus factor one |
| Dangerous-Workflow | Score 10; no `pull_request_target`; privileged credentials isolated | Added regression rejection for `pull_request_target`/`write-all` | VERIFIED | None | Future context interpolation still needs review |
| Dependency-Update-Tool | Score 0 on main | PR #52 adds weekly grouped-limit Dependabot coverage for pip, Actions, Docker | TECHNICALLY READY | Merge and rescan | Update PRs still require human review |
| Fuzzing | Score 0 | Added/recorded meaningful Hypothesis security properties | TECHNICALLY READY | Scorecard recognizes external fuzz services, not ordinary property tests | No continuous coverage-guided service |
| License | Score 10 | MIT, per-file SPDX/copyright guard retained | VERIFIED | None | Generated/vendor files excluded by policy |
| Maintained | Score 0; repository younger than Scorecard activity window | No fake activity created | EXTERNAL VERIFICATION REQUIRED | Passage of time and real activity | Young-project signal |
| Packaging | Score 10 | PyPI/release packaging controls retained | VERIFIED | None | Publication still depends on protected release workflow |
| Pinned-Dependencies | Score 0 on main | PR #52 pins Actions/containers; security tools now hash-locked | TECHNICALLY READY | Merge and rescan; normal CI/end-user resolution remains range-based | Some shell installs intentionally remain non-hash-locked outside security tooling |
| SAST | Score 0 on main | Weekly/main Bandit medium/high gate retained; scanner dependencies hash-locked | TECHNICALLY READY | Merge and Scorecard detection | Bandit is not a complete semantic analyzer |
| Security-Policy | Score 10 | Added private reporting, advisory workflow, dependency handling | VERIFIED | None | Response targets are not contractual SLA |
| Signed-Releases | Score 0 | Signed annotated tag, signer allow-list, attestations and verification docs exist | PENDING RELEASE VERIFICATION | A new hardened release must be produced/verified | Scorecard heuristics may still not credit GitHub attestations |
| Token-Permissions | Score 0 on main | PR #52 applies read defaults and job-scoped writes; regression rejects `write-all` | TECHNICALLY READY | Merge and rescan | Permission changes require continued review |
| Vulnerabilities | Score 9; one opt-in NLTK advisory | Recorded reachability analysis and OpenVEX; CI exception is explicit | TECHNICALLY READY | Upstream patched NLTK release | Optional extra carries unpatched code even though affected path is unreachable |
| Binary-Artifacts | Score 10 | No generated executables/unreviewable binaries | VERIFIED | None | Future additions guarded by review, not a dedicated binary scanner |
| CI-Tests | Score 10 | Python matrix, security and coverage gates | VERIFIED | None | Hosted CI availability |
| CII-Best-Practices | Score 7 | Official Silver; Gold technical evidence updated | ACHIEVED (Silver only) | Human/owner criteria and official BadgeApp award | Gold is not claimable |

The maximum honest improvement is to merge the hardened controls and let the official
scanner recalculate. Maintained, Contributors, and Code-Review cannot be repaired by
repository text; doing so would game the measurement.
