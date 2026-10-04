# Final claims matrix

## Proven (engineering tests / CI on recorded heads)

| Claim | Evidence |
|-------|----------|
| TOTP replay resistance (matched counter) | `test_totp_matched_counter_security.py` @ M3 `620399b` |
| Enterprise MCP stdio blocked in enterprise trust domain | `test_mcp_ws2_authority_matrix.py` |
| Legacy governance HTML not served in unified mode | M2 BYPASS-02 suites |
| SIEM forwarder fails closed on delivery exhaustion | `test_m5_chaos_fail_closed.py`, `test_siem_delivery_m3.py` |
| UNKNOWN upstream does not auto-retry consequential execution | `test_mcp_ws2_upstream_reconciliation.py`, SDK reconciliation tests |
| PostgreSQL authority kernel concurrency (when PG available) | `test_phase7a_authority_kernel.py` |

## Qualified (Antigravity independent)

| Milestone | SHA | Status |
|-----------|-----|--------|
| M1 | Per Antigravity M1 record | **QUALIFIED** |
| M2 | `893d34a` | **QUALIFIED** |
| M3 | `620399b` | **QUALIFIED** |
| M4 | `52d9b3c5497af24bb7d4a7147e33deaadc64296e` | **QUALIFIED** (Antigravity exact-SHA PASS) |
| M5 | `46685fad1ad49cfde36341ea1fad146ce1d2e714` | **QUALIFIED** (Antigravity exact-SHA PASS) |
| M6 | M6 gate branch tip | **IMPLEMENTED_NOT_EXTERNALLY_QUALIFIED** until Antigravity M6 |

## Planned (not production-proven)

| Claim | Blocker |
|-------|---------|
| Production multi-region cloud | No `terraform apply`; no prod deploy |
| Hyperscale throughput | No measured load test at target QPS |
| Full SOC 2 / ISO certification | Not certified |
| Live origin/LB bypass resistance | Staging drill deferred |

## Unsupported / prohibited (must not claim)

- SOC 2 Type II certified
- ISO 27001 certified
- “Cannot be bypassed” absolute language
- Production cloud live until deployed and independently qualified
- Antigravity M4/M5 PASS before formal reports
