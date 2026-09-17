# WhitePact Phase 7A: Validated Dependency Graph & Execution Sequence

**Document Status:** CANONICAL SPECIFICATION PASS 4.2 (SECURITY CONSISTENCY CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Overview & Graph Invariants

This document defines the strict, mathematically sound dependency graph for Phase 7A implementation.

### Critical Graph Invariants:
1. **Linear Migration Sequencing:**
   `0048`
   -> `0049_runtime_execution_requests.py`
   -> `0050_runtime_execution_authorizations.py`
   -> `0051_runtime_execution_attempts.py`
   -> `0052_runtime_worker_leases.py`.
2. **PostgreSQL Schema Before Logic:** All migrations (0049–0052) and underlying repositories exist BEFORE the centralized issuance service is declared operational.
3. **Dispatcher Activation Gate (Task 10 Gate):** Task 10 requires all 15 security prerequisites to be fully verified in design and implementation:
   - 1. Durable immutable request storage (`0049_runtime_execution_requests`, trigger-protected append-only).
   - 2. Tenant-scoped idempotent issuance (`UNIQUE(organization_id, idempotency_key)`, universal key requirement).
   - 3. All 3 production issuance paths closed via PostgreSQL persistence.
   - 4. Atomic approval consumption and authorization issuance (`UNIQUE(approval_id)`).
   - 5. Canonical admission transaction combining nonce insert, authorization status update, and attempt transition `LEASED -> ADMITTED` (`rowcount == 1`).
   - 6. Universal epoch invalidation covering all 14 authority mutations.
   - 7. Monotonic worker fencing (`runtime_execution_fences` atomic counter + synchronous expiry check).
   - 8. Durable attempt state machine (`0051_runtime_execution_attempts`, `evidence_status` column).
   - 9. One-shot backend-start claim (`claim_backend_start` with `rowcount == 1` returning clean `BackendExecutionClaim`).
   - 10. Atomic pre-effect CAS transitions (`claim_local_effect_start` & `claim_external_effect_transmission`) closing read/write races.
   - 11. Target resolution and IP pinning in `SafeNetworkBackend`.
   - 12. Complete append-only request immutability trigger rejecting all UPDATE/DELETE.
   - 13. Concurrency-safe idempotency insertion handling duplicate key collisions.
   - 14. Universal capacity reservation and release on all terminal paths.
   - 15. Preservation of `SafeNetworkBackend` and container isolation.
   - **Zero Task 10 activation may proceed before this gate passes.**

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
| **Task 8A1** | Durable Request Storage (Mig 0049) & Repository | SERIAL CORE | Head `0048` | `migrations/0049_*.py`, `db/execution_request_repository.py` | YES (Schema lane) |
| **Task 8A2** | Durable Auth Storage (Mig 0050) & Repository | SERIAL CORE | Task 8A1 | `migrations/0050_*.py`, `db/execution_authorization_repository.py` | NO (Migration chain) |
| **Task 8A3** | Execution Attempt Schema (Mig 0051) & Repository | SERIAL CORE | Task 8A2 | `migrations/0051_*.py`, `db/execution_attempt_repository.py` | NO (Migration chain) |
| **Task 8A4** | Worker Lease & Fence Schema (Mig 0052) & Repositories | SERIAL CORE | Task 8A3 | `migrations/0052_*.py`, `db/execution_fence_repository.py`, `db/admission_lease_repository.py` | NO (Migration chain) |
| **Task 8A5** | Centralized Issuer & Approval Atomicity | SERIAL CORE | Tasks 8A1-8A4 | `governance/execution_issuer.py`, `governance/approval_service.py`, `mcp/governance_integration.py`, `mcp/upstream_dispatch.py` | NO (Requires full schema) |
| **Task 8B** | Universal Epoch Coverage (14 Mutations), Revalidation & Atomic Admission (F4.2-01) | SERIAL CORE | Task 8A5 | `db/execution_nonce_repository.py`, `governance/execution.py`, `iam/session.py`, `iam/break_glass.py`, `runtime/revalidation.py` | NO (Database atomic) |
| **Task 9A** | Worker Lease Acquisition, Monotonic Fencing & Backend-Start Claim | SERIAL CORE | Tasks 8A4, 8A5 | `runtime/worker/lease.py`, `db/execution_attempt_repository.py` (`claim_backend_start`) | NO (Requires leases & attempts) |
| **Task 9B** | Pre-Effect CAS, Executor Verification, Target/IP Pinning & Capacity Management (F4.2-02, F4.2-04) | SERIAL CORE | Tasks 8B, 9A | `governance/execution.py` (`InternalToolExecutor`), `governance/upstream_executor.py` (`UpstreamMCPExecutor`), `db/execution_attempt_repository.py`, `runtime/admission/controller.py` | NO (Requires claim & receipt) |
| **Task 10** | Dispatcher Activation Gate (15 Mandatory Prerequisites) | INTEGRATION GATE | Tasks 6, 7, 8B, 9B | `runtime/dispatcher.py`, `runtime/worker/worker.py` | NO (Activation Gate) |
| **Task 11** | Worker Lease Heartbeat, Crash Recovery & Stale Reaper | SERIAL CORE | Task 10 | `runtime/worker/supervisor.py` | NO (Depends on Gate) |
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

    subgraph LANE_SCHEMA [Lane Schema: Linear PostgreSQL Migrations 0049-0052]
        HEAD --> T8A1[Task 8A1: Mig 0049 Execution Requests & Repo]
        T8A1 --> T8A2[Task 8A2: Mig 0050 Execution Auths & Repo]
        T8A2 --> T8A3[Task 8A3: Mig 0051 Execution Attempts & Repo with evidence_status]
        T8A3 --> T8A4[Task 8A4: Mig 0052 Worker Leases & Fences Repo]
    end

    subgraph LANE_A2 [Lane A2: Durable Issuance & Canonical Admission]
        T8A4 --> T8A5[Task 8A5: Centralized Issuance Service & Approval Atomicity]
        T8A5 --> T8B[Task 8B: 14 Mutation Epoch Bump & Atomic admit_execution + LEASED->ADMITTED]
    end

    subgraph LANE_C1 [Lane C1: Fencing, Backend-Start Claim & Pre-Effect CAS]
        T8A4 & T8A5 --> T9A[Task 9A: Monotonic Fencing & claim_backend_start]
        T8B & T9A --> T9B[Task 9B: Atomic CAS claim_local_effect_start / claim_external_effect_transmission & Evidence Precedence]
    end

    subgraph GATE_10 [Integration Gate: Dispatcher Activation]
        T6 & T7 & T8B & T9B --> T10[Task 10 Gate: Dispatcher Activation<br/>Strict Preconditions: All 15 Security Invariants Proven]
    end

    subgraph LANE_C2 [Lane C2: Crash Recovery & Side-Effect Safety]
        T10 --> T11[Task 11: Worker Heartbeats, Reaper & Capacity Reconciler]
        T11 --> T12[Task 12: Uncertain Side-Effect Idempotency]
    end

    subgraph LANE_B [Lane B: WP-ISO-01 Container Hardening]
        T13[Task 13: CPU/RAM/PID Limits] --> T14[Task 14: Workspace 10MB/100 Files]
        T13 --> T15[Task 15: Timeout & SIGKILL]
    end

    subgraph SHUTDOWN [Operations, Shutdown & Probes]
        T10 & T15 --> T16[Task 16: Two-Phase Graceful Shutdown]
        T16 --> T17[Task 17: Probe Decoupling /livez /readyz]
    end

    subgraph INTEGRATION [Final Test & Verification Gates]
        T11 & T12 & T14 & T17 --> T19[Task 19: Multi-Process Real Infra Suite]
        T1 --> T18[Task 18: 15 Prometheus Metrics]
        T6 --> T21[Task 21: Configuration Bounds]
        T18 & T19 & T21 --> T20[Task 20: Canonical Security Regression]
        T20 --> T22[Task 22: Candidate Freeze & Evidence Pack]
    end
```
