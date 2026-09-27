# WhitePact ISO/IEC 27001:2022 ISMS Readiness Pack

**Status:** First-party implementation/readiness evidence; not certification  
**Standard target:** ISO/IEC 27001:2022 (including awareness that Amendment 1:2024 exists)  
**Review date:** 2026-09-13  
**Owner:** WhitePact maintainer / service owner

> ISO/IEC 27001:2022 defines requirements for an information security management system (ISMS). WhitePact can establish and operate the ISMS internally; only an accredited external certification body can issue certification.

Official reference: https://www.iso.org/standard/27001

## 1. ISMS scope

The WhitePact ISMS scope covers:

- WhitePact source code and repository governance.
- Build, test, release and software supply-chain processes.
- Provider-operated reference/hosted services where WhitePact is the operator.
- Administrative dashboard, REST/API and MCP/agent integration surfaces.
- Authentication, authorization, approval, audit/evidence and tenant-isolation controls.
- Security/privacy-relevant configuration, secrets and cryptographic keys.
- Operational monitoring, incident response, continuity and backup/restore processes.
- Third-party infrastructure and service-provider relationships that materially affect WhitePact security.

Customer-operated self-hosted environments are outside WhitePact's direct operational control except for the software/security design and documented shared-responsibility boundary.

## 2. Organizational context and interested parties

| Interested party | Relevant needs / obligations |
|---|---|
| Enterprise customers | Confidentiality, integrity, availability, access control, evidence, incident response, vendor assurance |
| Developers/integrators | Secure releases, documented interfaces, predictable governance behavior, vulnerability disclosure |
| End users/data subjects | Appropriate privacy, minimization, security and rights handling where WhitePact is controller/processor |
| Maintainer/service owner | Sustainable operation, secure development, risk visibility, continuity |
| Infrastructure/subprocessors | Clear responsibility boundaries, secure credentials, supported configurations |
| Regulators/contracts | Applicable privacy/security duties and accurate public claims |
| Auditors/certification bodies | Traceable evidence and honest control boundaries |

The current solo-maintainer concentration of duties is explicitly treated as a residual risk, not hidden by documentation.

## 3. Information security policy objectives

WhitePact adopts the following measurable objectives:

1. No knowingly exploitable Critical security finding may be released without explicit documented risk acceptance and containment rationale.
2. Protected `main` requires mandatory status checks and signed-off changes according to repository policy.
3. Security/dependency/secret scanning remains active in CI and recurring workflows.
4. Material incidents follow the documented incident-response process and preserve evidence.
5. Material vendors and subprocessors are reviewed at least annually and on significant change; higher-risk changes trigger immediate review.
6. The risk register is reviewed at least quarterly and on significant architecture/vendor/regulatory change.
7. Enterprise release claims are bound to exact-SHA evidence, SBOM and provenance.
8. Security/privacy evidence never requires committing secrets or customer-sensitive incident data.

## 4. Risk assessment and treatment

Canonical risk method: `compliance/RISK_MANAGEMENT_POLICY.md`.

Each material risk records asset/process, threat/failure mode, likelihood, impact, inherent risk, controls, residual risk, treatment, owner, target date/status and review date.

Current high-priority residual risks include independent-assurance absence, resilience/cross-region limitations, prompt-injection/agent-abuse risk, evidence drift from final release, and solo-maintainer continuity/separation of duties.

## 5. Statement-of-Applicability-style control map

This is a readiness control map, not a substitute for the licensed text of ISO/IEC 27001 or ISO/IEC 27002 and not an external auditor's Statement of Applicability.

| Control domain | Applicability | WhitePact evidence | Current state |
|---|---|---|---|
| Information-security governance and policies | Applicable | `GOVERNANCE.md`, risk policy, repository governance | Implemented first-party |
| Roles/responsibilities and segregation | Applicable | governance/risk docs; branch protection; CODEOWNERS/process | Partial due solo-maintainer concentration |
| Asset/information inventory | Applicable | repository, AI inventory, vendor/subprocessor inventory | Implemented / continuously maintained |
| Access control and identity | Applicable | RBAC, OIDC/SAML, SSO/MFA, API-key controls | Implemented |
| Cryptography/key management | Applicable | `compliance/KEY_MANAGEMENT.md`, field encryption, secrets controls | Implemented design; operating evidence continues |
| Secure development/change management | Applicable | protected branch, CI, DCO, code review, tests, dependency review | Implemented |
| Vulnerability management | Applicable | security scans, dependency audit, Gitleaks, vulnerability policy | Implemented first-party; independent pentest open |
| Logging/monitoring/evidence | Applicable | hash-chained audit/evidence, metrics, verification/export | Implemented with documented limitations |
| Backup/continuity/recovery | Applicable | SLA, continuity plan, backup/restore scripts/evidence | Partial; HA/cross-region proof open |
| Incident management | Applicable | incident runbook + tabletop exercise | Implemented process; real-incident evidence accumulates over time |
| Supplier/subprocessor security | Applicable | vendor risk assessment, DPA/subprocessor list | Implemented process / inherited controls |
| Privacy and data protection | Applicable | privacy policy, DPA, PII controls, retention commitments | Partial; counsel review and retention automation/evidence need closure |
| Physical/datacenter security | Shared/inherited | cloud-provider controls | WhitePact does not operate its own datacenter |
| Personnel lifecycle/security training | Limited current applicability | solo-maintainer governance | Must expand before team growth |

## 6. Documented procedures and evidence set

Canonical evidence includes:

- `SECURITY.md`
- `ENTERPRISE_SECURITY.md`
- `GOVERNANCE.md`
- `PRIVACY_POLICY.md`
- `SLA.md`
- `compliance/RISK_MANAGEMENT_POLICY.md`
- `compliance/VULNERABILITY_MANAGEMENT.md`
- `compliance/INCIDENT_RESPONSE_RUNBOOK.md`
- `compliance/PROJECT_CONTINUITY_PLAN.md`
- `compliance/VENDOR_RISK_ASSESSMENT.md`
- `compliance/KEY_MANAGEMENT.md`
- `compliance/REPOSITORY_GOVERNANCE.md`
- OpenSSF/SLSA/SBOM/release evidence
- CI workflow history and exact-release test results

## 7. Internal audit readiness

Before external certification, WhitePact can conduct a documented first-party internal review against this scope. Because the current maintainer owns the controls being reviewed, that self-review is useful readiness evidence but weak separation of duties. A future independent internal auditor/advisor or certification-body Stage 1 review should validate the scope and findings.

Internal review should verify:

- policies are current and approved;
- risk register entries have owners/treatment/status;
- mandatory CI/security checks still enforce intended controls;
- access lists/keys are reviewed;
- backup restoration and key rotation have current evidence;
- incidents/findings are closed or accepted with rationale;
- vendor/subprocessor inventory matches reality;
- public trust claims match actual assurance state.

## 8. Management review inputs

At least annually, and before a certification engagement, management review should record:

- changes in context/interested parties;
- security incidents and near-misses;
- vulnerability/pentest/audit findings;
- risk-treatment status;
- security objective performance;
- vendor/subprocessor changes;
- continuity/restore/rotation exercises;
- customer security requirements;
- legal/regulatory changes;
- resourcing/separation-of-duties needs;
- improvement decisions and owners.

## 9. Certification blockers that remain genuinely external or operational

1. Accredited certification-body engagement and audit.
2. Stronger independent oversight/separation of duties as the organization grows.
3. Continued operating evidence from the final enterprise release and hosted environment.
4. Independent penetration/security review.
5. Closure/proof for any current operational gaps such as cross-region resilience or retention automation where applicable to scope.

## 10. Claim boundary

Allowed now: **"WhitePact has implemented an ISO/IEC 27001:2022-aligned ISMS readiness structure and first-party control evidence."**

Not allowed without external certificate: **"WhitePact is ISO/IEC 27001 certified."**
