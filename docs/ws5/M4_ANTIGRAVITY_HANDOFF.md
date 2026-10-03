# M4 — Antigravity handoff (draft)

**Status:** `M4_ENGINEERING_IN_PROGRESS` — populate when final exact-head candidate freezes.  
**Qualified M3 ancestor:** `620399b7973f5ed058d45218610be228e72d3ed8` (immutable).

| Section | Evidence (to fill at freeze) |
|---------|------------------------------|
| Exact SHA / tree / CI run | TBD |
| PostgreSQL concurrency | `tests/test_m4_postgres_assault_campaign.py` + suites |
| SSO / IAM | `tests/test_iam_adversarial_matrix.py` |
| SCIM | `tests/test_scim_and_session_lifecycle.py` |
| TOTP (M3 carry) | `tests/test_totp_matched_counter_security.py` |
| OTEL | `tests/test_m4_telemetry_fail_closed.py` |
| Cloud / origin static | `tests/test_m4_cloud_origin_static.py`, `infra/terraform/**` |
| Runbooks | `docs/operations/runbooks/` |
| Hostile campaign | `tests/test_m4_hostile_regression_campaign.py` |
| Known limitations | `docs/ws5/M4_P2_P3_DISPOSITION.md` |

Do not claim independent M4 PASS from Cursor.
