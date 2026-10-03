# WS-5 / M4 — engineering status

**Base:** qualified M3 @ `620399b7973f5ed058d45218610be228e72d3ed8`  
**Branch:** `cursor/whitepact-m4-successor-engineering-f7a9`  
**Cursor status:** `M4_ENGINEERING_IN_PROGRESS`  
**Do not claim independent M4 PASS.**

## Scope matrix

| Area | Evidence | Notes |
|------|----------|--------|
| PostgreSQL concurrency | `tests/test_auth_real_postgres.py` | Isolated PG via `tests/pg_test_url.py` |
| SSO / SCIM | `tests/test_scim_and_session_lifecycle.py` | Session + SCIM lifecycle |
| Restore chokepoint | `tests/test_restore_admission_chokepoint.py` | Fail-closed restore |
| SIEM / audit | `tests/test_siem_audit_export.py`, `tests/test_m4_audit_export_batch_smoke.py` | Export + batch smoke |
| Cloud plan-only | `infra/terraform/**`, `tests/test_terraform_m4_validate.py` | **validate only — no apply** |
| a11y | `web/src/components/AccessibleDialog.tsx` + CI a11y job | |
| Tracing | `src/responsibleai/dashboard/telemetry.py` | OTEL no-op safe |
| Operator runbooks | `docs/operations/OPERATOR_RUNBOOK_INDEX.md` | |
| Gate index | `tests/test_m4_engineering_gates.py` | |

## Stale stack policy

PR **#134** / legacy WS-5 branch is **not** the M4 authority. M5 integrated RC must rebuild from qualified M1→M2→M3→M4 after M4 Antigravity qualification.

## Next

1. Hostile M4 regression (`tests/test_m4_hostile_regression_campaign.py`)  
2. Full exact-head CI on `cursor/whitepact-m4-qualification-gate-f7a9`  
3. Mark `M4_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY` only after **18/18** green
