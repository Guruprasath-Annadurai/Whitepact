# WhitePact Phase 7A Critical Path Analysis

**Document Status:** Approved Architecture Specification
**Target Worktree:** `/Users/ag/whitepact-phase7a-final-plan`
**Base Candidate SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c`
**Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Alembic Head:** `0048` (`0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Critical Path Calculation

The implementation critical path represents the sequence of dependent tasks that defines the minimum calendar time to completion. No task on the critical path can be delayed without delaying the entire Phase 7A completion.

Because tasks in Lane B (WP-ISO-01), Lane C (Worker Lease), Lane D (Redis), and Lane E (Observability) can run in parallel with Lane A (Admission & Concurrency), the critical path is strictly dictated by the **Governance-to-Execution Decoupling Chain**.

---

## 2. Sequence of Critical Path Milestones

```
[PREREQUISITE] Codex Approval of Auth Candidate (13e8de0)
      │
      ▼ (Critical Task 1)
[CP-01] Task 1: Admission Domain Models & State Machine
      │
      ▼ (Critical Task 2)
[CP-02] Task 2: Local Deterministic Admission Controller
      │
      ▼ (Critical Task 4)
[CP-03] Task 4: Per-Tenant Concurrency Quotas
      │
      ▼ (Critical Task 6)
[CP-04] Task 6: Bounded Multi-Tenant Fair Queue
      │
      ▼ [CHECKPOINT 1: CodeRabbit / Codex Review of Admission Core]
      │
      ▼ (Critical Task 9: Joins Lane A with Lane C Task 8)
[CP-05] Task 9: Worker Dispatcher & Inline Decoupling
      │
      ▼ (Critical Task 10)
[CP-06] Task 10: Crash Recovery & Stale Lease Reaper
      │
      ▼ (Critical Task 11)
[CP-07] Task 11: Side-Effect Uncertainty & Idempotency Guard
      │
      ▼ [CHECKPOINT 2: CodeRabbit / Codex Review of Worker Lease & Crash Recovery]
      │
      ▼ (Critical Task 17: Joins with Lane B Task 16 & Lane D Task 13)
[CP-08] Task 17: Graceful Shutdown Supervisor
      │
      ▼ (Critical Task 18)
[CP-09] Task 18: Readiness / Liveness Probe Decoupling
      │
      ▼ (Critical Task 20)
[CP-10] Task 20: Real Infrastructure Distributed Tests (PG + Redis + Docker)
      │
      ▼ [CHECKPOINT 3: Real Infrastructure Gate (Full Multi-Process Validation)]
      │
      ▼ (Critical Task 21)
[CP-11] Task 21: Canonical Security Regression Suite
      │
      ▼ [GATE: Full Test Suite Twice Clean-Process (3,581+ Tests x 2)]
      │
      ▼ (Critical Task 22)
[CP-12] Task 22: Candidate Freeze & Review Evidence Pack
      │
      ▼
[FINAL] Freeze Phase 7A Candidate for Codex Independent Review
```

---

## 3. Parallel Off-Path Subsystems (Independent Acceleration)

While the critical path advances through CP-01 to CP-07, the following tasks execute concurrently on worker lanes:

1. **Lane B (WP-ISO-01 Hardening):**
   - Task 14 (Compute Limits CPU/RAM/PID)
   - Task 15 (Workspace & File Limits)
   - Task 16 (Timeout and Cancellation)
   - *Joins Critical Path at:* Task 17 (Graceful Shutdown).
2. **Lane C (Worker Lease Durability):**
   - Task 8 (Worker Lease Contract & Migration 0049)
   - *Joins Critical Path at:* Task 9 (Dispatcher Decoupling).
3. **Lane D (Redis Ephemeral Coordination):**
   - Task 12 (Redis Coordination Primitives)
   - Task 13 (Redis Fail-Closed Behavior)
   - *Joins Critical Path at:* Task 17 (Graceful Shutdown).
4. **Lane E (Observability):**
   - Task 19 (Phase 7A Prometheus Metrics)
   - *Joins Critical Path at:* Task 20 (Real Infra Integration).

---

## 4. Formal Review Checkpoints and Verification Gates

| Checkpoint / Gate | Timing | Scope of Review | Required Verifiers | Action on Failure |
| :--- | :--- | :--- | :--- | :--- |
| **Prerequisite Gate** | Pre-Implementation | Formal Codex Approval of `13e8de0` | Codex | Abort Phase 7A; return to auth remediation |
| **Review Checkpoint 1** | Post-Task 6 | Admission domain, concurrency quotas, fair queue | CodeRabbit + Concurrency Architect | Fix findings before proceeding to Task 9 |
| **Review Checkpoint 2** | Post-Task 11 | Worker lease, mutual exclusion, crash recovery, idempotency | Codex Independent Review | Rework worker lease logic; freeze implementation |
| **Review Checkpoint 3** | Post-Task 20 | Real PostgreSQL, real Redis, and real Docker execution | Distributed Systems Architect | Debug race conditions under real infrastructure |
| **Full Suite Gate 1** | Pre-Freeze | Full test suite from clean process (Run 1) | Automated Pytest (`pytest tests/ -q`) | 0 failures allowed; fix regressions |
| **Full Suite Gate 2** | Pre-Freeze | Full test suite from clean process (Run 2) | Automated Pytest (`pytest tests/ -q`) | 0 failures allowed; verify determinism |
| **Static Gates** | Pre-Freeze | `git diff --check`, Ruff, Mypy, SPDX, Gitleaks, Alembic | Static linters & security scanners | 0 lint or typing errors allowed |
| **Final Review Gate** | Post-Task 22 | Complete Phase 7A candidate freeze | Codex Independent Review | Freeze SHA returned to Codex for Phase 7B readiness |
