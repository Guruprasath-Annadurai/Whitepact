# OSPS Baseline Current Audit

Normative version: **2026.08.28** (current official checklist retrieved 2026-08-30).
Official BadgeApp status at audit time: **Level 1 awarded; Level 2 95%; Level 3 0%**.
Repository status below is a self-audit and does not change that award.

## Level 1

| Control ID | Level | Requirement | Evidence | Status | Action taken | Blocker |
|---|---:|---|---|---|---|---|
| OSPS-AC-01.01 | 1 | MFA for sensitive repository access | BadgeApp L1; GitHub account criterion | VERIFIED | Preserved | Account evidence remains owner-controlled |
| OSPS-AC-02.01 | 1 | least privilege for new collaborators | GitHub permission assignment; one collaborator | VERIFIED | Honest roles recorded | None |
| OSPS-AC-03.01 | 1 | prevent direct primary-branch commits | classic main protection requires PR/checks | VERIFIED | API evidence recorded | None |
| OSPS-AC-03.02 | 1 | protect primary branch deletion | deletion disabled | VERIFIED | API evidence recorded | None |
| OSPS-BR-01.01 | 1 | validate untrusted pipeline metadata | no dangerous interpolation/`pull_request_target` | VERIFIED | regression guard added | Future workflow review |
| OSPS-BR-01.03 | 1 | isolate untrusted code from privileged CI assets | read-only PR jobs; publish separated | VERIFIED | permission audit retained | None |
| OSPS-BR-03.01 | 1 | encrypted official project channels | GitHub/PyPI/website HTTPS | VERIFIED | live site checked | None |
| OSPS-BR-03.02 | 1 | authenticated encrypted distribution | PyPI/GitHub HTTPS and release verification | VERIFIED | preserved | None |
| OSPS-BR-07.01 | 1 | prevent unencrypted secrets in VCS | Gitleaks, GitHub secret scanning/push protection | VERIFIED | settings checked | Optional non-provider patterns disabled |
| OSPS-DO-01.01 | 1 | basic user guides | README/docs/quickstart | VERIFIED | preserved | None |
| OSPS-DO-02.01 | 1 | defect-reporting guide | SUPPORT, CONTRIBUTING | VERIFIED | SUPPORT added | None |
| OSPS-GV-02.01 | 1 | public discussion mechanisms | GitHub issues/PRs | VERIFIED | route documented | None |
| OSPS-GV-03.01 | 1 | contribution process | CONTRIBUTING | VERIFIED | preserved | None |
| OSPS-LE-02.01 | 1 | source has open-source license | MIT/OSI | VERIFIED | preserved | None |
| OSPS-LE-02.02 | 1 | released assets use open-source license | wheel/sdist includes MIT metadata | VERIFIED | build checks preserved | None |
| OSPS-LE-03.01 | 1 | repository license file | LICENSE | VERIFIED | preserved | None |
| OSPS-LE-03.02 | 1 | license accompanies releases | build metadata/source archive | VERIFIED | preserved | None |
| OSPS-QA-01.01 | 1 | public static source URL | public GitHub repository | VERIFIED | preserved | None |
| OSPS-QA-01.02 | 1 | public attributable change history | Git history | VERIFIED | preserved | None |
| OSPS-QA-02.01 | 1 | direct dependency list | pyproject.toml | VERIFIED | preserved | None |
| OSPS-QA-04.01 | 1 | list project repositories if multiple | single authoritative repository | NOT APPLICABLE | scope recorded | None |
| OSPS-QA-05.01 | 1 | no generated executables in VCS | Scorecard Binary-Artifacts 10 | VERIFIED | preserved | None |
| OSPS-QA-05.02 | 1 | no unreviewable binaries | source inventory/Scorecard | VERIFIED | preserved | None |
| OSPS-VM-02.01 | 1 | publish security contacts | SECURITY.md | VERIFIED | private route added | None |

## Level 2

| Control ID | Level | Requirement | Evidence | Status | Action taken | Blocker |
|---|---:|---|---|---|---|---|
| OSPS-AC-04.01 | 2 | default CI permissions least privilege | top-level `contents: read`; scoped jobs | TECHNICALLY READY | PR #52 hardening retained | Merge and official reassessment |
| OSPS-BR-02.01 | 2 | unique release identifiers | SemVer tags/releases | VERIFIED | preserved | None |
| OSPS-BR-04.01 | 2 | release change/security log | CHANGELOG/release workflow | VERIFIED | preserved | None |
| OSPS-BR-05.01 | 2 | standardized dependency tooling | pip/pyproject/npm/Actions | VERIFIED | security lock added | None |
| OSPS-BR-06.01 | 2 | signed release or signed hash manifest | signed tags, GitHub attestations/digests | PENDING RELEASE VERIFICATION | preserved | New hardened release must be verified |
| OSPS-DO-06.01 | 2 | document dependency selection/tracking | CONTRIBUTING, Dependabot, vulnerability policy | VERIFIED | process consolidated | None |
| OSPS-DO-07.01 | 2 | document build and prerequisites | CONTRIBUTING/RELEASING/pyproject | VERIFIED | preserved | None |
| OSPS-GV-01.01 | 2 | list members with sensitive access | MAINTAINERS | VERIFIED | created honest list | None |
| OSPS-GV-01.02 | 2 | document roles/responsibilities | MAINTAINERS/GOVERNANCE | VERIFIED | roles clarified | None |
| OSPS-GV-03.02 | 2 | acceptable-contribution guide | CONTRIBUTING/CODE_REVIEW | VERIFIED | preserved | None |
| OSPS-LE-01.01 | 2 | contributor legal assertion each commit | DCO workflow | VERIFIED | policy guard retained | None |
| OSPS-QA-03.01 | 2 | status checks pass or explicit bypass | strict required checks | VERIFIED | API evidence recorded | Bypass audit is GitHub-side |
| OSPS-QA-06.01 | 2 | automated tests before acceptance | required CI matrix | VERIFIED | preserved | None |
| OSPS-SA-01.01 | 2 | design documents actors/actions | SPEC, runtime map, threat model | VERIFIED | threat model expanded | None |
| OSPS-SA-02.01 | 2 | external-interface documentation | MCP/HTTP/SDK docs and schemas | VERIFIED | preserved | Provider live compatibility is separate |
| OSPS-SA-03.01 | 2 | security assessment | INTERNAL_SECURITY_REVIEW | VERIFIED (internal) | current evidence added | Not independent |
| OSPS-VM-01.01 | 2 | coordinated disclosure/timeframe | SECURITY.md | VERIFIED | advisory process expanded | None |
| OSPS-VM-03.01 | 2 | private reporting | GitHub PVR enabled + email | VERIFIED | API/settings checked | None |
| OSPS-VM-04.01 | 2 | publish discovered-vulnerability data | advisories/changelog/security policy | TECHNICALLY READY | publication process documented | No project advisory has yet required publication |

## Level 3

| Control ID | Level | Requirement | Evidence | Status | Action taken | Blocker |
|---|---:|---|---|---|---|---|
| OSPS-AC-04.02 | 3 | job permissions are minimum necessary | workflow permission audit | TECHNICALLY READY | PR #52 + regression guard | Merge/rescan |
| OSPS-BR-01.04 | 3 | validate trusted collaborator pipeline input | release tag/signer/version checks | TECHNICALLY READY | dangerous-workflow review documented | Release verification |
| OSPS-BR-02.02 | 3 | associate every asset with unique release | versioned wheel/sdist/release/SBOM | PENDING RELEASE VERIFICATION | preserved | Next release |
| OSPS-BR-07.02 | 3 | secrets lifecycle policy | ENTERPRISE_SECURITY, KEY_MANAGEMENT, incident runbook | VERIFIED | routes cross-referenced | Hosted rotation evidence is deployment-specific |
| OSPS-DO-03.01 | 3 | integrity/authenticity verification instructions | docs/VERIFY_RELEASE.md on SLSA branch; RELEASING | PENDING RELEASE VERIFICATION | no SLSA duplication | Merge SLSA work and release |
| OSPS-DO-03.02 | 3 | verify release author identity | signed tag/signer allow-list docs | VERIFIED | preserved | Consumer must execute verification |
| OSPS-DO-04.01 | 3 | scope/duration of support | SUPPORT/SECURITY | VERIFIED | created | None |
| OSPS-DO-05.01 | 3 | state end of security updates | SUPPORT/SECURITY | VERIFIED | clarified latest-only model | None |
| OSPS-GV-04.01 | 3 | review collaborators before escalation | MAINTAINERS process | VERIFIED | explicit grant/removal process added | Actual future decisions require evidence |
| OSPS-QA-02.02 | 3 | SBOM with compiled release assets | CycloneDX release output | PENDING RELEASE VERIFICATION | preserved | Next hardened release |
| OSPS-QA-04.02 | 3 | consistent controls across multiple repos | single-repository scope | NOT APPLICABLE | scope recorded | Reassess if split |
| OSPS-QA-06.02 | 3 | document test execution | CONTRIBUTING and workflows | VERIFIED | preserved | None |
| OSPS-QA-06.03 | 3 | major changes add/update tests | CONTRIBUTING/CODE_REVIEW | VERIFIED | regression guard added | Human enforcement plus CI |
| OSPS-QA-07.01 | 3 | one non-author human approval | approval count 0; sole maintainer | HUMAN MATURITY BLOCKER | no synthetic reviewer | Genuine second reviewer and enforced history |
| OSPS-SA-03.02 | 3 | threat/attack-surface analysis | SECURITY_THREAT_MODEL | TECHNICALLY READY | comprehensive model added | Independent validation absent |
| OSPS-VM-04.02 | 3 | VEX for non-affecting component vulnerabilities | `security/whitepact.openvex.json` | TECHNICALLY READY | NLTK exception encoded | Validate/publish and revisit upstream fix |
| OSPS-VM-05.01 | 3 | SCA vulnerability/license threshold policy | VULNERABILITY_MANAGEMENT + dependency review | VERIFIED | thresholds recorded | None |
| OSPS-VM-05.02 | 3 | address SCA violations pre-release | vulnerability release rules | VERIFIED | blocking rule documented | Operational adherence evidence per release |
| OSPS-VM-05.03 | 3 | automatically evaluate/block dependency changes | Dependency Review, pip-audit, explicit exception | TECHNICALLY READY | scanner install hash-locked | Merge and required-check owner action |
| OSPS-VM-06.01 | 3 | SAST remediation threshold | Bandit `-ll` + policy | VERIFIED | threshold documented | None |
| OSPS-VM-06.02 | 3 | automatically evaluate/block code weaknesses | PR/main/weekly Bandit | TECHNICALLY READY | PR trigger added | Add as required check after merge |

## Claim boundary

WhitePact may claim the **officially awarded OSPS Baseline Level 1** only. It may say it
has implemented or is technically ready for named higher-level controls with links to
evidence, but not that Level 2 or Level 3 is achieved. Level 3 cannot be achieved while
QA-07.01 lacks genuine non-author approval. Release-dependent rows must be demonstrated
on the exact published release.
