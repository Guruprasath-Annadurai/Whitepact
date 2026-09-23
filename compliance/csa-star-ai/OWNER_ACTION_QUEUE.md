# Owner action queue — CSA STAR for AI Level 1

Accountable owner (current): **Founder / Security Owner (Guruprasath Annadurai)**

Cursor/cloud agents cannot perform these actions. Controls depending on them remain **NO** or **NA** until evidence exists.

| ID | Control area | Action | Why required | Exact steps | Evidence to capture | Est. time | Blocks submission? |
|----|--------------|--------|--------------|-------------|---------------------|-----------|-------------------|
| OA-001 | All 320 | Copy `WhitePact_AI_CAIQ_v1.1_STAR_Level1_COMPLETED_DRAFT.xlsx` and PDF audit into `compliance/csa-star-ai/source/`; run `python scripts/csa_star_ai/ingest_workbook.py` | Row-level ledger and FINAL workbook export require official workbook | Place files; commit redacted copy if approved; run ingest | `ledger/remediation_ledger.json` with 320 rows; ingest log | 30 min | **YES** |
| OA-002 | CEK / DSP / BCR | Export hosting provider encryption-at-rest, backup, and region settings (Postgres/Redis/object storage) | Cannot claim provider encryption without dated screenshots/exports | Provider console → security/compliance → export PDF | Dated PDF in `compliance/csa-star-ai/evidence/provider/` | 1–2 h | **YES** (many controls) |
| OA-003 | IAM | Enable/enforce MFA on GitHub, DNS, hosting, Paddle, and production admin accounts | Organizational access control | Enable MFA; document account list | Screenshot + account inventory row | 1 h | **YES** |
| OA-004 | GRC / HRS | Legal review of DPA/privacy notice; counsel sign-off | Legal determinations are owner/counsel | Send `compliance/DPA_TEMPLATE.md` to counsel | Signed approval email/PDF | External | **YES** (legal rows) |
| OA-005 | A&A | Independent third-party audit / STAR Level 2 attestation (if pursuing L2) | STAR L1 is self-assessment; L2 needs external firm | Engage auditor per `compliance/SOC2_ALTERNATIVE_PATH.md` | Auditor report | Weeks | No for L1 |
| OA-006 | EDM | Document solo-founder endpoint controls (FileVault, screen lock, OS updates) | No corporate MDM; honest SSRM | Complete checklist in ORGANIZATIONAL_CONTROL_REGISTER | Signed self-attestation dated | 30 min | Partial |
| OA-007 | STA | Register secondary security contact with CSA STAR portal | Registry requirement | CSA portal profile | Screenshot | 15 min | Partial |

Add rows as remediation identifies additional owner-only gaps.
