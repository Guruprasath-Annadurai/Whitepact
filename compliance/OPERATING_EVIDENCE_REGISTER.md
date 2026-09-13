# WhitePact Operating Evidence Register

**Status:** Active first-party evidence collection register  
**Start date:** 2026-09-13  
**Owner:** WhitePact maintainer / service owner

## Purpose

Define what operating evidence WhitePact should retain from real operations so future SOC 2, ISO, CSA, enterprise-security and customer reviews can verify control operation without reconstructing history later.

> Do not create fake historical tickets, reviews, incidents or approvals. If an event did not occur during a period, record that no event occurred and retain evidence that the monitoring/process remained active.

## Evidence handling rules

- Never commit customer secrets, raw credentials, confidential incident payloads or unnecessary personal data merely for audit evidence.
- Prefer metadata, redacted exports, hashes, CI URLs/IDs, dates and attestations over sensitive raw content.
- Evidence must identify the period, system/release, reviewer/owner and outcome.
- High-risk exceptions require explicit risk acceptance.
- Evidence tied to a software release should record the exact commit/release SHA.

## Evidence schedule

| Evidence ID | Control/evidence | Minimum cadence/trigger | Expected evidence | Framework reuse |
|---|---|---|---|---|
| OE-001 | Privileged access review | Quarterly and personnel/role change | dated list of privileged identities/roles, removals, reviewer | SOC2, ISO27001, CSA |
| OE-002 | API key/credential lifecycle | On creation/revocation + quarterly review | key metadata, role/scope, created/revoked dates; no raw keys | SOC2, ISO27001, CSA |
| OE-003 | Production/release changes | Every release/material production change | PR/commit, required CI, approver/process evidence, release SHA | SOC2 CC8, ISO27001, CSA |
| OE-004 | Security/dependency/secret scans | Every required CI + scheduled scans | workflow result/artifact IDs, findings/remediation | SOC2, ISO27001, CSA, OpenSSF |
| OE-005 | Vulnerability findings | On finding | severity, owner, remediation/risk acceptance, retest | SOC2, ISO27001, CSA |
| OE-006 | Backup completion | Per configured backup schedule | provider/job/log metadata and failures | SOC2 Availability, ISO27001, CSA |
| OE-007 | Restore exercise | At least quarterly before mature enterprise claims; after major backup change | date, backup used, RTO/RPO result, issues/corrections | SOC2 Availability, ISO27001 |
| OE-008 | Incident response/tabletop | At least annually and on real material incident | exercise/incident timeline, decisions, corrective actions | SOC2, ISO27001, CSA, privacy laws |
| OE-009 | Vendor/subprocessor review | At least annually and on material change | vendor, service, security/privacy evidence, decision | SOC2 CC9, ISO27001, CSA, GDPR/DPDP |
| OE-010 | Risk review | Quarterly and significant change | reviewed risk register, changes, acceptances, owners | SOC2, ISO27001, ISO42001, CSA |
| OE-011 | AI inventory/risk review | Material AI/model/tool change + annual review | inventory diff, impact/risk review, approval | ISO42001, STAR for AI, EU AI Act, NIST AI RMF |
| OE-012 | Privacy/data-flow review | Annual and material data/vendor change | RoPA/data-flow diff, retention/subprocessor changes | GDPR, DPDP, SOC2 Privacy |
| OE-013 | Retention/deletion operation | Per retention job/manual procedure | counts/categories/date/outcome; no deleted content | GDPR, DPDP, SOC2 Privacy |
| OE-014 | Rights/grievance requests | On real request | received/verified/responded dates, result; content stored securely outside public repo | GDPR, DPDP, SOC2 Privacy |
| OE-015 | Key rotation exercise | At least annually and after suspected compromise | date, key class, successful rotation/re-encryption/rollback evidence | SOC2, ISO27001, CSA |
| OE-016 | Evidence-chain verification | Scheduled and before assurance release | verification result, exact system/release, failures/remediation | SOC2 Processing Integrity, ISO27001, ISO42001 |
| OE-017 | Business continuity review | Annual + material architecture change | BCP review, dependencies, recovery assumptions, actions | SOC2 Availability, ISO27001 |
| OE-018 | Management review | At least annually | inputs, decisions, improvement actions, owners | ISO27001, ISO42001 |
| OE-019 | Public compliance-claim review | Before material public claim/release | claim, supporting evidence, prohibited wording check | All assurance programs |
| OE-020 | Customer offboarding/revocation | On real offboarding | account/key/revocation timestamps and retained/deleted data actions | SOC2, ISO27001, privacy |

## Evidence record template

Use this structure for each real evidence item:

```text
Evidence ID:
Control:
Period / event date:
System / environment:
Release / commit SHA (if applicable):
Owner / reviewer:
Event or test performed:
Outcome:
Exceptions / findings:
Corrective action / risk acceptance:
Evidence location (secure link, workflow run, ticket, redacted artifact):
Retention / confidentiality classification:
```

## Current baseline notes — 2026-09-13

Known existing evidence includes protected-branch enforcement, mandatory CI/security workflows, signed/provenance release controls, an incident-response tabletop exercise, internal security review, vendor-risk documentation, continuity documentation and extensive automated tests.

This register does not retroactively invent quarterly evidence for periods where no formal register existed. Existing dated artifacts may be cited where they genuinely demonstrate prior operation.

## Audit handoff rule

When an auditor/certification body is engaged, export only evidence for the agreed scope and period, redact secrets/customer data, and preserve the original source of truth. Do not reshape evidence in a way that changes its factual meaning.
