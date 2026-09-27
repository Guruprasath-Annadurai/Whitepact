# WhitePact CSA STAR + STAR for AI Submission Readiness — 2026-09-13

**Status:** First-party submission-readiness package; no registry status claimed  
**Owner:** WhitePact maintainer / service owner  
**Review date:** 2026-09-13

## Current official pathways

### CSA STAR Level 1

CSA STAR Level 1 is a self-assessment pathway based on CSA's Cloud Controls Matrix / CAIQ materials and publication in the STAR Registry. WhitePact may prepare and submit its own assessment; no paid independent auditor is required for Level 1.

WhitePact currently has a historical completed CAIQ v4.0.3 workbook and extensive supporting evidence. Because CSA's current registry/resources in 2026 include newer CAIQ-Lite/CAIQ v4.1.x materials, the final submission must use the current workbook/version accepted by CSA at submission time rather than assuming the historical v4.0.3 file remains the preferred current format.

### CSA STAR for AI Level 1

CSA STAR for AI Level 1 is the self-assessment pathway based on the AI Controls Matrix (AICM) and AI-CAIQ. CSA's current 2026 AICM v1.1 materials include AI-CAIQ and mappings to ISO/IEC 42001, the EU AI Act and NIST AI RMF. Publication/acceptance in the STAR Registry is the event that permits WhitePact to claim the corresponding Level 1 listing.

Official references:

- https://cloudsecurityalliance.org/star
- https://cloudsecurityalliance.org/star/ai
- https://cloudsecurityalliance.org/artifacts/ai-controls-matrix-v1-1

## WhitePact role/scope for assessment

WhitePact is primarily an AI application/orchestration governance and runtime assurance provider. It does not currently train or distribute its own foundation-model weights. Depending on exact CSA role taxonomy in the current workbook, WhitePact should map most closely to application/orchestration/service-provider roles rather than a foundation-model developer for controls that presuppose ownership of model pre-training, training datasets or base-model weights.

N/A responses must be narrowly justified. They must never be used to avoid an applicable control merely because WhitePact is small.

## Evidence already available

- `compliance/CAIQ_SELF_ASSESSMENT.md`
- `compliance/CAIQ_EVIDENCE_BOUNDARY.md`
- `compliance/CAIQv4.0.3_WhitePact_completed.xlsx` (historical baseline; update to current accepted format before final submission)
- `compliance/AI_GOVERNANCE_POLICY.md`
- `compliance/RISK_MANAGEMENT_POLICY.md`
- `compliance/ENTERPRISE_ASSURANCE_MASTER_INDEX.md`
- `compliance/ISO_42001_AIMS_READINESS.md`
- `compliance/NIST_AI_RMF_MAPPING.md`
- `compliance/EU_AI_ACT_TECHNICAL_MAPPING.md`
- `compliance/OWASP_AI_AGENT_SECURITY_MAPPING.md`
- `compliance/INTERNAL_SECURITY_REVIEW.md`
- `compliance/VULNERABILITY_MANAGEMENT.md`
- `compliance/INCIDENT_RESPONSE_RUNBOOK.md`
- `compliance/VENDOR_RISK_ASSESSMENT.md`
- `compliance/PROJECT_CONTINUITY_PLAN.md`
- `compliance/KEY_MANAGEMENT.md`
- OpenSSF/SLSA/SBOM/release-provenance evidence
- protected-branch and mandatory-CI evidence

## Final submission checklist — STAR Level 1

- [x] Security/control evidence inventory exists.
- [x] CAIQ self-assessment evidence exists.
- [x] Known limitations are documented rather than silently marked Yes.
- [x] Vendor/shared-responsibility boundaries are documented.
- [x] Risk-management policy exists.
- [x] Incident-response and continuity evidence exists.
- [x] Public claim boundaries exist.
- [ ] Obtain/download the current CSA-approved CAIQ/CAIQ-Lite workbook at actual submission time.
- [ ] Transfer/reconcile answers from the historical v4.0.3 baseline into that current workbook.
- [ ] Verify applicant legal/organizational identity and organizational-domain email requirements.
- [ ] Authorized representative reviews and signs/attests to the self-assessment where required.
- [ ] Upload through the authenticated CSA submission workflow.
- [ ] Wait for CSA acceptance/publication and record the registry URL/date.

The unchecked items are owner/registry actions rather than paid-auditor work.

## Final submission checklist — STAR for AI Level 1

- [x] AI governance policy exists.
- [x] AI system inventory exists.
- [x] AI risk and impact-assessment triggers exist.
- [x] Human-oversight and agent/tool boundary policy exists.
- [x] AI incident process exists.
- [x] NIST AI RMF / EU AI Act / ISO 42001 support mappings exist.
- [x] Model-provider/customer shared-responsibility boundaries are documented.
- [ ] Obtain the current AI-CAIQ/AICM workbook/package accepted by CSA at submission time.
- [ ] Complete/reconcile the AI-CAIQ against exact current WhitePact evidence.
- [ ] Review role applicability and N/A rationales against the current AICM role taxonomy.
- [ ] Authorized representative signs/attests where required.
- [ ] Submit through CSA's authenticated STAR for AI workflow.
- [ ] Wait for CSA acceptance/publication and record the registry URL/date.

## Answering rules

For both assessments:

- **Yes** only when an implemented or genuinely inherited/shared control has evidence.
- **No** when an applicable control is absent.
- **N/A** only when genuinely outside WhitePact's present role/scope, with rationale.
- A roadmap item is never evidence for Yes.
- A provider's SOC/ISO certificate is never WhitePact's certificate.
- Internal security scans are never called an independent pentest.
- Governance approval/gating is never automatically called OS/container sandboxing.
- Exact-release evidence should replace branch-only evidence before final enterprise launch claims.

## Previous submission history

Earlier WhitePact CSA materials recorded submission/rejection friction related to applicant/organizational-domain identity. That history must be treated as a workflow lesson, not as current registry status. Before resubmission, verify the organizational email and applicant identity requirements in the live CSA portal.

## Claim boundary

Before registry publication, WhitePact may say:

- **"CSA STAR Level 1 self-assessment prepared / submission-ready"** when the current workbook is complete.
- **"STAR for AI Level 1 AI-CAIQ prepared / submission-ready"** when the current AI-CAIQ is complete.

WhitePact must not say **"CSA certified"**, **"STAR listed"**, **"STAR for AI listed"**, **"independently audited"**, or equivalent until the relevant registry/publication evidence actually exists.
