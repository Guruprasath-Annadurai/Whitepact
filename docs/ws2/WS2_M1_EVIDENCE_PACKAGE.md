# WS-2 — M1 evidence package (engineering)

**Status:** Integration gate **incomplete** — **not** Antigravity M1 qualified. **Do not** request Antigravity M1 until gates in `WS2_INTEGRATION_GATE_STATUS.md` are green.

## SHA ladder (no drift)

| Milestone | SHA | Status |
|-----------|-----|--------|
| **Current development head** | `ae181d7c0cf156e0104ac22d291fd79b74271e36` | PR #130 tip (verified) |
| **Merged `main` base SHA** | *pending* | Blocked: PR [#129](https://github.com/Guruprasath-Annadurai/Whitepact/pull/129) not merged; `origin/main` = `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` |
| **Final implementation SHA** | *pending rebase* | Engineering complete on stacked branch; **not** final until rebased on merged `main` |
| **Final tree SHA** | *pending rebase* | Same as final implementation SHA after rebase push |
| **Exact-head CI-qualified SHA** | *pending* | Requires green GitHub Actions on rebased PR #130 targeting `main` |

> Stacked-branch SHAs and local pass counts are **historical context only** after rebase. Never treat them as exact-head CI evidence for a newer tree.

## Integration gates (1–10)

See `docs/ws2/WS2_INTEGRATION_GATE_STATUS.md`.

| Gate | Status |
|------|--------|
| 1 Antigravity WS-1 M0 | **PENDING** — packet at `docs/ws1/WS1_ANTIGRAVITY_CONFIRMATION_PACKET.md` |
| 2 Merge PR #129 | **PENDING** founder approval |
| 3–5 Rebase + ancestry | **BLOCKED** on #2 |
| 6 WS-2 bundle (rebased) | **PARTIAL** — see below (stacked head) |
| 7 Full repo tests (rebased) | **PARTIAL** — see below (stacked head) |
| 8 Exact-head GitHub CI | **BLOCKED** — PR #130 base ≠ `main`; empty check rollup |
| 9 This package | **IN PROGRESS** |
| 10 BLK-P0-02 / BLK-P0-03 | **OPEN** |

## Test results (stacked branch `ae181d7` — not rebased CI)

| Suite | Command / scope | Result | Log |
|-------|-----------------|--------|-----|
| WS-2 pre-M1 bundle | 15 modules (see below) | **183 passed** | `/opt/cursor/artifacts/ws2_m1_full_bundle_ae181d7.log` (via agent run) |
| PostgreSQL nonce race | `test_postgres_distinct_connections_consume_once` | **1 passed** | `/opt/cursor/artifacts/ws2_postgres_nonce.log` |
| Full repository | `pytest tests/ -q` | **5168 passed**, **11 failed**, 41 skipped | `/opt/cursor/artifacts/ws2_full_repo_pytest_stacked.log` |

### Full-repo failures on stacked branch (local env)

All 11 failures are configuration / production-preflight tests (`tests/test_config.py`, `tests/test_cursor_v1_hardening.py`, `tests/test_enterprise_layer1_remediation.py`) — typical when production `Settings` expectations (Postgres URL, field encryption key) are not set for the whole-suite run. **Re-validate on rebased tree under CI-equivalent env** (gate #8).

### WS-2 bundle command

```bash
pytest \
  tests/test_mcp_enterprise_trust_domain.py \
  tests/test_mcp_ws2_authority_matrix.py \
  tests/test_ws2_execution_boundary_invariant.py \
  tests/test_executor_bypass_invariant.py \
  tests/test_mcp_ws2_live_invalidation_matrix.py \
  tests/test_mcp_ws2_failclosed_dependency_matrix.py \
  tests/test_mcp_ws2_upstream_reconciliation.py \
  tests/test_ws2_isolation_child_admission.py \
  tests/test_mcp_ws2_worker_retry_matrix.py \
  tests/test_mcp_governance_dispatch.py \
  tests/test_upstream_gateway.py \
  tests/test_resume_after_approval.py \
  tests/test_phase1_execution.py \
  tests/test_phase1_live_admission.py \
  tests/test_phase7a_feature_flag.py \
  -q
```

## PostgreSQL concurrency evidence

| Test | Result (cloud agent, isolated PG) |
|------|-----------------------------------|
| `tests/test_phase1_execution.py::test_postgres_distinct_connections_consume_once` | **PASS** |
| `tests/test_phase1_execution.py::test_sqlite_distinct_connections_consume_once` | **PASS** (in bundle) |

## CI URLs

| Run | URL |
|-----|-----|
| WS-1 qualified (M0 reference) | https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36725514596 |
| PR #130 exact-head (rebased on merged `main`) | **pending** |

## Phase 7A scope

**Excluded from production launch candidate.** See `docs/ws2/WS2_PHASE7A_PRODUCTION_SCOPE.md`.

## Findings

| ID | Status |
|----|--------|
| BLK-P0-02 | **OPEN** |
| BLK-P0-03 | **OPEN** |

## Artifacts

- `docs/ws2/WS2_EXECUTION_PATH_MAP.md`
- `docs/ws2/WS2_EXECUTION_BOUNDARY_ALLOWLIST.md`
- `docs/ws2/WS2_ANTIGRAVITY_M1_PACKET.md` (draft — do not send until gate #8)

## Non-goals

- Merge PR #130, PyPI, Cloud provision, production deploy, Antigravity M1 self-certification
