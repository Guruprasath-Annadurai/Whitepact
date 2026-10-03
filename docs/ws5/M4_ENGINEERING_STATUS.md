# WS-5 / M4 — engineering status

**Base:** qualified M3 @ `620399b7973f5ed058d45218610be228e72d3ed8`  
**Branch:** `cursor/whitepact-m4-successor-engineering-f7a9`  
**Cursor status:** `M4_ENGINEERING_IN_PROGRESS` (successor ahead of gate `bfc4a01`)  
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

## Active work (successor branch only)

- PostgreSQL assault: `tests/test_m4_postgres_assault_campaign.py`
- Hostile campaign: `tests/test_m4_hostile_regression_campaign.py`
- OTEL fail-closed: `tests/test_m4_telemetry_fail_closed.py`
- Origin/cloud static: `tests/test_m4_cloud_origin_static.py`
- Runbooks: `docs/operations/runbooks/*`
- P2/P3: `docs/ws5/M4_P2_P3_DISPOSITION.md`

## Gate policy

- **#138 @ `bfc4a01`:** intermediate evidence only (`docs/ws5/M4_INTERMEDIATE_CI_EVIDENCE.md`)
- Final freeze: new exact SHA after closure → full **18/18** → `M4_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY`
