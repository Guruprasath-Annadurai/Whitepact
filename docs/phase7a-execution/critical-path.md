# WhitePact Phase 7A Critical Path Analysis

**Document Status:** CANONICAL SPECIFICATION PASS 4.3 (SECURITY BOUNDARY CLOSURE)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Critical Path Calculation

The implementation critical path represents the sequence of dependent tasks defining the minimum safe calendar time to completion. No task on the critical path can be delayed without delaying Phase 7A completion.

Because tasks in Lane B (WP-ISO-01 compute and filesystem limits) and Lane D (Observability metrics and configuration bounds) run in parallel with Lane A1 (Admission & Coordination) and Lane C1 (Attempt state machine & worker lease fencing), the critical path is strictly dictated by the **Durable Authority, Issuance, Atomic Admission, Attempt Fencing, and Dispatch Activation Chain**.

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
      ▼ (Critical Task 8A1: Migration 0049 & Request Repo)
[CP-08A1] Task 8A1: Durable Request Schema (Mig 0049, Append-Only) & Repository
      │
      ▼ (Critical Task 8A2: Migration 0050 & Auth Repo)
[CP-08A2] Task 8A2: Durable Auth Schema (Mig 0050, UNIQUE approval_id) & Repository
      │
      ▼ (Critical Task 8A3: Migration 0051 & Attempt Repo)
[CP-08A3] Task 8A3: Execution Attempt Schema (Mig 0051, Nullable Lease Fields, evidence_status & backend_start_token_hash) & Repository
      │
      ▼ (Critical Task 8A4: Migration 0052, Lease & Fence Repos)
[CP-08A4] Task 8A4: Worker Lease & Execution Fence Schema (Mig 0052) & Repositories
      │
      ▼ (Critical Task 8A5: Centralized Issuance Service)
[CP-08A5] Task 8A5: Centralized Issuer, Approval Atomicity & Universal Idempotency
      │
      ▼ (Critical Task 8B: Canonical Admission)
[CP-08B] Task 8B: Universal 14-Mutation Epoch Coverage, Atomic Admission Transaction & AdmissionReceipt
      │
      ▼ (Critical Task 9A: Fencing & Backend Start Claim)
[CP-09A] Task 9A: Monotonic Fencing, Synchronous Expiry Check & claim_backend_start() (Token Hash Persistence)
      │
      ▼ (Critical Task 9B: Downstream Executor Verification & SafeNetwork IP Pinning)
[CP-09B] Task 9B: Pre-Effect Atomic CAS with Lease Revalidation (claim_local/external), SafeNetwork IP Pinning, Evidence Precedence & Capacity Release
      │
      ▼ [CHECKPOINT 1: Coordination, All-Path Durable Issuance & Single Admission Core Verification]
      │
      ▼ (Critical Task 10: INTEGRATION GATE)
[CP-10] Task 10 Gate: Worker Dispatcher & Execution Worker (Requires ALL 16 Security Prerequisites Proven)
      │
      ▼ (Critical Task 11: Lane C2)
[CP-11] Task 11: Worker Heartbeats, Crash Recovery, Crash Point O Reconciler & Stale Lease Reaper
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
[FINAL] Freeze Phase 7A Candidate for Independent Review
```

---

## 3. Parallel Off-Path Subsystems

1. **Lane B (WP-ISO-01 Hardening):** Tasks 13, 14, 15 (Joins Critical Path at Task 16).
2. **Lane D (Operations & Observability):** Tasks 18, 21 (Joins Critical Path at Task 19).
