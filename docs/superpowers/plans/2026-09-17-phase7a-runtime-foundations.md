# WhitePact Phase 7A Runtime Foundations Implementation Plan

**Document Status:** Approved Implementation Master Execution Plan
**Goal:** Implement resilient, multi-tenant runtime admission control, bounded fair queueing, distributed worker leases, crash recovery, WP-ISO-01 resource limits, two-phase graceful shutdown, and decoupled health probes without compromising canonical governance authority.
**Architecture:** Distributed Runtime Foundations with decoupled admission, ephemeral Redis coordination, durable PostgreSQL lease checkpoints, and air-gapped Docker container execution.
**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Redis 7, Docker, Prometheus Client.
**Spec:** `docs/phase7a-prep/PHASE7A_RUNTIME_FOUNDATIONS_MASTER_DESIGN.md`
**Base Candidate SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c`
**Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Alembic Head:** `0048` (`0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Global Invariants and Constraints

1. **Codex Prerequisite:** The authentication candidate (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`) must be formally approved by Codex before Phase 7A implementation execution begins. Implementation starts exclusively from the exact approved SHA.
2. **Authority Decoupling:** Governance Authorization (`ExecutionAuthorization`) != Admission (Capacity Slot) != Queue Token != Worker Lease != Redis State.
3. **No Authority Widening:** Capacity tokens or worker leases can never bestow, elevate, or synthesize governance authority.
4. **No DENY Bypass:** If policy evaluation yields `DENY`, execution is immediately halted before admission evaluation. Admission controllers cannot evaluate or admit denied requests.
5. **No EA Bypass:** No worker may invoke tool execution without a valid, active, non-expired `ExecutionAuthorization` verified against PostgreSQL.
6. **Redis Non-Canonical:** Redis stores only ephemeral counters, semaphores, and transient dispatch metadata. Authority, Policy, Approval, EA, BreakGlass, and Evidence remain exclusively in PostgreSQL.
7. **Fail-Closed Coordination:** If Redis fails, times out, or partitions, the runtime fails closed to HTTP 503 (Capacity Unavailable) or local process limits. It never fails open to unmetered execution.
8. **Docker Air-Gap Invariant:** Direct container networking is strictly disabled via `--network=none`. WP-ISO-01 CPU (0.5), RAM (256MB), PID (32), workspace (10MB), and file count (100) limits are enforced.
9. **Test-First Methodology:** Every implementation step strictly follows RED (failing test) -> GREEN (minimal implementation) -> REFACTOR -> VERIFY -> COMMIT. No production code is committed without its preceding failing test.
10. **Zero Premature Claims:** No claims of 10k readiness or production deployment are made during Phase 7A. High-scale stress validation is deferred to Phase 7C.

---

## 2. Master Implementation Tasks (1 through 22)

### Task 1: Admission Domain Model and State Machine
- **Files:**
  - CREATE `src/responsibleai/runtime/admission/models.py`
  - CREATE `tests/runtime/test_admission_models.py`
- **Interfaces Consumed:** None (foundation leaf models).
- **Interfaces Produced:** Enums `AdmissionState` (`ADMITTED`, `QUEUED`, `CAPACITY_DELAYED`, `REJECTED_LIMIT`, `CANCELLED`, `EXPIRED`, `RUNNING`, `COMPLETED`, `FAILED`, `TIMED_OUT`), `AdmissionRejectionReason`, dataclasses `CapacityReservation`, `AdmissionDecision`.
- **Step 1 Failing Test:** Write `tests/runtime/test_admission_models.py` asserting legal state transitions and rejecting invalid transitions (e.g., cannot transition directly from `REJECTED_LIMIT` to `RUNNING`).
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_admission_models.py -v`
  Verify failure: `ModuleNotFoundError: No module named 'responsibleai.runtime.admission'`.
- **Step 3 Minimal Code:** Implement `src/responsibleai/runtime/admission/models.py` with explicit state validation and dataclass definitions.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_admission_models.py -v`
  Verify: 100% pass.
- **Step 5 Focused Regression:** Run full unit suite:
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/test_auth_canonical_seams.py -q`
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/models.py tests/runtime/test_admission_models.py`
  `git commit -m "feat(runtime): define admission domain models and state machine"`

---

### Task 2: Local Deterministic Admission Controller
- **Files:**
  - CREATE `src/responsibleai/runtime/admission/controller.py`
  - CREATE `tests/runtime/test_admission_controller.py`
- **Interfaces Consumed:** `src/responsibleai/runtime/admission/models.py`.
- **Interfaces Produced:** `ExecutionAdmissionController.reserve_execution(org_id, principal_id, action_class, authorization_id, idempotency_key) -> AdmissionDecision`, `release_execution(reservation_id)`.
- **Step 1 Failing Test:** Write tests in `test_admission_controller.py` attempting sequential and concurrent reservations up to local concurrency threshold, verifying `ADMITTED` outcome when under limit and `CAPACITY_DELAYED` when over limit.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_admission_controller.py -v`
- **Step 3 Minimal Code:** Implement in-process semaphore-backed capacity tracking with thread-safe acquisition in `controller.py`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_admission_controller.py -v`
- **Step 5 Focused Regression:** Run `test_admission_models.py` and `test_admission_controller.py`.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/controller.py tests/runtime/test_admission_controller.py`
  `git commit -m "feat(runtime): implement deterministic in-process admission controller"`

---

### Task 3: Global Concurrency Enforcement
- **Files:**
  - MODIFY `src/responsibleai/runtime/admission/controller.py`
  - CREATE `tests/runtime/test_global_concurrency.py`
- **Interfaces Consumed:** `Settings.max_global_executions` (default 250).
- **Interfaces Produced:** Global ceiling validation ensuring system-wide concurrent executions never exceed 250 containers.
- **Step 1 Failing Test:** Write `tests/runtime/test_global_concurrency.py` simulating 300 simultaneous reservation attempts across distinct tenants; assert exactly 250 succeed with `ADMITTED` and 50 receive `CAPACITY_DELAYED`.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_global_concurrency.py -v`
- **Step 3 Minimal Code:** Add global capacity semaphore in `ExecutionAdmissionController` bounded by `settings.max_global_executions`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_global_concurrency.py -v`
- **Step 5 Focused Regression:** Verify Tasks 1-3 test suite passes.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/controller.py tests/runtime/test_global_concurrency.py`
  `git commit -m "feat(runtime): enforce strict global execution concurrency ceiling"`

---

### Task 4: Per-Tenant Concurrency Enforcement
- **Files:**
  - MODIFY `src/responsibleai/runtime/admission/controller.py`
  - CREATE `tests/runtime/test_tenant_concurrency.py`
- **Interfaces Consumed:** `Settings.max_tenant_executions` (default 25 slots per org).
- **Interfaces Produced:** Per-tenant semaphore tracking in `ExecutionAdmissionController`.
- **Step 1 Failing Test:** Write `tests/runtime/test_tenant_concurrency.py` where Tenant A requests 40 slots; assert slots 1-25 are `ADMITTED`, slots 26-40 are `CAPACITY_DELAYED` or `REJECTED_LIMIT`, while Tenant B immediately acquires slots up to 25 without interference.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_tenant_concurrency.py -v`
- **Step 3 Minimal Code:** Add tenant-keyed slot registry in `ExecutionAdmissionController` with automatic slot reclamation upon `release_execution()`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_tenant_concurrency.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/runtime/ -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/controller.py tests/runtime/test_tenant_concurrency.py`
  `git commit -m "feat(runtime): enforce per-tenant execution quotas and isolation"`

---

### Task 5: Workload-Class Concurrency Partitioning
- **Files:**
  - MODIFY `src/responsibleai/runtime/admission/controller.py`
  - CREATE `tests/runtime/test_workload_concurrency.py`
- **Interfaces Consumed:** Action classification metadata (Standard Tool vs Heavy Compute).
- **Interfaces Produced:** Dual-pool reservation: Standard Pool (200 slots) and Heavy Compute Pool (50 slots).
- **Step 1 Failing Test:** Write `test_workload_concurrency.py` saturating heavy compute pool (50 requests); assert 51st heavy request is delayed, but standard tool execution requests continue to admit successfully into the standard pool.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_workload_concurrency.py -v`
- **Step 3 Minimal Code:** Implement partitioned semaphores by workload category in `ExecutionAdmissionController`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_workload_concurrency.py -v`
- **Step 5 Focused Regression:** Verify all admission controller tests pass.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/controller.py tests/runtime/test_workload_concurrency.py`
  `git commit -m "feat(runtime): implement workload-class capacity partitioning"`

---

### Task 6: Fairness and Bounded Multi-Tenant Queue
- **Files:**
  - CREATE `src/responsibleai/runtime/queue/models.py`
  - CREATE `src/responsibleai/runtime/queue/bounded_queue.py`
  - CREATE `src/responsibleai/runtime/queue/fair_scheduler.py`
  - CREATE `tests/runtime/test_bounded_queue.py`
- **Interfaces Consumed:** `AdmissionDecision`.
- **Interfaces Produced:** `MultiTenantFairQueue.enqueue(item) -> QueueTicket`, `dequeue(worker_id) -> QueuedPayload`, `queue_depth() -> int`.
- **Step 1 Failing Test:** Write `tests/runtime/test_bounded_queue.py` where Tenant A enqueues 500 items, and Tenant B enqueues 5 items. Verify dequeue interleaves items in round-robin fashion, preventing Tenant A from monopolizing dispatch, and verify enqueuing past global queue capacity (2,000) raises `QueueCapacityExceededError`.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_bounded_queue.py -v`
- **Step 3 Minimal Code:** Implement per-tenant FIFO subqueues managed by a deficit round-robin scheduler with a hard global item cap.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_bounded_queue.py -v`
- **Step 5 Focused Regression:** Verify queue bounds and fairness under high concurrency.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/queue/ tests/runtime/test_bounded_queue.py`
  `git commit -m "feat(runtime): implement bounded multi-tenant fair queue"`

---

### Task 7: ExecutionAuthorization Queue-Time Revalidation
- **Files:**
  - CREATE `src/responsibleai/runtime/revalidation.py`
  - CREATE `tests/runtime/test_revalidation.py`
- **Interfaces Consumed:** `ExecutionAuthorization`, `OrgRepository`, `IamRepository`.
- **Interfaces Produced:** `revalidate_queued_authorization(auth_id, org_id, principal_id, session_id, db_session) -> RevalidationResult`.
- **Step 1 Failing Test:** Write `tests/runtime/test_revalidation.py` with 5 explicit failure cases:
  1. Authorization expires while queued.
  2. Tenant transitions to `canceled`/`inactive` while queued.
  3. Principal is revoked while queued.
  4. BreakGlass session expires while queued.
  5. Policy rule modified to explicit DENY while queued.
  Assert all 5 cases return `RevalidationResult.INVALID` with specific reason codes.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_revalidation.py -v`
- **Step 3 Minimal Code:** Implement `revalidate_queued_authorization` reading fresh state from database under snapshot isolation before allowing worker execution.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_revalidation.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/runtime/test_revalidation.py tests/test_auth_canonical_seams.py -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/revalidation.py tests/runtime/test_revalidation.py`
  `git commit -m "security(runtime): enforce queue-time authorization revalidation"`

---

### Task 8: Worker Lease Contract and Database Checkpoint
- **Files:**
  - CREATE `migrations/versions/0049_runtime_worker_leases.py`
  - CREATE `src/responsibleai/runtime/worker/lease.py`
  - CREATE `src/responsibleai/db/admission_lease_repository.py`
  - CREATE `tests/runtime/test_worker_lease.py`
- **Interfaces Consumed:** PostgreSQL database engine (down_revision strictly `0048`).
- **Interfaces Produced:** `AdmissionLeaseRepository.acquire_lease(auth_id, worker_id, ttl_seconds)`, `heartbeat_lease(lease_id)`, `release_lease(lease_id)`.
- **Step 1 Failing Test:** Write `tests/runtime/test_worker_lease.py` verifying:
  1. Two workers attempting to acquire a lease for the same `authorization_id` concurrently: exactly one succeeds, second is rejected.
  2. Expired lease allows acquisition by a second worker.
  3. Heartbeat extends lease expiration.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_worker_lease.py -v`
- **Step 3 Minimal Code:** Create migration `0049` defining `runtime_worker_leases` table with `UNIQUE(authorization_id)` and implement repository using row-level locking.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_worker_lease.py -v`
- **Step 5 Focused Regression:** Verify migration cycle on real PostgreSQL (`0048 -> 0049 -> 0048 -> 0049`).
- **Step 6 Commit:**
  `git add migrations/versions/0049_runtime_worker_leases.py src/responsibleai/runtime/worker/lease.py src/responsibleai/db/admission_lease_repository.py tests/runtime/test_worker_lease.py`
  `git commit -m "feat(runtime): introduce durable worker lease contract and repository"`

---

### Task 9: Worker Dispatcher Separation
- **Files:**
  - CREATE `src/responsibleai/runtime/dispatcher.py`
  - CREATE `src/responsibleai/runtime/worker/worker.py`
  - MODIFY `src/responsibleai/mcp/governance_integration.py`
  - CREATE `tests/runtime/test_dispatcher.py`
- **Interfaces Consumed:** `ExecutionAdmissionController`, `MultiTenantFairQueue`, `AdmissionLeaseRepository`.
- **Interfaces Produced:** `ExecutionDispatcher.dispatch_action()`, `ExecutionWorker.process_next()`.
- **Step 1 Failing Test:** Write `tests/runtime/test_dispatcher.py` demonstrating decoupled execution: HTTP handler returns queued receipt immediately without blocking on container execution; background worker acquires lease, executes tool, and updates outcome.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_dispatcher.py -v`
- **Step 3 Minimal Code:** Decouple direct inline execution in `governance_integration.py` through the dispatcher and implement worker execution loop.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_dispatcher.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/mcp/test_governance_integration.py tests/runtime/test_dispatcher.py -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/dispatcher.py src/responsibleai/runtime/worker/worker.py src/responsibleai/mcp/governance_integration.py tests/runtime/test_dispatcher.py`
  `git commit -m "feat(runtime): decouple inline execution into worker pool dispatch"`

---

### Task 10: Crash Recovery and Stale Lease Reaper
- **Files:**
  - CREATE `src/responsibleai/runtime/worker/supervisor.py`
  - CREATE `tests/runtime/test_crash_recovery.py`
- **Interfaces Consumed:** `AdmissionLeaseRepository`, `ContainerIsolationBackend`.
- **Interfaces Produced:** `WorkerSupervisor.reap_stale_leases() -> int`.
- **Step 1 Failing Test:** Write `tests/runtime/test_crash_recovery.py` simulating worker process death during container execution (heartbeat missing for >15 seconds); verify reaper identifies the dead lease, marks status `WORKER_CRASHED`, cleans up any orphan container, and transitions request state safely.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_crash_recovery.py -v`
- **Step 3 Minimal Code:** Implement background reaper task in `supervisor.py` querying stale leases via `AdmissionLeaseRepository.list_stale_leases()`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_crash_recovery.py -v`
- **Step 5 Focused Regression:** Verify worker lease and supervisor test suites pass.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/worker/supervisor.py tests/runtime/test_crash_recovery.py`
  `git commit -m "feat(runtime): implement worker crash recovery and stale lease reaper"`

---

### Task 11: External Side-Effect Uncertainty and Idempotency
- **Files:**
  - MODIFY `src/responsibleai/runtime/worker/worker.py`
  - CREATE `tests/runtime/test_external_effect_idempotency.py`
- **Interfaces Consumed:** Tool metadata (`is_idempotent: bool`, `has_external_side_effects: bool`).
- **Interfaces Produced:** Explicit outcome resolution for crashed or timed-out workers.
- **Step 1 Failing Test:** Write `test_external_effect_idempotency.py` with a non-idempotent tool that crashes during execution; assert reaper records state `UNCERTAIN_EXTERNAL_EFFECT` and REFUSES automatic re-execution. For an idempotent tool, assert safe retry is permitted.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_external_effect_idempotency.py -v`
- **Step 3 Minimal Code:** Add side-effect classification logic in worker failure handler; prevent blind replay of uncertain actions.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_external_effect_idempotency.py -v`
- **Step 5 Focused Regression:** Verify zero duplicate executions for non-idempotent actions.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/worker/worker.py tests/runtime/test_external_effect_idempotency.py`
  `git commit -m "security(runtime): guard external side-effects against blind replay"`

---

### Task 12: Redis Distributed Coordination
- **Files:**
  - CREATE `src/responsibleai/runtime/coordination/base.py`
  - CREATE `src/responsibleai/runtime/coordination/redis_coordinator.py`
  - CREATE `tests/runtime/test_redis_coordinator.py`
- **Interfaces Consumed:** `aioredis` / `redis.asyncio` client.
- **Interfaces Produced:** `RedisDistributedCoordinator.acquire_semaphore(key, limit, ttl)`, `release_semaphore(key)`.
- **Step 1 Failing Test:** Write `tests/runtime/test_redis_coordinator.py` testing distributed semaphores and concurrency locks across simulated concurrent clients against mock and real Redis.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_redis_coordinator.py -v`
- **Step 3 Minimal Code:** Implement Lua script-backed atomic semaphore acquisition with TTL expirations in `redis_coordinator.py`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_redis_coordinator.py -v`
- **Step 5 Focused Regression:** Verify distributed semaphore correctness.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/coordination/ tests/runtime/test_redis_coordinator.py`
  `git commit -m "feat(runtime): implement redis distributed coordination primitives"`

---

### Task 13: Redis Failure / Fail-Closed Behavior
- **Files:**
  - MODIFY `src/responsibleai/runtime/admission/controller.py`
  - CREATE `tests/runtime/test_redis_fail_closed.py`
- **Interfaces Consumed:** `RedisDistributedCoordinator`.
- **Interfaces Produced:** Fail-closed exception handling when Redis is unreachable or timing out.
- **Step 1 Failing Test:** Write `tests/runtime/test_redis_fail_closed.py` simulating Redis network partitions, connection timeouts, and command errors; assert admission controller refuses execution with HTTP 503 (`CAPACITY_COORDINATION_FAILED`) and NEVER allows unmetered execution.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_redis_fail_closed.py -v`
- **Step 3 Minimal Code:** Wrap Redis coordination calls in strict try/except blocks falling back to safe local rejection.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_redis_fail_closed.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/runtime/test_redis_fail_closed.py -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/controller.py tests/runtime/test_redis_fail_closed.py`
  `git commit -m "security(runtime): enforce fail-closed behavior on redis failure"`

---

### Task 14: WP-ISO-01 CPU / Memory / PID Limits
- **Files:**
  - MODIFY `src/responsibleai/isolation/models.py`
  - MODIFY `src/responsibleai/isolation/container_backend.py`
  - CREATE `tests/isolation/test_wp_iso_01_compute_limits.py`
- **Interfaces Consumed:** `ResourceLimits`.
- **Interfaces Produced:** Enforcement of Docker execution arguments: `--cpus=0.5`, `--memory=256m`, `--pids-limit=32`.
- **Step 1 Failing Test:** Write `tests/isolation/test_wp_iso_01_compute_limits.py` asserting that generated Docker command-line arguments strictly include CPU, memory, and PID limits, and verify OOM/PID-bomb workloads are killed deterministically.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_wp_iso_01_compute_limits.py -v`
- **Step 3 Minimal Code:** Update `ContainerIsolationBackend._build_run_command()` to inject exact flags from `ResourceLimits`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_wp_iso_01_compute_limits.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/isolation/ -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/isolation/models.py src/responsibleai/isolation/container_backend.py tests/isolation/test_wp_iso_01_compute_limits.py`
  `git commit -m "feat(isolation): enforce WP-ISO-01 CPU memory and PID limits"`

---

### Task 15: WP-ISO-01 Workspace / File / Output Limits
- **Files:**
  - MODIFY `src/responsibleai/isolation/models.py`
  - MODIFY `src/responsibleai/isolation/filesystem.py`
  - CREATE `tests/isolation/test_wp_iso_01_filesystem_limits.py`
- **Interfaces Consumed:** `ResourceLimits.max_workspace_bytes` (10MB), `max_workspace_files` (100).
- **Interfaces Produced:** Pre-flight and runtime workspace size and file count enforcement.
- **Step 1 Failing Test:** Write `tests/isolation/test_wp_iso_01_filesystem_limits.py` asserting:
  1. Writing 101 files raises `WorkspaceLimitExceededError`.
  2. Writing a file exceeding 10 MB total workspace size raises `WorkspaceLimitExceededError`.
  3. Output stdout/stderr exceeding 64 KB is safely truncated with an indicator.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_wp_iso_01_filesystem_limits.py -v`
- **Step 3 Minimal Code:** Implement aggregate file counting and byte summation in `EphemeralWorkspace.populate()` and output truncation in `ContainerIsolationBackend`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_wp_iso_01_filesystem_limits.py -v`
- **Step 5 Focused Regression:** Verify workspace and isolation suites pass.
- **Step 6 Commit:**
  `git add src/responsibleai/isolation/models.py src/responsibleai/isolation/filesystem.py tests/isolation/test_wp_iso_01_filesystem_limits.py`
  `git commit -m "feat(isolation): enforce WP-ISO-01 workspace file count and output limits"`

---

### Task 16: Timeout and Cancellation
- **Files:**
  - MODIFY `src/responsibleai/isolation/container_backend.py`
  - CREATE `tests/isolation/test_container_cancellation.py`
- **Interfaces Consumed:** `ResourceLimits.wall_timeout_seconds` (15.0s).
- **Interfaces Produced:** Forced process termination and container removal on timeout or cancellation.
- **Step 1 Failing Test:** Write `tests/isolation/test_container_cancellation.py` executing a container with `sleep 30`; assert container is terminated within 15.5s, exit code reflects timeout, and container is forcibly removed (`docker rm -f`).
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_container_cancellation.py -v`
- **Step 3 Minimal Code:** Implement async timeout wrapper with guaranteed container cleanup on `asyncio.TimeoutError`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_container_cancellation.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/isolation/ -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/isolation/container_backend.py tests/isolation/test_container_cancellation.py`
  `git commit -m "feat(isolation): implement deterministic timeout cancellation and container cleanup"`

---

### Task 17: Graceful Shutdown Supervisor
- **Files:**
  - CREATE `src/responsibleai/runtime/shutdown.py`
  - MODIFY `src/responsibleai/dashboard/app.py`
  - CREATE `tests/runtime/test_graceful_shutdown.py`
- **Interfaces Consumed:** FastAPI lifespan context, active container registry.
- **Interfaces Produced:** `GracefulShutdownSupervisor.initiate_drain()`, `is_draining() -> bool`.
- **Step 1 Failing Test:** Write `tests/runtime/test_graceful_shutdown.py` simulating SIGTERM:
  1. Ingestion drain immediately causes `/readyz` to return 503.
  2. Running containers are allowed up to 30s to complete.
  3. Remaining containers killed forcefully at deadline.
  4. Zero orphan containers remain.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_graceful_shutdown.py -v`
- **Step 3 Minimal Code:** Implement two-phase drain supervisor and register signal handlers in FastAPI lifespan.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_graceful_shutdown.py -v`
- **Step 5 Focused Regression:** Run shutdown test suite.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/shutdown.py src/responsibleai/dashboard/app.py tests/runtime/test_graceful_shutdown.py`
  `git commit -m "feat(runtime): implement two-phase graceful shutdown supervisor"`

---

### Task 18: Readiness and Liveness Probe Decoupling
- **Files:**
  - CREATE `src/responsibleai/runtime/health.py`
  - MODIFY `src/responsibleai/dashboard/app.py`
  - CREATE `tests/dashboard/test_health_probes.py`
- **Interfaces Consumed:** `GracefulShutdownSupervisor`, Database connection pool, Redis client.
- **Interfaces Produced:** Decoupled `/livez` and `/readyz` endpoints.
- **Step 1 Failing Test:** Write `tests/dashboard/test_health_probes.py` asserting:
  1. `/livez` returns 200 even when database is degraded (pure event-loop probe).
  2. `/readyz` returns 503 if PostgreSQL connection fails.
  3. `/readyz` returns 503 if database migration is behind head (`< 0048`).
  4. `/readyz` returns 503 when `is_draining()` is True.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/dashboard/test_health_probes.py -v`
- **Step 3 Minimal Code:** Implement `HealthChecker` in `health.py` and mount distinct probe handlers in `app.py`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/dashboard/test_health_probes.py -v`
- **Step 5 Focused Regression:** Verify health and API endpoints pass.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/health.py src/responsibleai/dashboard/app.py tests/dashboard/test_health_probes.py`
  `git commit -m "feat(ops): decouple kubernetes liveness and readiness health probes"`

---

### Task 19: Phase 7A Observability and Telemetry
- **Files:**
  - MODIFY `src/responsibleai/dashboard/prometheus.py`
  - CREATE `tests/dashboard/test_runtime_metrics.py`
- **Interfaces Consumed:** Prometheus Client Registry.
- **Interfaces Produced:** 15 metrics under `whitepact_*` (admission counts, queue depths, active leases, durations).
- **Step 1 Failing Test:** Write `tests/dashboard/test_runtime_metrics.py` verifying metrics are registered, exported on `/metrics`, incremented on admission/execution events, and contain bounded label sets.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/dashboard/test_runtime_metrics.py -v`
- **Step 3 Minimal Code:** Declare and wire metrics in `prometheus.py`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/dashboard/test_runtime_metrics.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/dashboard/ -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/dashboard/prometheus.py tests/dashboard/test_runtime_metrics.py`
  `git commit -m "feat(observability): register Phase 7A runtime prometheus metrics"`

---

### Task 20: Real Infrastructure Distributed Integration Tests
- **Files:**
  - CREATE `tests/runtime/test_real_infra_distributed.py`
- **Interfaces Consumed:** Real PostgreSQL, Real Redis, Real Docker daemon.
- **Interfaces Produced:** Multi-process distributed integration suite.
- **Step 1 Failing Test:** Write tests exercising:
  1. 40 concurrent workers across 2 processes competing for execution leases in PostgreSQL.
  2. Redis distributed semaphore under network latency.
  3. Real Docker container executing with WP-ISO-01 limits.
  4. Graceful shutdown of worker nodes while containers are active.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_real_infra_distributed.py -v`
- **Step 3 Minimal Code:** Refine coordination timeouts and integration plumbing.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_real_infra_distributed.py -v`
- **Step 5 Focused Regression:** Verify real infrastructure tests pass cleanly.
- **Step 6 Commit:**
  `git add tests/runtime/test_real_infra_distributed.py`
  `git commit -m "test(runtime): add real infrastructure distributed integration suite"`

---

### Task 21: Phase 7A Canonical Security Regression
- **Files:**
  - CREATE `tests/runtime/test_phase7a_security_regression.py`
- **Interfaces Consumed:** Full runtime and governance pipeline.
- **Interfaces Produced:** Canonical regression suite verifying all 14 Phase 7A security invariants.
- **Step 1 Failing Test:** Write tests explicitly attempting:
  1. Authority widening via admission token (must fail).
  2. DENY policy bypass via admission queue (must fail).
  3. ExecutionAuthorization bypass via direct worker call (must fail).
  4. Cross-tenant execution slot hijacking (must fail).
  5. Stale authorization execution (must fail).
  6. Egress escape from container (must fail).
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_phase7a_security_regression.py -v`
- **Step 3 Minimal Code:** Verify all guards are sealed.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_phase7a_security_regression.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/test_auth_canonical_seams.py tests/test_auth_real_postgres.py tests/runtime/ -q`.
- **Step 6 Commit:**
  `git add tests/runtime/test_phase7a_security_regression.py`
  `git commit -m "security(runtime): add canonical Phase 7A security regression suite"`

---

### Task 22: Candidate Freeze and Review Evidence Pack
- **Files:**
  - CREATE `docs/phase7a-execution/implementation-evidence.md`
- **Interfaces Consumed:** Full test suite run outputs, git diff, coverage reports.
- **Interfaces Produced:** Verification evidence pack for independent Codex and CodeRabbit review.
- **Step 1 Verification:**
  1. Run full test suite twice from clean processes:
     `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/ -q`
  2. Run static gates:
     `git diff --check`
     `/Users/ag/Whitepact/.venv/bin/ruff check .`
     `/Users/ag/Whitepact/.venv/bin/mypy src/`
     `python3 scripts/manage_license_headers.py --check`
     `gitleaks detect -v`
     `/Users/ag/Whitepact/.venv/bin/alembic -c alembic.ini heads` (must equal 1: `0049`)
- **Step 2 Evidence Compilation:** Record exact outputs and commit hashes in `docs/phase7a-execution/implementation-evidence.md`.
- **Step 3 Commit:**
  `git add docs/phase7a-execution/implementation-evidence.md`
  `git commit -m "docs(phase7): freeze Phase 7A implementation evidence pack"`
