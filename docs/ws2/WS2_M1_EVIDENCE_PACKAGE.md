# WS-2 — M1 evidence package (engineering)

**Status:** Engineering in progress — **not** M1 qualified. **Do not** request Antigravity M1 until integration gate (§12) is satisfied.

## SHA ladder (no drift)

| Milestone | SHA | Status |
|-----------|-----|--------|
| **Current development head** | `20509e038383aaf672916d86b8847a23916d41de` | Authoritative for local bundle runs on stacked branch |
| **Final implementation head** | *pending* | Set when Lane A engineering complete (not yet declared) |
| **Final rebased head** (onto merged WS-1 `main`) | *pending* | Requires PR #129 merge + rebase of #130 |
| **Exact-head CI-qualified SHA** | *pending* | Requires green GitHub Actions on rebased PR #130 |

> During active development, only **current development head** is authoritative for local runs. Older SHAs and pass counts are historical, not exact-head evidence.

## Integration gate (WS-1 / WS-2)

| Step | Status |
|------|--------|
| Antigravity WS-1 M0 confirmation | Pending founder/Antigravity |
| Founder approves merge PR #129 | Not done |
| Merged `main` SHA recorded | *pending* (`origin/main` was `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` at last check) |
| PR #130 rebased on merged `main` | *pending* |
| Full repo CI on rebased head | *pending* |

## Findings disposition

| ID | Status |
|----|--------|
| BLK-P0-02 | **OPEN** |
| BLK-P0-03 | **OPEN** |

## Test bundle (local)

Run the full WS-2 pre-M1 bundle:

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

**Latest local bundle result (stacked branch, pre-rebase):** **181 passed** — log: `/opt/cursor/artifacts/ws2_m1_full_bundle.log` (2026-09-30 UTC). This is **not** exact-head CI evidence.

## PostgreSQL concurrency qualification

| Environment | Command | Result |
|-------------|---------|--------|
| `WHITEPACT_TEST_POSTGRES_EXECUTION` (auto-configured when isolated PG reachable) | `pytest tests/test_phase1_execution.py::test_postgres_distinct_connections_consume_once -q` | **PASS** (local cloud agent run) |
| Unavailable PG | Same test | **skipped** — must not be treated as equivalent to SQLite |

## CI URLs

| Run | URL |
|-----|-----|
| WS-1 qualified (reference only) | [36725514596](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36725514596) |
| PR #130 exact-head | *pending rebase onto merged `main`* |

## Artifacts

- Execution paths: `docs/ws2/WS2_EXECUTION_PATH_MAP.md`
- Allowlist review: `docs/ws2/WS2_EXECUTION_BOUNDARY_ALLOWLIST.md`
- Antigravity packet (draft): `docs/ws2/WS2_ANTIGRAVITY_M1_PACKET.md`

## Known limitations

- Community stdio remains ungoverned by design; enterprise forbids stdio.
- Isolation child runner (LOCAL_DEV) executes `dispatch_tool` on stdin JSON without cryptographic admission — production blocks same-process execution without broker (`test_ws2_isolation_child_admission.py`).
- Phase 7A worker queue qualified only in non-production; production gate refuses dispatcher start.
- Stacked-branch local tests ≠ post-rebase integration qualification.

## Non-goals

- Antigravity M1 self-certification
- Merge PR #130 / publish PyPI / cloud provision
