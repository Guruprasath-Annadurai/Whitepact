# CAIQ Evidence Boundary

Assessment: CSA CAIQ v4.0.3 workbook, 261 assessment questions.  
Review date: 2026-08-31. Scope: WhitePact repository plus the limited live-site evidence
in `HARDENED_SITE_VERIFICATION.md`. This is a **self-assessment**, not CSA STAR
certification, attestation, or an independent assurance opinion.

## Classification rules

Every populated workbook response now begins with one of these evidence classes:

| Class | Meaning |
|---|---|
| SOURCE-CODE VERIFIED | The cited implementation/test/workflow was inspected in this repository; operating effectiveness in a customer's deployment is not implied. |
| DEPLOYMENT VERIFIED | The behavior was directly observed against the named live boundary and date. No CAIQ row currently relies solely on this class. |
| DOCUMENTED PROCESS | A repository policy/runbook exists; repeated operation and independent effectiveness are not proven. |
| OWNER ASSERTION REQUIRED | The response depends on hosting, account, people, contracts, or production configuration not provable from source. |
| ORGANIZATIONAL CONTROL | The requirement is primarily a people/legal/governance/provider responsibility. A `No` or `NA` remains visible. |
| NOT IMPLEMENTED | The in-scope requirement is not fully implemented or evidenced. |

## Results and corrections

The workbook retains all 261 official questions. After evidence review it contains **72
Yes, 157 No, and 32 NA** responses (plus two header rows). Thirty-five prior `Yes`
answers were downgraded to `No` because the cited evidence showed only a partial control,
a document rather than operation, an unverified provider assertion, or a different
technical capability.

Downgraded IDs:

`A&A-01.1`, `A&A-04.1`, `A&A-05.1`, `A&A-06.1`, `BCR-01.1`, `BCR-03.1`,
`BCR-08.1`, `BCR-08.2`, `BCR-09.1`, `CCC-01.1`, `CCC-03.1`, `CEK-03.1`,
`CEK-06.1`, `CEK-14.1`, `DSP-01.1`, `DSP-08.2`, `DSP-10.1`, `DSP-12.1`,
`DSP-13.1`, `DSP-19.1`, `GRC-05.1`, `GRC-07.1`, `HRS-13.1`, `IAM-12.1`,
`IAM-14.1`, `IVS-02.1`, `IVS-03.2`, `IVS-09.1`, `LOG-02.1`, `LOG-03.1`,
`LOG-05.1`, `LOG-09.1`, `LOG-13.1`, `STA-01.1`, and `STA-02.1`.

Examples of corrected boundaries:

- Framework mappings do not verify legal/regulatory compliance.
- A hash chain is tamper-evident; it does not make logs read-only to database admins or
  establish retention.
- Optional MFA does not prove MFA is enforced for every sensitive access path.
- Provider documentation does not prove WhitePact's backups, capacity, regions, internal
  TLS, or disaster recovery are operating as described today.
- An incident runbook is not a fully exercised business-continuity/disaster-recovery plan.
- A cryptography library is not automatically a certified cryptographic module.
- Privacy/DPA drafts without counsel approval do not establish compliance.

## Evidence use

The workbook can support customer due diligence when supplied together with the source
commit, current deployment architecture, subprocessor register, live configuration
evidence, and owner sign-off. Before a STAR Level 1 submission, an accountable owner must
review every `OWNER ASSERTION REQUIRED` and `ORGANIZATIONAL CONTROL` row, correct SSRM
ownership for the actual service, verify all URLs, and approve the final response.

CSA STAR Level 1 requires a submission/registry process outside this repository. STAR
Level 2 requires independent certification or attestation. Both remain **EXTERNAL
VERIFICATION REQUIRED**; nothing in this workbook is an official CSA certificate.
