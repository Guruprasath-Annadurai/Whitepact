# Owner action queue — CSA STAR for AI Level 1

Accountable owner (current): **Founder / Security Owner (Guruprasath Annadurai)**

Cursor/cloud agents cannot perform these actions. Controls depending on them remain **NO** or **NA** until evidence exists.

| ID | Control area | Action | Why required | Exact steps | Evidence to capture | Est. time | Blocks submission? |
|----|--------------|--------|--------------|-------------|---------------------|-----------|-------------------|
| OA-001 | All 320 | **DONE (2026-09-23):** Official AI-CAIQ v1.1 acquired; SHA-256 in `SOURCE_INTEGRITY.json`. Phase 2 role normalization complete. |
| OA-001b | All 320 | Download **official** AI-CAIQ v1.1 from [CSA artifact page](https://cloudsecurityalliance.org/artifacts/ai-consensus-assessments-initiative-questionnaire-ai-caiq-v1-1) (use “Download it now” or account login). Save **unmodified** as `compliance/csa-star-ai/source/CSA_AI-CAIQ_v1.1_Official_upstream.xlsx`. Run `record_source_integrity.py`, `ingest_workbook.py`, `assess_evidence.py`. Optional: store PDF audit separately; it is not a substitute for the CSA workbook. | Authoritative 320-row ingest blocked without pristine CSA file | Follow `source/SOURCE_INTEGRITY.json` manual_steps | `SOURCE_INTEGRITY.json` with SHA-256; `remediation_ledger.json` (320 rows, UNASSESSED→assessed) | 30–60 min | **YES** |
| OA-002 | CEK / DSP / BCR | Export hosting provider encryption-at-rest, backup, and region settings (Postgres/Redis/object storage) | Cannot claim provider encryption without dated screenshots/exports | Provider console → security/compliance → export PDF | Dated PDF in `compliance/csa-star-ai/evidence/provider/` | 1–2 h | **YES** (many controls) |
| OA-003 | IAM | Enable/enforce MFA on GitHub, DNS, hosting, Paddle, and production admin accounts | Organizational access control | Enable MFA; document account list | Screenshot + account inventory row | 1 h | **YES** |
| OA-004 | GRC / HRS | Legal review of DPA/privacy notice; counsel sign-off | Legal determinations are owner/counsel | Send `compliance/DPA_TEMPLATE.md` to counsel | Signed approval email/PDF | External | **YES** (legal rows) |
| OA-005 | A&A | Independent third-party audit / STAR Level 2 attestation (if pursuing L2) | STAR L1 is self-assessment; L2 needs external firm | Engage auditor per `compliance/SOC2_ALTERNATIVE_PATH.md` | Auditor report | Weeks | No for L1 |
| OA-006 | EDM | Document solo-founder endpoint controls (FileVault, screen lock, OS updates) | No corporate MDM; honest SSRM | Complete checklist in ORGANIZATIONAL_CONTROL_REGISTER | Signed self-attestation dated | 30 min | Partial |
| OA-007 | STA | Register secondary security contact with CSA STAR portal | Registry requirement | CSA portal profile | Screenshot | 15 min | Partial |

Add rows as remediation identifies additional owner-only gaps.
