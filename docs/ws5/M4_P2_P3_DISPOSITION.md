# M4 P2 / P3 disposition (engineering)

| Item | Disposition | Evidence |
|------|-------------|----------|
| Worker lease contention | `ENGINEERING_ACCEPTED LIMITATION` | `test_phase7a_authority_kernel.py` |
| SSO/SCIM edge cases | `FIXED` (engineering) | `test_iam_adversarial_matrix.py`, `test_m4_scim_adversarial_extension.py`, enterprise SSO tests |
| Accessibility keyboard flows | `FIXED` (engineering) | CI WCAG + `web/src/test/m4-keyboard-matrix.test.tsx` |
| OTEL E2E trace proof | `FIXED` (engineering) | `test_m4_otel_correlation.py`, `test_m4_telemetry_fail_closed.py` |
| Audit index performance | `FIXED` (engineering) | `test_m4_audit_index_performance_guard.py`, `test_m4_audit_export_batch_smoke.py` |
| Restore verification | `FIXED` (engineering) | `test_restore_admission_chokepoint.py`, `test_m4_restore_drill_evidence.py`, runbook |
| Cloud provision | `DEFERRED — NON-LAUNCH-BLOCKING` | Plan-only terraform |
| Origin/LB direct access | `ENGINEERING_ACCEPTED LIMITATION` | `test_m4_cloud_origin_static.py`; live staging bypass deferred |
| Legacy domain overhang | `DEFERRED — NON-LAUNCH-BLOCKING` | Master report |

Antigravity may reclassify during independent M4 qualification.
