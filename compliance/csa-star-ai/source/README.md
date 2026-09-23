# AI-CAIQ source artifacts

Copy the following files into this directory:

1. `WhitePact_AI_CAIQ_v1.1_STAR_Level1_COMPLETED_DRAFT.xlsx`
2. `WhitePact_AI_CAIQ_v1.1_Readiness_Audit_and_Remediation.pdf`

Then run from repository root:

```bash
python scripts/csa_star_ai/ingest_workbook.py
```

Do **not** edit official question text inside the workbook. Only respondent columns (C–F per campaign spec) are updated on export.
