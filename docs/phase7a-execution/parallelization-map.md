# WhitePact Phase 7A Fast-Track Parallelization Map

**Document Status:** CANONICAL SPECIFICATION PASS 2 (ATOMIC AUTHORITY INTEGRATION CORRECTION)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Fast-Track Principles

1. **Disjoint File Sets:** No two parallel lanes may edit or create the same source or test file.
2. **Disjoint Invariants:** Each lane owns a separate security dimension.
3. **Strict Gate Sequencing:** Tasks with functional dependencies across lanes must pass explicit integration gates. Specifically, crash recovery and side-effect handling (Lane C2) cannot begin until the dispatcher integration gate (Task 10) is verified green.
4. **Plan-Neutrality:** Fairness across all lanes is strictly plan-neutral.
5. **Stable Contracts:** Inter-lane communication relies exclusively on immutable typed dataclasses and abstract interfaces defined upfront in Task 1.

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
- **Primary Responsibility:** Durable `ExecutionAuthorization` storage (migration `0049`), repository, durable issuance integration before queueing in `mcp/governance_integration.py`, two-stage revalidation, and single atomic admission transaction in `db/execution_nonce_repository.py` and `governance/execution.py`.
- **Tasks Owned:** Tasks 8A, 8B.
- **Files Owned:**
  - `migrations/versions/0049_runtime_execution_authorizations.py` [CREATE]
  - `src/responsibleai/db/execution_authorization_repository.py` [CREATE]
  - `src/responsibleai/mcp/governance_integration.py` [MODIFY] (Durable Issuance Phase)
  - `src/responsibleai/db/execution_nonce_repository.py` [MODIFY] (Atomic Combined Transaction)
  - `src/responsibleai/governance/execution.py` [MODIFY] (Canonical Admission Gate)
  - `src/responsibleai/runtime/revalidation.py` [CREATE]
  - `tests/runtime/test_durable_execution_authorization.py` [CREATE]
  - `tests/runtime/test_durable_issuance.py` [CREATE]
  - `tests/runtime/test_atomic_admission.py` [CREATE]
  - `tests/runtime/test_revalidation.py` [CREATE]

---

### Lane B: WP-ISO-01 Isolation & Resource Hardening
- **Primary Responsibility:** Container containment, CPU (0.5), memory (256MB), PID (32) limits, workspace directory byte ceilings (10 MB), file count ceilings (100 files), and timeout termination.
- **Tasks Owned:** Tasks 13, 14, 15.
- **Files Owned:**
  - `src/responsibleai/isolation/models.py` [MODIFY]
  - `src/responsibleai/isolation/filesystem.py` [MODIFY]
  - `src/responsibleai/isolation/container_backend.py` [MODIFY]
  - `tests/isolation/test_wp_iso_01_*.py` [CREATE]
  - `tests/isolation/test_container_cancellation.py` [CREATE]

---

### Lane C1: Worker Lease Schema & Database Exclusivity
- **Primary Responsibility:** Worker lease lifecycle, execution-keyed lease identity (`execution_id`, `attempt`), database schema migration `0050` (down_revision `0049`), PostgreSQL partial unique index on `ACTIVE` leases, and row-level locking.
- **Tasks Owned:** Task 9.
- **Files Owned:**
  - `migrations/versions/0050_runtime_worker_leases.py` [CREATE]
  - `src/responsibleai/runtime/worker/lease.py` [CREATE]
  - `src/responsibleai/db/admission_lease_repository.py` [CREATE]
  - `tests/runtime/test_worker_lease.py` [CREATE]
  - `tests/runtime/test_worker_lease_db_concurrency.py` [CREATE]

---

### INTEGRATION GATE: Task 10 — Worker Dispatcher & Canonical Admission Bridge
- **Primary Responsibility:** Decouples inline execution in `mcp/governance_integration.py` into enqueue and worker dispatch. Bridges queue tickets to worker execution loop, enforces Stage 1 early invalidation, acquires worker lease, and invokes canonical `admit_execution()`.
- **Task Owned:** Task 10.
- **Files Owned:**
  - `src/responsibleai/runtime/dispatcher.py` [CREATE]
  - `src/responsibleai/runtime/worker/worker.py` [CREATE]
  - `src/responsibleai/mcp/governance_integration.py` [MODIFY] (Dispatcher Route Phase)
  - `tests/runtime/test_dispatcher.py` [CREATE]
  - `tests/runtime/test_execution_worker.py` [CREATE]
- **Gate Pre-requisites:** Lane A1 (Tasks 1-7), Lane A2 (Tasks 8A, 8B), and Lane C1 (Task 9).

---

### Lane C2: Worker Recovery, Heartbeats & Side-Effect Safety
- **Primary Responsibility:** Worker pool supervisor, heartbeat stream renewal, stale lease background reaper, and external side-effect uncertainty management (`UNCERTAIN` state handling, zero blind replays).
- **Tasks Owned:** Tasks 11, 12.
- **Files Owned:**
  - `src/responsibleai/runtime/worker/supervisor.py` [CREATE]
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
   ├─► LANE A1: Admission & Coordination (Tasks 1-7) ─────────────────────────► [GATE A1 PASS]
   │                                                                                 │
   ├─► LANE A2: Durable Issuance & Atomic Admission (Tasks 8A, 8B) ───────────► [GATE A2 PASS]
   │     │                                                                           │
   │     └─► LANE C1: Worker Lease Schema & DB Exclusivity (Task 9) ──► [GATE C1 PASS]│
   │                                                                           │     │
   ├─► LANE B: WP-ISO-01 Isolation Hardening (Tasks 13-15) ────────────────────┼─────┤
   │                                                                           │     │
   ├─► LANE D1: Config & Metrics Foundation (Tasks 18, 21) ────────────────────┼─────┤
   │                                                                           ▼     ▼
   │                                                      [INTEGRATION GATE: TASK 10 DISPATCHER]
   │                                                       (Requires Gate A1, A2, and Gate C1)
   │                                                                           │
   ├───────────────────────────────────────────────────────────────────────────┴─────┐
   │                                                                                 │
   ├─► LANE C2: Worker Recovery, Heartbeats & Side-Effects (Tasks 11, 12) ───────────┤
   │                                                                                 │
   ├─► LANE D2: Graceful Shutdown & Decoupled Health Probes (Tasks 16, 17) ──────────┤
   │                                                                                 │
   ▼                                                                                 ▼
[MILESTONE: ALL COMPONENT GATES GREEN]
   │
   └─► LANE E: Multi-Process Integration & Security Regression (Tasks 19, 20, 22)
         │
         ▼
[PHASE 7A CANDIDATE FREEZE READY FOR CODEX FINAL REVIEW]
```
