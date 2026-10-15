# M5 — Antigravity handoff

**Status:** `M5_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY`  
**Qualified M4 ancestor (immutable):** `52d9b3c5497af24bb7d4a7147e33deaadc64296e` / tree `2c0447e733b3d96dea1feaf0144f5ec3aa43b8b4` (Antigravity **FULL PASS**)  
**Qualified M3 ancestor:** `620399b7973f5ed058d45218610be228e72d3ed8` / tree `15b7934d93ad8692f5a5e8c2225c5f69c130da00`

| Field | Value |
|-------|--------|
| Gate branch | `cursor/whitepact-m5-integrated-rc-f7a9` |
| PR | #135 |
| Exact-head record | `docs/ws6/M5_EXACT_HEAD_CI_EVIDENCE.md` |
| Engineering integration | `c77bdef42bd01fc079402b56846ba8fa61810830` (prep `635b812`) |
| Obsolete RC | PR #137 — see `docs/ws6/M5_PR137_DISPOSITION.md` |

## Evidence map

| Area | Tests / docs |
|------|----------------|
| M1–M4 regression | `test_m4_m123_regression_index.py`, `test_m4_hostile_regression_campaign.py` |
| M5 integrated | `test_m5_integrated_regression_campaign.py`, `test_m5_integrated_rc_gate.py` |
| Chaos / fail-closed | `test_m5_chaos_campaign_matrix.py`, `test_m4_chaos_fail_closed.py` |
| UNKNOWN outcome | `test_m5_unknown_outcome_regression.py`, `test_mcp_ws2_upstream_reconciliation.py` |
| Revocation stress | `test_m5_revocation_stress_matrix.py`, `test_revocation_kernel.py` |
| MCP | `test_m5_mcp_regression_index.py`, `test_mcp_ws2_authority_matrix.py` |
| SDK | `test_sdk_governance_contract_matrix.py`, `test_sdk_governance_reconciliation_m3.py` |
| PostgreSQL | `test_m4_postgres_assault_campaign.py`, `test_phase7a_authority_kernel.py` |
| Clean install | `test_m5_clean_install_validation.py`, CI wheel smokes |
| Customer journey | `tests/js/customer-journey.e2e.mjs`, `test_m5_journey_evidence_index.py` |
| Authority path | `docs/enterprise/FINAL_AUTHORITY_PATH_PROOF.md` |
| Release gate script | `scripts/release/m5_integrated_regression_gate.sh` |

## Known limitations

See `docs/enterprise/KNOWN_LIMITATIONS.md`. No production cloud deploy; no package publish.

Cursor does **not** claim independent M5 PASS.
