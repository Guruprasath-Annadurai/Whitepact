# WhitePact Enterprise Assurance Master Index

**Baseline reviewed:** `main@8f8ef53f0460c99115f5656dfa4d31775bca4d6a`  
**Pre-audit closure branch:** `compliance/preaudit-assurance-closure-2026-09-13`  
**Review date:** 2026-09-13  
**Owner:** WhitePact maintainer / service owner

> This is WhitePact's canonical first-party evidence index. It is designed to reduce duplicate evidence collection across enterprise questionnaires, SOC 2 readiness, ISO/IEC 27001:2022, ISO/IEC 42001:2023, CSA STAR, CSA STAR for AI, GDPR, India DPDP, EU AI Act, NIST and customer security reviews. It is **not** an external audit or certification.

## Status vocabulary

- **Implemented** — control exists in code/process and has repository evidence.
- **Partial** — meaningful control exists, but an applicable part remains open.
- **Inherited/shared** — a subprocessor/customer/provider owns part of the control; WhitePact documents the boundary.
- **Prepared** — documentation/process is ready, but external publication/certification/sign-off is pending.
- **External-only** — cannot legitimately be completed by WhitePact itself.
- **N/A** — genuinely outside WhitePact's current role/scope, with rationale.

## Canonical control families

| ID | Control family | Status | Canonical evidence | Framework reuse | External dependency |
|---|---|---|---|---|---|
| WP-01 | Governance, accountability, policy ownership | Implemented / constrained by solo-maintainer structure | `GOVERNANCE.md`, `compliance/RISK_MANAGEMENT_POLICY.md`, `compliance/REPOSITORY_GOVERNANCE.md` | SOC 2 CC1/CC2; ISO 27001 clauses 4–10; ISO 42001 clauses 4–10; CSA GRC; NIST Govern | Independent oversight remains external/organizational |
| WP-02 | Identity, authentication and access control | Implemented | RBAC/OIDC/SAML/SSO/MFA implementation; `ENTERPRISE_SECURITY.md`; CAIQ evidence | SOC 2 Security; ISO 27001 access controls; CSA IAM; GDPR Art. 32; DPDP safeguards | Live-tenant/customer configuration is shared |
| WP-03 | Tenant isolation and authorization | Implemented with exact-release revalidation required | org-scoped repositories/tests; governance gateway; audit/evidence tests | SOC 2 Security/Confidentiality; ISO 27001; CSA IAM/DSP; GDPR/DPDP safeguards | Independent pentest verification external |
| WP-04 | Runtime AI/agent governance | Implemented V1 capabilities; V2 roadmap excluded from current claims | `compliance/AI_GOVERNANCE_POLICY.md`, governance code/tests, `SPEC.md`, `DETERMINISTIC_VS_PROBABILISTIC.md` | ISO 42001; CSA AICM/AI-CAIQ; NIST AI RMF; EU AI Act technical readiness | External conformity/legal interpretation where applicable |
| WP-05 | Human approval, revocation, evidence and accountability | Implemented | approval repository, evidence repository, hash-chain verification, revocation/nonce tests | SOC 2 Processing Integrity/Security; ISO 27001 logging/access; ISO 42001 oversight; CSA logging/change controls | Exact final-release evidence required |
| WP-06 | Secure development and change control | Implemented | protected `main`, required CI, DCO, code review policy, Ruff/Mypy/tests, dependency review | SOC 2 CC8; ISO 27001 secure development/change; CSA application security | None beyond operating evidence accumulation |
| WP-07 | Software supply-chain and release integrity | Implemented | signed release-tag gate, SBOM, trusted publishing, SLSA/provenance docs, pinned actions, OpenSSF evidence | SOC 2 CC7/CC8; ISO 27001 supplier/secure development; CSA supply-chain; buyer questionnaires | External scorecard/registry results remain third-party evidence |
| WP-08 | Vulnerability management and security testing | Implemented first-party; independent assurance open | `SECURITY.md`, `compliance/VULNERABILITY_MANAGEMENT.md`, `compliance/INTERNAL_SECURITY_REVIEW.md`, security workflows, fuzzing/dynamic-analysis docs | SOC 2 CC7; ISO 27001 vulnerability management; CSA TVM; NIST Protect/Detect | Independent pentest/security review external-only |
| WP-09 | Incident response and investigation | Implemented process; real-incident history limited | `compliance/INCIDENT_RESPONSE_RUNBOOK.md`, tabletop exercise, audit/evidence controls | SOC 2 CC7; ISO 27001 incident mgmt; CSA SEF; GDPR/DPDP breach handling | Real incidents and external regulator/customer interactions cannot be fabricated |
| WP-10 | Business continuity, backup and resilience | Partial | `SLA.md`, `compliance/PROJECT_CONTINUITY_PLAN.md`, backup/restore scripts/evidence | SOC 2 Availability; ISO 27001 continuity; CSA BCR | Cross-region/HA proof and production operating evidence remain open |
| WP-11 | Privacy, data minimization, retention and subprocessors | Partial / documented | `PRIVACY_POLICY.md`, `compliance/DPA_TEMPLATE.md`, vendor-risk assessment, retention mechanisms | SOC 2 Privacy/Confidentiality; ISO 27001 privacy/security; GDPR; DPDP; CSA DSP | Counsel review external; automated retention must match adopted policy |
| WP-12 | Key/secrets/cryptographic management | Implemented with operational-evidence limits | `compliance/KEY_MANAGEMENT.md`, field encryption, secret scanning, CI secrets policy | SOC 2 Security/Confidentiality; ISO 27001 cryptography; CSA CEK | Real production rotation exercise should be retained as operating evidence |
| WP-13 | Vendor and subprocessor risk | Implemented process / inherited controls | `compliance/VENDOR_RISK_ASSESSMENT.md`, DPA subprocessor list, provider trust docs | SOC 2 CC9; ISO 27001 supplier relationships; CSA supply chain; GDPR processor diligence | Provider certifications are not WhitePact certifications |
| WP-14 | AI inventory, risk and impact governance | Implemented first-party process | `compliance/AI_GOVERNANCE_POLICY.md`, `compliance/RISK_MANAGEMENT_POLICY.md`, `compliance/ISO_42001_AIMS_READINESS.md` | ISO 42001; CSA AICM/AI-CAIQ; NIST AI RMF; EU AI Act readiness | External certification/legal opinion remains external |
| WP-15 | Regulatory and customer transparency | Prepared / partial | public trust claims, privacy policy, framework mappings, trust-status docs | CSA STAR; STAR for AI; GDPR/DPDP transparency; EU AI Act transparency | Registry publication, legal review, external certifications |

## Framework map

### SOC 2 readiness

Primary evidence: `compliance/SOC2_READINESS.md`, `compliance/SOC2_READINESS_ADDENDUM_2026-09-13.md`, WP-01 through WP-13 above.

Internal work can complete control design, policy, mapping, evidence indexing and operating procedures. A SOC 2 report itself requires an independent qualified CPA/audit firm and, for Type II, an observation period of operating evidence.

### ISO/IEC 27001:2022 readiness

Primary evidence: `compliance/ISO_27001_ISMS_READINESS.md`, risk policy, incident response, continuity, vendor risk, key management, repository/security evidence.

Internal work can establish the ISMS scope, risk method, objectives, Statement-of-Applicability-style mapping, internal review inputs and evidence index. Certification requires an accredited external certification body.

### ISO/IEC 42001:2023 readiness

Primary evidence: `compliance/ISO_42001_AIMS_READINESS.md`, `compliance/AI_GOVERNANCE_POLICY.md`, AI inventory and AI risk register.

Internal work can establish and operate the AIMS. Certification requires an external certification body.

### CSA STAR Level 1 / STAR for AI Level 1

Primary evidence: CAIQ, CAIQ evidence boundary, CSA readiness pack, AI governance policy, risk policy and AI-CAIQ preparation.

Level 1 is a self-assessment pathway, but WhitePact may not claim registry status until CSA accepts/publishes the submission.

### GDPR / India DPDP / EU AI Act

Primary evidence: `PRIVACY_POLICY.md`, `compliance/DPA_TEMPLATE.md`, incident response, vendor risk, AI governance policy and `compliance/PRIVACY_REGULATORY_READINESS_2026-09-13.md`.

These are legal/regulatory regimes, not purchasable certifications. WhitePact can implement technical/organizational readiness internally; definitive legal advice and any regulator/court determination remain external.

## Exact-release evidence rule

No enterprise launch claim may rely solely on branch-level evidence. Before V1 enterprise launch:

1. Freeze the candidate release SHA.
2. Re-run the mandatory CI/security/regression suite on that exact SHA.
3. Bind the release artifact/SBOM/provenance to that SHA.
4. Capture deployment/health/backup/restore/rotation/revocation evidence against that release.
5. Update this index from **prepared** to **release-verified** only where evidence exists.

## Public claim boundaries

WhitePact may accurately say it has implemented controls, published mappings, completed internal self-assessments, prepared audit/certification evidence, and adopted management-system policies when true.

WhitePact must not say it is SOC 2 audited, ISO certified, independently penetration tested, attorney-certified, CSA STAR listed, or STAR for AI listed until the relevant independent or registry evidence exists.