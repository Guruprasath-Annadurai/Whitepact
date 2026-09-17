# WhitePact Phase 7A Fast-Track Parallelization Map

**Document Status:** CANDIDATE IMPLEMENTATION PLAN (PENDING INDEPENDENT REVIEW)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (Auth Candidate Under Codex Review)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`

---

## 1. Fast-Track Principles

Parallelization in Phase 7A must never compromise the integrity of WhitePact's core security doctrine:
1. **Disjoint File Sets:** No two parallel lanes may edit or create the same source or test file.
2. **Disjoint Invariants:** Each lane owns a separate security dimension (e.g., Lane A owns capacity limits and distributed coordination; Lane B owns container resource isolation; Lane C owns worker lease durability).
3. **Plan-Neutrality:** Fairness across all lanes is plan-neutral; commercial plan does not influence queue scheduling or governance authority.
4. **Stable Contracts:** Inter-lane communication relies exclusively on immutable typed dataclasses and abstract interfaces defined upfront in Task 1.

---

## 2. Parallel Implementation Lanes

### Lane A: Admission & Distributed Coordination Engine
- **Primary Responsibility:** Admission state machine, in-process controller, Redis distributed semaphores, fail-closed boundaries, multi-tenant concurrency quotas, plan-neutral fair queueing, and queue-time authorization revalidation.
- **Tasks Owned:** Tasks 1, 2, 3, 4, 5, 6, 7, 8.
- **Files Owned:**
  - `src/responsibleai/runtime/admission/models.py` [CREATE]
  - `src/responsibleai/runtime/admission/controller.py` [CREATE]
  - `src/responsibleai/runtime/coordination/base.py` [CREATE]
  - `src/responsibleai/runtime/coordination/redis_coordinator.py` [CREATE]
  - `src/responsibleai/runtime/queue/models.py` [CREATE]
  - `src/responsibleai/runtime/queue/bounded_queue.py` [CREATE]
  - `src/responsibleai/runtime/queue/fair_scheduler.py` [CREATE]
  - `src/responsibleai/runtime/revalidation.py` [CREATE]
  - `tests/runtime/test_admission_*.py` [CREATE]
  - `tests/runtime/test_coordination_contract.py` [CREATE]
  - `tests/runtime/test_redis_*.py` [CREATE]
  - `tests/runtime/test_integrated_concurrency.py` [CREATE]
  - `tests/runtime/test_bounded_queue.py` [CREATE]
  - `tests/runtime/test_revalidation.py` [CREATE]
- **Lane Dependency:** Auth canonical approval (`13e8de0`).
- **Merge / Reconciliation Point:** Milestone 1 (Coordination & Admission Core Verification).
- **Security Reviewer:** Codex Independent Review.

---

### Lane B: WP-ISO-01 Isolation & Resource Hardening
- **Primary Responsibility:** Enforcing physical container containment, CPU (0.5), memory (256MB), PID (32) limits, workspace directory byte ceilings (10 MB), file count ceilings (100 files), and timeout termination.
- **Tasks Owned:** Tasks 13, 14, 15.
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
- **Primary Responsibility:** Worker lease lifecycle, execution-keyed lease identity (`execution_id`, `attempt`), database schema migration `0049` (conditional on head `0048`), row-level locking, heartbeat renewal, crash recovery reaper, and side-effect safety (`UNCERTAIN` state).
- **Tasks Owned:** Tasks 9, 11, 12.
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
- **Lane Dependency:** Integrates with outputs of Lanes A, B, and C.
- **Merge / Reconciliation Point:** Milestone 4 (System Integration).
- **Security Reviewer:** SRE / Observability Architect.

---

## 3. Parallel Execution Timeline and Activation Gates

```
TIME ────────────────────────────────────────────────────────────────────────►
[Auth Approved: 13e8de0]
   │
   ├─► LANE A: Admission & Coordination (Tasks 1-8) ─────────────► [Gate A Pass]
   │                                                                    │
   ├─► LANE B: WP-ISO-01 Isolation Hardening (Tasks 13-15) ─────────────┤
   │                                                                    │
   ├─► LANE C: Worker Lease & Mig 0049 (Tasks 9, 11, 12) ────────► [Gate C Pass]
   │                                                                    │
   └─► LANE D: Config & Metrics Foundation (Tasks 18, 21) ──────────────┤
                                                                        ▼
                                                [DISPATCHER ACTIVATION GATE]
                                                 (Requires Gate A & Gate C)
                                                                        │
   ┌────────────────────────────────────────────────────────────────────┘
   │
   ├─► Task 10: Dispatcher & Worker Decoupling (Activation)
   ├─► Task 16: Graceful Shutdown Integration
   ├─► Task 17: Health Probes Integration
   │
   ▼
[MILESTONE: INTEGRATED SYSTEM VERIFICATION]
   │
   ├─► Task 19: Real Infra Distributed Tests (PG + Redis + Docker)
   ├─► Task 20: Phase 7A Canonical Security Regression
   └─► Task 22: Candidate Freeze & Evidence Pack
   │
   ▼
[PHASE 7A CANDIDATE READY FOR CODEX FINAL REVIEW]
```

---

## 4. Conflict Avoidance Protocols

1. **Dispatcher Activation Barrier:** `src/responsibleai/mcp/governance_integration.py` is modified ONLY in Task 10, after both Lane A (coordination) and Lane C (worker leases) are verified green.
2. **Shared File Lockout:** `src/responsibleai/dashboard/app.py` is touched ONLY in Lane D (Tasks 16 and 17).
3. **Database Migration Lockout:** Migration `0049` is created exclusively in Lane C (Task 9).
4. **Zero Contention Verification:** Prior to any merge, `git diff --name-only` is run against base to verify zero overlapping paths.
