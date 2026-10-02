# WS-5 / M4 — engineering status

**Branch:** `cursor/whitepact-ws5-m4-cloud-hardening-f7a9` (stacked on M3 / PR #133)  
**Cursor status:** `M4_ENGINEERING_COMPLETE — READY_FOR_INDEPENDENT_AUDIT` (plan-only; **no provision**)

## Scope

| Area | Deliverable | Constraint |
|------|-------------|------------|
| WS-7 cloud | `infra/terraform/**` imported from qualified cloud branch | `terraform validate` only; **BLOCKED — UNSAFE TO PROVISION** per `docs/phase0/ANTIGRAVITY_CLOUD_PRESTAGING_AUDIT_REGISTER.md` |
| PostgreSQL | `tests/test_auth_real_postgres.py` concurrency + migration proofs | Requires CI/local PG (`tests/pg_test_url.py`) |
| SSO/SCIM | `tests/test_scim_and_session_lifecycle.py` | Engineering regression gate |
| a11y | `web/src/components/AccessibleDialog.tsx` + existing CI a11y job | No new live audit claim |
| Tracing | OTEL hooks in dashboard settings | REPORT_ONLY until E2E trace proof |

## Evidence

- `tests/test_terraform_m4_validate.py`
- `infra/terraform/README.md` (provision blocker notice)

## Next

- **M5** integrated RC SHA declaration + attack regression campaign on stacked head.
