# WhitePact Phase 7A Fast-Track Parallelization Map

**Document Status:** Approved Architecture Specification
**Target Worktree:** `/Users/ag/whitepact-phase7a-final-plan`
**Base Candidate SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c`
**Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`

---

## 1. Fast-Track Principles

Parallelization in Phase 7A must never compromise the integrity of WhitePact's core security doctrine:
1. **Disjoint File Sets:** No two parallel lanes may edit or create the same source or test file.
2. **Disjoint Invariants:** Each lane owns a separate security dimension (e.g., Lane A owns capacity limits; Lane B owns container resource isolation; Lane C owns telemetry).
3. **Stable Contracts:** Inter-lane communication relies exclusively on immutable typed dataclasses and abstract interfaces defined upfront in Task 1.

---

## 2. Parallel Implementation Lanes

### Lane A: Admission & Concurrency Engine (Critical Security Core)
- **Primary Responsibility:** Admission state machine, global/tenant/workload capacity semaphores, bounded fair queueing, and queue-time authorization revalidation.
- **Tasks Owned:** Tasks 1, 2, 3, 4, 5, 6, 7.
- **Files Owned:**
  - `src/responsibleai/runtime/admission/models.py` [CREATE]
  - `src/responsibleai/runtime/admission/controller.py` [CREATE]
  - `src/responsibleai/runtime/queue/models.py` [CREATE]
  - `src/responsibleai/runtime/queue/bounded_queue.py` [CREATE]
  - `src/responsibleai/runtime/queue/fair_scheduler.py` [CREATE]
  - `src/responsibleai/runtime/revalidation.py` [CREATE]
  - `tests/runtime/test_admission_*.py` [CREATE]
  - `tests/runtime/test_tenant_concurrency.py` [CREATE]
  - `tests/runtime/test_bounded_queue.py` [CREATE]
  - `tests/runtime/test_revalidation.py` [CREATE]
- **Lane Dependency:** Auth canonical approval (`13e8de0`).
- **Merge / Reconciliation Point:** Milestone 1 (Admission Core Verification).
- **Security Reviewer:** Codex Independent Review.

---

### Lane B: WP-ISO-01 Isolation & Resource Hardening
- **Primary Responsibility:** Enforcing physical container containment, CPU/memory/PID limits, workspace directory byte ceilings (10 MB), file count ceilings (100 files), and timeout termination.
- **Tasks Owned:** Tasks 14, 15, 16.
- **Files Owned:**
  - `src/responsibleai/isolation/models.py` [MODIFY]
  - `src/responsibleai/isolation/filesystem.py` [MODIFY]
  - `src/responsibleai/isolation/container_backend.py` [MODIFY]
  - `tests/isolation/test_wp_iso_01_*.py` [CREATE]
  - `tests/isolation/test_container_cancellation.py` [CREATE]
- **Lane Dependency:** Zero dependency on Lane A or Lane C. Can begin immediately upon auth approval.
- **Merge / Reconciliation Point:** Milestone 2 (Isolation Hardening Verification).
- **Security Reviewer:** CodeRabbit + Security Architect Review.

---

### Lane C: Worker Lease & Durable Checkpoint Engine
- **Primary Responsibility:** Worker lease lifecycle, database schema migration `0049`, row-level locking, heartbeat renewal, and crash recovery reaper.
- **Tasks Owned:** Tasks 8, 10, 11.
- **Files Owned:**
  - `migrations/versions/0049_runtime_worker_leases.py` [CREATE]
  - `src/responsibleai/runtime/worker/lease.py` [CREATE]
  - `src/responsibleai/runtime/worker/supervisor.py` [CREATE]
  - `src/responsibleai/db/admission_lease_repository.py` [CREATE]
  - `tests/runtime/test_worker_lease.py` [CREATE]
  - `tests/runtime/test_crash_recovery.py` [CREATE]
  - `tests/runtime/test_external_effect_idempotency.py` [CREATE]
- **Lane Dependency:** Migration head `0048` verified. Can run in parallel with Lane A and Lane B.
- **Merge / Reconciliation Point:** Milestone 3 (Worker Durability Verification).
- **Security Reviewer:** Codex Independent Review.

---

### Lane D: Ephemeral Distributed Coordination (Redis)
- **Primary Responsibility:** Redis semaphore client, atomic Lua scripts for distributed token buckets, and fail-closed exception boundaries.
- **Tasks Owned:** Tasks 12, 13.
- **Files Owned:**
  - `src/responsibleai/runtime/coordination/base.py` [CREATE]
  - `src/responsibleai/runtime/coordination/redis_coordinator.py` [CREATE]
  - `tests/runtime/test_redis_coordinator.py` [CREATE]
  - `tests/runtime/test_redis_fail_closed.py` [CREATE]
- **Lane Dependency:** Zero dependency on Lane B or Lane C. Requires Task 1 models.
- **Merge / Reconciliation Point:** Milestone 1 (Integrated with Lane A).
- **Security Reviewer:** Concurrency / Reliability Engineer.

---

### Lane E: Observability & Health Probes
- **Primary Responsibility:** Registering 15 Prometheus runtime metrics under `whitepact_*`, decoupling Kubernetes `/livez` and `/readyz` probe routes, and graceful shutdown signal integration.
- **Tasks Owned:** Tasks 17, 18, 19.
- **Files Owned:**
  - `src/responsibleai/dashboard/prometheus.py` [MODIFY]
  - `src/responsibleai/runtime/health.py` [CREATE]
  - `src/responsibleai/runtime/shutdown.py` [CREATE]
  - `src/responsibleai/dashboard/app.py` [MODIFY]
  - `tests/dashboard/test_runtime_metrics.py` [CREATE]
  - `tests/dashboard/test_health_probes.py` [CREATE]
  - `tests/runtime/test_graceful_shutdown.py` [CREATE]
- **Lane Dependency:** Integrates with outputs of Lanes A, B, and C.
- **Merge / Reconciliation Point:** Milestone 4 (System Integration).
- **Security Reviewer:** SRE / Observability Architect.

---

## 3. Parallel Execution Timeline and Synchronization Points

```
TIME ────────────────────────────────────────────────────────────────────────►
[Auth Approved]
   │
   ├─► LANE A: Admission & Concurrency (Tasks 1-7) ──────────────► [Sync Point 1]
   │                                                                    │
   ├─► LANE B: WP-ISO-01 Isolation Hardening (Tasks 14-16) ─────────────┤
   │                                                                    │
   ├─► LANE C: Worker Lease & Migration 0049 (Tasks 8, 10, 11) ────────┤
   │                                                                    │
   └─► LANE D: Redis Coordination (Tasks 12-13) ────────────────────────┤
                                                                        ▼
                                                   [MILESTONE: CORE CONVERGENCE]
                                                                        │
   ┌────────────────────────────────────────────────────────────────────┘
   │
   ├─► Task 9: Dispatcher & Worker Decoupling (Lane A + C Integration)
   ├─► LANE E: Observability & Shutdown (Tasks 17, 18, 19)
   │
   ▼
[MILESTONE: INTEGRATED SYSTEM VERIFICATION]
   │
   ├─► Task 20: Real Infra Distributed Tests (PG + Redis + Docker)
   ├─► Task 21: Phase 7A Canonical Security Regression
   └─► Task 22: Candidate Freeze & Evidence Pack
   │
   ▼
[PHASE 7A CANDIDATE READY FOR CODEX FINAL REVIEW]
```

---

## 4. Conflict Avoidance Protocols

1. **Shared File Lockout:** `src/responsibleai/dashboard/app.py` is touched ONLY in Lane E (Tasks 17 and 18). No other lane may touch this file.
2. **Database Migration Lockout:** Migration `0049` is created exclusively in Lane C (Task 8). No other lane may create or modify migrations.
3. **Isolation Containment:** `src/responsibleai/isolation/*` is modified exclusively in Lane B (Tasks 14-16).
4. **Zero Contention Verification:** Prior to any merge, `git diff --name-only` is run against base to verify zero overlapping paths.
