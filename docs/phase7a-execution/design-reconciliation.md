# WhitePact Phase 7A Design Reconciliation

**Document Status:** CANONICAL SPECIFICATION PASS 4.2 (SECURITY CONSISTENCY CLOSURE)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary

This document provides a systematic reconciliation between the Phase 7A Master Design (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`) and the approved canonical enterprise authentication baseline (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

Pass 4.2 definitively closes all remaining security consistency gaps:
1. **Atomic Admission & Attempt Transition (F4.2-01):** Canonical admission burns the single-use nonce, marks authorization `CONSUMED`, and transitions attempt `LEASED -> ADMITTED` in ONE atomic PostgreSQL transaction (`rowcount == 1`).
2. **Atomic Pre-Effect CAS (F4.2-02):** Eliminates read/write races. Executors invoke `claim_local_effect_start` or `claim_external_effect_transmission` immediately before side-effect execution, asserting `rowcount == 1`. Concurrent duplicate calls fail closed before touching backend.
3. **Clean Durable Claim (F4.2-03):** `BackendExecutionClaim` removes decorative `backend_start_token`. Security is enforced by durable database state and atomic CAS transitions.
4. **Strict Evidence Precedence & Durable Status (F4.2-04):** Normal success commits evidence before attempt completion. `evidence_status` (`PENDING`, `COMMITTED`, `INCOMPLETE`) is durably owned by `runtime_execution_attempts` (Migration `0051`).
5. **Durable Immutable Execution Requests:** Append-only `runtime_execution_requests` (Migration `0049`), trigger rejects UPDATE/DELETE, universal idempotency key requirement.
6. **Approval Consumption & Authorization Atomicity:** Single transaction in `governance_execution_authorizations` (Migration `0050`) with `UNIQUE(approval_id)`.
7. **Monotonic Generation Allocation & Fencing:** Dedicated table `runtime_execution_fences` (Migration `0052`) provides atomic monotonic generation increments; synchronous lease expiry verification.

---

## 2. Invariant Reconciliation Matrix

| Subsystem / Dimension | Status | Detailed Findings & Adaptations |
| :--- | :--- | :--- |
| **Execution Request Storage** | SECURITY-RELEVANT ADAPTATION | Persisted in `runtime_execution_requests` (Migration 0049). Append-only, trigger rejects UPDATE/DELETE, zero mutable status. |
| **Idempotency & Deduplication** | RECONCILED & CONCURRENCY-SAFE | Universal key requirement. Atomic insert on conflict loads existing row and compares digest. Identical -> return existing; different -> HTTP 409. |
| **Approval Consumption** | SECURITY-RELEVANT ADAPTATION | Combined with authorization issuance in ONE transaction. `UNIQUE(approval_id)` in `governance_execution_authorizations` (Migration 0050) guarantees single use. |
| **Canonical Admission & Attempt Transition** | SECURITY-RELEVANT ADAPTATION (F4.2-01) | `admit_execution()` in ONE atomic transaction: burns nonce, updates authorization `ISSUED -> CONSUMED`, and transitions attempt `LEASED -> ADMITTED` (`rowcount == 1`). |
| **One-Shot Backend-Start Claim** | SECURITY-RELEVANT ADAPTATION (F4.2-03) | `claim_backend_start()` atomically verifies unexpired lease under lock, transitions `ADMITTED -> BACKEND_STARTING` (`rowcount == 1`), returns clean `BackendExecutionClaim`. |
| **Atomic Pre-Effect CAS** | SECURITY-RELEVANT ADAPTATION (F4.2-02) | `claim_local_effect_start` / `claim_external_effect_transmission` execute atomic CAS with `rowcount == 1` immediately pre-container/pre-socket. Eliminates check-then-write race. |
| **Evidence Precedence & Status Ownership** | RECONCILED & ORDERED (F4.2-04) | Evidence write precedes normal attempt completion. Durable `evidence_status` on `runtime_execution_attempts` records `COMMITTED` or `INCOMPLETE`. |
| **Monotonic Fencing** | RECONCILED & HARDENED | Dedicated `runtime_execution_fences` counter table (Migration 0052). Atomic `UPDATE ... RETURNING`. Fence synchronously checks unexpired lease (`expires_at > now`). |
| **SafeNetwork Boundary** | HARDENED | Resolves DNS, validates target fingerprint, pins IP address, and executes atomic CAS immediately pre-socket. |
| **Capacity Management** | HARDENED | Every reservation has an explicit release path on completion, failure, early invalidation, or background reconciliation. |
| **PostgreSQL Migration Sequence** | RESOLVED & ORDERED | Canonical head `0048` -> `0049_runtime_execution_requests` -> `0050_runtime_execution_authorizations` -> `0051_runtime_execution_attempts` -> `0052_runtime_worker_leases`. |

---

## 3. Critical Architectural Clarifications

### 3.1 Backend-Start Claim & Pre-Effect CAS Linearization
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
  4. Return clean BackendExecutionClaim
              │
              ▼
[Executor Pre-Effect Atomic CAS immediately before Side-Effect]
  Local: claim_local_effect_start() -> CAS: BACKEND_STARTING -> RUNNING (rowcount == 1)
  External: claim_external_effect_transmission() -> CAS: BACKEND_STARTING -> RUNNING/EFFECT_TRANSMITTING (rowcount == 1)
              │
        ┌─────┴─────┐
        │ Success   │ Failure (0 rows / Race lost / Fabricated claim)
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
[Update Attempt: state = 'COMPLETED', effect_state = 'EFFECT_CONFIRMED', evidence_status = 'COMMITTED']
(If evidence write fails: state = 'COMPLETED', evidence_status = 'INCOMPLETE')
           │
           ▼
[Update Lease: status = 'COMPLETED']
           │
           ▼
[Release Capacity Reservation in Redis / Semaphore]
```
