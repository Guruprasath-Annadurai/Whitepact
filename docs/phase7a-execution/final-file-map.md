# WhitePact Phase 7A: Final Implementation File Map

**Document Status:** CANONICAL SPECIFICATION PASS 4 (SECURITY REMEDIATION)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Overview and Core Invariants

This document maps every file to be **CREATED**, **MODIFIED**, or **TESTED** during Phase 7A (Runtime Foundations). Every path and symbol has been verified against the approved canonical baseline (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

Phase 7A adheres to the core architecture rule:
> **Governance Authorization (ExecutionAuthorization) ≠ Admission (Capacity Slot) ≠ Queue Token ≠ Worker Lease ≠ Redis State**

Commercial attributes (`Plan`, `subscription_status`, billing) are strictly decoupled from governance semantics:
- Commercial entitlement does not equal governance authority.
- Commercial plan does not equal tenant lifecycle.
- Commercial status does not equal tenant deletion or tombstone.
- Phase 7A fairness is plan-neutral.

---

## 2. Existing Production Files Explicitly Modified

| Existing Production File | Function / Symbol Modified | Why Modification Is Required |
| :--- | :--- | :--- |
| `src/responsibleai/mcp/governance_integration.py` | `execute_governed_action()`, `resolve_approval_and_execute()` | **Durable Issuance & Approval Atomicity:** Routes through `DurableExecutionAuthorizationIssuer.issue()` and `ApprovalExecutionService.consume_and_issue()` to persist `runtime_execution_requests` and `governance_execution_authorizations` in PostgreSQL before enqueueing. |
| `src/responsibleai/mcp/upstream_dispatch.py` | `dispatch_upstream_action()` | **Upstream Issuance Integration:** Routes through `DurableExecutionAuthorizationIssuer.issue()` before queueing/dispatch. Eliminates upstream issuance bypass, guaranteeing that external MCP actions are durably persisted before execution. |
| `src/responsibleai/governance/execution.py` | `admit_execution()`, `InternalToolExecutor.execute()` | **Canonical Admission & Downstream Adaptation:** Returns in-process `AdmissionReceipt` upon atomic transaction commit. Adapts `InternalToolExecutor.execute()` to accept `AdmissionReceipt` and not call `admit_execution()` again, eliminating double-admission. |
| `src/responsibleai/governance/upstream_executor.py` | `UpstreamMCPExecutor.execute()` | **Single Admission for Upstream:** Adapts `UpstreamMCPExecutor.execute()` to accept `AdmissionReceipt` context instead of invoking `admit_execution()` again. Strictly preserves `SafeNetworkBackend`, fingerprint validation, and SSRF protections. |
| `src/responsibleai/db/execution_nonce_repository.py` | `ExecutionNonceRepository.consume()` | **Atomic Transaction Owner:** Adapts the existing `self._engine.raw.begin()` transaction to combine: (1) epoch lock; (2) epoch comparison; (3) nonce insert; (4) conditional update on `governance_execution_authorizations` (`status = 'CONSUMED'`) asserting `rowcount == 1`. |
| `src/responsibleai/iam/session.py` | `revoke_session()` | **Epoch Invalidation Coverage:** Updates session revocation to call `bump_epoch_on_connection(conn, org_id, scope="governance")` in addition to `scope="iam_session"`. |
| `src/responsibleai/iam/break_glass.py` | `terminate_break_glass()` | **Epoch Invalidation Coverage:** Updates break-glass termination to call `bump_epoch_on_connection(conn, org_id, scope="governance")` in the same transaction. |
| `src/responsibleai/isolation/models.py` | `ResourceLimits`, `IsolationProfile` | Extends `ResourceLimits` with WP-ISO-01 frozen design requirements (`max_workspace_bytes: 10MB`, `max_workspace_files: 100`, `max_artifacts: 20`). |
| `src/responsibleai/isolation/filesystem.py` | `EphemeralWorkspace.populate()` | Enforces workspace bounds during directory population (10MB byte ceiling, 100 file count ceiling). |
| `src/responsibleai/isolation/container_backend.py` | `ContainerIsolationBackend.execute()`, `is_available()` | Enforces Docker flags (`--cpus=0.5`, `--memory=256m`, `--pids-limit=32`, `--network=none`) and registers containers for clean shutdown. |
| `src/responsibleai/dashboard/app.py` | `lifespan()`, `k8s_health()`, `health()` | Integrates two-phase graceful shutdown supervisor and decouples `/livez` and `/readyz` endpoints. |
| `src/responsibleai/dashboard/prometheus.py` | Metrics registry | Registers the 15 Phase 7A Prometheus runtime metrics under the `whitepact_*` namespace. |
| `src/responsibleai/dashboard/config.py` | `Settings` | Adds bounds validators for provisional runtime configuration settings and `HOSTED_GOVERNANCE_STRICT`. |

---

## 3. Detailed File Map Grouped by Responsibility

### 1. ADMISSION & COORDINATION
| Exact Path | Action | Responsibility / Symbols | Dependent Tasks | Tests |
| :--- | :--- | :--- | :--- | :--- |
| `src/responsibleai/runtime/admission/models.py` | CREATE | `AdmissionState`, `AdmissionDecision`, `AdmissionRejectionReason`, `CapacityReservation`, `WorkloadClass`. | Task 1 | `tests/runtime/test_admission_models.py` |
| `src/responsibleai/runtime/admission/controller.py` | CREATE | In-process and distributed capacity gatekeeper: `reserve_execution()`, `release_execution()`. Fail-closed. | Tasks 2, 5, 6 | `tests/runtime/test_admission_controller.py`, `tests/runtime/test_redis_fail_closed.py`, `tests/runtime/test_integrated_concurrency.py` |
| `src/responsibleai/runtime/coordination/base.py` | CREATE | Abstract `DistributedCoordinator` defining semaphore and lease lock primitives. | Task 3 | `tests/runtime/test_coordination_contract.py` |
| `src/responsibleai/runtime/coordination/redis_coordinator.py` | CREATE | Lua-script backed distributed semaphores in Redis with fail-closed semantics. | Task 4 | `tests/runtime/test_redis_coordinator.py` |

---

## 2. QUEUE & FAIRNESS
| Exact Path | Action | Responsibility / Symbols | Dependent Tasks | Tests |
| :--- | :--- | :--- | :--- | :--- |
| `src/responsibleai/runtime/queue/models.py` | CREATE | `QueueTicket`. Non-privileged pointers only (`execution_id`, `authorization_id`, `org_id`, `enqueued_at`). Zero authority credentials. | Task 7 | `tests/runtime/test_bounded_queue.py` |
| `src/responsibleai/runtime/queue/bounded_queue.py` | CREATE | Bounded multi-tenant execution queue with strict capacity ceilings. | Task 7 | `tests/runtime/test_bounded_queue.py` |
| `src/responsibleai/runtime/queue/fair_scheduler.py` | CREATE | Round-robin plan-neutral fair tenant queue dispatcher. | Task 7 | `tests/runtime/test_fair_scheduler.py` |

---

### 3. DURABLE AUTHORITY & CANONICAL ADMISSION
| Exact Path | Action | Responsibility / Symbols | Dependent Tasks | Tests |
| :--- | :--- | :--- | :--- | :--- |
| `migrations/versions/0049_runtime_execution_requests.py` | CREATE | Creates `runtime_execution_requests` table. Down-revision: `0048`. RFC 8785 canonical JSON payload, `action_digest`, `UNIQUE(organization_id, idempotency_key)`, append-only trigger. | Task 8A | `tests/test_postgres_migrations.py` |
| `src/responsibleai/db/execution_request_repository.py` | CREATE | Async PostgreSQL repository for execution requests (`create()`, `get()`). | Task 8A | `tests/db/test_execution_request_repository.py` |
| `migrations/versions/0050_runtime_execution_authorizations.py` | CREATE | Creates `governance_execution_authorizations` table. Down-revision: `0049`. Losslessly persists all 11 fields; `UNIQUE(approval_id)`; status machine (`ISSUED`, `CONSUMED`). | Task 8A | `tests/test_postgres_migrations.py` |
| `src/responsibleai/db/execution_authorization_repository.py` | CREATE | Async PostgreSQL repository for authorizations (`create()`, `get()`). | Task 8A | `tests/db/test_execution_authorization_repository.py` |
| `src/responsibleai/governance/execution_issuer.py` | CREATE | Centralized `DurableExecutionAuthorizationIssuer` service ensuring PostgreSQL persistence prior to queueing. | Task 8A | `tests/runtime/test_durable_issuance_all_paths.py` |
| `src/responsibleai/governance/approval_service.py` | CREATE | `ApprovalExecutionService.consume_and_issue(...)` combining approval consumption and authorization issuance in single transaction. | Task 8A | `tests/governance/test_approval_issuance_atomicity.py` |
| `src/responsibleai/mcp/governance_integration.py` | MODIFY | **Durable Issuance Integration:** Routes `execute_governed_action()` and `resolve_approval_and_execute()` through issuer before enqueueing. | Task 8A | `tests/runtime/test_durable_issuance_all_paths.py` |
| `src/responsibleai/mcp/upstream_dispatch.py` | MODIFY | **Upstream Durable Issuance:** Routes `dispatch_upstream_action()` through issuer before enqueueing, closing upstream gap. | Task 8A | `tests/runtime/test_durable_issuance_all_paths.py` |
| `src/responsibleai/db/execution_nonce_repository.py` | MODIFY | **Atomic Admission Transaction:** Adapts `consume()` to lock epoch, insert nonce, and conditionally update authorization with `rowcount == 1` in single transaction. | Task 8B | `tests/runtime/test_atomic_admission.py` |
| `src/responsibleai/governance/execution.py` | MODIFY | **Canonical Admission API & AdmissionReceipt:** Preserves `admit_execution()`, returns `AdmissionReceipt`. Adapts `InternalToolExecutor.execute()` to accept `AdmissionReceipt`. | Task 8B | `tests/runtime/test_atomic_admission.py`, `tests/runtime/test_single_admission_internal_tool.py` |
| `src/responsibleai/governance/upstream_executor.py` | MODIFY | **Upstream Single Admission:** Adapts `UpstreamMCPExecutor.execute()` to accept `AdmissionReceipt` context and avoid duplicate admission. | Task 8B, 10 | `tests/runtime/test_single_admission_upstream.py` |
| `src/responsibleai/runtime/revalidation.py` | CREATE | Two-stage revalidation: Stage 1 `early_queue_invalidation()`; Stage 2 `pre_flight_revalidation()`. | Task 8B | `tests/runtime/test_revalidation.py` |

---

### 4. ATTEMPT STATE MACHINE, WORKER LEASE & FENCING
| Exact Path | Action | Responsibility / Symbols | Dependent Tasks | Tests |
| :--- | :--- | :--- | :--- | :--- |
| `migrations/versions/0051_runtime_execution_attempts.py` | CREATE | Creates `runtime_execution_attempts` table. Down-revision: `0050`. State machine (`PENDING`..`UNCERTAIN`), `effect_id`, `effect_state`, partial unique index on active attempts. | Task 9 | `tests/test_postgres_migrations.py` |
| `src/responsibleai/db/execution_attempt_repository.py` | CREATE | PostgreSQL repository for execution attempts and one-shot backend-start transition (`ADMITTED -> BACKEND_STARTING` with `rowcount == 1`). | Task 9 | `tests/db/test_execution_attempt_repository.py` |
| `migrations/versions/0052_runtime_worker_leases.py` | CREATE | Creates `runtime_worker_leases` table. Down-revision: `0051`. Monotonic `lease_generation` (BIGINT), partial unique index `WHERE status = 'ACTIVE'`. | Task 9 | `tests/test_postgres_migrations.py` |
| `src/responsibleai/runtime/worker/lease.py` | CREATE | `WorkerLease` data contract keyed on `execution_id`, `lease_generation`, and `attempt_id`. | Task 9 | `tests/runtime/test_worker_lease.py` |
| `src/responsibleai/db/admission_lease_repository.py` | CREATE | PostgreSQL repository for worker leases with row-level `FOR UPDATE` locking and heartbeat updates. | Task 9 | `tests/db/test_admission_lease_repository.py`, `tests/runtime/test_worker_lease_db_concurrency.py` |

---

### 5. DISPATCHER, WORKER & RECOVERY
| Exact Path | Action | Responsibility / Symbols | Dependent Tasks | Tests |
| :--- | :--- | :--- | :--- | :--- |
| `src/responsibleai/runtime/dispatcher.py` | CREATE | Bridges queue to worker pools. Runs early invalidation, acquires lease with generation N, and dispatches. Gated on all 10 activation prerequisites. | Task 10 (Gate) | `tests/runtime/test_dispatcher.py` |
| `src/responsibleai/runtime/worker/worker.py` | CREATE | Execution worker process loop: pre-flight revalidation, canonical `admit_execution()`, atomic one-shot backend-start transition, container/network invocation, heartbeat stream. | Task 10 (Gate) | `tests/runtime/test_execution_worker.py` |
| `src/responsibleai/runtime/worker/supervisor.py` | CREATE | Background reaper for stale leases, dead worker cleanup, and capacity reservation reconciliation. | Task 11 (C2) | `tests/runtime/test_crash_recovery.py` |
| `src/responsibleai/runtime/worker/worker.py` | MODIFY | Enforces `UNCERTAIN` state on disrupted external side-effects (zero blind replay). | Task 12 (C2) | `tests/runtime/test_external_effect_idempotency.py` |

---

### 6. ISOLATION, OPS & TEST INFRASTRUCTURE
| Exact Path | Action | Responsibility / Symbols | Dependent Tasks | Tests |
| :--- | :--- | :--- | :--- | :--- |
| `src/responsibleai/isolation/models.py` | MODIFY | `ResourceLimits` with 10MB workspace, 100 files, 20 artifacts. | Tasks 13, 14 | `tests/isolation/test_resource_limits.py` |
| `src/responsibleai/isolation/filesystem.py` | MODIFY | Workspace bounds enforcement during population. | Task 14 | `tests/isolation/test_filesystem.py` |
| `src/responsibleai/isolation/container_backend.py` | MODIFY | Docker containment flags (`--network=none`, limits) and tracking. | Tasks 13, 15 | `tests/isolation/test_container_backend.py` |
| `src/responsibleai/runtime/shutdown.py` | CREATE | Two-phase graceful shutdown supervisor (30s timeout). | Task 16 | `tests/runtime/test_graceful_shutdown.py` |
| `src/responsibleai/runtime/health.py` | CREATE | Independent `/livez` and `/readyz` probe logic with 1.0s caching. | Task 17 | `tests/runtime/test_health.py` |
| `src/responsibleai/dashboard/prometheus.py` | MODIFY | Registers 15 runtime metrics under `whitepact_*`. | Task 18 | `tests/dashboard/test_runtime_metrics.py` |
| `src/responsibleai/dashboard/config.py` | MODIFY | Bounds validators on provisional runtime settings and `HOSTED_GOVERNANCE_STRICT`. | Task 21 | `tests/dashboard/test_runtime_config_bounds.py` |
| `tests/runtime/conftest.py` | CREATE | Test fixtures for PG, Redis, and container environments. | All Tasks | Test infrastructure |
| `tests/runtime/test_multi_process_lease_and_admission_race.py` | CREATE | Real multi-process independent OS process race tests against PG. | Task 19 | Self-testing integration suite |
| `tests/runtime/test_real_infra_distributed.py` | CREATE | Full real infrastructure distributed suite (PG + Redis + Docker). | Task 19 | Self-testing integration suite |
| `tests/runtime/test_phase7a_security_regression.py` | CREATE | Canonical security regression verifying all 14 invariants. | Task 20 | Self-testing regression suite |
