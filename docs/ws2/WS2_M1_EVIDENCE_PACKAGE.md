# WS-2 — M1 evidence package (engineering)

**Status:** WS-1 → WS-2 **integration gate engineering complete**; exact-head CI **qualified** on `32745a3be8cbb76f4b4767876122a568a392d4d9`. **Not** Antigravity M1 qualified. **Do not** request Antigravity M1 until founder dispatches independent review (BLK-P0-02/03 remain OPEN).

## SHA ladder (no drift)

| Milestone | SHA | Status |
|-----------|-----|--------|
| **Merged `main` base SHA** | `cb7f479593706d841a698dafb5463f7adc744fca` | WS-1 merge commit (PR #129); prior `main` `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` |
| **WS-1 merged implementation tip** | `3b7bb2543c082b19233bf68dec8978e4df1e8b77` | Antigravity M0 FULL PASS; CI [36874569609](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36874569609) |
| **Current development head** | `32745a3be8cbb76f4b4767876122a568a392d4d9` | PR #130 tip (rebased on `cb7f479`; evidence docs + integration fixes) |
| **Final tree SHA** | `19b6d1cc8b20ca6fc21ed3e8c5bb0c5da4867059` | At `32745a3be8cbb76f4b4767876122a568a392d4d9` |
| **Exact-head CI-qualified SHA** | `32745a3be8cbb76f4b4767876122a568a392d4d9` | CI [36913753488](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36913753488) **success** (all required checks) |

> Stacked-branch SHAs (`ae181d7`, `1ae68b3`, …) are **historical context only**. Do not treat them as exact-head CI evidence.

## Integration gates (1–10)

See `docs/ws2/WS2_INTEGRATION_GATE_STATUS.md`.

| Gate | Status |
|------|--------|
| 1 Antigravity WS-1 M0 | **COMPLETE** (FULL PASS) |
| 2 Merge PR #129 | **COMPLETE** |
| 3–5 Rebase + ancestry | **COMPLETE** |
| 6 WS-2 bundle (rebased) | **COMPLETE** — **183 passed** |
| 7 Full repo tests (rebased) | **COMPLETE** — **5179 passed**, 41 skipped, 0 failed |
| 8 Exact-head GitHub CI | **COMPLETE** — [36913753488](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36913753488) |
| 9 This package | **COMPLETE** (engineering handoff; Antigravity M1 separate) |
| 10 BLK-P0-02 / BLK-P0-03 | **OPEN** |

## Test results (rebased tree — local qualification)

| Suite | Command / scope | Result | Log |
|-------|-----------------|--------|-----|
| WS-2 pre-M1 bundle | 15 modules (see below) | **183 passed** | `/opt/cursor/artifacts/ws2_m1_full_bundle.log` |
| PostgreSQL nonce race | `test_postgres_distinct_connections_consume_once` | **1 passed** | `/opt/cursor/artifacts/ws2_postgres_nonce.log` |
| Full repository | `pytest tests/ -q` | **5179 passed**, 41 skipped, 0 failed | `/opt/cursor/artifacts/full_suite_post_rebase_af2babe.log` |

### Former 11 full-suite failures (resolved)

Production-preflight tests failed until `WHITEPACT_MCP_TRUST_DOMAIN=enterprise` was set in production `Settings` / fixtures (`tests/test_config.py`, `tests/test_cursor_v1_hardening.py`, `tests/test_enterprise_layer1_remediation.py`). **No weakening of WS-2 authority controls.**

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
| WS-1 qualified (M0, pre-merge head) | https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36874569609 |
| PR #130 exact-head (rebased on `main`, qualified) | https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36913753488 |

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
- `docs/ws2/WS2_ANTIGRAVITY_M1_PACKET.md` (draft — do not send until gate #8 green)

## Non-goals

- Merge PR #130, PyPI, Cloud provision, production deploy, Antigravity M1 self-certification
