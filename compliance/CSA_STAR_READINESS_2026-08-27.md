# WhitePact — CSA STAR Level 1 + STAR for AI Level 1 Readiness Review

**Review date:** 2026-08-27  
**Repository:** `Guruprasath-Annadurai/Whitepact`  
**Target:** CSA STAR Level 1 using CAIQ-Lite v4.1.0, plus STAR for AI Level 1 using AI-CAIQ v1.1  
**Assessment type:** First-party self-assessment/readiness review. Not an independent audit.

## Executive conclusion

WhitePact has substantial technical evidence for a first-party CSA STAR submission: vulnerability disclosure, automated security scanning, dependency review, secret scanning, OpenSSF Scorecard, signed-release gating, SBOM generation, GitHub build provenance, RBAC, SSO/MFA, tenant isolation, hash-chained audit evidence, incident-response documentation, vendor-risk documentation, continuity/DR evidence, and explicit limitations.

The repository is materially stronger than a typical pre-revenue/solo-maintainer project, but it is **not** independently audited. A CSA Level 1 submission must retain honest `No`/`N/A` answers where controls are absent or out of scope.

The recommended cloud-security path is **CAIQ-Lite v4.1.0** because CSA explicitly accepts CCM/CAIQ-Lite submissions into the STAR Registry and the Lite assessment is intended for smaller/resource-constrained organizations. The AI path is the current **AI-CAIQ v1.1** self-assessment.

## Scope statement

WhitePact is an AI governance/runtime assurance platform with an API/dashboard, MCP and agent integration surfaces, guardrails, trust/evaluation functions, multi-tenant persistence, and a hosted reference deployment. It is primarily an AI application/orchestration governance provider, not a foundation-model provider.

The reference deployment currently relies on managed third parties including Render, Supabase, and Upstash. Provider certifications do not become WhitePact certifications; inherited infrastructure controls must be described as shared/third-party controls.

## Evidence already present

| Area | Evidence | Assessment |
|---|---|---|
| Vulnerability disclosure | `SECURITY.md` | Strong |
| Application security testing | `.github/workflows/security-scan.yml`, Bandit, pip-audit | Strong first-party evidence |
| Dependency/security review | dependency-review, Gitleaks, security workflows | Strong |
| Source ownership/review | `.github/CODEOWNERS`, PR template | Good; branch protection itself remains unverified through connected API |
| Supply chain | signed release-tag gate, trusted PyPI publishing, CycloneDX SBOM, GitHub build provenance | Strong |
| Internal security review | `compliance/INTERNAL_SECURITY_REVIEW.md` | Strong self-review; explicitly not a pentest |
| Identity/access | RBAC, OIDC/SAML, SSO enforcement, TOTP MFA | Strong |
| Multi-tenancy | org-scoped repositories/data | Strong documented implementation |
| Auditability | hash-chained audit log, verification/export endpoints | Strong with documented limitations |
| Vendor risk | `compliance/VENDOR_RISK_ASSESSMENT.md` | Good; cadence gap addressed by new risk policy |
| Incident response | `compliance/INCIDENT_RESPONSE_RUNBOOK.md` and tabletop evidence | Good |
| Continuity/DR | SLA, backup/restore scripts, project continuity evidence | Good for current stage; single-region/free-tier residual risk remains |
| Data protection | key-management documentation, optional field encryption, infra-level encryption for reference deployment | Mixed/shared; app does not universally enforce at-rest encryption |
| Independent assurance | None | Open gap; must be answered honestly |
| AI governance | Product-level controls existed; dedicated AICM governance policy added in this branch | Improved on merge |
| Formal risk cadence | Previously informal | Formal quarterly/change-triggered policy added in this branch |

## Material findings

### 1. Independent assurance remains absent

WhitePact has a serious internal security review and recurring automated scans, but no independent penetration test, SOC 2 report, ISO 27001 certificate, or other independent annual assurance. This is an acceptable disclosure in Level 1 self-assessment; it must not be converted into a false `Yes` for independent-audit questions.

### 2. Branch protection is unverified, not proven absent

The connected GitHub integration returned `403 Resource not accessible by integration` for classic branch-protection inspection. Repository rulesets visible through the integration were empty. Therefore the assessment must state **classic protection not independently verified during this review** rather than claiming either protected or unprotected.

### 3. Formal risk cadence was a real governance gap

Existing self-assessment and vendor-risk documents admitted that risk review was informal/opportunistic. `compliance/RISK_MANAGEMENT_POLICY.md` in this branch establishes a real quarterly and significant-change cadence plus an initial risk register. This becomes operating evidence when approved/merged and followed.

### 4. AI scope must be precise

WhitePact governs/evaluates AI and agents, but does not currently train a foundation model. Model-training, model-weight, and training-dataset controls that presuppose WhitePact owns such assets should normally be `N/A` with scope rationale, not fabricated `Yes` answers.

### 5. Agent governance is not identical to sandbox isolation

WhitePact has governance outcomes, approval gates, authentication/authorization, auditability and tool-integration controls. Those do not by themselves prove that every third-party tool/plugin executes inside a hardened OS/container sandbox. AI-CAIQ sandbox questions must reflect the actual integration architecture.

### 6. Reference deployment resilience is intentionally limited

The current free-tier reference deployment does not have cross-region failover. This is documented rather than hidden. BCR/resilience answers must distinguish existing backup/recovery procedures from unavailable HA/redundancy.

## Submission-answer rules

Every CAIQ/AI-CAIQ answer must follow these rules:

1. `Yes` only when a currently implemented control or inherited/shared control is evidenced.
2. `No` when the control applies but is not implemented.
3. `N/A` only where the control is genuinely outside WhitePact's role/service scope, with a written rationale.
4. Third-party certifications must be attributed to the provider; never imply they certify WhitePact.
5. Self-conducted testing must never be described as independent.
6. Future roadmap items are not current controls.
7. Product features that map customers to NIST/ISO/EU AI Act frameworks must not be conflated with WhitePact's own organizational certification.

## High-confidence answer themes

### Likely `Yes` / implemented

- vulnerability-disclosure process;
- automated application/dependency/security testing;
- API input validation and API-key handling;
- role-based access control and tenant isolation;
- SSO and MFA capability;
- security event/audit evidence and export/verification;
- source version control and release provenance;
- SBOM generation for releases;
- incident-response documentation;
- vendor-risk review;
- secure webhook URL validation / SSRF protections;
- data-retention mechanisms and PII guardrail capability;
- AI governance decision outcomes including allow/redact/approval/deny/quarantine where implemented;
- human-approval workflow capability;
- AI input/output governance and privacy controls where enabled.

### `No` / open or unverified

- independent annual audit/assurance;
- independent penetration test;
- cross-region reference-deployment redundancy;
- universal application-layer encryption at rest;
- verified branch-protection configuration through this review channel;
- blanket sandbox isolation for every external agent tool/plugin.

### Common `N/A` for WhitePact's present role

Subject to question wording and final applicant scope:

- physical datacenter operations owned by managed infrastructure providers;
- WhitePact-owned foundation-model pre-training controls;
- protection/rotation of WhitePact-owned foundation model weights when no such weights exist;
- training-dataset poisoning/provenance controls where WhitePact does not train the model;
- customer-selected LLM-provider controls where the customer owns the provider relationship, except for WhitePact's integration boundary.

## Evidence improvements created in this work

- `compliance/RISK_MANAGEMENT_POLICY.md`
- `compliance/AI_GOVERNANCE_POLICY.md`
- this readiness review

These documents intentionally close policy/process gaps without inventing historical evidence. Controls requiring evidence over time must be demonstrated by actually following the stated cadence after adoption.

## Final status

| Target | Readiness state | What remains outside repository work |
|---|---|---|
| CSA STAR Level 1 — CAIQ-Lite v4.1.0 | **Submission-preparation ready with disclosed gaps** | Complete official CAIQ-Lite workbook, applicant identity fields, legal attestation, CSA account upload/publication |
| CSA STAR for AI Level 1 — AI-CAIQ v1.1 | **Submission-preparation ready with disclosed gaps** | Complete official AI-CAIQ workbook, applicant identity fields, legal attestation, CSA account upload/publication |

**Important:** Until CSA publishes the assessments in the STAR Registry, WhitePact must not claim it “has CSA STAR Level 1” or “has STAR for AI Level 1.” It may accurately state that it is preparing/completing the corresponding self-assessments.
