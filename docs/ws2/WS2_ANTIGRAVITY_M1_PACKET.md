# WS-2 — Antigravity M1 independent qualification packet

**Request:** Independently reproduce and judge runtime authority closure for WS-2. Cursor **does not** close BLK-P0-02 or BLK-P0-03.

## Repository coordinates

- **Repo:** `Guruprasath-Annadurai/Whitepact`
- **Branch:** `cursor/whitepact-ws2-runtime-authority-f7a9`
- **PR:** #130 (rebase onto merged `main` after #129 before final CI sign-off)

## Reproduction checklist

1. **Enterprise stdio denial** — `WHITEPACT_MCP_TRUST_DOMAIN=enterprise` → `python -m responsibleai.mcp.server` exits **2**; message references hosted MCP.
2. **Production downgrade denial** — `Settings(environment="production", mcp_trust_domain="community")` raises `ValueError`.
3. **Hosted fail-closed** — `tests/test_mcp_governance_dispatch.py` with governance enabled; missing services → `governance_unavailable` / no dispatch.
4. **Upstream fail-closed** — unregistered server → `governance_denied` (`test_mcp_ws2_authority_matrix.py`).
5. **Grant expiry** — `AuthorizationExpiredError`; dispatch mock not awaited.
6. **Action digest binding** — forged digest → `AuthorizationActionMismatchError`.
7. **Cross-tenant binding** — org mismatch on execute.
8. **Revocation epoch invalidation** — bump epoch after grant; `StaleRevocationEpochError` before dispatch (`test_mcp_ws2_authority_matrix.py`, `test_phase1_live_admission.py`).
9. **Approval invalidation** — `test_resume_after_approval.py` (replay, drift, security state).
10. **Resolver / DB failure** — `apply_governance` without resolver; evidence write failure (`test_mcp_ws2_authority_matrix.py`, `test_final_coverage_batch11.py`).
11. **Durable concurrent nonce** — `test_phase1_execution.py` + `test_phase1_live_admission.py` + matrix concurrent case.
12. **Worker / retry duplicate protection** — `test_phase7a_authority_kernel.py` (registry in `sovereign/gauntlet_registry.py`); resume replay in `test_resume_after_approval.py`.
13. **Execution-path binding** — review `docs/ws2/WS2_EXECUTION_PATH_MAP.md` against code.
14. **Static bypass invariant** — `pytest tests/test_ws2_execution_boundary_invariant.py`.
15. **UNKNOWN / reconciliation** — governance outcome UNKNOWN paths in `governance_integration.py` tests / synthetic counter tests.

## Suggested commands

```bash
git fetch origin cursor/whitepact-ws2-runtime-authority-f7a9
git checkout cursor/whitepact-ws2-runtime-authority-f7a9
pip install -e '.[dashboard]'  # or project-standard install
pytest tests/test_mcp_ws2_authority_matrix.py \
  tests/test_ws2_execution_boundary_invariant.py \
  tests/test_mcp_enterprise_trust_domain.py \
  tests/test_executor_bypass_invariant.py \
  tests/test_mcp_governance_dispatch.py \
  tests/test_upstream_gateway.py \
  tests/test_phase1_execution.py \
  tests/test_phase1_live_admission.py \
  tests/test_resume_after_approval.py -q
```

Optional PostgreSQL:

```bash
export WHITEPACT_TEST_POSTGRES_EXECUTION='postgresql+asyncpg://...'
pytest tests/test_phase1_execution.py::test_postgres_distinct_connections_consume_once -q
```

## M1 declaration criteria (Antigravity only)

M1 may be declared only when independent review confirms:

> Every supported **enterprise** path capable of performing a consequential action cannot execute unless the canonical authority boundary authorizes that exact action under **current** authority state.

Until then, disposition remains **OPEN** for BLK-P0-02 and BLK-P0-03.
