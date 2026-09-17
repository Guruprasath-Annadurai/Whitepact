# WhitePact Phase 7A Design Reconciliation

**Document Status:** CANONICAL SPECIFICATION PASS 4.3 (SECURITY BOUNDARY CLOSURE)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary

This document provides a systematic reconciliation between the Phase 7A Master Design (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`) and the approved canonical enterprise authentication baseline (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

Pass 4.3 definitively closes all remaining security consistency and boundary gaps:
1. **Atomic Admission & Attempt Transition (F4.2-01):** Canonical admission burns the single-use nonce, marks authorization `CONSUMED`, and transitions attempt `LEASED -> ADMITTED` in ONE atomic PostgreSQL transaction (`rowcount == 1`).
2. **Synchronous Lease Revalidation at Final CAS (F4.3-01):** Both `claim_local_effect_start()` and `claim_external_effect_transmission()` execute as a PostgreSQL transaction that synchronously revalidates the CURRENT active unexpired lease under row lock (`FOR UPDATE`). Zombie workers whose leases expired or were superseded during GC stalls fail closed. Fencing correctness does NOT depend on reaper timing.
3. **Non-Reconstructible Backend Claim & Action Binding (F4.3-02):** `claim_backend_start()` generates a cryptographically secure random token (`backend_start_token`) returned only in `BackendExecutionClaim`, while storing only `backend_start_token_hash` in PostgreSQL. The final pre-effect CAS checks `backend_start_token_hash`, verifies the immutable durable request `action_digest`, and clears `backend_start_token_hash = NULL`.
4. **Target Fingerprint Contract (F4.3-03):** `BackendExecutionClaim` carries `target_fingerprint: str | None` sourced from durable authorization. Upstream execution enforces that caller cannot override durable target fingerprint, validates resolved target via `SafeNetworkBackend`, and pins IP before final CAS.
5. **Strict Evidence Precedence & Crash Consistency (F4.2-04, F4.3-04):** Normal success commits evidence in EvidenceStore before attempt completion. While attempt is in state `RUNNING`, `evidence_status` remains `PENDING`. Terminal attempt CAS sets `evidence_status = 'COMMITTED'`. Crash Point O is deterministically reconciled by supervisor detecting the durable EvidenceStore record.
6. **Durable Immutable Execution Requests:** Append-only `runtime_execution_requests` (Migration `0049`), trigger rejects UPDATE/DELETE, universal idempotency key requirement.
7. **Approval Consumption & Authorization Atomicity:** Single transaction in `governance_execution_authorizations` (Migration `0050`) with `UNIQUE(approval_id)`.
8. **Monotonic Generation Allocation & Fencing:** Dedicated table `runtime_execution_fences` (Migration `0052`) provides atomic monotonic generation increments; synchronous lease expiry verification.

---

## 2. Invariant Reconciliation Matrix

| Subsystem / Dimension | Status | Detailed Findings & Adaptations |
| :--- | :--- | :--- |
| **Execution Request Storage** | SECURITY-RELEVANT ADAPTATION | Persisted in `runtime_execution_requests` (Migration 0049). Append-only, trigger rejects UPDATE/DELETE, zero mutable status. |
| **Idempotency & Deduplication** | RECONCILED & CONCURRENCY-SAFE | Universal key requirement. Atomic insert on conflict loads existing row and compares digest. Identical -> return existing; different -> HTTP 409. |
| **Approval Consumption** | SECURITY-RELEVANT ADAPTATION | Combined with authorization issuance in ONE transaction. `UNIQUE(approval_id)` in `governance_execution_authorizations` (Migration 0050) guarantees single use. |
| **Canonical Admission & Attempt Transition** | SECURITY-RELEVANT ADAPTATION (F4.2-01) | `admit_execution()` in ONE atomic transaction: burns nonce, updates authorization `ISSUED -> CONSUMED`, and transitions attempt `LEASED -> ADMITTED` (`rowcount == 1`). |
| **One-Shot Backend-Start Claim** | SECURITY-RELEVANT ADAPTATION (F4.3-02) | `claim_backend_start()` verifies unexpired lease under lock, generates raw `backend_start_token`, stores `backend_start_token_hash` on attempt, transitions `ADMITTED -> BACKEND_STARTING` (`rowcount == 1`), returns `BackendExecutionClaim`. |
| **Atomic Pre-Effect CAS** | SECURITY-RELEVANT ADAPTATION (F4.3-01, F4.3-02, F4.3-03) | `claim_local_effect_start` / `claim_external_effect_transmission` execute atomic CAS with `rowcount == 1` immediately pre-container/pre-socket. Synchronously revalidates lease `FOR UPDATE`, checks immutable request `action_digest` and `target_fingerprint`, and consumes token hash (`NULL`). Eliminates check-then-write race and zombie worker execution. |
| **Evidence Precedence & Status Ownership** | RECONCILED & ORDERED (F4.2-04, F4.3-04) | Evidence write precedes normal attempt completion. Durable `evidence_status` on `runtime_execution_attempts` records `COMMITTED` or `INCOMPLETE`. Crash Point O is deterministically reconciled. |
| **Monotonic Fencing** | RECONCILED & HARDENED | Dedicated `runtime_execution_fences` counter table (Migration 0052). Atomic `UPDATE ... RETURNING`. Fence synchronously checks unexpired lease (`expires_at > now`). |
| **SafeNetwork Boundary** | HARDENED | Resolves DNS, validates durable target fingerprint, pins IP address, and executes atomic CAS immediately pre-socket. |
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
  2. Generate raw backend_start_token; compute token_hash
  3. UPDATE runtime_execution_attempts
     SET state = 'BACKEND_STARTING', effect_state = 'EFFECT_STARTING',
         backend_start_token_hash = token_hash
     WHERE state = 'ADMITTED' AND lease_generation = N
  4. Assert rowcount == 1 (Rollback if 0)
  5. Return BackendExecutionClaim (with raw token & target_fingerprint)
              │
              ▼
[Executor Pre-Effect Atomic CAS immediately before Side-Effect]
  In ONE PostgreSQL Transaction:
  1. Lock active lease in runtime_worker_leases (assert status=ACTIVE AND expires_at > now)
  2. Verify durable request action_digest (and target_fingerprint for external)
  3. Local: claim_local_effect_start() -> UPDATE: BACKEND_STARTING -> RUNNING, backend_start_token_hash = NULL (rowcount == 1)
  4. External: claim_external_effect_transmission() -> UPDATE: BACKEND_STARTING -> RUNNING/EFFECT_TRANSMITTING, backend_start_token_hash = NULL (rowcount == 1)
              │
        ┌─────┴─────┐
        │ Success   │ Failure (0 rows / Lease expired / Generation superseded / Bad token)
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
(runtime_execution_attempts.evidence_status remains PENDING in state RUNNING)
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
