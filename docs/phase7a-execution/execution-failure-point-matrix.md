# WhitePact Phase 7A: Execution Failure-Point Matrix

**Document Status:** CANONICAL SPECIFICATION PASS 2 (ATOMIC AUTHORITY INTEGRATION CORRECTION)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Failure Handling Principles

This document maps every discrete failure point across the distributed execution pipeline, defining observable states, failure classifications, and corrective recovery actions.

### Core Invariants:
1. **Zero Blind External Replays:** Once an external side-effect is initiated, automatic retry is strictly **FORBIDDEN**. The state is marked `UNCERTAIN` until reconciled.
2. **Atomic Admission Boundary:** The database transaction inside `ExecutionNonceRepository.consume()` (locking epoch, inserting nonce, conditionally updating authorization with `rowcount == 1`) is the singular linearizing point of execution authority.
3. **Issuance Gate:** If database insertion of `ExecutionAuthorization` fails, NO `QueueTicket` is created.

---

## 2. Failure-Point Classification Matrix

| # | Exact Failure Boundary | Failure / Error Condition | Observable System State | Classification | Recovery / Corrective Action |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **FP-00** | **During Authorization Issuance** | PostgreSQL disconnect or DB error when persisting `ExecutionAuthorization`. | No DB row in `governance_execution_authorizations`; zero queue tickets created. | **NO RETRY** (Request fails closed) | Request fails immediately with HTTP 500/503. Zero queue entries created. Client may retry from edge. |
| **FP-01** | **After Dequeue, Before EA Load** | Dispatcher crashes immediately after pulling `QueueTicket` from fair queue. | Redis item removed; no DB lease exists; EA status is `ISSUED`. | **SAFE RETRY** | Ticket is re-enqueued by supervisor unacknowledged-message reaper, or client retries with `idempotency_key`. |
| **FP-02** | **During Early Revalidation** | Dispatcher crashes while checking EA status or tenant lifecycle in DB. | No DB lease exists; EA status is `ISSUED`. | **SAFE RETRY** | Supervisor detects unassigned ticket and re-enqueues. EA remains unconsumed. |
| **FP-03** | **During Worker Lease Acquisition** | Worker crashes while executing `INSERT INTO runtime_worker_leases`. | Lease row either exists (if committed) or does not exist (if rolled back). EA status is `ISSUED`. | **SAFE RETRY** | If lease committed, heartbeat reaper detects dead worker after `lease_ttl` and transitions lease to `EXPIRED`. Ticket can be retried under new attempt. |
| **FP-04** | **After Lease Acquisition, Before `admit_execution`** | Worker crashes after holding `ACTIVE` lease, before invoking `admit_execution`. | Lease is `ACTIVE` with stalled heartbeat; EA is `ISSUED`; nonce is NOT in `governance_execution_nonces`. | **SAFE RETRY** | Supervisor reclaims expired lease (`status = 'EXPIRED'`). Nonce was never burned, so new worker can safely acquire lease attempt `N+1` and admit. |
| **FP-05A** | **During `admit_execution` (Stale Revocation Epoch)** | Epoch bumped while request sat in queue; mismatch detected after `lock_epoch()`. | `StaleRevocationEpochError` raised. Transaction rolls back. Nonce NOT inserted; EA status remains `ISSUED`. | **NO RETRY** (Authority invalidated) | Worker marks lease `FAILED` with code `STALE_EPOCH`. Capacity released. No execution. |
| **FP-05B** | **During `admit_execution` (Nonce Replay Race)** | Racing worker already inserted nonce; caught by DB PK violation. | `NonceAlreadyConsumedError` raised. Transaction rolls back. EA status remains `ISSUED` or `CONSUMED`. | **NO RETRY** (Replay rejected) | Worker catches error, marks lease `FAILED` with code `NONCE_ALREADY_CONSUMED`. Capacity released. |
| **FP-05C** | **During `admit_execution` (Conditional Update rowcount == 0)** | Nonce inserted, but conditional update `WHERE status = 'ISSUED' AND expires_at > now` returns rowcount 0. | `AuthorizationAlreadyConsumedError` raised. Entire transaction rolls back. Nonce insert undone. | **NO RETRY** (Atomic rollback) | Rollback ensures nonce is NOT burned if authorization update failed. Lease marked `FAILED`. |
| **FP-05D** | **During `admit_execution` (Pre-Commit Disconnect)** | Worker or DB dies after conditional update succeeds, before transaction COMMIT. | PostgreSQL rolls back entire transaction automatically. Nonce absent; EA remains `ISSUED`. | **SAFE RETRY** | Authority was never committed as consumed. Stale lease reaped; subsequent attempt can retry. |
| **FP-06** | **Two Processes Concurrently Consuming Same Authorization** | Worker A and Worker B both call `admit_execution()` for same authorization. | Process A commits: nonce inserted, EA `status = CONSUMED`. Process B conditional update gets rowcount 0 -> rolls back. | **CONCURRENT RACE RESOLVED** | Exactly 1 process succeeds (`rowcount == 1`). Process B transaction rolls back completely. Consequential execution winners = 1. |
| **FP-07** | **After `admit_execution`, Before Container Launch** | Worker dies immediately after commit of `admit_execution`, before Docker starts. | Nonce is in `governance_execution_nonces`; EA is `CONSUMED`; container was never created. | **NO RETRY** (Permit spent) | Lease expires. Because nonce is burned, automated re-execution is prohibited. Action is marked `FAILED_PRE_EXECUTION` in evidence. Client must issue fresh request. |
| **FP-08** | **During Container Execution (Internal Tool)** | Worker dies or container crashes while executing sandboxed read/compute tool. | Nonce burned; EA `CONSUMED`; container dead or running without supervisor. | **SAFE RETRY** (Idempotent read tools only) / **RECONCILIATION REQUIRED** (Stateful) | Supervisor orphan reaper destroys container (`docker rm -f`). Read-only tools can retry with new permit; stateful tools quarantined. |
| **FP-09** | **During External Network Effect** | Worker dies or network cuts out while sending request to Upstream MCP Server / HTTP webhook. | Nonce burned; EA `CONSUMED`; remote endpoint may or may not have processed mutation. | **UNCERTAIN** | **ZERO BLIND RETRY.** Supervisor transitions execution status to `UNCERTAIN`. Requires manual intervention or upstream idempotency verification before resolution. |
| **FP-10** | **External Upstream Timeout** | Remote server times out without returning HTTP / MCP response. | Nonce burned; EA `CONSUMED`; remote outcome unknown. | **UNCERTAIN** | Worker marks outcome `UNCERTAIN` with reason `UPSTREAM_TIMEOUT`. Leases finalized as `UNCERTAIN`. No automated retry. |
| **FP-11** | **After Execution, Before Evidence Write** | Worker dies after container / external call finishes, before writing `governance_evidence`. | Tool output received in worker memory; DB evidence row missing; lease `ACTIVE`. | **RECONCILIATION REQUIRED** | Lease expires. Supervisor checks workspace directory / container logs to extract result and write recovery evidence record before marking `COMPLETED`. |
| **FP-12** | **After Evidence Write, Before Lease Release** | Worker dies after writing `governance_evidence`, before updating lease to `COMPLETED`. | Evidence is durably recorded; lease is still `ACTIVE` with stalled heartbeat. | **SAFE RETRY** (Idempotent finalization) | Supervisor detects expired lease, inspects `governance_evidence`, sees existing terminal evidence for `execution_id`, and transitions lease directly to `COMPLETED`. |
| **FP-13** | **Silent Worker Crash / Heartbeat Loss** | Worker thread freezes or host experiences kernel panic during execution. | Lease `ACTIVE`; `heartbeat_at` older than `heartbeat_timeout_seconds`. | **UNCERTAIN** | Supervisor reclaims lease. If permit was consumed, status moves to `ORPHANED_UNCERTAIN`. Container is forcibly killed via docker daemon. |
| **FP-14** | **Late Worker Attempt After Lease Stolen** | Zombie worker resumes and attempts to write completion after its lease was reclaimed. | Lease row is already marked `EXPIRED` or held by another attempt. | **NO RETRY** | Worker lease update specifies `WHERE lease_id = :id AND status = 'ACTIVE'`. Rowcount is 0. Zombie worker detects loss of ownership and aborts immediately. |

---

## 3. Failure Boundaries Summary

- **Total Failure Points Analyzed:** 16 discrete boundaries.
- **Safe Retry Count:** 5 (Only when permit has NOT been committed as consumed or action is idempotent finalization).
- **No Retry Count:** 6 (Permit spent, issuance failed closed, or canonical security rejection).
- **Uncertain / Reconciliation Count:** 5 (Consequential side-effect state unknown).
- **Blind External Replays Permitted:** **ZERO (0)**.
