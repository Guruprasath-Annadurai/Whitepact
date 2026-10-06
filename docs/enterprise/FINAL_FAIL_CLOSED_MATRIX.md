# Final fail-closed matrix (M6)

Classification: `DENY` | `RETRY_SAFE` | `UNKNOWN` | `RECONCILIATION_REQUIRED` | `NON_AUTHORITY_CRITICAL_DEGRADED`

| Subsystem | Failure | Classification | Evidence |
|-----------|---------|----------------|----------|
| DB (primary) | Unavailable during approval | `DENY` / no grant | `test_restore_admission_chokepoint.py`, PG assault |
| DB | Unavailable during grant consume | `DENY` | `test_phase7a_authority_kernel.py` |
| Policy engine | Unresolved policy | `DENY` | `test_web_policy_management.py` |
| Authority resolver | Stale / revoked epoch | `DENY` | `test_revocation_kernel.py`, IAM matrix |
| Approval repository | Expired / rejected | `DENY` | `test_approval_expiry.py` |
| Grant / nonce repository | Replay / double consume | `DENY` | `test_phase7a_authority_kernel.py` |
| Executor | Transport error after accept | `UNKNOWN` | `test_mcp_ws2_upstream_reconciliation.py` |
| MCP upstream | Timeout / malformed | `UNKNOWN` or `DENY` | MCP fail-closed matrix |
| Evidence repository | Read failure | `DENY` / no retry authority | SDK reconciliation tests |
| SIEM forwarder | Delivery exhausted | `NON_AUTHORITY_CRITICAL_DEGRADED` | `test_siem_delivery_m3.py` — **no new authority** |
| Telemetry (OTEL) | Exporter down | `NON_AUTHORITY_CRITICAL_DEGRADED` | `test_m4_telemetry_fail_closed.py` |
| SSO | Invalid assertion | `DENY` | `test_iam_adversarial_matrix.py` |
| SCIM | Deprovision race | `DENY` stale session | `test_scim_and_session_lifecycle.py` |
| Billing (Paddle) | Sandbox outage | `DENY` / degraded billing UI | Paddle sandbox tests |

**Doctrine:** supporting infrastructure failure must never mint execution authority.
