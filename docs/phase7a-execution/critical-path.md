# WhitePact Phase 7A Critical Path Analysis

**Document Status:** CANONICAL SPECIFICATION PASS 3 (FINAL CALL-PATH & SINGLE-ADMISSION CLOSURE)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Critical Path Calculation

The implementation critical path represents the sequence of dependent tasks defining the minimum safe calendar time to completion. No task on the critical path can be delayed without delaying Phase 7A completion.

Because tasks in Lane B (WP-ISO-01 compute and filesystem limits) and Lane D (Observability metrics and configuration bounds) run in parallel with Lane A1 (Admission & Coordination) and Lane C1 (Worker Lease Schema), the critical path is strictly dictated by the **Durable Authority, Issuance, Atomic Admission, and Dispatch Activation Chain**.

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
      ▼ (Critical Task 8A: Lane A2)
[CP-08A] Task 8A: Durable EA Storage (Migration 0049), Centralized Issuer & All-Path Issuance Integration
      │
      ▼ (Critical Task 8B: Lane A2)
[CP-08B] Task 8B: Two-Stage Revalidation, Atomic Admission Transaction Integration & Admitted Context
      │
      ▼ (Critical Task 9: Lane C1)
[CP-09] Task 9: Worker Lease Contract, Migration 0050 & DB-Enforced Exclusivity
      │
      ▼ [CHECKPOINT 1: Coordination, All-Path Durable Issuance & Single Admission Core Verification]
      │
      ▼ (Critical Task 10: INTEGRATION GATE)
[CP-10] Task 10 Gate: Worker Dispatcher & Execution Worker (Requires All Issuance Paths Closed & Single Admission Proven)
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

## 3. Parallel Off-Path Subsystems

1. **Lane B (WP-ISO-01 Hardening):** Tasks 13, 14, 15 (Joins Critical Path at Task 16).
2. **Lane D (Operations & Observability):** Tasks 18, 21 (Joins Critical Path at Task 19).
