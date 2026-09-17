# WhitePact Phase 7A: Concrete Parallelization Map & Subagent Task Plan

**Document Status:** CANONICAL SPECIFICATION PASS 4.3 (SECURITY BOUNDARY CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Proposed Migrations:** `0049_runtime_execution_requests.py` through `0052_runtime_worker_leases.py`

---

## 1. Overview and Invariants

This document establishes the verified concurrent execution waves for Phase 7A implementation. It eliminates race conditions, ensures zero file collisions across concurrent lanes, and enforces the mandatory activation gate for the worker dispatcher.

### Core Concurrency Rules:
1. **Zero File Collisions:** No two subagents or tasks in the same wave may write to the same file.
2. **Linear Migration Sequencing:** Migration `0049` -> `0050` -> `0051` -> `0052`.
3. **Dispatcher Activation Gate (Task 10 Gate):** Task 10 requires all 16 security prerequisites proven in implementation before activation.
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

### Lane Schema & Persistence: Migrations & Repositories (Lane S)
- **Primary Responsibility:** Sequential PostgreSQL migrations `0049` through `0052` and their respective domain repositories.
- **Tasks Owned:** Tasks 8A1, 8A2, 8A3, 8A4.
- **Files Owned:**
  - `migrations/versions/0049_runtime_execution_requests.py` [CREATE]
  - `src/responsibleai/db/execution_request_repository.py` [CREATE]
  - `migrations/versions/0050_runtime_execution_authorizations.py` [CREATE]
  - `src/responsibleai/db/execution_authorization_repository.py` [CREATE]
  - `migrations/versions/0051_runtime_execution_attempts.py` [CREATE]
  - `src/responsibleai/db/execution_attempt_repository.py` [CREATE]
  - `migrations/versions/0052_runtime_worker_leases.py` [CREATE]
  - `src/responsibleai/db/execution_fence_repository.py` [CREATE]
  - `src/responsibleai/runtime/worker/lease.py` [CREATE]
  - `src/responsibleai/db/admission_lease_repository.py` [CREATE]

---

### Lane A2: Centralized Issuance & Canonical Admission
- **Primary Responsibility:** Centralized issuance service (`DurableExecutionAuthorizationIssuer`), approval atomicity (`ApprovalExecutionService`), universal epoch invalidation (all 14 mutations), and canonical admission transaction (`admit_execution`).
- **Tasks Owned:** Tasks 8A5, 8B.
- **Files Owned:**
  - `src/responsibleai/governance/execution_issuer.py` [CREATE]
  - `src/responsibleai/governance/approval_service.py` [CREATE]
  - `src/responsibleai/mcp/governance_integration.py` [MODIFY]
  - `src/responsibleai/mcp/upstream_dispatch.py` [MODIFY]
  - `src/responsibleai/db/execution_nonce_repository.py` [MODIFY]
  - `src/responsibleai/governance/execution.py` [MODIFY]
  - `src/responsibleai/iam/session.py` [MODIFY]
  - `src/responsibleai/iam/break_glass.py` [MODIFY]
  - `src/responsibleai/runtime/revalidation.py` [CREATE]

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

---

### Lane C1: Fencing, Backend-Start Claim & Executor Verification
- **Primary Responsibility:** Monotonic fencing, synchronous lease expiry checks, `claim_backend_start()` generating raw `backend_start_token` and storing `backend_start_token_hash`, pre-effect atomic CAS (`claim_local_effect_start`, `claim_external_effect_transmission`) with synchronous lease revalidation `FOR UPDATE`, durable request action/fingerprint binding, and `SafeNetworkBackend` IP pinning.
- **Tasks Owned:** Tasks 9A, 9B.
- **Files Owned:**
  - `src/responsibleai/db/execution_attempt_repository.py` (`claim_backend_start`, `claim_local_effect_start`, `claim_external_effect_transmission`) [MODIFY]
  - `src/responsibleai/governance/execution.py` (`InternalToolExecutor`) [MODIFY]
  - `src/responsibleai/governance/upstream_executor.py` (`UpstreamMCPExecutor`) [MODIFY]
  - `tests/runtime/test_execution_attempt_state_machine.py` [CREATE]
  - `tests/runtime/test_worker_lease_fencing.py` [CREATE]
  - `tests/runtime/test_one_shot_backend_start.py` [CREATE]

---

### Lane C2: Crash Recovery & Worker Supervision
- **Primary Responsibility:** Worker process execution loop, heartbeat streams, background lease reaper for dead workers, Crash Point O evidence reconciliation, capacity reservation reconciliation, and `UNCERTAIN` state handling for interrupted external effects.
- **Tasks Owned:** Tasks 10, 11, 12.
- **Files Owned:**
  - `src/responsibleai/runtime/dispatcher.py` [CREATE]
  - `src/responsibleai/runtime/worker/worker.py` [CREATE]
  - `src/responsibleai/runtime/worker/supervisor.py` [CREATE]
  - `tests/runtime/test_dispatcher.py` [CREATE]
  - `tests/runtime/test_execution_worker.py` [CREATE]
  - `tests/runtime/test_crash_recovery.py` [CREATE]
  - `tests/runtime/test_external_effect_idempotency.py` [CREATE]

---

### Lane D: Operations, Health & Telemetry
- **Primary Responsibility:** Registering 15 Prometheus runtime metrics under `whitepact_*`, decoupling Kubernetes `/livez` and `/readyz` probe routes, graceful shutdown signal integration, configuration bounds validation, and `HOSTED_GOVERNANCE_STRICT`.
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
- **Primary Responsibility:** Multi-process independent OS process race tests against real PostgreSQL and real Redis, real Docker container integration, canonical security regression, candidate freeze.
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
   ├── WAVE 1: FOUNDATIONS & SEQUENTIAL MIGRATIONS
   │   ├── Subagent 1 (Lane A1): Task 1 (Admission Models) -> Task 2 (Local Controller) & Task 3 (Coordination Base)
   │   ├── Subagent 2 (Lane B):  Task 13 (Compute Limits) & Task 14 (Workspace 10MB/100 Files)
   │   ├── Subagent 3 (Lane D):  Task 18 (15 Prometheus Metrics)
   │   └── Subagent 4 (Lane S):  Task 8A1 (Mig 0049) -> Task 8A2 (Mig 0050) -> Task 8A3 (Mig 0051) -> Task 8A4 (Mig 0052)
   │
   ├── WAVE 2: ISSUANCE, CONCURRENCY & CANONICAL ADMISSION
   │   ├── Subagent 1 (Lane A1): Task 4 (Redis Coordinator) -> Task 5 (Fail-Closed) -> Task 6 (Concurrency) -> Task 7 (Fair Queue)
   │   ├── Subagent 5 (Lane A2): Task 8A5 (Centralized Issuance & Approval Atomicity) [after 8A4 completes]
   │   │                         -> Task 8B (Epoch Coverage 14 Mutations, Atomic Admission, AdmissionReceipt)
   │   ├── Subagent 6 (Lane C1): Task 9A (Monotonic Fencing, Synchronous Expiry & claim_backend_start) [after 8A5]
   │   │                         -> Task 9B (Pre-Effect Atomic CAS & SafeNetwork IP Pinning) [after 8B & 9A]
   │   ├── Subagent 2 (Lane B):  Task 15 (Container Timeout/Cancellation)
   │   └── Subagent 3 (Lane D):  Task 21 (Config Bounds & HOSTED_GOVERNANCE_STRICT)
   │
   ├── INTEGRATION GATE: TASK 10 DISPATCHER ACTIVATION
   │   Preconditions: ALL 16 Security Prerequisites Fully Verified
   │   └── Subagent 7: Task 10 (Worker Dispatcher & Execution Worker Gate)
   │
   ├── WAVE 3: WORKER RECOVERY, SHUTDOWN & HEALTH
   │   ├── Subagent 7 (Lane C2): Task 11 (Worker Heartbeats, Reaper & Capacity Reconciler) -> Task 12 (Uncertain Side-Effects)
   │   └── Subagent 3 (Lane D):  Task 16 (Graceful Shutdown) -> Task 17 (Health Probes)
   │
   └── WAVE 4: REAL INFRASTRUCTURE INTEGRATION & CANONICAL FREEZE
       └── Subagent 8 (Lane E): Task 19 (Multi-Process PG/Redis/Docker Suite)
                                 -> Task 20 (Phase 7A Security Regression)
                                 -> Task 22 (Evidence Pack & Freeze)
```
