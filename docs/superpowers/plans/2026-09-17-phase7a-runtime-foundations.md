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

4. **Durable Issuance Integration & Queue Contract (P0-1):**
   - `ExecutionAuthorization` is persisted in PostgreSQL (`governance_execution_authorizations`, migration `0049`) by `src/responsibleai/mcp/governance_integration.py` immediately at decision time.
   - **Non-Bypassable Issuance Invariant:** NO `QueueTicket` may be generated until database insertion of the `ExecutionAuthorization` commits successfully. If database persistence fails, the request fails closed immediately (HTTP 500/503), leaving 0 queue entries and 0 dispatchable authority.
   - `QueueTicket != authority`. Queue tickets contain strictly unprivileged references (`execution_id`, `authorization_id`, `org_id`, `principal_id`, `action_digest`, `enqueued_at`).

5. **Worker Lease Identity & DB-Enforced Exclusivity (P0-3):**
   - Lease identity is based on `execution_id` and `attempt`.
   - Required lease binding: `lease_id, execution_id, authorization_id, org_id, worker_id, attempt, status, issued_at, expires_at, heartbeat_at, completed_at`.
   - **Database-Enforced Invariant:** Exactly one worker may hold an `ACTIVE` lease for a given `execution_id` at any time, enforced by PostgreSQL partial unique index:
     `CREATE UNIQUE INDEX idx_runtime_worker_leases_active_execution ON runtime_worker_leases (execution_id) WHERE status = 'ACTIVE';`
   - Concurrent lease acquisitions fail closed at the database constraint level.

6. **Atomic Canonical Admission & Integration Gate (P0-2, P1-2):**
   - The worker dispatcher (Task 10) acts as the non-bypassable Integration Gate between Lane A1 (coordination), Lane A2 (durable issuance & atomic admission), Lane C1 (worker lease schema), and Lane C2 (worker recovery).
   - Dispatcher and worker loops MUST NOT bypass `src/responsibleai/governance/execution.py:admit_execution()`.
   - `ExecutionNonceRepository.consume()` in `src/responsibleai/db/execution_nonce_repository.py` owns the singular PostgreSQL transaction combining:
     1. Revocation epoch row lock (`lock_epoch`) and epoch verification.
     2. Single-use nonce insertion into `governance_execution_nonces`.
     3. Conditional update on `governance_execution_authorizations` (`status = 'CONSUMED', consumed_at = now() WHERE status = 'ISSUED' AND expires_at > now()`) asserting `rowcount == 1`.
     If rowcount is 0, the entire transaction rolls back, undoing nonce insertion.

7. **Side-Effect Safety & Idempotency Guard:**
   - The runtime explicitly separates `execution_id`, `attempt_id`, `effect_id`, and `idempotency_key`.
   - For non-idempotent or uncertain external side effects: a worker crash after external action dispatch but before local acknowledgement must NEVER trigger blind replay.
   - The crash recovery reaper records state `UNCERTAIN`. Worker lease expiry does NOT grant permission to repeat an uncertain external effect.

8. **Two-Stage Revalidation, Derived Expiration & Singular Revocation (P1-1):**
   - **Singular Revocation:** Tenant-wide epoch revocation (`governance_revocation_epochs`) is the sole revocation engine. Individual authorization `REVOKED` state is eliminated to prevent dual-source ambiguity.
   - **Derived Expiration:** Expiration is derived from `now >= expires_at`. No background daemon mutates rows to `EXPIRED`. Atomic query guard `WHERE expires_at > now()` prevents expired permit consumption.
   - **Two-Stage Partitioning:**
     - **Stage 1: Early Queue Invalidation:** Evaluated by Dispatcher before acquiring lease or burning nonce. Fast-aborts on expired authorization (`now >= expires_at`), consumed authorization (`status != 'ISSUED'`), or inactive/deleted tenant in `OrgRepository`.
     - **Stage 2: Final Pre-Flight Revalidation:** Evaluated by Worker immediately before `admit_execution()`. Verifies action digest match, principal identity, session validity, target fingerprint drift, and BreakGlass TTL.

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

### Task 8A: Durable Request Storage (Mig 0049), Auth Storage (Mig 0050), Centralized Issuer & Approval Atomicity
- **Files:**
  - CREATE `migrations/versions/0049_runtime_execution_requests.py`
  - CREATE `src/responsibleai/db/execution_request_repository.py`
  - CREATE `migrations/versions/0050_runtime_execution_authorizations.py`
  - CREATE `src/responsibleai/db/execution_authorization_repository.py`
  - CREATE `src/responsibleai/governance/execution_issuer.py`
  - CREATE `src/responsibleai/governance/approval_service.py`
  - MODIFY `src/responsibleai/mcp/governance_integration.py`
  - MODIFY `src/responsibleai/mcp/upstream_dispatch.py`
  - CREATE `tests/runtime/test_durable_execution_request.py`
  - CREATE `tests/runtime/test_durable_execution_authorization.py`
  - CREATE `tests/runtime/test_durable_issuance_all_paths.py`
  - CREATE `tests/governance/test_approval_issuance_atomicity.py`
- **Interfaces Consumed:** `ExecutionAuthorization`, `OrgRepository`, `governance_revocation_epochs`, `governance_approvals`.
- **Interfaces Produced:** `ExecutionRequestRepository.create()`, `ExecutionAuthorizationRepository.create()`, `DurableExecutionAuthorizationIssuer.issue()`, and `ApprovalExecutionService.consume_and_issue()`.
- **Step 1 Failing Test:** Write `tests/runtime/test_durable_issuance_all_paths.py`, `test_durable_execution_request.py`, and `test_approval_issuance_atomicity.py` verifying:
  1. RFC 8785 canonical JSON serialization, action digest computation, and append-only immutability.
  2. Tenant-scoped idempotency via `UNIQUE(organization_id, idempotency_key)`.
  3. Approval consumption and authorization issuance committed in ONE transaction with `UNIQUE(approval_id)`.
  4. All 3 production issuance call sites (`execute_governed_action`, `resolve_approval_and_execute`, `dispatch_upstream_action`) commit request and authorization before queueing.
  5. If DB persistence fails: request fails closed (HTTP 500/503), ZERO `QueueTicket` rows created (`queue_depth == 0`).
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_durable_execution_request.py tests/runtime/test_durable_issuance_all_paths.py tests/governance/test_approval_issuance_atomicity.py -v`
- **Step 3 Minimal Code:**
  1. Create migration `0049` (`runtime_execution_requests`) and `0050` (`governance_execution_authorizations`).
  2. Implement `ExecutionRequestRepository` and `ExecutionAuthorizationRepository`.
  3. Implement `DurableExecutionAuthorizationIssuer` and `ApprovalExecutionService`.
  4. Modify `governance_integration.py` and `upstream_dispatch.py` to route through issuer.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_durable_execution_request.py tests/runtime/test_durable_issuance_all_paths.py tests/governance/test_approval_issuance_atomicity.py -v`
- **Step 5 Focused Regression:** Run migration tests and `pytest tests/runtime/test_durable_issuance_all_paths.py -q`.
- **Step 6 Commit:**
  `git add migrations/versions/0049_runtime_execution_requests.py migrations/versions/0050_runtime_execution_authorizations.py src/responsibleai/db/execution_request_repository.py src/responsibleai/db/execution_authorization_repository.py src/responsibleai/governance/execution_issuer.py src/responsibleai/governance/approval_service.py src/responsibleai/mcp/governance_integration.py src/responsibleai/mcp/upstream_dispatch.py tests/runtime/test_durable_execution_request.py tests/runtime/test_durable_issuance_all_paths.py tests/governance/test_approval_issuance_atomicity.py`
  `git commit -m "feat(runtime): implement durable request storage, authorization storage, and approval atomicity"`

---

### Task 8B: Universal Epoch Coverage (14 Mutations), Two-Stage Revalidation & Atomic Admission
- **Files:**
  - MODIFY `src/responsibleai/db/execution_nonce_repository.py`
  - MODIFY `src/responsibleai/governance/execution.py`
  - MODIFY `src/responsibleai/governance/upstream_executor.py`
  - MODIFY `src/responsibleai/iam/session.py`
  - MODIFY `src/responsibleai/iam/break_glass.py`
  - CREATE `src/responsibleai/runtime/revalidation.py`
  - CREATE `tests/runtime/test_atomic_admission.py`
  - CREATE `tests/runtime/test_single_admission_internal_tool.py`
  - CREATE `tests/runtime/test_single_admission_upstream.py`
  - CREATE `tests/runtime/test_epoch_coverage_all_mutations.py`
- **Interfaces Consumed:** `ExecutionNonceRepository`, `ExecutionAuthorizationRepository`, `governance_revocation_epochs`, `SessionService`, `BreakGlassService`.
- **Interfaces Produced:** Atomic `ExecutionNonceRepository.consume()`, canonical `admit_execution()` returning `AdmissionReceipt`, and adapted downstream executors (`InternalToolExecutor`, `UpstreamMCPExecutor`) with zero re-admission.
- **Step 1 Failing Test:** Write `tests/runtime/test_atomic_admission.py`, `test_single_admission_internal_tool.py`, `test_single_admission_upstream.py`, and `test_epoch_coverage_all_mutations.py` asserting:
  1. Nonce insertion and authorization status update (`ISSUED -> CONSUMED`) execute in the SAME PostgreSQL transaction on `self._engine.raw.begin()`.
  2. All 14 authority mutations advance `scope="governance"` epoch under row lock, failing stale queued authorizations.
  3. Session revocation and BreakGlass termination advance governance epoch.
  4. `InternalToolExecutor.execute()` and `UpstreamMCPExecutor.execute()` accept `AdmissionReceipt` and do NOT call `admit_execution()`; call count is exactly 1 per execution attempt.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_atomic_admission.py tests/runtime/test_epoch_coverage_all_mutations.py -v`
- **Step 3 Minimal Code:**
  1. Modify `execution_nonce_repository.py:consume()` to combine epoch lock, nonce insert, and conditional update on `governance_execution_authorizations` (`status = 'CONSUMED'`) asserting `rowcount == 1`.
  2. Update `execution.py:admit_execution()` to return typed `AdmissionReceipt`.
  3. Adapt `InternalToolExecutor.execute()` and `UpstreamMCPExecutor.execute()` to accept `AdmissionReceipt`.
  4. Update `iam/session.py` and `iam/break_glass.py` to bump governance epoch on mutation.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_atomic_admission.py tests/runtime/test_epoch_coverage_all_mutations.py tests/runtime/test_single_admission_internal_tool.py tests/runtime/test_single_admission_upstream.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/runtime/test_atomic_admission.py -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/db/execution_nonce_repository.py src/responsibleai/governance/execution.py src/responsibleai/governance/upstream_executor.py src/responsibleai/iam/session.py src/responsibleai/iam/break_glass.py src/responsibleai/runtime/revalidation.py tests/runtime/test_atomic_admission.py tests/runtime/test_single_admission_internal_tool.py tests/runtime/test_single_admission_upstream.py tests/runtime/test_epoch_coverage_all_mutations.py`
  `git commit -m "security(runtime): bind atomic admission transaction, universal epoch coverage, and admission receipt"`

---

### Task 9: Attempt State Machine (Mig 0051), Worker Lease Schema (Mig 0052) & Fencing
- **Files:**
  - CREATE `migrations/versions/0051_runtime_execution_attempts.py`
  - CREATE `src/responsibleai/db/execution_attempt_repository.py`
  - CREATE `migrations/versions/0052_runtime_worker_leases.py`
  - CREATE `src/responsibleai/runtime/worker/lease.py`
  - CREATE `src/responsibleai/db/admission_lease_repository.py`
  - CREATE `tests/runtime/test_execution_attempt_state_machine.py`
  - CREATE `tests/runtime/test_worker_lease_fencing.py`
  - CREATE `tests/runtime/test_one_shot_backend_start.py`
- **Interfaces Consumed:** PostgreSQL database engine (down_revision strictly `0050`).
- **Interfaces Produced:** `ExecutionAttemptRepository` (managing attempt state machine and one-shot backend start) and `AdmissionLeaseRepository` (managing monotonic `lease_generation` fencing).
- **Step 1 Failing Test:** Write `tests/runtime/test_execution_attempt_state_machine.py`, `test_worker_lease_fencing.py`, and `test_one_shot_backend_start.py` verifying:
  1. Monotonic lease generation: each new lease for an execution receives generation N+1.
  2. Pre-backend start fencing: worker holding generation N fails closed if active lease is generation N+1 or expired.
  3. One-shot backend-start transition: `UPDATE runtime_execution_attempts SET state = 'BACKEND_STARTING' WHERE state = 'ADMITTED'` asserting `rowcount == 1`. Second invocation fails closed.
  4. Attempt states: `PENDING` -> `LEASED` -> `ADMITTED` -> `BACKEND_STARTING` -> `RUNNING` -> `COMPLETED`/`FAILED`/`UNCERTAIN`.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_execution_attempt_state_machine.py tests/runtime/test_worker_lease_fencing.py tests/runtime/test_one_shot_backend_start.py -v`
- **Step 3 Minimal Code:**
  1. Create migrations `0051` and `0052`.
  2. Implement `ExecutionAttemptRepository` with atomic `claim_backend_start()` method.
  3. Implement `AdmissionLeaseRepository` with monotonic generation assignment and row-level fencing.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_execution_attempt_state_machine.py tests/runtime/test_worker_lease_fencing.py tests/runtime/test_one_shot_backend_start.py -v`
- **Step 5 Focused Regression:** Verify real PostgreSQL migration cycle `0048 -> 0049 -> 0050 -> 0051 -> 0052 -> 0051 -> 0050 -> 0049 -> 0048`.
- **Step 6 Commit:**
  `git add migrations/versions/0051_runtime_execution_attempts.py migrations/versions/0052_runtime_worker_leases.py src/responsibleai/db/execution_attempt_repository.py src/responsibleai/runtime/worker/lease.py src/responsibleai/db/admission_lease_repository.py tests/runtime/test_execution_attempt_state_machine.py tests/runtime/test_worker_lease_fencing.py tests/runtime/test_one_shot_backend_start.py`
  `git commit -m "feat(runtime): introduce attempt state machine, monotonic worker fencing, and one-shot backend start"`

---

### Task 10: Integration Gate — Worker Dispatcher Decoupling & Canonical Execution Bridge
- **Files:**
  - CREATE `src/responsibleai/runtime/dispatcher.py`
  - CREATE `src/responsibleai/runtime/worker/worker.py`
  - MODIFY `src/responsibleai/mcp/governance_integration.py`
  - MODIFY `src/responsibleai/mcp/upstream_dispatch.py`
  - CREATE `tests/runtime/test_dispatcher.py`
  - CREATE `tests/runtime/test_execution_worker.py`
- **Activation Gate Preconditions (ALL 10 Required):**
  1. Durable immutable request storage (`0049_runtime_execution_requests`).
  2. Tenant-scoped idempotent issuance (`UNIQUE(organization_id, idempotency_key)`).
  3. All 3 production issuance paths closed via PostgreSQL persistence.
  4. Atomic approval consumption and authorization issuance (`UNIQUE(approval_id)`).
  5. Canonical admission transaction combining nonce insert and authorization status update (`rowcount == 1`).
  6. Universal epoch invalidation covering all 14 authority mutations.
  7. Monotonic worker fencing (`0052_runtime_worker_leases.lease_generation`).
  8. Durable attempt and effect state machine (`0051_runtime_execution_attempts`).
  9. One-shot backend-start transition (`ADMITTED -> BACKEND_STARTING` with `rowcount == 1`).
  10. Preservation of `SafeNetworkBackend` and container isolation.
- **Interfaces Consumed:** Tasks 6, 7, 8A, 8B, 9.
- **Interfaces Produced:** Non-bypassable `ExecutionDispatcher` and `ExecutionWorker.process_next()` pipeline.
- **Step 1 Failing Test:** Write `tests/runtime/test_dispatcher.py` and `test_execution_worker.py` asserting:
  1. Dispatcher enqueues lightweight `QueueTicket` carrying zero credentials.
  2. Worker pulls ticket, runs Stage 1 Early Queue Invalidation.
  3. Worker acquires exclusive `ACTIVE` lease with monotonic generation N.
  4. Worker runs Stage 2 Pre-flight Revalidation against durable request and authorization.
  5. Worker invokes canonical `admit_execution()`, receiving `AdmissionReceipt`.
  6. Worker invokes atomic one-shot backend start in PostgreSQL (`ADMITTED -> BACKEND_STARTING`).
  7. Worker hands off to `InternalToolExecutor` or `UpstreamMCPExecutor`. Zero double admission.
  8. Outcome, evidence, attempt completion, and lease finalization execute in strict order.
- **Step 2 Run RED:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_dispatcher.py tests/runtime/test_execution_worker.py -v`
- **Step 3 Minimal Code:** Connect `governance_integration.py` and `upstream_dispatch.py` to the dispatcher, implement worker loop with canonical admission and backend-start transition, and bridge to container and upstream executors.
- **Step 4 Run GREEN:**
  `PYTHONPATH=src /Users/ag/Whitepact/.venv/bin/pytest tests/runtime/test_dispatcher.py tests/runtime/test_execution_worker.py -v`
- **Step 5 Focused Regression:** Run `pytest tests/mcp/test_governance_integration.py tests/runtime/test_dispatcher.py tests/runtime/test_execution_worker.py -q`.
- **Step 6 Commit:**
  `git add src/responsibleai/runtime/dispatcher.py src/responsibleai/runtime/worker/worker.py src/responsibleai/mcp/governance_integration.py src/responsibleai/mcp/upstream_dispatch.py tests/runtime/test_dispatcher.py tests/runtime/test_execution_worker.py`
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
     `/Users/ag/Whitepact/.venv/bin/alembic -c alembic.ini heads` (must equal 1: `0052`)
- **Step 2 Evidence Compilation:** Record exact outputs and commit hashes in `docs/phase7a-execution/implementation-evidence.md`.
- **Step 3 Commit:**
  `git add docs/phase7a-execution/implementation-evidence.md`
  `git commit -m "docs(phase7): freeze Phase 7A implementation evidence pack"`
