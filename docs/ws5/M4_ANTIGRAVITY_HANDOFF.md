# M4 — Antigravity handoff

**Status:** `M4_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY` (pending exact-head **18/18** on gate SHA recorded below).  
**Qualified M3 ancestor (immutable):** `620399b7973f5ed058d45218610be228e72d3ed8` / tree `15b7934d93ad8692f5a5e8c2225c5f69c130da00`

| Field | Value |
|-------|--------|
| Gate branch | `cursor/whitepact-m4-qualification-gate-f7a9` |
| Successor branch | `cursor/whitepact-m4-successor-engineering-f7a9` |
| Intermediate evidence | `bfc4a01` — PR #138 (`docs/ws5/M4_INTERMEDIATE_CI_EVIDENCE.md`) |
| Final candidate SHA | *(record on gate tip after push)* |
| CI run | *(record workflow id when 18/18)* |

## Evidence map

| Area | Tests / docs |
|------|----------------|
| PostgreSQL concurrency | `test_m4_postgres_assault_campaign.py`, `test_auth_real_postgres.py`, `test_phase5_postgres_concurrency.py`, `test_phase7a_authority_kernel.py`, `test_pg_security_preservation.py` |
| IAM / SSO | `test_iam_adversarial_matrix.py`, `test_enterprise_layer2_identity_security.py` |
| SCIM | `test_scim_and_session_lifecycle.py`, `test_m4_scim_adversarial_extension.py` |
| TOTP (M3 carry) | `test_totp_matched_counter_security.py` — `M3-P1-TOTP-REPLAY-01` |
| OTEL | `test_m4_otel_correlation.py`, `test_m4_telemetry_fail_closed.py` |
| Audit / SIEM perf | `test_m4_audit_index_performance_guard.py`, `test_m4_audit_export_batch_smoke.py` |
| Restore | `test_restore_admission_chokepoint.py`, `test_m4_restore_drill_evidence.py` |
| Chaos / fail-closed | `test_m4_chaos_fail_closed.py` |
| Revocation | `test_m4_revocation_under_failure.py`, `test_revocation_kernel.py` |
| Cloud / origin static | `test_m4_cloud_origin_static.py`, `infra/terraform/**` |
| Hostile campaign | `test_m4_hostile_regression_campaign.py` |
| M1–M3 regression index | `test_m4_m123_regression_index.py` |
| a11y keyboard | `web/src/test/m4-keyboard-matrix.test.tsx` + CI WCAG |
| Runbooks | `docs/operations/runbooks/` |
| P2/P3 | `docs/ws5/M4_P2_P3_DISPOSITION.md` |

## Known limitations

- Cloud: plan-only; no `terraform apply`.
- Origin bypass: static checks only until staging drill.
- PG battery: requires isolated PostgreSQL (`tests/pg_test_url.py`).

Cursor does **not** claim independent M4 PASS.
