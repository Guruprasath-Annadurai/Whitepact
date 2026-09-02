# GitHub Actions — SHA Pinning

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, supply-chain row of
`00_MASTER_READINESS_AUDIT.md` — "GitHub Actions pinning not
independently verified in this audit (by SHA vs. tag)."

## Finding

Confirmed by direct grep across every workflow file
(`.github/workflows/*.yml`, 8 files, 34 `uses:` lines): **every single
one** referenced a mutable version tag (`@v4`, `@v2.4.0`,
`@release/v1`, etc.), none pinned to a commit SHA. A mutable tag can be
force-moved by the action's own maintainer (or, in a supply-chain
compromise scenario, by an attacker who gains control of the action's
repository) to point at different, potentially malicious code without
this repository's own workflow files ever changing — the exact
class of risk OpenSSF Scorecard's "Pinned-Dependencies" check exists
to catch.

## Fix

All 34 `uses:` references across all 8 workflow files pinned to the
full commit SHA their version tag currently resolves to, with the
original tag preserved as a trailing comment (the same convention
Dependabot itself uses, so Dependabot's own GitHub-Actions update
mechanism can still find and propose SHA-to-SHA updates going forward):

```yaml
uses: actions/checkout@11d5960a326750d5838078e36cf38b85af677262 # v4
```

Every SHA was resolved directly via `gh api repos/<owner>/<repo>/commits/<tag>`
(real API calls against the actual action repositories, not guessed or
copied from memory) at the time of this change:

| Action | Tag | SHA |
|---|---|---|
| `actions/checkout` | v4 | `11d5960a326750d5838078e36cf38b85af677262` |
| `actions/setup-python` | v5 | `a26af69be951a213d495a4c3e4e4022e16d87065` |
| `actions/upload-artifact` | v4 | `ea165f8d65b6e75b540449e92b4886f43607fa02` |
| `azure/setup-helm` | v4 | `1a275c3b69536ee54be43f2070a358922e12c8d4` |
| `actions/setup-node` | v4 | `49933ea5288caeca8642d1e84afbd3f7d6820020` |
| `codecov/codecov-action` | v4 | `b9fd7d16f6d7d1b5d2bec1a2887e65ceed900238` |
| `github/codeql-action/init` | v3 | `6f5948dfacef28e207b48d0905cf90c03365536d` |
| `github/codeql-action/autobuild` | v3 | `6f5948dfacef28e207b48d0905cf90c03365536d` |
| `github/codeql-action/analyze` | v3 | `6f5948dfacef28e207b48d0905cf90c03365536d` |
| `github/codeql-action/upload-sarif` | v3 | `6f5948dfacef28e207b48d0905cf90c03365536d` |
| `actions/dependency-review-action` | v4 | `2031cfc080254a8a887f58cffee85186f0e49e48` |
| `gitleaks/gitleaks-action` | v2 | `ff98106e4c7b2bc287b24eaf42907196329070c7` |
| `actions/attest-build-provenance` | v2 | `e8998f949152b193b063cb0ec769d69d929409be` |
| `pypa/gh-action-pypi-publish` | release/v1 | `dc37677b2e1c63e2034f94d8a5b11f265b73ba33` |
| `softprops/action-gh-release` | v2 | `3bb12739c298aeb8a4eeaf626c5b8d85266b0e65` |
| `ossf/scorecard-action` | v2.4.0 | `62b2cac7ed8198b15735ed49ab1e5cf35480ba46` |

(`github/codeql-action`'s four sub-actions all resolve to the same
commit — they're built from the same repository release, which is
expected, not an error.)

## Verification

Every workflow file re-parsed as valid YAML after the edit
(`python3 -c "import yaml; yaml.safe_load(open(f))"` per file, all 8
pass) — the mechanical `uses: X@Y # Z` substitution didn't corrupt any
file's structure.

## Maintenance going forward

Dependabot is already enabled for this repository and natively
understands the `owner/repo@<sha> # <tag>` pinning convention — it
will continue to propose version-bump PRs by updating both the SHA and
the trailing comment together, the same as it would for a plain tag
reference. No new tooling or process is required; the only behavior
change is that a bump now requires a real PR (visible, reviewable) to
take effect, instead of happening silently the moment an action
maintainer moves their tag.
