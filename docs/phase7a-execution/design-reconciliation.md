# WhitePact Phase 7A Design Reconciliation

**Document Status:** CANONICAL SPECIFICATION PASS 4 (SECURITY REMEDIATION)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary

This document provides a systematic reconciliation between the Phase 7A Master Design (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`) and the approved canonical enterprise authentication baseline (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

This Pass 4 correction definitively closes all 10 security findings from the independent adversarial review:
1. **Durable Immutable Execution Requests (F03, F07):** Schema `runtime_execution_requests` (Migration `0049`) stores RFC 8785 canonical JSON bytes, `action_digest`, and tenant-scoped idempotency (`UNIQUE(organization_id, idempotency_key)`).
2. **Approval Consumption & Authorization Atomicity (F04):** Schema `governance_execution_authorizations` (Migration `0050`) enforces `UNIQUE(approval_id)`. Approval consumption and authorization issuance occur in ONE PostgreSQL transaction.
3. **Attempt State Machine & One-Shot Backend Start (F01, F06):** Schema `runtime_execution_attempts` (Migration `0051`) tracks legal attempt states (`PENDING`..`UNCERTAIN`) and effect states (`NO_EFFECT`..`EFFECT_UNCERTAIN`). Atomic update `ADMITTED -> BACKEND_STARTING` with `rowcount == 1` guarantees one-shot execution.
4. **Monotonic Worker Fencing (F02):** Schema `runtime_worker_leases` (Migration `0052`) enforces `lease_generation` (BIGINT). Stale/zombie workers cannot begin backend execution.
5. **Universal Epoch Invalidation (F05):** All 14 authority mutations advance `governance_revocation_epochs.epoch` under a row lock, closing TOCTOU windows between issuance and admission.
6. **Explicit Execution Scope (F08):** Distinguishes Hosted Governed Mode (mandatory full chain) from Community Local stdio mode. In hosted configuration, unmediated execution is unreachable.
7. **Evidence & Lease Finalization Ordering (F09):** Result -> Outcome state -> Evidence store -> Mark attempt terminal -> Finalize lease -> Release capacity.
8. **Capacity Reservation Crash Reconciliation (F10):** Redis ephemeral counters are audited and reconciled against PostgreSQL active attempts and leases. Worker death cannot permanently leak capacity.

---

## 2. Invariant Reconciliation Matrix

| Subsystem / Dimension | Status | Detailed Findings & Adaptations |
| :--- | :--- | :--- |
| **Execution Request Storage** | SECURITY-RELEVANT ADAPTATION | Persisted in `runtime_execution_requests` (Migration 0049). Append-only, RFC 8785 canonical JSON bytes, `UNIQUE(organization_id, idempotency_key)`. Worker reconstructs action without policy re-evaluation. |
| **Approval Consumption** | SECURITY-RELEVANT ADAPTATION | Combined with authorization issuance in ONE transaction. `UNIQUE(approval_id)` in `governance_execution_authorizations` (Migration 0050) guarantees an approval can mint at most one authorization. |
| **Canonical Admission Gate** | SECURITY-RELEVANT ADAPTATION | `admit_execution()` in `governance/execution.py` remains the non-bypassable admission API. Returns in-process `AdmissionReceipt`. Nonce insert and authorization update (`rowcount == 1`) committed under row lock. |
| **Backend-Start Transition** | SECURITY-RELEVANT ADAPTATION | One-shot atomic transition `ADMITTED -> BACKEND_STARTING` in `runtime_execution_attempts` (Migration 0051) with `rowcount == 1`. Possession of `AdmissionReceipt` alone grants no right to execute. |
| **Worker Lease & Fencing** | SECURITY-RELEVANT ADAPTATION | Monotonic `lease_generation` in `runtime_worker_leases` (Migration 0052). Atomic fence check before backend start halts stale/zombie workers. |
| **Revocation Architecture** | RECONCILED & HARDENED | All 14 mutable authority sources advance `scope="governance"` epoch under row lock. Invalidation of queued work is universally linearized. |
| **Effect State & Idempotency** | RECONCILED & HARDENED | Stable `effect_id` generated per attempt. Transmitted as `Idempotency-Key` to upstream servers. Automatic replay from `EFFECT_TRANSMITTING` or `UNCERTAIN` is strictly forbidden. |
| **Evidence Finalization Order** | RECONCILED & ORDERED | Evidence write precedes lease finalization and attempt completion. If evidence write fails after confirmed effect, attempt is marked `COMPLETED` with `evidence_status = 'INCOMPLETE'`. |
| **Execution Scopes** | RECONCILED & SEPARATED | Hosted Governed Mode strictly enforces complete chain. Community local stdio direct mode is documented as separate trust domain and blocked in hosted configurations. |
| **PostgreSQL Migration Sequence** | RESOLVED & ORDERED | Canonical head `0048` -> `0049_runtime_execution_requests` -> `0050_runtime_execution_authorizations` -> `0051_runtime_execution_attempts` -> `0052_runtime_worker_leases`. |
| **Docker Isolation** | UNCHANGED | Ephemeral container execution with `--network=none`, CPU 0.5, RAM 256MB, PID 32, and WP-ISO-01 workspace limits (10MB, 100 files). |

---

## 3. Critical Architectural Clarifications

### 3.1 One-Shot Backend Start Architecture
```
[AdmissionReceipt Held by Worker]
              │
              ▼
[Atomic Backend-Start Transaction in PostgreSQL]
  1. Lock active lease row (assert lease_generation == N)
  2. UPDATE runtime_execution_attempts
     SET state = 'BACKEND_STARTING', effect_state = 'EFFECT_STARTING'
     WHERE state = 'ADMITTED' AND lease_generation = N
  3. Assert rowcount == 1 (Rollback if 0)
              │
        ┌─────┴─────┐
        │ Success   │ Failure (0 rows / Stale worker / Reused receipt)
        ▼           ▼
[Invoke Backend]   [Halt Immediately: Zero Container / Network Execution]
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
