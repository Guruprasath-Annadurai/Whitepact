# Current OpenSSF Scorecard Evidence

Evidence captured from the official Scorecard API at `2026-08-31T06:12:07Z` for
`github.com/Guruprasath-Annadurai/Whitepact` at commit
`a46980d4873ab614f462878903ee4389c51f0e8f`. Scorecard v5.0.0
(`ea7e27ed41b76ab879c862fa0ca4cc9c61764ee4`) reported **6.1/10**. The
corresponding repository workflow run was
[`33363206684`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/33363206684)
and completed successfully. This is the current public score; branch-only controls below are
not included in it.

Normative evidence sources:

- Official result API: <https://api.scorecard.dev/projects/github.com/Guruprasath-Annadurai/Whitepact>
- Public viewer: <https://scorecard.dev/viewer/?uri=github.com/Guruprasath-Annadurai/Whitepact>
- Check documentation: <https://github.com/ossf/scorecard/tree/main/docs/checks>

| Check | Official score | Evidence interpretation | Branch status / remaining boundary |
|---|---:|---|---|
| [Binary-Artifacts](https://github.com/ossf/scorecard/blob/main/docs/checks.md#binary-artifacts) | 10 | no committed binary artifacts detected | preserve |
| [Branch-Protection](https://github.com/ossf/scorecard/blob/main/docs/checks.md#branch-protection) | -1 | scanner received `Resource not accessible by integration` | GitHub API audit separately confirms strict checks, admin enforcement, no force-push/deletion and conversation resolution; no required reviews/signatures; scanner result remains unresolved |
| [CI-Tests](https://github.com/ossf/scorecard/blob/main/docs/checks.md#ci-tests) | 10 | CI detected on 30/30 recent merged changesets | preserve |
| [CII-Best-Practices](https://github.com/ossf/scorecard/blob/main/docs/checks.md#cii-best-practices) | 7 | Silver badge detected | Gold includes human/account evidence not manufactured here |
| [Code-Review](https://github.com/ossf/scorecard/blob/main/docs/checks.md#code-review) | 0 | 0/30 recent changesets had qualifying approval | genuine non-author review history required |
| [Contributors](https://github.com/ossf/scorecard/blob/main/docs/checks.md#contributors) | 0 | no qualifying organizations detected | genuine independent contributor history required |
| [Dangerous-Workflow](https://github.com/ossf/scorecard/blob/main/docs/checks.md#dangerous-workflow) | 10 | no dangerous workflow pattern detected | regression guard rejects `pull_request_target` and `workflow_run` |
| [Dependency-Update-Tool](https://github.com/ossf/scorecard/blob/main/docs/checks.md#dependency-update-tool) | 10 | Dependabot detected | preserve reviewed updates |
| [Fuzzing](https://github.com/ossf/scorecard/blob/main/docs/checks.md#fuzzing) | 0 | no recognized continuous-fuzzing integration | meaningful Atheris/ClusterFuzzLite path assessed, but not added because its container could not be executed locally; see `FUZZING_READINESS.md` |
| [License](https://github.com/ossf/scorecard/blob/main/docs/checks.md#license) | 10 | recognized MIT license | preserve SPDX enforcement |
| [Maintained](https://github.com/ossf/scorecard/blob/main/docs/checks.md#maintained) | 0 | repository is less than 90 days old | time and genuine activity only |
| [Packaging](https://github.com/ossf/scorecard/blob/main/docs/checks.md#packaging) | 10 | release packaging detected | preserve trusted builder |
| [Pinned-Dependencies](https://github.com/ossf/scorecard/blob/main/docs/checks.md#pinned-dependencies) | 5 | remaining pip/download findings in Docker, scripts, and workflows | branch replaces dependency resolution with generated hash locks, digest-pins ZAP, and removes flagged pipe/install patterns; official rescan required |
| [SAST](https://github.com/ossf/scorecard/blob/main/docs/checks.md#sast) | 0 | recognized SAST not detected | branch adds GitHub CodeQL while retaining Bandit; official run and rescan required |
| [Security-Policy](https://github.com/ossf/scorecard/blob/main/docs/checks.md#security-policy) | 10 | actionable policy detected | preserve |
| [Signed-Releases](https://github.com/ossf/scorecard/blob/main/docs/checks.md#signed-releases) | 0 | release assets did not match Scorecard's recognized signature/provenance evidence | branch exports the real GitHub/Sigstore bundle as `.sigstore` and verifies it before publication; a new release and rescan are required |
| [Token-Permissions](https://github.com/ossf/scorecard/blob/main/docs/checks.md#token-permissions) | 10 | least-privilege token permissions detected | preserve; regression guard rejects broad write declarations |
| [Vulnerabilities](https://github.com/ossf/scorecard/blob/main/docs/checks.md#vulnerabilities) | 10 | no vulnerabilities detected in Scorecard scope | preserve SCA/OpenVEX process; this is not a no-vulnerability warranty |

## Repository-controlled change boundary

This branch adds three generated, fully resolved Python hash locks; uses them in
CI, builds, scans, and the production image; adds recognized CodeQL analysis;
exports and verifies GitHub's real portable provenance bundle; and enforces these
controls with `scripts/check_scorecard_regressions.py`. It does not alter review
history, repository age, contributor identity, public release history, scanner
permissions, or external service evidence.

No post-change score is predicted. Until these controls merge, execute on GitHub,
produce a new release where applicable, and the official service rescans the
repository, the only publishable score remains **6.1/10**.
