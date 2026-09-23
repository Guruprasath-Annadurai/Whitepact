# CSA STAR for AI — Level 1 / AI-CAIQ v1.1 Remediation

**Campaign branch:** `cursor/csa-star-ai-level1-remediation`  
**Base release candidate (untouched):** `acddae1e96050c1dbe3981327f47dc102beb9262`

## Purpose

This directory is the **evidence and remediation source of truth** for WhitePact's CSA STAR for AI Level 1 submission using **AI-CAIQ v1.1** (320 controls).

Principles (non-negotiable):

- A **name is a query, not an identity** applies to directory work elsewhere; here: **DOCUMENT ≠ OPERATING EFFECTIVENESS**, **CODE ≠ PRODUCTION OPERATION**, **POLICY ≠ PRACTICE**, **CONFIG OPTION ≠ ENABLED CONFIGURATION**.
- **Never** upgrade a control to YES without evidence that would survive an enterprise security review.
- Official CSA question wording lives only in the submission workbook; supporting material lives here.

## Source artifacts (owner-supplied)

Place the external audit deliverables here (not committed if they contain sensitive notes — use encrypted storage; a redacted copy may be committed when approved):

| File | Role |
|------|------|
| `source/WhitePact_AI_CAIQ_v1.1_STAR_Level1_COMPLETED_DRAFT.xlsx` | Baseline answers (98 YES / 152 NO / 70 NA) |
| `source/WhitePact_AI_CAIQ_v1.1_Readiness_Audit_and_Remediation.pdf` | Control-by-control remediation narrative |

**Status:** As of campaign start, these files are **not present in the repository**. Ingest is blocked until they are copied to `source/`. See `OWNER_ACTION_QUEUE.md` item **OA-001**.

## Tooling

```bash
# After OA-001 (workbook in source/)
python scripts/csa_star_ai/ingest_workbook.py

# After ledger remediation updates
python scripts/csa_star_ai/export_final_workbook.py \
  --output compliance/csa-star-ai/WhitePact_AI_CAIQ_v1.1_STAR_Level1_FINAL.xlsx
```

Outputs:

- `ledger/remediation_ledger.json` — 320-row internal ledger
- `ledger/control_changes.csv` — delta report for re-audit
- `CONTROL_MATRIX.md` — generated summary (post-ingest)

## Related legacy CAIQ (CCM v4.0.3)

`compliance/CAIQv4.0.3_WhitePact_completed.xlsx` remains for **cloud CCM** self-assessment traceability. It is **not** the AI-CAIQ v1.1 submission workbook (261 vs 320 questions).

## Index

| Document | Description |
|----------|-------------|
| [CONTROL_MATRIX.md](./CONTROL_MATRIX.md) | Row-level matrix (generated after ingest) |
| [TECHNICAL_EVIDENCE_INDEX.md](./TECHNICAL_EVIDENCE_INDEX.md) | Code/test/CI pointers |
| [ORGANIZATIONAL_CONTROL_REGISTER.md](./ORGANIZATIONAL_CONTROL_REGISTER.md) | Human/process controls |
| [OWNER_ACTION_QUEUE.md](./OWNER_ACTION_QUEUE.md) | Founder/provider actions |
| [REMEDIATION_REPORT.md](./REMEDIATION_REPORT.md) | Campaign log |
| [SSRM_MAPPING.md](./SSRM_MAPPING.md) | Shared responsibility |
| [SUBPROCESSOR_REGISTER.md](./SUBPROCESSOR_REGISTER.md) | Vendors (Paddle, hosting, etc.) |
| [INCIDENT_EXERCISE_REPORT.md](./INCIDENT_EXERCISE_REPORT.md) | Tabletop (exercise, not real incident) |
| [DR_RESTORE_EXERCISE_REPORT.md](./DR_RESTORE_EXERCISE_REPORT.md) | Restore drill evidence |
| [AI_RISK_MANAGEMENT_EVIDENCE.md](./AI_RISK_MANAGEMENT_EVIDENCE.md) | AI-specific controls → code |
| [FINAL_READINESS_REPORT.md](./FINAL_READINESS_REPORT.md) | Before/after readiness |
| [PRODUCTION_CONFIG_BASELINE.md](./PRODUCTION_CONFIG_BASELINE.md) | Env baseline & fail-closed rules |
