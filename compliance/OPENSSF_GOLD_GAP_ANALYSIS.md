# OpenSSF Best Practices Gold — WhitePact Gap Analysis

**Project:** WhitePact  
**Badge project:** 14112  
**Current earned Metal level:** Silver  
**Current earned Baseline level:** Baseline Level 1  
**Evidence refreshed:** 2026-08-31
**Purpose:** keep the path to Gold evidence-based. A criterion is not marked Met merely because code or documentation can be added; organizational and historical requirements must be satisfied by real project history.

## Current Gold blockers

### Organizational blockers — cannot be solved by repository automation

| Criterion | Current status | Why it remains open |
|---|---|---|
| `bus_factor` | **Unmet** | WhitePact currently has one primary maintainer. Gold requires a bus factor of at least two. Documentation and backups improve continuity but do not create a second knowledgeable maintainer. |
| `contributors_unassociated` | **Unmet** | Gold requires at least two unassociated significant contributors. WhitePact does not currently have that contributor history. |
| `two_person_review` | **Unmet** | Gold requires at least 50% of proposed modifications before release to be reviewed by a person other than the author. A solo-maintainer project cannot self-review its way into compliance. |

These three criteria must remain Unmet until real people and real review history satisfy them.

## Account / external-evidence blockers

| Criterion | Current status | Why it remains open |
|---|---|---|
| `require_2FA` | **OWNER ACTION REQUIRED** | Repository files cannot prove the maintainer's real GitHub 2FA state. Do not mark Met without owner/account evidence. |
| `secure_2FA` | **OWNER ACTION REQUIRED** | Requires evidence of a cryptographic second factor such as TOTP, passkey, or security key. Repository code cannot prove this. |
| `hardened_site` | **TECHNICALLY READY** | External checks on 2026-08-30/31 verified HTTPS redirect, HSTS, CSP, frame/MIME/referrer/permissions headers, certificate, and TLS 1.2/1.3. `compliance/HARDENED_SITE_VERIFICATION.md` records residual limitations. BadgeApp submission/award remains owner/external work. |

## Technical Gold work

| Criterion | Status | Evidence / next action |
|---|---|---|
| `achieve_silver` | **Met** | WhitePact has earned the OpenSSF Best Practices Silver badge. |
| `copyright_per_file` | **TECHNICALLY READY** | Tracked first-party source files under `src/`, `tests/`, `scripts/`, and `examples/` carry a copyright statement matching the root MIT `LICENSE`. `scripts/manage_license_headers.py --check` is enforced by the OpenSSF Policy Guard. Official BadgeApp evidence must be refreshed. |
| `license_per_file` | **TECHNICALLY READY** | The same tracked first-party source files carry `SPDX-License-Identifier: MIT`, enforced by CI. See `compliance/OPENSSF_SOURCE_LICENSES.md`; official BadgeApp evidence must be refreshed. |
| `repo_distributed` | **Met** | Git/GitHub is the authoritative distributed source repository. |
| `code_review_standards` | **Met** | `docs/CODE_REVIEW.md` defines review scope, security review checks, and acceptance criteria while explicitly not claiming independent review history. |
| `test_invocation` | **Met** | `CONTRIBUTING.md#running-tests` documents standard `pytest` invocation. |
| `test_continuous_integration` | **Met** | `.github/workflows/ci.yml` runs automated tests and quality gates. |
| `test_branch_coverage80` | **Met** | GitHub CI run 33198911431 measured **82.32% pure branch coverage (1928/2342)** and the CI gate requires at least 80%. |
| `test_statement_coverage90` | **Met** | GitHub CI run 33198911431 measured **92.29% pure statement coverage (10630/11518)** and the CI gate requires at least 90%. |
| `crypto_used_network` | **Met** | Production deployment documentation requires HTTPS/TLS at the trusted ingress boundary. |
| `crypto_tls12` | **Met** | Production documentation requires modern TLS support; live-site negotiation should be captured with the hardened-site evidence. |
| `security_review` | **Met as self-review** | WhitePact documents a human internal security review and clearly states that it is not an independent penetration test. Gold permits project-member review; independent assessment remains a separate enterprise assurance goal. |
| `hardening` | **Met** | Dashboard security middleware and other defense-in-depth controls are documented and tested. |
| `dynamic_analysis` | **Met** | Automated tests exceed the 80% pure branch-coverage route required by the project's selected dynamic-analysis path. |
| `dynamic_analysis_enable_assertions` | **Met** | Pytest assertions are executed throughout CI across security and runtime behavior. |

## OpenSSF Scorecard hardening now on `main`

PR #52 landed the repository-side Scorecard hardening on `main` without changing
WhitePact runtime feature logic. The official v5.0.0 assessment on 2026-08-31 reports
**6.0/10** for `79f604bcd5162aca92419f2801cfad3903ad9874`:

- GitHub Actions are pinned to full immutable commit SHAs.
- Workflow `GITHUB_TOKEN` permissions are reduced to least privilege, including moving release write/OIDC permissions to the publishing job only.
- Dependabot is enabled for GitHub Actions, Python, and Docker dependencies.
- Python, Postgres, and Redis container inputs are pinned to immutable Docker Hub index digests.
- `scripts/check_pinned_actions.py` and `.github/workflows/openssf-policy.yml` prevent movable Action tags from being reintroduced.
- `scripts/manage_license_headers.py` and the OpenSSF policy workflow prevent first-party source license/copyright metadata from regressing.
- Existing DCO, Gitleaks, dependency-review, Scorecard, SAST/dependency scan, release provenance, SBOM and signed-tag controls remain intact.

## Remaining Scorecard limitations

Hash-pinned Actions and container images materially improve `Pinned-Dependencies`.
Bandit and pip-audit now resolve from a generated `requirements-security.lock` using
`--require-hashes`. Normal CI and end-user dependency ranges intentionally remain flexible;
therefore this is stronger security-tooling evidence, not a claim that every shell install
in the repository is fully hash-locked.

The current official deductions remain visible in
`compliance/OPENSSF_SCORECARD_GAP_ANALYSIS.md`. Gold is governed by BadgeApp criteria,
not by turning the aggregate Scorecard number into a substitute award.

## Why Gold is deliberately not claimed yet

Gold is not a code-completion badge. Several criteria measure project governance and independent participation. WhitePact should earn those through actual community growth and review history rather than create fake maintainers, reviewers, or contributors. Account and live-deployment criteria also remain explicitly open until evidence exists.

The repository can be technically hardened immediately; the Gold badge should change only when the public evidence supports every MUST criterion.
