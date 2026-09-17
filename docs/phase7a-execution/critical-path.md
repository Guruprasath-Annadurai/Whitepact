# WhitePact Phase 7A Critical Path Analysis

**Document Status:** CANONICAL SPECIFICATION PASS 2 (POST-CODEX REVIEW REMEDIATION)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Critical Path Calculation

The implementation critical path represents the sequence of dependent tasks defining the minimum safe calendar time to completion. No task on the critical path can be delayed without delaying the entire Phase 7A completion.

Because tasks in Lane B (WP-ISO-01 compute and filesystem limits) and Lane D (Observability metrics and configuration bounds) can run in parallel with Lane A (Admission & Coordination) and Lane C1 (Worker Lease Schema), the critical path is strictly dictated by the **Coordination-to-Dispatch Activation Chain**.

---

## 2. Sequence of Critical Path Milestones

```
[APPROVED CANONICAL FOUNDATION: 13e8de0 | MIGRATION HEAD: 0048]
      │
      ▼ (Critical Task 1)
[CP-01] Task 1: Admission Domain Models & State Machine
      │
      ▼ (Critical Task 2)
[CP-02] Task 2: Local Deterministic Admission Controller
      │
      ▼ (Critical Task 3)
[CP-03] Task 3: Distributed Coordination Abstract Contract
      │
      ▼ (Critical Task 4)
[CP-04] Task 4: Redis Distributed Coordinator Implementation
      │
      ▼ (Critical Task 5)
[CP-05] Task 5: Redis Failure & Fail-Closed Boundary
      │
      ▼ (Critical Task 6)
[CP-06] Task 6: Multi-Tenant Concurrency Quotas (Plan-Neutral)
      │
      ▼ (Critical Task 7)
[CP-07] Task 7: Bounded Multi-Tenant Fair Queue
      │
      ▼ (Critical Task 8: Lane A)
[CP-08] Task 8: Durable EA Storage (Migration 0049) & Two-Stage Revalidation
      │
      ▼ (Critical Task 9: Lane C1)
[CP-09] Task 9: Worker Lease Contract, Migration 0050 & DB-Enforced Exclusivity
      │
      ▼ [CHECKPOINT 1: Coordination, Durable EA & Lease Exclusivity Core Verification]
      │
      ▼ (Critical Task 10: INTEGRATION GATE)
[CP-10] Task 10: Worker Dispatcher & Canonical admit_execution Bridge
      │
      ▼ (Critical Task 11: Lane C2)
[CP-11] Task 11: Worker Heartbeats, Crash Recovery & Stale Lease Reaper
      │
      ▼ (Critical Task 12: Lane C2)
[CP-12] Task 12: Side-Effect Safety & Uncertain State Handling (Zero Blind Replay)
      │
      ▼ [CHECKPOINT 2: Worker Lifecycle & Side-Effect Recovery Verification]
      │
      ▼ (Critical Task 16: Joins with Lane B Task 15)
[CP-13] Task 16: Graceful Shutdown Supervisor (Two-Phase Drain)
      │
      ▼ (Critical Task 17)
[CP-14] Task 17: Readiness / Liveness Probe Decoupling (/readyz vs /livez)
      │
      ▼ (Critical Task 19: Joins with Lane D Tasks 18 & 21)
[CP-15] Task 19: Multi-Process Real Infrastructure Tests (Independent OS Processes)
      │
      ▼ [CHECKPOINT 3: Real Infrastructure Gate (Multi-Process Execution against PG/Redis/Docker)]
      │
      ▼ (Critical Task 20)
[CP-16] Task 20: Canonical Security Regression Suite
      │
      ▼ [GATE: Full Test Suite Twice Clean-Process (3,581+ Tests x 2)]
      │
      ▼ (Critical Task 22)
[CP-17] Task 22: Candidate Freeze & Review Evidence Pack
      │
      ▼
[FINAL] Freeze Phase 7A Candidate for Codex Independent Review
```

---

## 3. Parallel Off-Path Subsystems (Independent Acceleration)

While the critical path advances through CP-01 to CP-12, the following tasks execute concurrently on worker lanes:

1. **Lane B (WP-ISO-01 Hardening):**
   - Task 13 (Compute Limits: CPU 0.5, RAM 256MB, PID 32)
   - Task 14 (Workspace Limits: 10MB workspace, 100 files, 64KB output)
   - Task 15 (Timeout 15s and Container Cancellation)
   - *Joins Critical Path at:* Task 16 (Graceful Shutdown).
2. **Lane D (Operations & Observability):**
   - Task 18 (Phase 7A Prometheus Metrics)
   - Task 21 (Configuration Bounds & Provisional Defaults Audit)
   - *Joins Critical Path at:* Task 19 (Real Infra Integration).

---

## 4. Formal Review Checkpoints and Verification Gates

| Checkpoint / Gate | Timing | Scope of Review | Required Verifiers | Action on Failure |
| :--- | :--- | :--- | :--- | :--- |
| **Foundation Gate** | Pre-Implementation | Approved Canonical Base `13e8de0`, Head `0048` | Codebase Audit | Abort Phase 7A; return to auth remediation |
| **Review Checkpoint 1** | Post-Task 9 | Admission domain, Redis coordination, Migration `0049` (EA), Migration `0050` (Lease partial unique index) | Concurrency Architect | Fix findings before activating dispatcher |
| **Review Checkpoint 2** | Post-Task 12 | Worker lifecycle, canonical `admit_execution` integration, crash recovery, UNCERTAIN side-effect handling | Codex Independent Review | Rework worker lease logic; freeze implementation |
| **Review Checkpoint 3** | Post-Task 19 | Real PostgreSQL, real Redis, and real Docker multi-process execution (`test_multi_process_lease_and_admission_race.py`) | Distributed Systems Architect | Debug race conditions under real infrastructure |
| **Full Suite Gate 1** | Pre-Freeze | Full test suite from clean process (Run 1) | Automated Pytest (`pytest tests/ -q`) | 0 failures allowed; fix regressions |
| **Full Suite Gate 2** | Pre-Freeze | Full test suite from clean process (Run 2) | Automated Pytest (`pytest tests/ -q`) | 0 failures allowed; verify determinism |
| **Static Gates** | Pre-Freeze | `git diff --check`, Ruff, Mypy, SPDX, Gitleaks, Alembic | Static linters & security scanners | 0 lint or typing errors allowed |
| **Final Review Gate** | Post-Task 22 | Complete Phase 7A candidate freeze | Codex Independent Review | Freeze SHA returned to Codex for Phase 7B readiness |
