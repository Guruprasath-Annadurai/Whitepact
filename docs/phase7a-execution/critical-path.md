# WhitePact Phase 7A Critical Path Analysis

**Document Status:** CANDIDATE IMPLEMENTATION PLAN (PENDING INDEPENDENT REVIEW)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (Auth Candidate Under Codex Review)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Assumed Alembic Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`, conditional upon Codex approval of `13e8de0`)

---

## 1. Critical Path Calculation

The implementation critical path represents the sequence of dependent tasks defining the minimum safe calendar time to completion. No task on the critical path can be delayed without delaying the entire Phase 7A completion.

Because tasks in Lane B (WP-ISO-01 compute and filesystem limits) and Lane D (Observability metrics and configuration bounds) can run in parallel with Lane A (Admission & Coordination) and Lane C (Worker Lease), the critical path is strictly dictated by the **Coordination-to-Dispatch Activation Chain**.

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
      ▼ (Critical Task 8)
[CP-08] Task 8: EA Queue-Time Revalidation (Non-Policy Boundary)
      │
      ▼ (Critical Task 9: Joins with Lane C)
[CP-09] Task 9: Worker Lease Contract & Migration 0049 (Execution-Keyed)
      │
      ▼ [CHECKPOINT 1: CodeRabbit / Codex Review of Coordination & Lease Core]
      │
      ▼ (Critical Task 10: ACTIVATION GATE)
[CP-10] Task 10: Worker Dispatcher Decoupling & Activation
      │
      ▼ (Critical Task 11)
[CP-11] Task 11: Crash Recovery & Stale Lease Reaper
      │
      ▼ (Critical Task 12)
[CP-12] Task 12: Side-Effect Safety & Idempotency Guard (UNCERTAIN Outcome)
      │
      ▼ [CHECKPOINT 2: CodeRabbit / Codex Review of Worker Lifecycle & Side-Effects]
      │
      ▼ (Critical Task 16: Joins with Lane B Task 15)
[CP-13] Task 16: Graceful Shutdown Supervisor (Two-Phase Drain)
      │
      ▼ (Critical Task 17)
[CP-14] Task 17: Readiness / Liveness Probe Decoupling (/readyz vs /livez)
      │
      ▼ (Critical Task 19: Joins with Lane D Tasks 18 & 21)
[CP-15] Task 19: Real Infrastructure Distributed Tests (PG + Redis + Docker)
      │
      ▼ [CHECKPOINT 3: Real Infrastructure Gate (Multi-Process Execution)]
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
| **Prerequisite Gate** | Pre-Implementation | Formal Codex Approval of `13e8de0` | Codex | Abort Phase 7A; return to auth remediation |
| **Review Checkpoint 1** | Post-Task 9 | Admission domain, Redis coordination, fail-closed boundaries, worker lease | CodeRabbit + Concurrency Architect | Fix findings before activating dispatcher |
| **Review Checkpoint 2** | Post-Task 12 | Worker lifecycle, crash recovery, side-effect safety, UNCERTAIN handling | Codex Independent Review | Rework worker lease logic; freeze implementation |
| **Review Checkpoint 3** | Post-Task 19 | Real PostgreSQL, real Redis, and real Docker multi-process execution | Distributed Systems Architect | Debug race conditions under real infrastructure |
| **Full Suite Gate 1** | Pre-Freeze | Full test suite from clean process (Run 1) | Automated Pytest (`pytest tests/ -q`) | 0 failures allowed; fix regressions |
| **Full Suite Gate 2** | Pre-Freeze | Full test suite from clean process (Run 2) | Automated Pytest (`pytest tests/ -q`) | 0 failures allowed; verify determinism |
| **Static Gates** | Pre-Freeze | `git diff --check`, Ruff, Mypy, SPDX, Gitleaks, Alembic | Static linters & security scanners | 0 lint or typing errors allowed |
| **Final Review Gate** | Post-Task 22 | Complete Phase 7A candidate freeze | Codex Independent Review | Freeze SHA returned to Codex for Phase 7B readiness |
