# WhitePact Phase 7A: Concrete Parallelization Map & Subagent Task Plan

**Document Status:** CANONICAL SPECIFICATION PASS 3 (FINAL CALL-PATH & SINGLE-ADMISSION CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Overview and Invariants

This document establishes the verified concurrent execution waves for Phase 7A implementation. It eliminates race conditions, ensures zero file collisions across concurrent lanes, and enforces the mandatory activation gate for the worker dispatcher.

### Core Concurrency Rules:
1. **Zero File Collisions:** No two subagents or tasks in the same wave may write to the same file.
2. **Linear Migration Sequencing:** Migration `0049` (Execution Authorizations) MUST precede migration `0050` (Worker Leases).
3. **Dispatcher Activation Gate (Task 10 Gate):** Task 10 requires:
   - ALL 3 production `authorize_execution()` issuance paths closed via durable PostgreSQL persistence (`governance_integration.py` and `upstream_dispatch.py`).
   - Single canonical `admit_execution()` ownership proven (Worker owns admission; `InternalToolExecutor` and `UpstreamServer` consume `AdmittedExecution` context without re-admission).
   - No execution dispatcher or worker process may be activated before this gate passes.
4. **Decoupled Business Logic:** Commercial billing attributes (`Plan`, `subscription_status`) are strictly excluded from all runtime scheduling, admission, and queueing logic.

---

## 2. Parallel Implementation Lanes

### Lane A1: Admission & Distributed Coordination Engine
- **Primary Responsibility:** Admission state machine, in-process controller, Redis distributed semaphores, fail-closed boundaries, multi-tenant concurrency quotas, and plan-neutral fair queueing.
- **Tasks Owned:** Tasks 1, 2, 3, 4, 5, 6, 7.
- **Files Owned:**
  - `src/responsibleai/runtime/admission/models.py` [CREATE]
  - `src/responsibleai/runtime/admission/controller.py` [CREATE]
  - `src/responsibleai/runtime/coordination/base.py` [CREATE]
  - `src/responsibleai/runtime/coordination/redis_coordinator.py` [CREATE]
  - `src/responsibleai/runtime/queue/models.py` [CREATE]
  - `src/responsibleai/runtime/queue/bounded_queue.py` [CREATE]
  - `src/responsibleai/runtime/queue/fair_scheduler.py` [CREATE]
  - `tests/runtime/test_admission_*.py` [CREATE]
  - `tests/runtime/test_coordination_contract.py` [CREATE]
  - `tests/runtime/test_redis_*.py` [CREATE]
  - `tests/runtime/test_integrated_concurrency.py` [CREATE]
  - `tests/runtime/test_bounded_queue.py` [CREATE]

---

### Lane A2: Durable Authority & Atomic Admission Engine
- **Primary Responsibility:** Durable `ExecutionAuthorization` storage (migration `0049`), repository, centralized issuance service (`execution_issuer.py`), durable issuance integration across all 3 production call sites (`mcp/governance_integration.py` and `mcp/upstream_dispatch.py`), two-stage revalidation, and single atomic admission transaction in `db/execution_nonce_repository.py` and `governance/execution.py` with `AdmittedExecution` context handoff to `InternalToolExecutor` and `UpstreamServer`.
- **Tasks Owned:** Tasks 8A, 8B.
- **Files Owned:**
  - `migrations/versions/0049_runtime_execution_authorizations.py` [CREATE]
  - `src/responsibleai/db/execution_authorization_repository.py` [CREATE]
  - `src/responsibleai/governance/execution_issuer.py` [CREATE]
  - `src/responsibleai/mcp/governance_integration.py` [MODIFY] (Durable Issuance Integration)
  - `src/responsibleai/mcp/upstream_dispatch.py` [MODIFY] (Upstream Issuance Integration)
  - `src/responsibleai/db/execution_nonce_repository.py` [MODIFY] (Atomic Combined Transaction)
  - `src/responsibleai/governance/execution.py` [MODIFY] (Canonical Admission Gate & AdmittedExecution)
  - `src/responsibleai/governance/upstream_executor.py` [MODIFY] (Upstream Single Admission)
  - `src/responsibleai/runtime/revalidation.py` [CREATE]
  - `tests/runtime/test_durable_execution_authorization.py` [CREATE]
  - `tests/runtime/test_durable_issuance_all_paths.py` [CREATE]
  - `tests/runtime/test_atomic_admission.py` [CREATE]
  - `tests/runtime/test_single_admission_internal_tool.py` [CREATE]
  - `tests/runtime/test_single_admission_upstream.py` [CREATE]
  - `tests/runtime/test_revalidation.py` [CREATE]

---

### Lane B: WP-ISO-01 Isolation & Resource Hardening
- **Primary Responsibility:** Container containment, CPU (0.5), memory (256MB), PID (32) limits, workspace directory byte ceilings (10 MB), file count ceilings (100 files), and timeout termination.
- **Tasks Owned:** Tasks 13, 14, 15.
- **Files Owned:**
  - `src/responsibleai/isolation/models.py` [MODIFY]
  - `src/responsibleai/isolation/filesystem.py` [MODIFY]
  - `src/responsibleai/isolation/container_backend.py` [MODIFY]
  - `tests/isolation/test_resource_limits.py` [CREATE]
  - `tests/isolation/test_filesystem.py` [CREATE]
  - `tests/isolation/test_container_backend.py` [CREATE]
- **Lane Independence:** Zero dependencies on runtime admission, queues, or Redis. Can execute 100% in parallel from Day 1.

---

### Lane C1: Worker Lease Schema & DB Exclusivity
- **Primary Responsibility:** Worker lease table schema (migration `0050`), partial unique index on active executions, `WorkerLease` model, and `AdmissionLeaseRepository` with row-level locks.
- **Tasks Owned:** Task 9.
- **Files Owned:**
  - `migrations/versions/0050_runtime_worker_leases.py` [CREATE]
  - `src/responsibleai/runtime/worker/lease.py` [CREATE]
  - `src/responsibleai/db/admission_lease_repository.py` [CREATE]
  - `tests/runtime/test_worker_lease.py` [CREATE]
  - `tests/db/test_admission_lease_repository.py` [CREATE]
  - `tests/runtime/test_worker_lease_db_concurrency.py` [CREATE]

---

### Lane C2: Crash Recovery & Worker Supervision
- **Primary Responsibility:** Worker process execution loop, heartbeat streams, background lease reaper for dead workers, and `UNCERTAIN` state handling for interrupted external effects.
- **Tasks Owned:** Tasks 10, 11, 12.
- **Files Owned:**
  - `src/responsibleai/runtime/dispatcher.py` [CREATE]
  - `src/responsibleai/runtime/worker/worker.py` [CREATE]
  - `src/responsibleai/runtime/worker/supervisor.py` [CREATE]
  - `tests/runtime/test_dispatcher.py` [CREATE]
  - `tests/runtime/test_execution_worker.py` [CREATE]
  - `tests/runtime/test_crash_recovery.py` [CREATE]
  - `tests/runtime/test_external_effect_idempotency.py` [CREATE]
- **Lane Dependency:** Strictly depends on Integration Gate (Task 10).

---

### Lane D: Operations, Health & Telemetry
- **Primary Responsibility:** Registering 15 Prometheus runtime metrics under `whitepact_*`, decoupling Kubernetes `/livez` and `/readyz` probe routes, graceful shutdown signal integration, and configuration bounds validation.
- **Tasks Owned:** Tasks 16, 17, 18, 21.
- **Files Owned:**
  - `src/responsibleai/dashboard/prometheus.py` [MODIFY]
  - `src/responsibleai/runtime/health.py` [CREATE]
  - `src/responsibleai/runtime/shutdown.py` [CREATE]
  - `src/responsibleai/dashboard/app.py` [MODIFY]
  - `src/responsibleai/dashboard/config.py` [MODIFY]
  - `tests/dashboard/test_runtime_metrics.py` [CREATE]
  - `tests/dashboard/test_health_probes.py` [CREATE]
  - `tests/runtime/test_graceful_shutdown.py` [CREATE]
  - `tests/dashboard/test_runtime_config_bounds.py` [CREATE]

---

### Lane E: Multi-Process Real Infrastructure Integration & Freeze
- **Primary Responsibility:** Multi-process independent OS process race tests against real PostgreSQL and real Redis (`test_multi_process_lease_and_admission_race.py`), real Docker container integration, canonical security regression, candidate freeze.
- **Tasks Owned:** Tasks 19, 20, 22.
- **Files Owned:**
  - `tests/runtime/conftest.py` [CREATE]
  - `tests/runtime/test_multi_process_lease_and_admission_race.py` [CREATE]
  - `tests/runtime/test_real_infra_distributed.py` [CREATE]
  - `tests/runtime/test_phase7a_security_regression.py` [CREATE]
  - `docs/phase7a-execution/*` [UPDATE]

---

## 3. Parallel Execution Timeline and Activation Gates

```
TIME ──────────────────────────────────────────────────────────────────────────────────────────►
[Approved Canonical Base: 13e8de0 | Head: 0048]
   │
   ├── WAVE 1: FOUNDATIONS & LEAF CONTRACTS
   │   ├── Subagent 1 (Lane A1): Task 1 (Admission Models)
   │   │   └── then Task 2 (Local Controller) & Task 3 (Coordination Base)
   │   ├── Subagent 2 (Lane B):  Task 13 (Compute Limits) & Task 14 (Workspace 10MB/100 Files)
   │   └── Subagent 3 (Lane D):  Task 18 (15 Prometheus Metrics)
   │
   ├── WAVE 2: PERSISTENCE, CONCURRENCY & ISOLATION
   │   ├── Subagent 1 (Lane A1): Task 4 (Redis Coordinator) -> Task 5 (Fail-Closed) -> Task 6 (Concurrency) -> Task 7 (Fair Queue)
   │   ├── Subagent 4 (Lane A2): Task 8A (Mig 0049, Centralized Issuer, All-Path Issuance) -> Task 8B (Atomic admit_execution, Context)
   │   ├── Subagent 5 (Lane C1): Task 9 (Mig 0050 & Worker Lease Exclusivity) [after 8A commits 0049]
   │   ├── Subagent 2 (Lane B):  Task 15 (Container Timeout/Cancellation)
   │   └── Subagent 3 (Lane D):  Task 21 (Config Bounds Audit)
   │
   ├── INTEGRATION GATE: TASK 10 DISPATCHER ACTIVATION
   │   Preconditions:
   │   1. All 3 production authorize_execution issuance paths closed (durable PG persistence).
   │   2. Single canonical admit_execution ownership proven (AdmittedExecution context handoff).
   │   └── Subagent 6: Task 10 (Worker Dispatcher & Execution Worker Gate)
   │
   ├── WAVE 3: WORKER RECOVERY, SHUTDOWN & HEALTH
   │   ├── Subagent 6 (Lane C2): Task 11 (Worker Heartbeats & Stale Reaper) -> Task 12 (Uncertain Side-Effects)
   │   └── Subagent 3 (Lane D):  Task 16 (Graceful Shutdown) -> Task 17 (Health Probes)
   │
   └── WAVE 4: REAL INFRASTRUCTURE INTEGRATION & CANONICAL FREEZE
       └── Subagent 7 (Lane E): Task 19 (Multi-Process PG/Redis/Docker Suite)
                                 -> Task 20 (Phase 7A Security Regression)
                                 -> Task 22 (Evidence Pack & Freeze)
```
