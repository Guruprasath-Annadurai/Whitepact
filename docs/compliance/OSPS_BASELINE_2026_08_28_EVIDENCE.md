# OpenSSF Open Source Project Security (OSPS) Baseline — Complete Evidence Register

**Normative Standard:** OpenSSF OSPS Baseline Specification  
**Normative Version:** **v2026.08.28** (Official Checklist retrieved 2026-08-30)  
**Project:** WhitePact (`Guruprasath-Annadurai/Whitepact`)  
**Evaluation Date:** 2026-09-28  
**Official BadgeApp Status:** **Level 1 Awarded**  
**Internal Verification Status:** **Level 1 PASS; Level 2 ELIGIBLE; Level 3 NOT YET ELIGIBLE**  

---

## 1. Executive Summary & Level Determinations

1. **Level 1:** **PASS / FULLY VERIFIED (100%)**  
   All 23 criteria across Access Control, Build/Release, Documentation, Governance, Legal, QA, and Vulnerability Management are fully satisfied and verified against repository evidence.
2. **Level 2:** **PASS / TECHNICALLY ELIGIBLE (100%)**  
   All 19 Level 2 controls (including token least-privilege, unique SemVer release identifiers, signed tags, cryptographic hash manifests, automated CI testing, and private vulnerability reporting) are fully implemented and verified.
3. **Level 3:** **NOT YET ELIGIBLE (BLOCKED ON OSPS-QA-07.01)**  
   WhitePact satisfies all technical Level 3 requirements (e.g. SLSA Build L3 provenance, CycloneDX SBOM attestations, release verification guide, secrets lifecycle policy, OpenVEX vulnerability filtering, SAST threshold enforcement). However, control **`OSPS-QA-07.01`** strictly mandates at least one non-author human approval prior to merge. Because WhitePact is maintained by a solo developer, Level 3 cannot be legitimately awarded until independent community reviewers participate in the pull request process.

---

## 2. Level 1 Control Evidence Register

| Control ID | Category | Requirement | Verifiable Repository Evidence | Classification | Status |
|---|---|---|---|---|---|
| **OSPS-AC-01.01** | Access Control | MFA required for sensitive repository access | GitHub account MFA enforced; BadgeApp Level 1 certified. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-AC-02.01** | Access Control | Least privilege for new collaborators | Explicit role definitions in `MAINTAINERS.md`; single collaborator role. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-AC-03.01** | Access Control | Prevent direct commits to primary branch | GitHub branch protection rules enabled on `main`; PR and passing CI required. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-AC-03.02** | Access Control | Protect primary branch deletion | Deletion protection enabled on `main` branch. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-01.01** | Build & Release | Validate untrusted pipeline metadata | No untrusted `pull_request_target` interpolation; explicit checkout refs. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-01.03** | Build & Release | Isolate untrusted code from privileged CI | Untrusted PR jobs run with read-only tokens; publishing isolated to tagged events. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-03.01** | Build & Release | Encrypted official project channels | HTTPS enforced across GitHub, PyPI, and `https://whitepact.com`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-03.02** | Build & Release | Authenticated & encrypted distribution | Releases distributed via HTTPS on PyPI and GitHub Releases with checksums. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-07.01** | Build & Release | Prevent unencrypted secrets in VCS | Gitleaks secret scanner workflow, pre-commit hooks, GitHub push protection. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-DO-01.01** | Documentation | Basic user guides provided | `README.md`, `docs/quickstart.md`, API documentation. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-DO-02.01** | Documentation | Defect reporting guide provided | `SUPPORT.md`, `CONTRIBUTING.md`, GitHub issue templates. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-GV-02.01** | Governance | Public discussion mechanism | GitHub Issues, Pull Requests, and Discussions enabled. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-GV-03.01** | Governance | Contribution process documented | `CONTRIBUTING.md` defines patch submission, linting, and testing workflows. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-LE-02.01** | Legal | Source has OSI-approved license | MIT License in root `LICENSE`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-LE-02.02** | Legal | Released assets use OSI license | PyPI wheels and sdist packages carry `License :: OSI Approved :: MIT License`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-LE-03.01** | Legal | Repository contains license file | `LICENSE` present in repository root. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-LE-03.02** | Legal | License accompanies binary releases | Package distributions contain embedded MIT license. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-01.01** | Quality | Public static source URL | Canonical repo at `https://github.com/Guruprasath-Annadurai/Whitepact`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-01.02** | Quality | Public attributable change history | Immutable Git commit history with author attribution and DCO sign-offs. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-02.01** | Quality | Direct dependency list maintained | Defined in `pyproject.toml` (`[project.dependencies]`). | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-04.01** | Quality | List project repositories if multiple | N/A — single monolithic repository architecture. | `NOT APPLICABLE` | **NOT APPLICABLE** |
| **OSPS-QA-05.01** | Quality | No generated executables in VCS | Zero pre-compiled binaries in Git; Scorecard Binary-Artifacts: 10/10. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-05.02** | Quality | No unreviewable binaries in VCS | Full source transparency; no binary blobs or proprietary modules. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-02.01** | Quality | Publish security contact details | `SECURITY.md` provides private security contact address. | `TECHNICAL REQUIREMENT` | **VERIFIED** |

---

## 3. Level 2 Control Evidence Register

| Control ID | Category | Requirement | Verifiable Repository Evidence | Classification | Status |
|---|---|---|---|---|---|
| **OSPS-AC-04.01** | Access Control | Default CI permissions least-privilege | Workflows declare top-level `permissions: contents: read`; Scorecard Token-Permissions: 10/10. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-02.01** | Build & Release | Unique release identifiers | Strict Semantic Versioning (SemVer 2.0.0) applied to Git tags and packages. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-04.01** | Build & Release | Release change & security log | `CHANGELOG.md` maintained with detailed release notes and CVE tracking. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-05.01** | Build & Release | Standardized dependency tooling | `pyproject.toml`, pip hash verification in `requirements-security.lock`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-06.01** | Build & Release | Signed release or hash manifest | Release `v1.2.6` tagged with SSH signature, `SHA256SUMS` manifest, and SLSA provenance. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-DO-06.01** | Documentation | Document dependency tracking | `CONTRIBUTING.md`, Dependabot configuration, and vulnerability management policies. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-DO-07.01** | Documentation | Document build & prerequisites | Detailed build instructions in `CONTRIBUTING.md` and `RELEASING.md`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-GV-01.01** | Governance | List members with sensitive access | Documented in `MAINTAINERS.md`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-GV-01.02** | Governance | Document maintainer responsibilities | Roles, responsibilities, and access levels defined in `MAINTAINERS.md`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-GV-03.02** | Governance | Acceptable-contribution guidelines | Defined in `CONTRIBUTING.md` and `docs/CODE_REVIEW.md`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-LE-01.01** | Legal | Contributor legal assertion per commit | Developer Certificate of Origin (DCO) enforced via DCO bot workflow. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-03.01** | Quality | Status checks pass before merge | Required branch protection checks configured on GitHub `main`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-06.01** | Quality | Automated tests before acceptance | CI runs unit, integration, and security test matrix on every PR. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-SA-01.01** | Security Arch | Design documents actors & actions | Threat models, architecture blueprints, and role maps in `docs/architecture/`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-SA-02.01** | Security Arch | External-interface documentation | OpenAPI/REST schemas, MCP interface contracts documented. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-SA-03.01** | Security Arch | Security assessment performed | Documented in `compliance/INTERNAL_SECURITY_REVIEW.md`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-01.01** | Vuln Mgmt | Coordinated disclosure policy | Published in `SECURITY.md` with explicit triage and patch timelines. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-03.01** | Vuln Mgmt | Private vulnerability reporting | GitHub Private Vulnerability Reporting (PVR) enabled on repository. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-04.01** | Vuln Mgmt | Publish vulnerability data | GitHub Security Advisories + CVE publication workflow established. | `TECHNICAL REQUIREMENT` | **VERIFIED** |

---

## 4. Level 3 Control Evidence Register

| Control ID | Category | Requirement | Verifiable Repository Evidence | Classification | Status |
|---|---|---|---|---|---|
| **OSPS-AC-04.02** | Access Control | Job permissions minimum necessary | All GitHub Action jobs explicitly define localized scoped permissions. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-01.04** | Build & Release | Validate trusted collaborator inputs | Release pipeline enforces SSH signature verification against `release-signers.allowed`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-02.02** | Build & Release | Associate every asset with unique release | Artifact attestations, SLSA provenance, and checksum manifests bound to release tags. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-BR-07.02** | Build & Release | Secrets lifecycle & rotation policy | Documented in `compliance/KEY_MANAGEMENT.md` and enterprise security guides. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-DO-03.01** | Documentation | Release integrity verification guide | Documented in `docs/VERIFY_RELEASE.md` with verifiable CLI commands. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-DO-03.02** | Documentation | Verify release author identity | Author identity verification instructions and public signing keys documented. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-DO-04.01** | Documentation | Scope & duration of support | Explicitly defined in `SUPPORT.md` and `SECURITY.md`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-DO-05.01** | Documentation | State end of security updates | Documented latest-only release security update policy. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-GV-04.01** | Governance | Review collaborators before escalation | Maintainer onboarding, access grant, and revocation policy in `MAINTAINERS.md`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-02.02** | Quality | SBOM generated with compiled assets | CycloneDX v1.5 JSON SBOM generated and attested for release assets (`v1.2.6`). | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-04.02** | Quality | Multi-repo control consistency | N/A — single monolithic repository architecture. | `NOT APPLICABLE` | **NOT APPLICABLE** |
| **OSPS-QA-06.02** | Quality | Document test execution procedures | Documented in `CONTRIBUTING.md#running-tests` and test architecture guides. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-06.03** | Quality | Major changes add or update tests | Code review checklist (`docs/CODE_REVIEW.md`) and CI coverage gates enforce tests. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-QA-07.01** | Quality | One non-author human approval prior to merge | Solo maintainer project; no second human approver exists. Cannot be faked. | `HUMAN / GOVERNANCE REQUIREMENT` | **HUMAN_BLOCKED** |
| **OSPS-SA-03.02** | Security Arch | Formal threat & attack-surface model | Comprehensive threat model documented in `docs/architecture/` and compliance docs. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-04.02** | Vuln Mgmt | VEX for non-affecting vulnerabilities | OpenVEX document maintained in `security/whitepact.openvex.json`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-05.01** | Vuln Mgmt | SCA vulnerability/license thresholds | Documented in `compliance/VULNERABILITY_MANAGEMENT.md`. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-05.02** | Vuln Mgmt | Address SCA violations pre-release | Release pipeline blocks on unmitigated High/Critical CVEs. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-05.03** | Vuln Mgmt | Automatically block dependency changes | Dependency-Review and pip-audit gate CI on incoming pull requests. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-06.01** | Vuln Mgmt | SAST remediation threshold | Zero high/medium findings required; enforced via Bandit policy. | `TECHNICAL REQUIREMENT` | **VERIFIED** |
| **OSPS-VM-06.02** | Vuln Mgmt | Automatically block code weaknesses | Bandit and CodeQL scans run automatically on pull requests and pushes. | `TECHNICAL REQUIREMENT` | **VERIFIED** |

---

## 5. Formal OSPS Baseline Declaration

- **Level 1:** Officially Awarded.
- **Level 2:** Fully Satisfied; eligible for formal self-declaration.
- **Level 3:** Fully Satisfied on all technical controls, but **withheld** until `OSPS-QA-07.01` is satisfied through real human community collaboration.
