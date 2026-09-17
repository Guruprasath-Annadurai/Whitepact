# WhitePact Phase 7A Runtime Foundations Implementation Plan

**Document Status:** CANONICAL SPECIFICATION PASS 2 (POST-CODEX REVIEW REMEDIATION)
**Goal:** Implement resilient, multi-tenant runtime admission control, plan-neutral fair queueing, distributed worker leases, crash recovery, WP-ISO-01 resource limits, two-phase graceful shutdown, and decoupled health probes without compromising canonical governance authority.
**Architecture:** Distributed Runtime Foundations with decoupled admission, ephemeral Redis coordination, durable PostgreSQL lease checkpoints, and air-gapped Docker container execution.
**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy, Alembic, PostgreSQL 16, Redis 7, Docker, Prometheus Client.
**Primary Specification:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (`/Users/ag/whitepact-phase7a-runtime-preparation/docs/phase7a-prep/PHASE7A_RUNTIME_FOUNDATIONS_MASTER_DESIGN.md`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Global Constraints and Core Architecture Rules

1. **Approved Canonical Baseline:**
   - The runtime implementation starts strictly from the approved enterprise auth canonical SHA: `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA`).
   - The design artifact (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` in `/Users/ag/whitepact-phase7a-runtime-preparation`) and previous plan artifacts are read-only specification inputs.
   - Documentation branches must NEVER be merged into runtime to make paths exist.

2. **Migration Sequencing:**
   - Migration head is verified as `0048` (`0048_enforce_paddle_binding_atomicity.py`).
   - Phase 7A introduces two clean, independently reversible migrations:
     - `migrations/versions/0049_runtime_execution_authorizations.py` (down_revision: `0048`)
     - `migrations/versions/0050_runtime_worker_leases.py` (down_revision: `0049`)

3. **Commercial / Governance Decoupling:**
   - Commercial entitlement != governance authority.
   - Commercial plan != tenant lifecycle.
   - Commercial subscription_status != tenant deletion / tombstone.
   - Commercial status != ExecutionAuthorization validity.
   - Commercial status != policy evaluation result.
   - Commercial status != approval state.
   - Commercial status != BreakGlass validity.
   - Tenant lifecycle revalidation must query canonical tenant records via `OrgRepository.get_org(org_id)`. Do not use `organizations.subscription_status` as a proxy for tenant liveness.
   - Default Phase 7A fairness is strictly **plan-neutral** (per-tenant round robin). Commercial plan weighting is prohibited in Phase 7A.

4. **Durable Authority Storage & Queue Contract (P0-1):**
   - `ExecutionAuthorization` is an in-memory dataclass today; for Phase 7A async worker execution, it is persisted durably in PostgreSQL (`governance_execution_authorizations`, migration `0049`) at policy decision time.
   - `QueueTicket != authority`. Queue tickets and payloads must NEVER contain reusable authority credentials or serialized permit secrets.
   - Allowed fields: `execution_id`, `authorization_id`, `org_id`, `principal_id`, `action_digest`, `idempotency_key`, `enqueued_at`.
   - Holding an `authorization_id` pointer does not grant authority. Workers load canonical `ExecutionAuthorization` directly from PostgreSQL and revalidate it.

5. **Worker Lease Identity & DB-Enforced Exclusivity (P0-3):**
   - Lease identity is based on `execution_id` and `attempt`.
   - Required lease binding: `lease_id, execution_id, authorization_id, org_id, worker_id, attempt, status, issued_at, expires_at, heartbeat_at, completed_at`.
   - **Database-Enforced Invariant:** Exactly one worker may hold an `ACTIVE` lease for a given `execution_id` at any time, enforced by PostgreSQL partial unique index:
     `CREATE UNIQUE INDEX idx_runtime_worker_leases_active_execution ON runtime_worker_leases (execution_id) WHERE status = 'ACTIVE';`
   - Concurrent lease acquisitions fail closed at the database constraint level.

6. **Distributed Coordination Order & Integration Gate (P0-2, P1-2):**
   - No multi-process execution path may become active while capacity enforcement is process-local only.
   - The worker dispatcher (Task 10) acts as the non-bypassable Integration Gate between Lane A (coordination & durable authority), Lane C1 (worker lease schema), and Lane C2 (worker recovery).
   - The dispatcher loop MUST NOT bypass canonical `admit_execution()`, which executes the singular atomic transaction locking the tenant epoch and burning the nonce.

7. **Side-Effect Safety & Idempotency Guard:**
   - The runtime explicitly separates `execution_id`, `attempt_id`, `effect_id`, and `idempotency_key`.
   - For non-idempotent or uncertain external side effects: a worker crash after external action dispatch but before local acknowledgement must NEVER trigger blind replay.
   - The crash recovery reaper records state `UNCERTAIN`. Worker lease expiry does NOT grant permission to repeat an uncertain external effect.

8. **Two-Stage Authorization Revalidation (P1-1):**
   - Revalidation is strictly partitioned into:
     - **Stage 1: Early Queue Invalidation:** Evaluated by Dispatcher before acquiring lease or burning nonce. Checks EA existence, expiration (`now < expires_at`), unconsumed state (`status == 'ISSUED'`), and tenant lifecycle in `OrgRepository` (active, non-tombstoned).
     - **Stage 2: Final Canonical Admission:** Evaluated by Worker immediately before execution. Checks action digest match, principal/session validity, target fingerprint drift, BreakGlass TTL, delegation chain, and consent proof, followed by atomic `admit_execution()`.
   - Worker dispatch does NOT re-evaluate policy.

9. **Resource & Capacity Bounds Classification:**
   - **Canonical Security Bounds (Verified Existing Defaults):** CPU 0.5 cores, Memory 256 MB, PIDs 32, File Descriptors 128, Timeout 15.0s, Output 64 KB (from `ResourceLimits`).
   - **Internal Starting Assumptions:** 10 MB workspace bytes, 100 workspace files (frozen internal starting bounds from WP-ISO-01 design).
   - **Configurable Provisional Defaults:** Global executions (provisional 250), tenant quota (provisional 25), queue depth (provisional 2000), artifacts (provisional 20), drain timeout (provisional 30.0s).
   - **Extensible Workload Model:** Workload classes are extensible types; fixed 200/50 pool splits are removed and made configurable.
   - **Phase 7C Scale Targets:** 10,000 users, 2,000 req/sec, 250 concurrent containers are performance benchmark targets for Phase 7C, NOT correctness criteria for Phase 7A.

10. **Test-First Methodology:** Every implementation step strictly follows RED (failing test) -> GREEN (minimal implementation) -> REFACTOR -> VERIFY -> COMMIT.

---

## 2. Corrected Implementation Task Sequence (Tasks 1 through 22)

### Task 1: Admission Domain Model and State Machine
- **Files:**
  - CREATE `src/responsibleai/runtime/admission/models.py`
  - CREATE `tests/runtime/test_admission_models.py`
- **Interfaces Consumed:** None.
- **Interfaces Produced:** Enums `AdmissionState` (`ADMITTED`, `QUEUED`, `CAPACITY_DELAYED`, `REJECTED_LIMIT`, `CANCELLED`, `EXPIRED`, `RUNNING`, `COMPLETED`, `FAILED`, `TIMED_OUT`, `UNCERTAIN`), `AdmissionRejectionReason`, dataclasses `CapacityReservation`, `AdmissionDecision`, extensible `WorkloadClass`.
- **Step 1 Failing Test:** Write `tests/runtime/test_admission_models.py` asserting legal state transitions and rejecting invalid transitions. Verify that `AdmissionDecision` cannot be converted into or used as an `ExecutionAuthorization`.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_admission_models.py -v`
  Verify failure: `ModuleNotFoundError: No module named 'responsibleai.runtime.admission'`.
- **Step 3 Minimal Code:** Implement `src/responsibleai/runtime/admission/models.py` with explicit state validation and dataclass definitions.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_admission_models.py -v`
- **Step 5 Focused Regression:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/test_auth_canonical_seams.py -q`
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/models.py tests/runtime/test_admission_models.py`
  `git commit -m "feat(runtime): define admission domain models and state machine"`

---

### Task 2: Local Deterministic Admission Controller & Capacity Contracts
- **Files:**
  - CREATE `src/responsibleai/runtime/admission/controller.py`
  - CREATE `tests/runtime/test_admission_controller.py`
- **Interfaces Consumed:** `src/responsibleai/runtime/admission/models.py`.
- **Interfaces Produced:** `ExecutionAdmissionController.reserve_execution(org_id, principal_id, workload_class, authorization_id, idempotency_key) -> AdmissionDecision`, `release_execution(reservation_id)`.
- **Step 1 Failing Test:** Write tests in `test_admission_controller.py` verifying thread-safe local semaphore reservation up to configured capacity, returning `ADMITTED` under limit and `CAPACITY_DELAYED` over limit.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_admission_controller.py -v`
- **Step 3 Minimal Code:** Implement in-process semaphore-backed capacity tracking in `controller.py`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_admission_controller.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/runtime/ -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/controller.py tests/runtime/test_admission_controller.py`
  `git commit -m "feat(runtime): implement deterministic in-process admission controller"`

---

### Task 3: Distributed Coordination Contract (Abstract Base Class & Mock)
- **Files:**
  - CREATE `src/responsibleai/runtime/coordination/base.py`
  - CREATE `tests/runtime/test_coordination_contract.py`
- **Interfaces Consumed:** None.
- **Interfaces Produced:** Abstract class `DistributedCoordinator` defining `acquire_semaphore(key, limit, ttl)`, `release_semaphore(key)`, `acquire_lease_lock(key, ttl)`, and in-memory `MockDistributedCoordinator`.
- **Step 1 Failing Test:** Write `test_coordination_contract.py` testing interface contracts, TTL expirations, and mock semaphore limits across simulated concurrent tasks.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_coordination_contract.py -v`
- **Step 3 Minimal Code:** Implement `base.py` with full type annotations.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_coordination_contract.py -v`
- **Step 5 Focused Regression:** Verify Tasks 1-3 pass.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/coordination/base.py tests/runtime/test_coordination_contract.py`
  `git commit -m "feat(runtime): define distributed coordinator abstract contract"`

---

### Task 4: Redis Distributed Coordination Implementation
- **Files:**
  - CREATE `src/responsibleai/runtime/coordination/redis_coordinator.py`
  - CREATE `tests/runtime/test_redis_coordinator.py`
- **Interfaces Consumed:** `DistributedCoordinator`, `redis.asyncio` client.
- **Interfaces Produced:** `RedisDistributedCoordinator` executing atomic Lua scripts for token bucket / semaphore counters.
- **Step 1 Failing Test:** Write `test_redis_coordinator.py` testing distributed semaphores against mock and real Redis, asserting atomic decrement/increment.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_redis_coordinator.py -v`
- **Step 3 Minimal Code:** Implement Lua script-backed atomic semaphore acquisition with TTL expirations in `redis_coordinator.py`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_redis_coordinator.py -v`
- **Step 5 Focused Regression:** Verify Redis coordination tests pass.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/coordination/redis_coordinator.py tests/runtime/test_redis_coordinator.py`
  `git commit -m "feat(runtime): implement atomic redis distributed coordinator"`

---

### Task 5: Redis Failure & Fail-Closed Behavior
- **Files:**
  - MODIFY `src/responsibleai/runtime/admission/controller.py`
  - CREATE `tests/runtime/test_redis_fail_closed.py`
- **Interfaces Consumed:** `RedisDistributedCoordinator`.
- **Interfaces Produced:** Strict fail-closed boundary handling: Redis connection drops, command timeouts, or network partitions result in HTTP 503 (`CAPACITY_COORDINATION_FAILED`), NEVER unmetered execution.
- **Step 1 Failing Test:** Write `tests/runtime/test_redis_fail_closed.py` injecting Redis connection drops and timeouts during reservation; assert admission controller strictly rejects execution.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_redis_fail_closed.py -v`
- **Step 3 Minimal Code:** Wrap coordinator calls in `ExecutionAdmissionController` with fail-closed exception handling.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_redis_fail_closed.py -v`
- **Step 5 Focused Regression:** Verify Tasks 1-5 pass.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/controller.py tests/runtime/test_redis_fail_closed.py`
  `git commit -m "security(runtime): enforce fail-closed behavior on redis coordination failure"`

---

### Task 6: Integrated Multi-Tenant Concurrency (Global, Tenant Quota, Workload Classes)
- **Files:**
  - MODIFY `src/responsibleai/runtime/admission/controller.py`
  - CREATE `tests/runtime/test_integrated_concurrency.py`
- **Interfaces Consumed:** `DistributedCoordinator`, `Settings`.
- **Interfaces Produced:** Configurable three-tier concurrency enforcement: global ceiling, per-tenant quota (plan-neutral), and extensible workload class allocation.
- **Step 1 Failing Test:** Write `test_integrated_concurrency.py` asserting:
  1. Global concurrency ceiling blocks reservations when full.
  2. Single tenant hitting per-tenant quota is delayed without starving other tenants.
  3. Workload class allocation functions without hardcoded assumptions.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_integrated_concurrency.py -v`
- **Step 3 Minimal Code:** Implement multi-tier check in `reserve_execution()` using coordinator semaphores.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_integrated_concurrency.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/runtime/ -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/admission/controller.py tests/runtime/test_integrated_concurrency.py`
  `git commit -m "feat(runtime): enforce multi-tenant global and quota concurrency"`

---

### Task 7: Bounded Multi-Tenant Fair Queue (Plan-Neutral)
- **Files:**
  - CREATE `src/responsibleai/runtime/queue/models.py`
  - CREATE `src/responsibleai/runtime/queue/bounded_queue.py`
  - CREATE `src/responsibleai/runtime/queue/fair_scheduler.py`
  - CREATE `tests/runtime/test_bounded_queue.py`
- **Interfaces Consumed:** `AdmissionDecision`.
- **Interfaces Produced:** `MultiTenantFairQueue.enqueue(item) -> QueueTicket`, `dequeue(worker_id) -> QueuedPayload`, `queue_depth() -> int`.
- **Step 1 Failing Test:** Write `test_bounded_queue.py` asserting:
  1. Tenant A enqueuing 500 items and Tenant B enqueuing 5 items results in interleaved round-robin dequeue (zero tenant starvation).
  2. Fairness is strictly plan-neutral (no priority given to commercial plan).
  3. `QueueTicket` contains only reference pointers (`execution_id`, `authorization_id`), zero credentials.
  4. Enqueuing beyond configurable queue depth raises `QueueCapacityExceededError`.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_bounded_queue.py -v`
- **Step 3 Minimal Code:** Implement per-tenant FIFO queues with round-robin scheduler and global bounds.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_bounded_queue.py -v`
- **Step 5 Focused Regression:** Verify queue bounds and fairness pass.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/queue/ tests/runtime/test_bounded_queue.py`
  `git commit -m "feat(runtime): implement bounded plan-neutral multi-tenant fair queue"`

---

### Task 8: Durable ExecutionAuthorization Storage (Migration 0049) & Full Revalidation
- **Files:**
  - CREATE `migrations/versions/0049_runtime_execution_authorizations.py`
  - CREATE `src/responsibleai/db/execution_authorization_repository.py`
  - CREATE `src/responsibleai/runtime/revalidation.py`
  - CREATE `tests/runtime/test_durable_execution_authorization.py`
  - CREATE `tests/runtime/test_revalidation.py`
- **Interfaces Consumed:** `ExecutionAuthorization`, `OrgRepository`, `governance_revocation_epochs`, `SessionService`, `BreakGlassService`.
- **Interfaces Produced:** `ExecutionAuthorizationRepository.create()`, `get()`, `mark_consumed()`, `mark_revoked()`, and `revalidate_queued_authorization()`.
- **Step 1 Failing Test:** Write `tests/runtime/test_durable_execution_authorization.py` and `test_revalidation.py` verifying:
  1. Lossless persistence of all 11 fields (`authorization_id`, `organization_id`, `principal_id`, `action_digest`, `target_fingerprint`, `decision`, `revocation_epoch`, `nonce`, `issued_at`, `expires_at`, `status`).
  2. Authorization survives process restart and queue delay.
  3. Cross-tenant authorization lookup is rejected (`WHERE organization_id = :org_id`).
  4. Early Queue Invalidation rejects expired, consumed, revoked authorizations and deleted/tombstoned tenants.
  5. Pre-flight revalidation verifies action digest match, principal identity, session validity, and BreakGlass TTL.
  6. Policy is NOT re-evaluated.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_durable_execution_authorization.py tests/runtime/test_revalidation.py -v`
- **Step 3 Minimal Code:**
  1. Implement migration `0049` creating `governance_execution_authorizations` table.
  2. Implement `ExecutionAuthorizationRepository` with atomic single-use status transitions.
  3. Implement `revalidation.py` partitioned into Stage 1 (early queue invalidation) and Stage 2 (pre-flight validation).
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_durable_execution_authorization.py tests/runtime/test_revalidation.py -v`
- **Step 5 Focused Regression:** Run migration tests and `pytest tests/runtime/test_durable_execution_authorization.py -q`.
- **Step 6 Commit:**
  `git add migrations/versions/0049_runtime_execution_authorizations.py src/responsibleai/db/execution_authorization_repository.py src/responsibleai/runtime/revalidation.py tests/runtime/test_durable_execution_authorization.py tests/runtime/test_revalidation.py`
  `git commit -m "feat(runtime): introduce durable execution authorization storage and full revalidation"`

---

### Task 9: Worker Lease Contract, Database Migration 0050 & DB-Enforced Exclusivity
- **Files:**
  - CREATE `migrations/versions/0050_runtime_worker_leases.py`
  - CREATE `src/responsibleai/runtime/worker/lease.py`
  - CREATE `src/responsibleai/db/admission_lease_repository.py`
  - CREATE `tests/runtime/test_worker_lease.py`
  - CREATE `tests/runtime/test_worker_lease_db_concurrency.py`
- **Interfaces Consumed:** PostgreSQL database engine (down_revision strictly `0049`).
- **Interfaces Produced:** `AdmissionLeaseRepository.acquire_lease(execution_id, authorization_id, org_id, worker_id, attempt, ttl_seconds)`, `heartbeat_lease(lease_id)`, `finalize_lease(lease_id, status)`.
- **Step 1 Failing Test:** Write `tests/runtime/test_worker_lease.py` and `test_worker_lease_db_concurrency.py` verifying:
  1. Lease identity is keyed on `execution_id` and `attempt`.
  2. Database-enforced mutual exclusion: PostgreSQL partial unique index `idx_runtime_worker_leases_active_execution` on `(execution_id) WHERE status = 'ACTIVE'` prevents concurrent active leases.
  3. Two racing workers competing for the same `execution_id`: exactly one succeeds, the loser catches `IntegrityError` and aborts.
  4. Stale lease heartbeat expiration and clean lease release.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_worker_lease.py tests/runtime/test_worker_lease_db_concurrency.py -v`
- **Step 3 Minimal Code:**
  1. Create migration `0050` with table `runtime_worker_leases` and partial unique index on `ACTIVE`.
  2. Implement `AdmissionLeaseRepository` with row-level `FOR UPDATE` locking and constraint-violation handling.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_worker_lease.py tests/runtime/test_worker_lease_db_concurrency.py -v`
- **Step 5 Focused Regression:** Verify real PostgreSQL migration cycle `0048 -> 0049 -> 0050 -> 0049 -> 0048 -> 0049 -> 0050`.
- **Step 6 Commit:**
  `git add migrations/versions/0050_runtime_worker_leases.py src/responsibleai/runtime/worker/lease.py src/responsibleai/db/admission_lease_repository.py tests/runtime/test_worker_lease.py tests/runtime/test_worker_lease_db_concurrency.py`
  `git commit -m "feat(runtime): introduce db-enforced worker lease exclusivity and repository"`

---

### Task 10: Integration Gate — Worker Dispatcher Decoupling & Canonical admit_execution Bridge
- **Files:**
  - CREATE `src/responsibleai/runtime/dispatcher.py`
  - CREATE `src/responsibleai/runtime/worker/worker.py`
  - MODIFY `src/responsibleai/mcp/governance_integration.py`
  - CREATE `tests/runtime/test_dispatcher.py`
  - CREATE `tests/runtime/test_execution_worker.py`
- **Interfaces Consumed:** `ExecutionAdmissionController`, `MultiTenantFairQueue`, `ExecutionAuthorizationRepository`, `AdmissionLeaseRepository`, `ExecutionNonceRepository`, `revocation_epoch_repository`, canonical `admit_execution()`.
- **Interfaces Produced:** Non-bypassable `ExecutionDispatcher` and `ExecutionWorker.process_next()` pipeline.
- **Step 1 Failing Test:** Write `tests/runtime/test_dispatcher.py` and `test_execution_worker.py` asserting:
  1. Dispatcher decouples admission from immediate inline execution.
  2. Enqueues lightweight `QueueTicket` carrying zero credentials.
  3. Worker pulls ticket, runs Stage 1 Early Queue Invalidation.
  4. Worker acquires exclusive `ACTIVE` lease via `AdmissionLeaseRepository`.
  5. Worker runs Stage 2 Pre-flight Revalidation against durable authorization record.
  6. Worker invokes canonical `admit_execution()`, atomically locking epoch and burning nonce.
  7. No tool execution or container launch is permitted without successful `admit_execution()`.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_dispatcher.py tests/runtime/test_execution_worker.py -v`
- **Step 3 Minimal Code:** Connect `governance_integration.py` to the dispatcher, implement worker loop with canonical `admit_execution()`, and bridge to isolation backend.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_dispatcher.py tests/runtime/test_execution_worker.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/mcp/test_governance_integration.py tests/runtime/test_dispatcher.py tests/runtime/test_execution_worker.py -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/dispatcher.py src/responsibleai/runtime/worker/worker.py src/responsibleai/mcp/governance_integration.py tests/runtime/test_dispatcher.py tests/runtime/test_execution_worker.py`
  `git commit -m "feat(runtime): activate worker dispatcher with non-bypassable canonical admission bridge"`

---

### Task 11: Crash Recovery & Stale Lease Reaper
- **Files:**
  - CREATE `src/responsibleai/runtime/worker/supervisor.py`
  - CREATE `tests/runtime/test_crash_recovery.py`
- **Interfaces Consumed:** Integration Gate Task 10, `AdmissionLeaseRepository`, `ContainerIsolationBackend`.
- **Interfaces Produced:** `WorkerSupervisor.reap_stale_leases() -> int`.
- **Step 1 Failing Test:** Write `test_crash_recovery.py` simulating worker process death during container execution (missing heartbeat); verify reaper identifies the dead lease, marks status `WORKER_CRASHED`, cleans up orphan containers, and releases capacity semaphores.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_crash_recovery.py -v`
- **Step 3 Minimal Code:** Implement background reaper task in `supervisor.py` querying stale leases via `AdmissionLeaseRepository.list_stale_leases()`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_crash_recovery.py -v`
- **Step 5 Focused Regression:** Verify crash recovery suite passes.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/worker/supervisor.py tests/runtime/test_crash_recovery.py`
  `git commit -m "feat(runtime): implement worker crash recovery and stale lease reaper"`

---

### Task 12: External Side-Effect Safety & Idempotency Guard
- **Files:**
  - MODIFY `src/responsibleai/runtime/worker/worker.py`
  - CREATE `tests/runtime/test_external_effect_idempotency.py`
- **Interfaces Consumed:** Integration Gate Task 10, Task 11, tool metadata (`is_idempotent: bool`, `has_external_side_effects: bool`).
- **Interfaces Produced:** Separation of `execution_id`, `attempt_id`, `effect_id`, and `idempotency_key`.
- **Step 1 Failing Test:** Write `test_external_effect_idempotency.py` asserting that a worker crashing after dispatching a non-idempotent action records outcome `UNCERTAIN` and REFUSES automatic replay. Verify lease expiry does NOT grant permission to repeat an uncertain external effect.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_external_effect_idempotency.py -v`
- **Step 3 Minimal Code:** Implement side-effect tracking and explicit `UNCERTAIN` status handling in worker failure routines.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_external_effect_idempotency.py -v`
- **Step 5 Focused Regression:** Verify zero duplicate executions for non-idempotent actions.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/worker/worker.py tests/runtime/test_external_effect_idempotency.py`
  `git commit -m "security(runtime): guard external side-effects against blind replay on lease expiry"`

---

### Task 13: WP-ISO-01 Compute Limits (CPU 0.5, RAM 256MB, PID 32)
- **Files:**
  - MODIFY `src/responsibleai/isolation/models.py`
  - MODIFY `src/responsibleai/isolation/container_backend.py`
  - CREATE `tests/isolation/test_wp_iso_01_compute_limits.py`
- **Interfaces Consumed:** `ResourceLimits` canonical defaults (`cpu_cores=0.5`, `max_memory_mb=256`, `max_pids=32`).
- **Interfaces Produced:** Physical container containment via Docker CLI arguments.
- **Step 1 Failing Test:** Write `test_wp_iso_01_compute_limits.py` asserting generated Docker run commands strictly include `--cpus=0.5`, `--memory=256m`, `--pids-limit=32`, and verify container termination on memory bomb.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_wp_iso_01_compute_limits.py -v`
- **Step 3 Minimal Code:** Inject compute limit flags into `ContainerIsolationBackend._build_run_command()`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_wp_iso_01_compute_limits.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/isolation/ -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/isolation/models.py src/responsibleai/isolation/container_backend.py tests/isolation/test_wp_iso_01_compute_limits.py`
  `git commit -m "feat(isolation): enforce WP-ISO-01 CPU memory and PID limits"`

---

### Task 14: WP-ISO-01 Workspace & File Limits (10MB, 100 Files, 64KB Output)
- **Files:**
  - MODIFY `src/responsibleai/isolation/models.py`
  - MODIFY `src/responsibleai/isolation/filesystem.py`
  - CREATE `tests/isolation/test_wp_iso_01_filesystem_limits.py`
- **Interfaces Consumed:** `ResourceLimits` internal starting bounds (`max_workspace_bytes=10485760`, `max_workspace_files=100`, `max_output_bytes=65536`).
- **Interfaces Produced:** Pre-execution workspace size and file count enforcement.
- **Step 1 Failing Test:** Write `test_wp_iso_01_filesystem_limits.py` asserting:
  1. Creating 101 files in workspace raises `WorkspaceLimitExceededError`.
  2. Writing a file exceeding 10 MB total workspace size raises `WorkspaceLimitExceededError`.
  3. Stdout/stderr exceeding 64 KB is safely truncated.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_wp_iso_01_filesystem_limits.py -v`
- **Step 3 Minimal Code:** Implement aggregate file counting and byte summation in `EphemeralWorkspace.populate()` and output truncation in `ContainerIsolationBackend`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/isolation/test_wp_iso_01_filesystem_limits.py -v`
- **Step 5 Focused Regression:** Verify workspace and filesystem tests pass.
- **Step 6 Commit:**
  `git add src/responsibleai/isolation/models.py src/responsibleai/isolation/filesystem.py tests/isolation/test_wp_iso_01_filesystem_limits.py`
  `git commit -m "feat(isolation): enforce WP-ISO-01 workspace file count and output limits"`

---

### Task 15: Timeout, Cancellation & Container Cleanup
- **Files:**
  - MODIFY `src/responsibleai/isolation/container_backend.py`
  - CREATE `tests/isolation/test_container_cancellation.py`
- **Interfaces Consumed:** `ResourceLimits.wall_timeout_seconds` (15.0s canonical default).
- **Interfaces Produced:** Deterministic process termination and container removal on timeout or cancellation.
- **Step 1 Failing Test:** Write `test_container_cancellation.py` executing a long-running container; assert termination within 15.5s, exit code indicates timeout, and container is forcibly removed (`docker rm -f`).
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

### Task 16: Graceful Shutdown Supervisor (Two-Phase Drain)
- **Files:**
  - CREATE `src/responsibleai/runtime/shutdown.py`
  - MODIFY `src/responsibleai/dashboard/app.py`
  - CREATE `tests/runtime/test_graceful_shutdown.py`
- **Interfaces Consumed:** FastAPI lifespan context, active container registry, `Settings.drain_timeout_seconds` (provisional default 30.0s).
- **Interfaces Produced:** `GracefulShutdownSupervisor.initiate_drain()`, `is_draining() -> bool`.
- **Step 1 Failing Test:** Write `tests/runtime/test_graceful_shutdown.py` simulating SIGTERM:
  1. Ingestion drain causes `/readyz` to return 503 immediately.
  2. Active containers drain within configurable deadline.
  3. Remaining containers forcefully removed; zero orphans remain.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_graceful_shutdown.py -v`
- **Step 3 Minimal Code:** Implement two-phase drain supervisor and hook into FastAPI lifespan.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_graceful_shutdown.py -v`
- **Step 5 Focused Regression:** Run shutdown test suite.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/shutdown.py src/responsibleai/dashboard/app.py tests/runtime/test_graceful_shutdown.py`
  `git commit -m "feat(runtime): implement two-phase graceful shutdown supervisor"`

---

### Task 17: Readiness and Liveness Probe Decoupling
- **Files:**
  - CREATE `src/responsibleai/runtime/health.py`
  - MODIFY `src/responsibleai/dashboard/app.py`
  - CREATE `tests/dashboard/test_health_probes.py`
- **Interfaces Consumed:** `GracefulShutdownSupervisor`, Database connection pool, Redis client.
- **Interfaces Produced:** Decoupled `/livez` and `/readyz` endpoints with 1.0-second TTL caching.
- **Step 1 Failing Test:** Write `tests/dashboard/test_health_probes.py` asserting:
  1. `/livez` returns 200 even when database is degraded (pure event loop probe).
  2. `/readyz` returns 503 if PostgreSQL connection fails.
  3. `/readyz` returns 503 if database migration is behind expected head.
  4. `/readyz` returns 503 when `is_draining()` is True.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/dashboard/test_health_probes.py -v`
- **Step 3 Minimal Code:** Implement `HealthChecker` in `health.py` and mount distinct handlers in `app.py`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/dashboard/test_health_probes.py -v`
- **Step 5 Focused Regression:** Verify health endpoints pass.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/health.py src/responsibleai/dashboard/app.py tests/dashboard/test_health_probes.py`
  `git commit -m "feat(ops): decouple kubernetes liveness and readiness health probes"`

---

### Task 18: Phase 7A Runtime Observability (15 Metrics)
- **Files:**
  - MODIFY `src/responsibleai/dashboard/prometheus.py`
  - CREATE `tests/dashboard/test_runtime_metrics.py`
- **Interfaces Consumed:** Prometheus Client Registry.
- **Interfaces Produced:** 15 metrics under `whitepact_*` (admission counts, queue depths, active leases, execution durations).
- **Step 1 Failing Test:** Write `test_runtime_metrics.py` verifying metrics registration, `/metrics` export, proper incrementing on events, and bounded label cardinality (no high-cardinality execution IDs in labels).
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

### Task 19: Multi-Process Real Infrastructure Integration Tests
- **Files:**
  - CREATE `tests/runtime/test_multi_process_lease_and_admission_race.py`
  - CREATE `tests/runtime/test_real_infra_distributed.py`
- **Interfaces Consumed:** Real PostgreSQL, Real Redis, Real Docker daemon.
- **Interfaces Produced:** Multi-process distributed integration suite testing kernel-level concurrency.
- **Step 1 Failing Test:** Write tests exercising:
  1. Independent OS processes (Process A and Process B via `multiprocessing.Process`) competing for active worker leases and authorization nonce consumption in real PostgreSQL; verify at most 1 process succeeds.
  2. 40 concurrent workers across multiple processes competing for execution leases in real PostgreSQL.
  3. Redis distributed semaphore under simulated network latency and fail-closed partition.
  4. Real Docker container executing with WP-ISO-01 limits.
  5. Graceful shutdown of worker nodes while containers are active.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_multi_process_lease_and_admission_race.py tests/runtime/test_real_infra_distributed.py -v`
- **Step 3 Minimal Code:** Refine coordination timeouts and integration plumbing.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_multi_process_lease_and_admission_race.py tests/runtime/test_real_infra_distributed.py -v`
- **Step 5 Focused Regression:** Verify real infrastructure tests pass cleanly.
- **Step 6 Commit:**
  `git add tests/runtime/test_multi_process_lease_and_admission_race.py tests/runtime/test_real_infra_distributed.py`
  `git commit -m "test(runtime): add multi-process real infrastructure integration suite"`

---

### Task 20: Phase 7A Canonical Security Regression Suite
- **Files:**
  - CREATE `tests/runtime/test_phase7a_security_regression.py`
- **Interfaces Consumed:** Full runtime and governance pipeline.
- **Interfaces Produced:** Canonical regression suite verifying all 14 Phase 7A security invariants:
  1. Authority widening via admission token = 0.
  2. DENY policy bypass via admission queue = 0.
  3. ExecutionAuthorization bypass via direct worker call = 0.
  4. Cross-tenant execution slot hijacking = 0.
  5. Stale authorization execution = 0.
  6. Egress escape from container = 0.
  7. Blind replay of uncertain side effects = 0.
- **Step 1 Failing Test:** Write tests explicitly attempting all 7 attack vectors.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_phase7a_security_regression.py -v`
- **Step 3 Minimal Code:** Verify all security guards are sealed.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_phase7a_security_regression.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/test_auth_canonical_seams.py tests/test_auth_real_postgres.py tests/runtime/ -q`.
- **Step 6 Commit:**
  `git add tests/runtime/test_phase7a_security_regression.py`
  `git commit -m "security(runtime): add canonical Phase 7A security regression suite"`

---

### Task 21: Configuration Audit & Provisional Defaults Validation
- **Files:**
  - MODIFY `src/responsibleai/dashboard/config.py`
  - CREATE `tests/dashboard/test_runtime_config_bounds.py`
- **Interfaces Consumed:** `Settings`.
- **Interfaces Produced:** Strict validation of provisional configuration bounds: global limits cannot exceed host capacity, timeouts must be positive, queue capacity must be bounded.
- **Step 1 Failing Test:** Write `test_runtime_config_bounds.py` verifying validation rules for all provisional runtime settings.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/dashboard/test_runtime_config_bounds.py -v`
- **Step 3 Minimal Code:** Add Pydantic validators in `Settings`.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/dashboard/test_runtime_config_bounds.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/dashboard/ -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/dashboard/config.py tests/dashboard/test_runtime_config_bounds.py`
  `git commit -m "feat(config): validate runtime configuration bounds and provisional settings"`

---

### Task 22: Candidate Freeze & Review Evidence Pack
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
     `/Users/ag/Whitepact/.venv/bin/alembic -c alembic.ini heads` (must equal 1: `0050`)
- **Step 2 Evidence Compilation:** Record exact outputs and commit hashes in `docs/phase7a-execution/implementation-evidence.md`.
- **Step 3 Commit:**
  `git add docs/phase7a-execution/implementation-evidence.md`
  `git commit -m "docs(phase7): freeze Phase 7A implementation evidence pack"`
