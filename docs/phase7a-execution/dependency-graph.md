# WhitePact Phase 7A: Validated Dependency Graph & Execution Sequence

**Document Status:** CANONICAL SPECIFICATION PASS 3 (FINAL CALL-PATH & SINGLE-ADMISSION CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Overview & Graph Invariants

This document defines the strict, mathematically sound dependency graph for Phase 7A implementation.

### Critical Graph Invariants:
1. **No Migration Cycle:** `0049_runtime_execution_authorizations.py` depends strictly on `0048`. `0050_runtime_worker_leases.py` depends strictly on `0049`.
2. **PostgreSQL Schema Before Logic:** No repository or transaction logic may execute before its underlying migration is committed.
3. **Dispatcher Activation Gate (Task 10 Gate):** Task 10 requires that:
   - ALL 3 production `authorize_execution()` issuance paths are closed via durable PostgreSQL persistence (`execute_governed_action`, `resolve_approval_and_execute` in `governance_integration.py`, and `dispatch_upstream_action` in `upstream_dispatch.py`).
   - Single canonical `admit_execution()` ownership is proven (Worker owns admission; `InternalToolExecutor` and `UpstreamServer` consume `AdmittedExecution` context without re-admission).
   - Zero Task 10 activation may proceed before this gate passes.
4. **Zero Bypass Paths:** Consequential execution requires durable issuance, valid worker lease, pre-flight revalidation, and atomic admission.

---

## 2. Task Master Table with Explicit Prerequisite Proofs

| Task ID | Task Name | Task Category | Strict Prerequisites | Target Files | Can Run in Parallel? |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Task 1** | Admission Domain Models | SERIAL CORE | Approved Canonical Base (`13e8de0`) | `runtime/admission/models.py` | NO (Foundation) |
| **Task 2** | Local Admission Controller | SERIAL CORE | Task 1 | `runtime/admission/controller.py` | NO |
| **Task 3** | Coordination Base Contract | SERIAL CORE | Task 1 | `runtime/coordination/base.py` | YES (after Task 1) |
| **Task 4** | Redis Coordinator Implementation | SERIAL CORE | Task 3 | `runtime/coordination/redis_coordinator.py` | YES (Leaf module) |
| **Task 5** | Redis Fail-Closed Behavior | SERIAL CORE | Tasks 2, 4 | `runtime/admission/controller.py` | NO |
| **Task 6** | Integrated Multi-Tenant Concurrency | SERIAL CORE | Tasks 2, 5 | `runtime/admission/controller.py` | NO |
| **Task 7** | Bounded Fair Queue (Plan-Neutral) | SERIAL CORE | Tasks 1, 6 | `runtime/queue/*` | YES (after Task 6) |
| **Task 8A** | Durable EA Storage (Mig 0049), Centralized Issuance Service & All-Path Issuance Integration | SERIAL CORE | Task 1, Head `0048` | `migrations/0049_*.py`, `db/execution_authorization_repository.py`, `governance/execution_issuer.py`, `mcp/governance_integration.py`, `mcp/upstream_dispatch.py` | YES (after Task 1) |
| **Task 8B** | Full Two-Stage Revalidation, Atomic Admission Transaction & Admitted Context | SERIAL CORE | Task 8A | `db/execution_nonce_repository.py`, `governance/execution.py`, `governance/upstream_executor.py`, `runtime/revalidation.py` | NO (Database atomic) |
| **Task 9** | Worker Lease Schema (Mig 0050) & DB Exclusivity | SERIAL CORE | Task 8A | `migrations/0050_*.py`, `runtime/worker/lease.py`, `db/admission_lease_repository.py` | NO (PostgreSQL) |
| **Task 10** | Dispatcher Activation Gate (All Issuance Paths Closed & Single Admission Proven) | INTEGRATION GATE | Tasks 6, 7, 8B, 9 | `runtime/dispatcher.py`, `runtime/worker/worker.py`, `mcp/governance_integration.py`, `mcp/upstream_dispatch.py` | NO (Activation Gate) |
| **Task 11** | Worker Lease Heartbeat & Crash Recovery | SERIAL CORE | Task 10 | `runtime/worker/supervisor.py` | NO (Depends on Gate) |
| **Task 12** | Side-Effect Safety & Uncertain State Handling | SERIAL CORE | Task 11 | `runtime/worker/worker.py` | NO (Depends on Task 11) |
| **Task 13** | WP-ISO-01 Compute Limits (CPU/RAM/PID) | PARALLEL SUPPORT | None | `isolation/models.py`, `isolation/container_backend.py` | YES (Isolation lane) |
| **Task 14** | WP-ISO-01 Workspace Limits (10MB/100 Files) | PARALLEL SUPPORT | Task 13 | `isolation/filesystem.py` | YES (Isolation lane) |
| **Task 15** | Timeout and Cancellation | PARALLEL SUPPORT | Task 13 | `isolation/container_backend.py` | YES (Isolation lane) |
| **Task 16** | Graceful Shutdown Supervisor | INTEGRATION GATE | Tasks 10, 15 | `runtime/shutdown.py`, `dashboard/app.py` | NO |
| **Task 17** | Health Probe Decoupling (/livez, /readyz) | INTEGRATION | Task 16 | `runtime/health.py`, `dashboard/app.py` | NO |
| **Task 18** | Observability & 15 Runtime Metrics | PARALLEL SUPPORT | Task 1 | `dashboard/prometheus.py` | YES (Metrics only) |
| **Task 19** | Multi-Process Real Infrastructure Integration | INTEGRATION GATE | Tasks 1-18 | `tests/runtime/test_multi_process_*.py`, `tests/runtime/test_real_infra_*.py` | NO |
| **Task 20** | Canonical Security Regression | INTEGRATION | Task 19 | `tests/runtime/test_phase7a_security_regression.py` | NO |
| **Task 21** | Configuration Audit & Bounds Validation | PARALLEL SUPPORT | Task 6 | `dashboard/config.py` | YES |
| **Task 22** | Candidate Freeze & Evidence Pack | INTEGRATION | Tasks 20, 21 | `docs/phase7a-execution/*` | NO |

---

## 3. Corrected Dependency Graph Visualization

```mermaid
flowchart TD
    HEAD[Approved Canonical Base: 13e8de0 & Mig 0048]

    subgraph LANE_A1 [Lane A1: Admission & Distributed Coordination]
        T1[Task 1: Domain Models] --> T2[Task 2: Local Controller]
        T1 --> T3[Task 3: Coordination Base]
        T3 --> T4[Task 4: Redis Coordinator]
        T2 & T4 --> T5[Task 5: Redis Fail-Closed]
        T5 --> T6[Task 6: Multi-Tenant Concurrency]
        T6 --> T7[Task 7: Plan-Neutral Fair Queue]
    end

    subgraph LANE_A2 [Lane A2: Durable Authority & Atomic Admission]
        T1 & HEAD --> T8A[Task 8A: Durable EA Mig 0049, Centralized Issuer & All-Path Integration]
        T8A --> T8B[Task 8B: Two-Stage Revalidation, Atomic admit_execution & Admitted Context]
    end

    subgraph LANE_C1 [Lane C1: Worker Lease Schema & DB Exclusivity]
        T8A --> T9[Task 9: Worker Lease Mig 0050 & DB Exclusivity]
    end

    subgraph GATE_10 [Integration Gate: Dispatcher Activation]
        T6 & T7 & T8B & T9 --> T10[Task 10 Gate: Dispatcher Activation<br/>Preconditions: All 3 Issuance Paths Closed & Single Admission Proven]
    end

    subgraph LANE_C2 [Lane C2: Crash Recovery & Side-Effect Safety]
        T10 --> T11[Task 11: Worker Heartbeats & Stale Lease Reaper]
        T11 --> T12[Task 12: Uncertain Side-Effect Idempotency]
    end

    subgraph LANE_B [Lane B: WP-ISO-01 Container Hardening]
        T13[Task 13: Compute Limits CPU 0.5 / RAM 256MB / PID 32] --> T14[Task 14: Workspace 10MB / 100 Files]
        T13 --> T15[Task 15: Timeout 15s & Container Cancellation]
    end

    subgraph LANE_D [Lane D: Operations & Observability]
        T10 & T15 --> T16[Task 16: Graceful Shutdown Supervisor]
        T16 --> T17[Task 17: Decoupled Health Probes]
        T1 --> T18[Task 18: Observability 15 Prometheus Metrics]
        T6 --> T21[Task 21: Config Bounds Audit]
    end

    subgraph LANE_E [Lane E: Multi-Process Verification & Freeze]
        T12 & T16 & T17 & T18 & T21 --> T19[Task 19: Multi-Process Real Infrastructure Integration]
        T19 --> T20[Task 20: Canonical Security Regression]
        T20 --> T22[Task 22: Candidate Freeze & Evidence Pack]
    end
```
