# WhitePact Phase 7A Design Reconciliation

**Document Status:** CANONICAL SPECIFICATION PASS 4.1 (SECURITY CONSISTENCY REMEDIATION)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary

This document provides a systematic reconciliation between the Phase 7A Master Design (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`) and the approved canonical enterprise authentication baseline (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

Pass 4.1 definitively resolves all remaining specification contradictions and closes all 15 findings:
1. **Durable Immutable Execution Requests (4.1-F06, 4.1-F07):** Schema `runtime_execution_requests` (Migration `0049`) is strictly append-only with zero mutable status. Trigger rejects all UPDATE and DELETE.
2. **Tenant-Scoped Concurrency-Safe Idempotency (4.1-F08, 4.1-F09):** Universal idempotency key requirement. Atomic insertion handles duplicate key races safely.
3. **Approval Consumption & Authorization Atomicity:** Schema `governance_execution_authorizations` (Migration `0050`) enforces `UNIQUE(approval_id)`. Approval consumption and authorization issuance occur in ONE PostgreSQL transaction.
4. **Attempt Schema & State Machine (4.1-F01, 4.1-F14, 4.1-F15):** Schema `runtime_execution_attempts` (Migration `0051`) has nullable lease fields in `PENDING` and enforces state CHECK constraints. Active partial unique index prevents concurrent duplicate attempts.
5. **Monotonic Generation Allocation & Fencing (4.1-F04, 4.1-F05):** Dedicated table `runtime_execution_fences` (Migration `0052`) provides atomic monotonic generation increments. Fence check synchronously verifies unexpired lease status (`expires_at > CURRENT_TIMESTAMP`).
6. **One-Shot Backend-Start Claim (4.1-F10):** Canonical API `ExecutionAttemptRepository.claim_backend_start()` atomically claims execution and returns `BackendExecutionClaim`.
7. **Direct Executor Bypass Closure (4.1-F03):** Executors accept ONLY `BackendExecutionClaim` and must call `assert_backend_start_claim(claim)` against PostgreSQL before compute or socket invocation.
8. **SafeNetwork Target & IP Pinning (4.1-F11, 4.1-F12):** Target resolved, IP pinned, and `effect_state = 'EFFECT_TRANSMITTING'` durably committed immediately pre-socket.
9. **Universal Capacity Release (4.1-F13):** Every capacity reservation made at enqueue terminates in an explicit release or background reconciliation.
10. **Universal Epoch Invalidation:** All 14 authority mutations advance `governance_revocation_epochs.epoch` under row lock.
11. **Explicit Scope Separation:** Clear boundary between Hosted Governed Mode and Community Local stdio mode.

---

## 2. Invariant Reconciliation Matrix

| Subsystem / Dimension | Status | Detailed Findings & Adaptations |
| :--- | :--- | :--- |
| **Execution Request Storage** | SECURITY-RELEVANT ADAPTATION | Persisted in `runtime_execution_requests` (Migration 0049). Append-only, trigger rejects UPDATE/DELETE, zero mutable status. Worker reconstructs action without policy re-evaluation. |
| **Idempotency & Deduplication** | RECONCILED & CONCURRENCY-SAFE | Universal key requirement. Atomic insert on conflict loads existing row and compares digest. Identical -> return existing; different -> HTTP 409. |
| **Approval Consumption** | SECURITY-RELEVANT ADAPTATION | Combined with authorization issuance in ONE transaction. `UNIQUE(approval_id)` in `governance_execution_authorizations` (Migration 0050) guarantees an approval can mint at most one authorization. |
| **Attempt State & Lease Nullability** | RESOLVED & HARDENED | `runtime_execution_attempts` (Migration 0051) has nullable lease fields in `PENDING`. Checked via `chk_attempt_lease_fields`. Active partial unique index on active states. |
| **Monotonic Fencing** | RECONCILED & HARDENED | Dedicated `runtime_execution_fences` counter table (Migration 0052). Atomic `UPDATE ... RETURNING`. Fence synchronously checks unexpired lease (`expires_at > now`). |
| **Canonical Admission Gate** | SECURITY-RELEVANT ADAPTATION | `admit_execution()` returns in-process `AdmissionReceipt`. Nonce insert and authorization update (`rowcount == 1`) committed under row lock. |
| **Backend-Start Claim & Verification** | SECURITY-RELEVANT ADAPTATION | `claim_backend_start()` returns `BackendExecutionClaim`. Executors verify claim via `assert_backend_start_claim(claim)` before side-effects. Closes direct executor bypass. |
| **SafeNetwork Boundary** | HARDENED | Resolves DNS, validates target fingerprint, pins IP address, commits `effect_state = 'EFFECT_TRANSMITTING'`, and transmits socket bytes. |
| **Capacity Management** | HARDENED | Every reservation has an explicit release path on completion, failure, early invalidation, or background reconciliation. |
| **Revocation Architecture** | RECONCILED & HARDENED | All 14 mutable authority sources advance `scope="governance"` epoch under row lock. |
| **PostgreSQL Migration Sequence** | RESOLVED & ORDERED | Canonical head `0048` -> `0049_runtime_execution_requests` -> `0050_runtime_execution_authorizations` -> `0051_runtime_execution_attempts` -> `0052_runtime_worker_leases`. |

---

## 3. Critical Architectural Clarifications

### 3.1 Backend-Start Claim & Executor Verification
```
[AdmissionReceipt Held by Worker]
              │
              ▼
[ExecutionAttemptRepository.claim_backend_start()]
  1. Lock active lease row (assert lease_generation == N AND expires_at > now)
  2. UPDATE runtime_execution_attempts
     SET state = 'BACKEND_STARTING', effect_state = 'EFFECT_STARTING'
     WHERE state = 'ADMITTED' AND lease_generation = N
  3. Assert rowcount == 1 (Rollback if 0)
  4. Return BackendExecutionClaim
              │
              ▼
[Executor Receives BackendExecutionClaim]
  1. Execute assert_backend_start_claim(claim) against PostgreSQL
  2. Assert state == 'BACKEND_STARTING', lease matches, digest matches
              │
        ┌─────┴─────┐
        │ Success   │ Failure (Claim invalid / Stale state / Fabricated)
        ▼           ▼
[Invoke Backend]   [Halt Immediately: Zero Container / Socket Execution]
```

### 3.2 Evidence and Finalization Order
```
[Backend Returns Result]
           │
           ▼
[Record Durable Outcome Row]
           │
           ▼
[Record Durable Evidence Bundle in EvidenceStore]
           │
           ▼
[Update Attempt: state = 'COMPLETED', effect_state = 'EFFECT_CONFIRMED']
           │
           ▼
[Update Lease: status = 'COMPLETED']
           │
           ▼
[Release Capacity Reservation in Redis / Semaphore]
```
