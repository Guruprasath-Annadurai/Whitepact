# WhitePact Phase 7A: Execution Security Check Ownership Matrix

**Document Status:** CANONICAL SPECIFICATION PASS 4.2 (SECURITY CONSISTENCY CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Proposed Migrations:** `0049_runtime_execution_requests.py` through `0052_runtime_worker_leases.py`

---

## 1. Architectural Principles

This document defines the strict, single-owner security verification model across the execution lifecycle, eliminating dual-source ambiguity, establishing one-shot backend execution, and binding the canonical admission transaction.

### Core Invariants:
1. **Single Canonical Owner:** Every security check and state transition has exactly one authoritative owner.
2. **Infrastructure Is Not Authority:** Neither a `QueueTicket`, an active worker lease, a Redis semaphore, nor an in-process `AdmissionReceipt` constitutes execution authority.
3. **Atomic Admission & Attempt Transition (F4.2-01):** Canonical admission burns the single-use nonce, marks authorization `CONSUMED`, and transitions the attempt from `LEASED` to `ADMITTED` in ONE PostgreSQL transaction (`rowcount == 1`).
4. **Atomic Pre-Effect CAS (F4.2-02):** Eliminates check-then-write races. Downstream execution requires atomic CAS updates (`claim_local_effect_start` or `claim_external_effect_transmission`) with `rowcount == 1` immediately prior to container execution or socket byte transmission.
5. **Durable Evidence Status Ownership (F4.2-04):** `runtime_execution_attempts.evidence_status` durably tracks evidence state (`PENDING`, `COMMITTED`, `INCOMPLETE`). Evidence persistence strictly precedes normal attempt completion.
6. **Zero Decorative Tokens (F4.2-03):** Authority is governed exclusively by PostgreSQL state machines and row-level locks.

---

## 2. Security Check Ownership Matrix

| Security Check / State | Canonical Owner | Queue-Time Check? | Pre-Dispatch Check? | Canonical Durable Check? | Duplication Allowed? | Rationale & Failure Mode |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Durable Execution Request** | `ExecutionRequestRepository` (`runtime_execution_requests`, Mig 0049) | YES (Persisted before enqueue) | YES (Worker loads from DB) | YES (Append-only table, trigger rejects all UPDATE/DELETE) | NO (Sole owner of serialized input) | Immutable record of action arguments, purpose, and identity. Zero mutable operational status. |
| **Tenant Idempotency Binding** | `runtime_execution_requests` (`UNIQUE(organization_id, idempotency_key)`) | YES (At API submission) | NO (Already bound) | YES (Database unique constraint) | NO (Sole owner of request deduplication) | Every hosted request assigned key. Atomic insert catches duplicates; same key + different digest fails closed (HTTP 409). |
| **Human Approval Consumption** | `ApprovalExecutionService` (`governance_approvals`) | YES (Status == APPROVED) | YES (Pre-flight check) | YES (Atomic UPDATE with rowcount == 1 in same TX as auth issuance) | NO (Sole owner of approval spending) | Atomic transition `APPROVED -> CONSUMED`. `UNIQUE(approval_id)` in `governance_execution_authorizations` prevents duplicate issuance. |
| **Authorization Issuance** | `DurableExecutionAuthorizationIssuer` (`governance_execution_authorizations`, Mig 0050) | YES (Committed before enqueue) | NO (Already durable) | YES (Foreign key & primary key constraints) | NO (Sole owner of issuance persistence) | If DB write fails, request fails closed immediately. Queue entry = 0, dispatch = 0. |
| **Revocation / Governance Epoch** | `governance_revocation_epochs` + `lock_epoch()` | NO (Avoids DB lock) | NO (Avoids unneeded lock) | YES (Sole owner: `admit_execution` via `lock_epoch`) | NO (Must execute under row lock) | Singular authoritative revocation mechanism. All 14 authority mutations advance `scope="governance"` epoch. |
| **Authorization Expiry** | `ExecutionAuthorization.is_expired` | YES (Fast drop) | YES (Pre-flight) | YES (Enforced via `WHERE expires_at > :now` in atomic UPDATE) | YES (Read-only timestamp comparison) | Expiration is derived, never persisted. Early drops prevent queue congestion; final atomic query guard guarantees zero clock-drift execution. |
| **Canonical Admission & Attempt Transition** | `ExecutionNonceRepository.consume()` | NO | NO | YES (Atomic PG transaction: epoch lock + nonce insert + auth `CONSUMED` + attempt `ADMITTED`) | NO (Exactly one admission per execution attempt) | Burns nonce, transitions auth (`rowcount == 1`), and transitions attempt `LEASED -> ADMITTED` (`rowcount == 1`). Emits `AdmissionReceipt`. |
| **Worker Lease & Active Exclusivity** | `runtime_worker_leases` (`AdmissionLeaseRepository`, Mig 0052) | NO | YES (Acquire lease before pre-flight) | YES (Partial unique index on `ACTIVE`) | NO (Sole owner of lease exclusivity) | Enforces that at most one worker holds active execution rights for an `execution_id` at any time. |
| **Monotonic Generation Allocation** | `runtime_execution_fences` (Mig 0052) | NO | YES (Allocated at lease acquisition) | YES (Atomic UPDATE RETURNING current_generation) | NO (Sole owner of generation numbers) | Monotonically strictly increasing. Eliminates concurrent MAX+1 race conditions. |
| **Durable Attempt State** | `runtime_execution_attempts` (`state`, Mig 0051) | NO | YES (Attempt initialized PENDING) | YES (Durable state machine: PENDING, LEASED, ADMITTED, BACKEND_STARTING, etc.) | NO (Sole owner of attempt lifecycle) | Tracks progress. Enforces `chk_attempt_lease_fields` (NULL in PENDING, NOT NULL in LEASED+). |
| **One-Shot Backend-Start Claim** | `ExecutionAttemptRepository.claim_backend_start()` | NO | NO | YES (Atomic UPDATE: `ADMITTED -> BACKEND_STARTING` with `rowcount == 1`) | NO (Sole owner of backend-start ownership) | Verifies unexpired lease & generation under lock; emits clean `BackendExecutionClaim`. |
| **Final Pre-Effect Local CAS** | `ExecutionAttemptRepository.claim_local_effect_start()` | NO | NO | YES (Atomic UPDATE: `BACKEND_STARTING -> RUNNING` with `rowcount == 1`) | NO (Pre-container linearization gate) | Only caller receiving `rowcount == 1` may invoke container. Second call matches 0 rows and fails closed. |
| **Final Pre-Effect External CAS** | `ExecutionAttemptRepository.claim_external_effect_transmission()` | NO | NO | YES (Atomic UPDATE: `BACKEND_STARTING -> RUNNING/EFFECT_TRANSMITTING` with `rowcount == 1`) | NO (Pre-socket linearization gate) | Only caller receiving `rowcount == 1` may transmit bytes to socket. Second call matches 0 rows and fails closed. |
| **Target Fingerprint Drift** | `check_target_fingerprint()` | NO (Target not resolved) | YES (After target lookup) | YES (In `UpstreamMCPExecutor` prior to transport) | NO (Requires freshly resolved target) | Verifies target resolution hasn't drifted between policy evaluation and execution. |
| **SafeNetwork Validation & IP Pinning** | `SafeNetworkBackend` | NO | NO | YES (Immediate pre-socket bind) | NO (Sole owner of network egress) | Enforces SSRF protection, IP pinning, redirect validation, and connects only to pinned IP. |
| **Container Isolation** | `ContainerIsolationBackend` | NO | NO | YES (Docker flags `--network=none`, limits) | NO (Sole owner of compute containment) | Enforces CPU 0.5, RAM 256MB, PID 32, workspace 10MB/100 files bounds. |
| **Durable Evidence & Audit** | `EvidenceStore` + `runtime_execution_attempts.evidence_status` | NO | NO | YES (Committed BEFORE attempt completion on success; `evidence_status='INCOMPLETE'` on failure) | NO (Sole owner of compliance evidence) | Normal success requires evidence before `COMPLETED`. If evidence fails after effect, records `INCOMPLETE` without re-running effect. |
| **Capacity Reservation & Release** | `AdmissionController` (Redis + DB Reconciler) | YES (Reserve at enqueue) | NO | YES (Explicit release on all terminal paths; audit reconciler) | NO (Sole owner of cluster concurrency) | Every reservation has explicit terminal release. Redis failure fails closed. Worker crash cannot leak capacity. |
