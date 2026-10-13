# M5 deterministic rebuild plan

**Status:** `M5_PREPARATION_ONLY — WAITING_FOR_QUALIFIED_M4_BASE`  
**Purpose:** Rebuild final M5 integrated RC immediately after Antigravity exact-SHA M4 PASS.

## Qualified anchors (literal lineage)

| Milestone | Exact SHA | Tree (record) | Independent status |
|-----------|-----------|---------------|-------------------|
| M1 | WS-2 qualified head per Antigravity M1 record | — | **QUALIFIED** |
| M2 | `893d34a9d009560a3d9f07887c1afa3018f9e6dc` | — | **QUALIFIED** |
| M3 | `620399b7973f5ed058d45218610be228e72d3ed8` | `15b7934d93ad8692f5a5e8c2225c5f69c130da00` | **QUALIFIED** |
| M4 (audit) | `52d9b3c5497af24bb7d4a7147e33deaadc64296e` | `2c0447e733b3d96dea1feaf0144f5ec3aa43b8b4` | **Antigravity in progress** — Cursor does not claim PASS |
| M4 substance | `5261eb96c12246232a80cdefd9a3b79592ee7a2e` | `638107e2381f26aaf4d412388d392442b3877736` | Engineering closure on M4 stack |

**Rule:** Final M5 RC branch MUST be created as `git checkout -b cursor/whitepact-m5-integrated-rc-f7a9 <qualified-m4-sha>` after PASS — not from stale PR #137 head alone.

## Obsolete / non-authoritative branches (exclude from final RC)

| Branch / PR | Reason |
|-------------|--------|
| PR #134 legacy WS-5 | Superseded by M4 realignment from `620399b` |
| PR #137 @ pre-M4 heads | Evidence only; lineage not M1→M2→M3→**qualified M4** |
| `cursor/whitepact-ws5-m4-cloud-hardening-f7a9` | Stale stack policy per `docs/ws5/M4_LINEAGE_RECORD.md` |
| Any branch not containing `620399b` + qualified M4 | Reject for M5 freeze |

## M5 features to carry forward (inventory)

| Workstream | Primary evidence | Cherry-pick risk |
|------------|------------------|------------------|
| Authority / MCP / grants | `tests/test_mcp_ws2_authority_matrix.py`, `test_mcp_ws2_failclosed_dependency_matrix.py` | Low on M4 base |
| SDK governance | `tests/test_sdk_governance_contract_m3.py`, `test_sdk_governance_reconciliation_m3.py` | Medium — verify API drift |
| Identity / SSO / SCIM / TOTP | `test_iam_adversarial_matrix.py`, `test_scim_and_session_lifecycle.py`, `test_totp_matched_counter_security.py` | Low |
| SIEM / audit | `test_siem_audit_export.py`, `test_siem_delivery_m3.py`, M4 audit perf guards | Low |
| Paddle sandbox | `test_paddle_sandbox_m3.py` (if present) | Low |
| Break-glass / revocation | `test_revocation_kernel.py`, M4/M5 revocation stress | Medium — race tests |
| Worker / Phase 7A | `test_phase7a_authority_kernel.py` | High — PG concurrency |
| Web / policy / journeys | `test_web_policy_management.py`, customer journey e2e | Medium |
| Cloud plan-only | `infra/terraform/**`, `test_terraform_m4_validate.py` | Low (no apply) |
| Chaos / UNKNOWN | `tests/test_m5_chaos_campaign_matrix.py`, upstream reconciliation | Low |

## Cherry-pick / migration map (prepared)

1. **Base:** `qualified_m4_sha` from Antigravity report (expected `52d9b3c…` if PASS matches frozen candidate).
2. **Apply prepared M5/M6 branch** as merge or selective cherry-pick:
   - `cursor/whitepact-m5-m6-parallel-prep-f7a9` — docs + test matrices only (safe).
   - Re-evaluate `cursor/whitepact-m5-integrated-rc-f7a9` commits **one-by-one** against diff vs qualified M4.
3. **Conflict hotspots:** `pyproject.toml`, `src/responsibleai/dashboard/app.py`, enterprise identity, MCP server dispatch, CI workflow timeouts.
4. **Migrations:** Alembic/SQL under `src/responsibleai/db/` — run `test_pg_security_preservation.py` + `test_auth_real_postgres.py` after merge.
5. **Docs-only:** `docs/ws6/*`, `docs/enterprise/*` — low conflict; land early.

## Regression matrix (M5 integrated)

Execute in CI and locally (see `tests/test_m5_integrated_regression_campaign.py`):

- Authority decision → approval → grant → execution → evidence → audit
- Revocation across sessions, API keys, grants, break-glass, SCIM
- SDK + MCP + worker + PostgreSQL concurrency
- Paddle sandbox, SIEM, lifecycle, SSO/SCIM adversarial slices

## Chaos / fail-closed matrix

See `tests/test_m5_chaos_campaign_matrix.py` and `tests/test_m5_unknown_outcome_regression.py`.

**Doctrine:** Supporting infrastructure failure must never create new authority.

## CI / release gates (post-M4 PASS)

1. Full pytest on integrated head (same matrix as M4 gate + M5 campaign).
2. **18/18** workflow on `cursor/whitepact-m5-integrated-rc-f7a9` only after lineage proof.
3. Record exact SHA, tree, run id in `docs/enterprise/FINAL_ARTIFACT_INVENTORY.md`.
4. Status → `M5_ENGINEERING_COMPLETE — READY_FOR_ANTIGRAVITY` (not independent PASS).

## Activation checklist (run once on M4 PASS)

- [ ] Verify Antigravity report SHA == expected qualified M4
- [ ] `git merge-base --is-ancestor 620399b <m4-pass-sha>`
- [ ] Create new `cursor/whitepact-m5-integrated-rc-f7a9` from `<m4-pass-sha>`
- [ ] Merge/cherry-pick `cursor/whitepact-m5-m6-parallel-prep-f7a9`
- [ ] Resolve conflicts; no test weakening
- [ ] Run `tests/test_m5_integrated_regression_campaign.py` + M4 hostile campaign
- [ ] Push; run full CI; freeze one M5 RC SHA

## M4 audit response mode

If Antigravity FAIL: **stop** M5 lineage construction; branch `cursor/whitepact-m4-remediation-*` from failed SHA; fix; new M4 candidate — do not advance M5 RC.
