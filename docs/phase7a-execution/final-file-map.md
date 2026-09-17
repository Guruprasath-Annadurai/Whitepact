# WhitePact Phase 7A: Final Implementation File Map

**Document Status:** CANDIDATE IMPLEMENTATION PLAN (PENDING INDEPENDENT REVIEW)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (Auth Candidate Under Codex Review)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Assumed Alembic Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`, conditional upon Codex approval of `13e8de0`)

---

## 1. Overview and Core Invariants

This document maps every file to be **CREATED**, **MODIFIED**, or **TESTED** during the implementation of Phase 7A (Runtime Foundations). Every path and symbol in this document has been verified against the physical candidate repository.

Phase 7A adheres to the core architecture rule:
> **Governance Authorization (ExecutionAuthorization) ≠ Admission (Capacity Slot) ≠ Queue Token ≠ Worker Lease ≠ Redis State**

Commercial attributes (`Plan`, `subscription_status`, billing) are strictly decoupled from governance semantics:
- Commercial entitlement does not equal governance authority.
- Commercial plan does not equal tenant lifecycle.
- Commercial status does not equal tenant deletion or tombstone.
- Phase 7A fairness is plan-neutral.

---

## 2. Capacity and Resource Bounds Classification

All capacity and resource values referenced across Phase 7A files are classified into distinct ontological categories:

| Parameter | Value | Category | Verification / Rationale |
| :--- | :--- | :--- | :--- |
| **Container Memory** | 256 MB | CANONICAL SECURITY BOUND | Verified existing default in `ResourceLimits.max_memory_mb` (`src/responsibleai/isolation/models.py`). |
| **Container CPU** | 0.5 cores | CANONICAL SECURITY BOUND | Verified existing default in `ResourceLimits.cpu_cores` (`src/responsibleai/isolation/models.py`). |
| **Container PIDs** | 32 | CANONICAL SECURITY BOUND | Verified existing default in `ResourceLimits.max_pids` (`src/responsibleai/isolation/models.py`). |
| **Container Timeout** | 15.0 s | CANONICAL SECURITY BOUND | Verified existing default in `ResourceLimits.wall_timeout_seconds` (`src/responsibleai/isolation/models.py`). |
| **Container Output** | 64 KB | CANONICAL SECURITY BOUND | Verified existing default in `ResourceLimits.max_output_bytes` (`src/responsibleai/isolation/models.py`). |
| **Workspace Bytes** | 10 MB | INTERNAL STARTING ASSUMPTION | Frozen internal starting assumption in WP-ISO-01 design (`max_workspace_bytes`). |
| **Workspace Files** | 100 files | INTERNAL STARTING ASSUMPTION | Frozen internal starting assumption in WP-ISO-01 design (`max_workspace_files`). |
| **Max Artifacts** | 20 | CONFIG DEFAULT REQUIRING VALIDATION | Configurable provisional default in `ResourceLimits.max_artifacts`. |
| **Drain Timeout** | 30.0 s | CONFIG DEFAULT REQUIRING VALIDATION | Configurable provisional default in `Settings.drain_timeout_seconds`. |
| **Global Concurrency** | Configurable (prov. 250) | CONFIG DEFAULT REQUIRING VALIDATION | Provisional default ceiling in `Settings.max_global_executions`; no public guarantee. |
| **Tenant Quota** | Configurable (prov. 25) | CONFIG DEFAULT REQUIRING VALIDATION | Provisional default quota in `Settings.max_tenant_executions`; plan-neutral. |
| **Queue Depth** | Configurable (prov. 2000) | CONFIG DEFAULT REQUIRING VALIDATION | Provisional bounded buffer depth in `Settings.execution_queue_capacity`. |
| **Workload Pools** | Extensible Classes | EXTENSIBLE CONFIGURABLE MODEL | Hard-coded 200/50 pool split is REMOVED. Extensible class model with configurable capacity allocations. |
| **10k Users / 2k rps** | Scale Target | PHASE 7C CAPACITY TARGET | Benchmark scale target for Phase 7C; NOT a correctness bound for Phase 7A. |

---

## 3. File Map Grouped by Responsibility

### 1. ADMISSION
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/admission/models.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Establishes the canonical domain models and transition types for execution admission (`AdmissionState`, `AdmissionDecision`, `AdmissionRejectionReason`, `CapacityReservation`, `WorkloadClass`). |
| **Security Sensitivity** | CRITICAL. Must enforce strict enum immutability. An admission state must never be constructible or representable as an `ExecutionAuthorization`. |
| **Dependent Tasks** | Task 1 (Admission domain model + state machine) |
| **Tests Proving Correctness** | `tests/runtime/test_admission_models.py` |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/admission/controller.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Central capacity gatekeeper implementing `reserve_execution()` and `release_execution()`. Coordinates local semaphores and delegates to distributed coordinators. |
| **Security Sensitivity** | CRITICAL. Must be fail-closed. If capacity cannot be verified, execution is rejected. Cannot widen permissions or bypass policy. Plan-neutral capacity tracking. |
| **Dependent Tasks** | Task 2 (Local deterministic admission controller), Task 6 (Integrated multi-tenant concurrency) |
| **Tests Proving Correctness** | `tests/runtime/test_admission_controller.py` |

---

### 2. QUEUE
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/queue/bounded_queue.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Implements bounded in-memory execution queueing with strict capacity ceilings to prevent memory exhaustion under burst traffic. |
| **Security Sensitivity** | HIGH. Prevents denial of service through unbounded queue allocation. Enforces strict timeouts on queued items. |
| **Dependent Tasks** | Task 7 (Fairness / bounded queue) |
| **Tests Proving Correctness** | `tests/runtime/test_bounded_queue.py` |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/queue/models.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Defines `QueueTicket` and `QueuedPayload`. Explicitly: `QueueTicket != authority`. Contains `execution_id`, `authorization_id`, `org_id`, `principal_id`, `action_ref`, `idempotency_key`, `enqueued_at`. Zero reusable authority credentials. |
| **Security Sensitivity** | CRITICAL. Must not leak credentials or grant authority. Reference to `authorization_id` is an unvalidated pointer until revalidated. |
| **Dependent Tasks** | Task 7 (Fairness / bounded queue) |
| **Tests Proving Correctness** | `tests/runtime/test_bounded_queue.py` |

---

### 3. FAIRNESS
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/queue/fair_scheduler.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Implements round-robin multi-tenant queue dispatching across per-tenant subqueues to guarantee zero tenant starvation. Strictly plan-neutral in Phase 7A. |
| **Security Sensitivity** | HIGH. Multi-tenant isolation: ensures high-traffic tenants cannot starve other tenants from acquiring available execution capacity. |
| **Dependent Tasks** | Task 7 (Fairness / bounded queue) |
| **Tests Proving Correctness** | `tests/runtime/test_fair_scheduler.py` |

---

### 4. LEASE
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/worker/lease.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Implements `WorkerLease` data contract, heartbeat renewal, and expiration verification. Keyed on `execution_id` and `attempt`. Required binding: `lease_id, execution_id, authorization_id, org_id, worker_id, attempt, issued_at, expires_at, heartbeat_at`. |
| **Security Sensitivity** | CRITICAL. Ensures mutual exclusion: exactly one worker may hold an active lease for a given `execution_id` at any time. |
| **Dependent Tasks** | Task 9 (Worker lease contract), Task 11 (Crash recovery) |
| **Tests Proving Correctness** | `tests/runtime/test_worker_lease.py` |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/db/admission_lease_repository.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | PostgreSQL repository for durable lease state, heartbeat persistence, and crash recovery queries (`acquire_lease()`, `record_heartbeat()`, `reclaim_stale_leases()`). Uses row-level `FOR UPDATE` locking. |
| **Security Sensitivity** | CRITICAL. Prevents concurrent duplicate execution across multiple worker nodes. |
| **Dependent Tasks** | Task 9 (Worker lease contract), Task 11 (Crash recovery) |
| **Tests Proving Correctness** | `tests/db/test_admission_lease_repository.py` |

---

### 5. WORKER
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/worker/worker.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Implements the `ExecutionWorker` process loop: dequeues payload, acquires lease, revalidates authorization, invokes container backend, streams heartbeats, records outcome. Stays disabled until distributed coordination is ready. |
| **Security Sensitivity** | CRITICAL. Worker must strictly honor cancellation, lease loss, and container termination. Stale workers abort immediately upon lost lease. |
| **Dependent Tasks** | Task 10 (Worker dispatcher separation) |
| **Tests Proving Correctness** | `tests/runtime/test_execution_worker.py` |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/worker/supervisor.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Manages worker pool lifecycle and background reaper for stale leases and dead workers. |
| **Security Sensitivity** | HIGH. Ensures dead workers do not leak active container instances or hold locks indefinitely. |
| **Dependent Tasks** | Task 10 (Worker dispatcher separation), Task 11 (Crash recovery) |
| **Tests Proving Correctness** | `tests/runtime/test_worker_supervisor.py` |

---

### 6. EXECUTION
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/mcp/governance_integration.py` [MODIFY] |
| **Current Symbol(s)** | `execute_governed_action()`, `resolve_approval_and_execute()` |
| **Why Change Required** | Decouple inline execution (`await executor.execute(...)`) into admission request, queueing, and worker dispatch. Kept disabled behind a feature flag until distributed coordination is active. |
| **Security Sensitivity** | CRITICAL. Must preserve fail-closed evidence persistence and ensure `ExecutionAuthorization` is never bypassed. |
| **Dependent Tasks** | Task 10 (Worker dispatcher separation) |
| **Tests Proving Correctness** | `tests/mcp/test_governance_integration.py` |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/dispatcher.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Bridges admission controller decisions to worker execution pools. |
| **Security Sensitivity** | HIGH. Ensures dispatch requests carry verified tokens and cannot be forged internally. |
| **Dependent Tasks** | Task 10 (Worker dispatcher separation) |
| **Tests Proving Correctness** | `tests/runtime/test_dispatcher.py` |

---

### 7. AUTHORIZATION REVALIDATION
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/revalidation.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Performs queue-time and pre-flight revalidation of `ExecutionAuthorization`: checks EA existence, expiration (`expires_at > now`), unconsumed state (`consumed is False`), tenant lifecycle in `OrgRepository` (tenant active, not deleted/tombstoned), principal/session validity, and BreakGlass TTL if dependent on BreakGlass. Does NOT re-evaluate policy. |
| **Security Sensitivity** | CRITICAL. Prevents execution under expired, revoked, or consumed authorizations or deleted tenants. |
| **Dependent Tasks** | Task 8 (ExecutionAuthorization queue-time revalidation) |
| **Tests Proving Correctness** | `tests/runtime/test_revalidation.py` |

---

### 8. RESOURCE LIMITS
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/isolation/models.py` [MODIFY] |
| **Current Symbol(s)** | `ResourceLimits`, `IsolationProfile` |
| **Why Change Required** | Extends `ResourceLimits` to incorporate WP-ISO-01 frozen design requirements: `max_workspace_bytes: int = 10485760` (10 MB), `max_workspace_files: int = 100`, `max_artifacts: int = 20`. Retains verified defaults (CPU 0.5, RAM 256MB, PID 32, timeout 15s, output 64KB). |
| **Security Sensitivity** | HIGH. Prevents resource starvation and disk exhaustion attacks on execution nodes. |
| **Dependent Tasks** | Task 13 (WP-ISO-01 compute limits), Task 14 (WP-ISO-01 workspace limits) |
| **Tests Proving Correctness** | `tests/isolation/test_resource_limits.py` |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/isolation/filesystem.py` [MODIFY] |
| **Current Symbol(s)** | `EphemeralWorkspace.populate()` |
| **Why Change Required** | Validates aggregate file count and total byte size during workspace population to enforce WP-ISO-01 starting bounds (10MB, 100 files). |
| **Security Sensitivity** | HIGH. Defends host storage against malicious tool inputs that write large or numerous files. |
| **Dependent Tasks** | Task 14 (WP-ISO-01 workspace limits) |
| **Tests Proving Correctness** | `tests/isolation/test_filesystem.py` |

---

### 9. ISOLATION
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/isolation/container_backend.py` [MODIFY] |
| **Current Symbol(s)** | `ContainerIsolationBackend.execute()`, `is_available()` |
| **Why Change Required** | Enforces Docker flags for CPU (`--cpus=0.5`), memory (`--memory=256m`), PIDs (`--pids-limit=32`), and adds active container tracking registry for clean shutdown. Preserves `--network=none`. |
| **Security Sensitivity** | CRITICAL. Maintains unconditional air-gap (`--network=none`) and eliminates container escape or resource exhaustion risks. |
| **Dependent Tasks** | Task 13 (WP-ISO-01 compute limits), Task 15 (Timeout and cancellation), Task 16 (Graceful shutdown) |
| **Tests Proving Correctness** | `tests/isolation/test_container_backend.py` |

---

### 10. SHUTDOWN
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/shutdown.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Implements the two-phase graceful shutdown supervisor: Phase 1 drains ingestion and fails readiness; Phase 2 drains execution containers with configurable 30s deadline. |
| **Security Sensitivity** | HIGH. Prevents orphan containers and data loss during rolling deployments or SIGTERM restarts. |
| **Dependent Tasks** | Task 16 (Graceful shutdown supervisor) |
| **Tests Proving Correctness** | `tests/runtime/test_graceful_shutdown.py` |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/dashboard/app.py` [MODIFY] |
| **Current Symbol(s)** | `lifespan()` |
| **Why Change Required** | Integrates `GracefulShutdownSupervisor` into FastAPI lifespan handler, handling SIGTERM and SIGINT signals cleanly. |
| **Security Sensitivity** | HIGH. Coordinates component teardown order (API -> Workers -> DB/Redis connections). |
| **Dependent Tasks** | Task 16 (Graceful shutdown supervisor) |
| **Tests Proving Correctness** | `tests/dashboard/test_lifespan_shutdown.py` |

---

### 11. HEALTH
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/health.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Encapsulates probe logic for liveness (event loop responsive), readiness (PG connected, migration head verified, Redis available if enabled, not draining), and health metrics. |
| **Security Sensitivity** | HIGH. Ensures misconfigured or unmigrated nodes are not sent customer traffic by Kubernetes. |
| **Dependent Tasks** | Task 17 (Readiness / liveness probe decoupling) |
| **Tests Proving Correctness** | `tests/runtime/test_health.py` |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/dashboard/app.py` [MODIFY] |
| **Current Symbol(s)** | `k8s_health()`, `health()` |
| **Why Change Required** | Decouple `/readyz` and `/livez` into independent endpoints with 1.0-second TTL caching and dependency checks. |
| **Security Sensitivity** | HIGH. `/readyz` returns 503 during graceful drain, directing ingress traffic away immediately. |
| **Dependent Tasks** | Task 17 (Readiness / liveness probe decoupling) |
| **Tests Proving Correctness** | `tests/dashboard/test_health_endpoints.py` |

---

### 12. OBSERVABILITY
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/dashboard/prometheus.py` [MODIFY] |
| **Current Symbol(s)** | `whitepact_decisions_total`, `whitepact_evaluation_seconds` |
| **Why Change Required** | Defines and registers the 15 required Phase 7A Prometheus metrics under the `whitepact_*` namespace. |
| **Security Sensitivity** | MEDIUM. Bounded label cardinality; metrics endpoints cannot expose sensitive payload contents or PII. |
| **Dependent Tasks** | Task 18 (Phase 7A runtime observability) |
| **Tests Proving Correctness** | `tests/dashboard/test_runtime_metrics.py` |

---

### 13. REDIS
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/coordination/base.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Abstract base class `DistributedCoordinator` defining semaphore, lease lock, and counter primitives. |
| **Security Sensitivity** | HIGH. Defines contract ensuring coordinators cannot act as authority sources. |
| **Dependent Tasks** | Task 3 (Distributed coordination contract), Task 4 (Redis implementation) |
| **Tests Proving Correctness** | `tests/runtime/test_coordination.py` |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `src/responsibleai/runtime/coordination/redis_coordinator.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Implements distributed semaphores and concurrency locks using Redis scripts. Enforces fail-closed semantics on connection loss. |
| **Security Sensitivity** | CRITICAL. Redis is ephemeral only. Coordination loss defaults to rejection (HTTP 503), never unmetered execution. |
| **Dependent Tasks** | Task 4 (Redis implementation), Task 5 (Redis fail-closed behavior) |
| **Tests Proving Correctness** | `tests/runtime/test_redis_coordinator.py` |

---

### 14. POSTGRES
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `migrations/versions/0049_runtime_worker_leases.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Creates `runtime_worker_leases` table for durable worker lease checkpoints and crash recovery. Down-revision is strictly `0048`, conditional upon Codex approving auth candidate `13e8de0`. |
| **Security Sensitivity** | CRITICAL. Keyed by `execution_id`. Enforces mutual exclusion and referential integrity to `organizations.id`. |
| **Dependent Tasks** | Task 9 (Worker lease contract), Task 11 (Crash recovery) |
| **Tests Proving Correctness** | `tests/test_auth_real_postgres.py`, `tests/test_postgres_migrations.py` |

---

### 15. TEST INFRASTRUCTURE
| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `tests/runtime/conftest.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Provides reusable fixtures for Redis test containers, PostgreSQL test connections, and mock isolation backends. |
| **Security Sensitivity** | LOW (Test harness). Must isolate test databases and Redis keys between test cases. |
| **Dependent Tasks** | All runtime tasks |
| **Tests Proving Correctness** | All runtime test suites |

| Attribute | Details |
| :--- | :--- |
| **Exact Path** | `tests/runtime/test_real_infra_distributed.py` [CREATE] |
| **Current Symbol(s)** | `[NEW FILE]` |
| **Why Change Required** | Real infrastructure integration suite executing multi-process tests against real PostgreSQL, real Redis, and real Docker. |
| **Security Sensitivity** | CRITICAL. Proves distributed invariants: mutual exclusion, crash recovery, fail-closed Redis partition, zero orphan containers. |
| **Dependent Tasks** | Task 19 (Real infrastructure distributed tests) |
| **Tests Proving Correctness** | Self-testing integration suite |
