# WS-2 — M1 evidence package (engineering)

**Status:** Engineering in progress — **not** M1 qualified. Cursor does not self-certify closure.

| Field | Value |
|-------|--------|
| Base `origin/main` SHA | `81beb3ac50e17068c7d6f26d9a07f2cb0442dbec` |
| WS-1 PR | [#129](https://github.com/Guruprasath-Annadurai/Whitepact/pull/129) — **not merged** at time of this revision |
| WS-2 branch | `cursor/whitepact-ws2-runtime-authority-f7a9` |
| WS-2 PR | [#130](https://github.com/Guruprasath-Annadurai/Whitepact/pull/130) (stacked on WS-1) |
| WS-2 tip | `a5c96e7` (see `git rev-parse HEAD` on branch) |
| Findings | **BLK-P0-02 OPEN**, **BLK-P0-03 OPEN** until Antigravity M1 |

## Changed-file inventory (WS-2 lane, cumulative)

- `src/responsibleai/mcp/trust_domain.py` — enterprise stdio refusal, production trust domain
- `src/responsibleai/mcp/server.py` — stdio guards, hosted preflight
- `src/responsibleai/dashboard/config.py` — `mcp_trust_domain`, production validator
- `tests/test_mcp_enterprise_trust_domain.py`
- `tests/test_mcp_ws2_authority_matrix.py`
- `tests/test_ws2_execution_boundary_invariant.py`
- `docs/ws2/WS2_RUNTIME_AUTHORITY_PLAN.md`
- `docs/ws2/WS2_EXECUTION_PATH_MAP.md`
- `docs/ws2/WS2_M1_EVIDENCE_PACKAGE.md` (this file)
- `docs/ws2/WS2_ANTIGRAVITY_M1_PACKET.md`
- `docs/enterprise/PHASE1_MASTER_EXECUTION_REPORT.md`

## Execution path map

See `docs/ws2/WS2_EXECUTION_PATH_MAP.md`.

## Adversarial test matrix (representative)

| Scenario | Test location | Dispatch not called |
|----------|---------------|---------------------|
| Enterprise stdio | `test_mcp_ws2_authority_matrix.py` | N/A (process exit) |
| Production community downgrade | matrix + `test_mcp_enterprise_trust_domain.py` | N/A |
| Hosted governance unavailable | matrix + `test_mcp_governance_dispatch.py` | Y |
| Forged / expired / cross-tenant / replay grant | matrix + `test_executor_bypass_invariant.py` | Y |
| Stale revocation epoch | matrix + `test_phase1_live_admission.py` | Y |
| Resolver / evidence fail-closed | matrix + `test_final_coverage_batch11.py` | Y |
| Upstream unregistered | matrix + `test_upstream_gateway.py` | Y |
| Concurrent nonce consumption | matrix + `test_phase1_execution.py` | exactly one dispatch |
| Static bypass invariant | `test_ws2_execution_boundary_invariant.py` | CI guard |

## Test counts (local, focused bundle)

Command:

```bash
pytest tests/test_mcp_ws2_authority_matrix.py \
  tests/test_ws2_execution_boundary_invariant.py \
  tests/test_mcp_enterprise_trust_domain.py \
  tests/test_executor_bypass_invariant.py \
  tests/test_mcp_governance_dispatch.py \
  tests/test_phase1_execution.py \
  tests/test_phase1_live_admission.py -q
```

Result: **48+** tests in WS-2 + admission bundle (exact count varies with collection); last run **48 passed** on WS-2 matrix + phase1 admission subset.

## CI URLs

- PR #130 is stacked on WS-1; **full GitHub CI on `main` triggers after rebase onto merged #129**.
- WS-1 qualified CI: [36725514596](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/36725514596)

## Database / concurrency

- SQLite: `test_phase1_execution.py::test_sqlite_distinct_connections_consume_once`
- PostgreSQL: `test_postgres_distinct_connections_consume_once` when `WHITEPACT_TEST_POSTGRES_EXECUTION` is set

## Known limitations

- Community stdio remains intentionally ungoverned for documented local use; enterprise mode refuses stdio entirely.
- Exact-head CI for PR #130 pending WS-1 merge + rebase.
- Performance numbers captured only as sub-second smoke in matrix (not a SLA).

## Non-goals (this milestone)

- PyPI publish (BLK-P0-05)
- Cloud provision / terraform apply
- WS-3 SaaS integration merge
- Self-declared M1 closure

## Antigravity handoff

See `docs/ws2/WS2_ANTIGRAVITY_M1_PACKET.md`.
