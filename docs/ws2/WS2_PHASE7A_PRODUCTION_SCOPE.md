# WS-2 — Phase 7A worker scope (production launch candidate)

## Disposition

**Phase 7A is NOT part of the current enterprise production launch candidate.**

Production Gate B is **compiled closed** (`PRODUCTION_GATE_B_OPEN = False` in `runtime/gate.py`). Queue/worker execution authority is a **non-production, opt-in** subsystem for staging/development only.

## Production activation is impossible (enforced layers)

| Layer | Mechanism | Test |
|-------|-----------|------|
| Compiled gate | `PRODUCTION_GATE_B_OPEN = False` | `tests/test_phase7a_feature_flag.py` |
| Settings validator | `refuse_production_phase7a()` on `Settings` construction | `tests/test_mcp_ws2_worker_retry_matrix.py` |
| Dispatcher start | `start_phase7a_dispatcher(environment="production")` raises | same |
| Hosted MCP preflight | `hosted_production_preflight` rejects `phase7a_dispatcher_enabled` | `tests/test_mcp_ws2_worker_retry_matrix.py` |
| MCP server startup | Production + flag → `HostedProductionSecurityError` | same |

Env tamper attempts (`PHASE7A_DISPATCHER_ENABLED`, `WHITEPACT_*`, `RAI_*`, `production` / `prod`) cannot enable workers in production while Gate B is closed.

## M1 qualification scope for workers

| Path | M1 status |
|------|-----------|
| Production worker queue / duplicate delivery / crash recovery | **Out of scope** — cannot run in production until Gate B opens |
| Governed resume + durable nonce (`resume_approval`, `test_resume_after_approval.py`, `test_phase1_live_admission.py`) | **In scope** for enterprise MCP/REST |
| Phase 7A kernel tests (`tests/test_phase7a_authority_kernel.py`) | **Staging/PostgreSQL** evidence only; not a production launch claim |

## Community / isolation child model

Enterprise **production** forbids same-process `dispatch_tool` without `IsolationBroker` (`governance/execution.py`). The LOCAL_DEV subprocess child trusts parent-supplied stdin JSON; that path is not reachable in production configuration. See `test_ws2_isolation_child_admission.py` and `WS2_EXECUTION_BOUNDARY_ALLOWLIST.md`.
