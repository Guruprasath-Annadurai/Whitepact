# M4 P2 / P3 disposition (engineering)

| Item | Disposition | Rationale |
|------|-------------|-----------|
| Worker lease contention | `ENGINEERING_ACCEPTED LIMITATION` | CAS + lease generation in `test_phase7a_authority_kernel.py`; monitor UNKNOWN rates |
| SSO/SCIM edge cases | `OPEN — BLOCKER` until PG+IAM campaign green | Expand `test_iam_adversarial_matrix.py` + SCIM races |
| Accessibility keyboard flows | `OPEN — BLOCKER` | CI WCAG + manual keyboard matrix pending |
| OTEL E2E trace proof | `ENGINEERING_ACCEPTED LIMITATION` | No-op safe (`test_m4_telemetry_fail_closed.py`); full E2E trace IDs deferred |
| Audit index performance | `OPEN — BLOCKER` | Needs PG dataset + plan evidence |
| Restore verification | `OPEN — BLOCKER` | Runbook + chokepoint tests; full DR drill pending |
| Cloud provision | `DEFERRED — NON-LAUNCH-BLOCKING` | Plan-only until founder + Antigravity cloud audit |
| Origin/LB direct access | `OPEN — BLOCKER` | Static terraform/MCP checks; live bypass test needs staging |
| Legacy domain overhang | `DEFERRED — NON-LAUNCH-BLOCKING` | Docs tracked in master report |

Update this table as blockers close on the final M4 candidate SHA.
