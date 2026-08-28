# OpenSSF Best Practices Gold — WhitePact Gap Analysis

**Project:** WhitePact  
**Badge project:** 14112  
**Current earned level:** Silver  
**Purpose:** keep the path to Gold evidence-based. A criterion is not marked Met merely because code or documentation can be added; organizational and historical requirements must be satisfied by real project history.

## Current Gold blockers

### Organizational blockers — cannot be solved by repository automation

| Criterion | Current status | Why it remains open |
|---|---|---|
| `bus_factor` | **Unmet** | WhitePact currently has one primary maintainer. Gold requires a bus factor of at least two. Documentation and backups improve continuity but do not create a second knowledgeable maintainer. |
| `contributors_unassociated` | **Unmet** | Gold requires at least two unassociated significant contributors. WhitePact does not currently have that contributor history. |
| `two_person_review` | **Unmet** | Gold requires at least 50% of proposed modifications before release to be reviewed by a person other than the author. A solo-maintainer project cannot self-review its way into compliance. |

These three criteria must remain Unmet until real people and real review history satisfy them.

## Technical Gold work

| Criterion | Status | Evidence / next action |
|---|---|---|
| `achieve_silver` | **Met** | WhitePact has earned the OpenSSF Best Practices Silver badge. |
| `copyright_per_file` | **Unmet** | The root MIT `LICENSE` has a copyright notice, but source files do not yet consistently carry per-file copyright statements. A later low-conflict licensing pass should add/enforce them. |
| `license_per_file` | **Unmet** | Source files do not yet consistently contain `SPDX-License-Identifier: MIT`. A later low-conflict licensing pass should add/enforce SPDX metadata without colliding with large in-flight feature branches. |
| `repo_distributed` | **Met** | Git/GitHub is the authoritative distributed source repository. |
| `require_2FA` | **Needs account-level evidence** | GitHub operates a mandatory-2FA program for eligible code contributors, but this personal repository cannot use an organization-level 2FA enforcement switch. Do not mark Met solely from a repository file. |
| `secure_2FA` | **Needs account-level evidence** | Requires evidence that cryptographic 2FA such as TOTP, passkey, security key, or equivalent is actually used/required; repository code cannot prove the maintainer's authentication method. |
| `code_review_standards` | **Met after this hardening branch** | `docs/CODE_REVIEW.md` defines review scope, security review checks, and acceptance criteria while explicitly not claiming independent review history. |
| `test_invocation` | **Met** | `CONTRIBUTING.md#running-tests` documents standard `pytest` invocation. The live badge entry needs the missing URL field corrected. |
| `test_continuous_integration` | **Met** | `.github/workflows/ci.yml` runs automated tests and quality gates. |
| `test_branch_coverage80` | **Met** | `compliance/OPENSSF_DYNAMIC_ANALYSIS.md` documents verified 80.19% pure branch coverage and CI enforces an 80% branch threshold. |
| `test_statement_coverage90` | **Not yet claimed** | Existing evidence proves the Silver 80% requirement and 80.19% branch coverage, but does not contain a current independently captured pure statement-coverage value at or above 90%. Measure first; add real tests if below 90%. |
| `crypto_used_network` | **Met** | Production deployment documentation requires HTTPS/TLS at the trusted ingress boundary. |
| `crypto_tls12` | **Met** | Production documentation supports TLS 1.2/1.3. |
| `hardened_site` | **Needs live-site evidence** | Gold requires CSP, HSTS, X-Content-Type-Options and X-Frame-Options on the project website/repository/download site. GitHub is known-good; `whitepact.com` must be checked live before claiming Met. |
| `security_review` | **Met as self-review** | WhitePact documents a human internal security review and clearly states that it is not an independent penetration test. Gold permits project-member review; independent assessment remains a separate enterprise assurance goal. |
| `hardening` | **Met** | Dashboard security middleware and other defense-in-depth controls are documented and tested. |
| `dynamic_analysis` | **Met** | Automated tests with >=80% pure branch coverage satisfy the project's selected dynamic-analysis route. |
| `dynamic_analysis_enable_assertions` | **Met** | Pytest assertions are executed throughout CI across security and runtime behavior. |

## OpenSSF Scorecard hardening in this branch

The `security/openssf-hardening` branch addresses repository-side Scorecard findings without changing WhitePact runtime behavior:

- GitHub Actions are pinned to full immutable commit SHAs.
- Workflow `GITHUB_TOKEN` permissions are reduced to least privilege, including moving release write/OIDC permissions to the publishing job only.
- Dependabot is enabled for GitHub Actions and Python dependencies.
- `scripts/check_pinned_actions.py` and `.github/workflows/openssf-policy.yml` prevent movable action tags from being reintroduced.
- Existing DCO, Gitleaks, dependency-review, Scorecard, SAST/dependency scan, release provenance, SBOM and signed-tag controls remain intact.

## Why Gold is deliberately not claimed yet

Gold is not a code-completion badge. Several criteria measure project governance and independent participation. WhitePact should earn those through actual community growth and review history rather than create fake maintainers, reviewers, or contributors.

The repository can be hardened immediately; the Gold badge should change only when the public evidence supports every MUST criterion.
