# Remediation campaign log

| Date | SHA | Action |
|------|-----|--------|
| 2026-09-23 | `acddae1` base | Branch `cursor/csa-star-ai-level1-remediation` created from Paddle RC |
| 2026-09-23 | TBD | Evidence pack + ingest/export tooling; subprocessor register; incident/DR exercises |

## Classification workflow (152 NOs)

Use ledger `remediation_type` field:

- **A** Source code — implement + test in `src/`  
- **B** Infrastructure — deploy manifests + OA-002  
- **C** Security process — runbooks + dated exercises  
- **D** Documentation — policies (honest limits)  
- **E** CI/supply chain — workflows + release evidence  
- **F** Organizational — ORGANIZATIONAL_CONTROL_REGISTER  
- **G** Cloud/subprocessor — SUBPROCESSOR_REGISTER + provider evidence  
- **H** Customer-shared — Column F in workbook  
- **I** External third party — auditor / counsel  

## Re-audit of 98 YES

Blocked until OA-001. Method: automated test mapping via `TECHNICAL_EVIDENCE_INDEX.md` + manual downgrade list (same discipline as `CAIQ_EVIDENCE_BOUNDARY.md`).
