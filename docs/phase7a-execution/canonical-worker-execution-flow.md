# WhitePact Phase 7A: Canonical Worker Execution Flow

**Document Status:** CANONICAL SPECIFICATION PASS 2 (ATOMIC AUTHORITY INTEGRATION CORRECTION)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Overview and Control Chain Invariants

This document specifies the authoritative, end-to-end execution control chain for Phase 7A.

### Core Architectural Invariants:
1. **Durable Issuance Precedes Queueing:** No `QueueTicket` may be generated until the `ExecutionAuthorization` is durably committed to PostgreSQL (`governance_execution_authorizations`).
2. **Zero Execution Without Canonical Admission:** No worker may execute a container or invoke a tool without successfully completing `admit_execution()` in `src/responsibleai/governance/execution.py`.
3. **Combined Atomic Admission Transaction:** `ExecutionNonceRepository.consume()` in `src/responsibleai/db/execution_nonce_repository.py` executes a single database transaction combining the epoch lock, nonce insertion, and conditional authorization status update (`ISSUED -> CONSUMED` with `rowcount == 1`).
4. **Queue Isolation:** Queue tickets (`QueueTicket`) contain strictly non-privileged pointers (`execution_id`, `authorization_id`, `org_id`, `principal_id`, `action_digest`).
5. **Database-Enforced Lease Exclusivity:** A worker must acquire an exclusive `ACTIVE` lease row in `runtime_worker_leases` before invoking `admit_execution()`.
6. **No Exactly-Once Network Promise:** If a remote network side-effect is interrupted, its outcome is marked `UNCERTAIN` and requires reconciliation or proof of idempotency; blind replay is forbidden.

---

## 2. End-to-End Control Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant Gateway as Policy Gateway (mcp/governance_integration.py)
    participant EA_Repo as ExecutionAuthRepository (PostgreSQL)
    participant AdmCtrl as Admission Controller & Queue
    participant Dispatcher as Worker Dispatcher
    participant LeaseRepo as WorkerLeaseRepository (PostgreSQL)
    participant NonceRepo as ExecutionNonceRepository (PostgreSQL)
    participant EpochRepo as RevocationEpochRepository (PostgreSQL)
    participant Worker as Execution Worker
    participant Backend as Container Isolation Backend

    Client->>Gateway: Submit ActionRequest
    Gateway->>Gateway: Evaluate Policies, Ceilings & Passports
    Note over Gateway: Decision: ALLOW or ALLOW_WITH_REDACTION
    Gateway->>Gateway: authorize_execution() -> In-Memory ExecutionAuthorization

    Gateway->>EA_Repo: create(authorization) [INSERT INTO governance_execution_authorizations]
    Note over Gateway,EA_Repo: If DB write fails, fail closed (HTTP 500/503). Zero queue tickets created.

    Gateway->>AdmCtrl: reserve_execution() & enqueue(QueueTicket)
    AdmCtrl-->>Client: Return 202 Accepted (execution_id)

    loop Fair Dequeue Loop
        Dispatcher->>AdmCtrl: Dequeue Next Ticket (Round-Robin Tenant)
    end

    Note over Dispatcher: Stage 1: Early Queue Invalidation
    Dispatcher->>EA_Repo: Read Authorization Status & Expiration
    Dispatcher->>Dispatcher: Fast Check: Tenant Active? now < expires_at? status == ISSUED?

    Dispatcher->>LeaseRepo: Acquire Lease (execution_id, attempt, status: ACTIVE)
    Note over LeaseRepo: PostgreSQL Partial Unique Index Enforces Exclusivity

    Dispatcher->>Worker: Dispatch to Worker Process with Lease Token

    Note over Worker: Stage 2: Final Canonical Admission
    Worker->>EA_Repo: Load Full ExecutionAuthorization & Action Payload
    Worker->>Worker: Revalidate Action Digest & Principal/Session Binding
    Worker->>Worker: Check BreakGlass Session Active & Unexpired (if applicable)

    Worker->>NonceRepo: admit_execution(authorization, action, nonce_repo)
    rect rgb(240, 248, 255)
        Note over NonceRepo,EpochRepo: Atomic Database Transaction in ExecutionNonceRepository.consume()
        NonceRepo->>EpochRepo: lock_epoch(conn, organization_id) FOR UPDATE
        EpochRepo-->>NonceRepo: Return Current Epoch
        NonceRepo->>NonceRepo: Verify expected_epoch == current_epoch
        NonceRepo->>NonceRepo: INSERT INTO governance_execution_nonces (nonce, auth_id, org_id)
        NonceRepo->>EA_Repo: UPDATE governance_execution_authorizations SET status = CONSUMED WHERE status = ISSUED AND expires_at > now
        NonceRepo->>NonceRepo: Assert rowcount == 1 (if 0: ROLLBACK & raise error)
    end
    NonceRepo-->>Worker: Admission Confirmed

    Worker->>Backend: Execute in Sandboxed Container (--network=none, limits)
    par Heartbeat Loop
        Worker->>LeaseRepo: Record Heartbeat (heartbeat_at = now())
    and Container Wait
        Backend-->>Worker: Return Result / stdout / exit_code
    end

    Worker->>LeaseRepo: Finalize Lease (status: COMPLETED)
    Worker->>AdmCtrl: Release Capacity Reservation
    Worker->>Gateway: Record Evidence & Outcome
```

---

## 3. Step-by-Step State Transitions and Failure Exits

### Step 1: Policy Gateway Decision & Durable Issuance
- **Actor:** `src/responsibleai/mcp/governance_integration.py` (`execute_governed_action` and `resolve_approval_and_execute`).
- **Action:** Evaluates policies; if decision is `ALLOW` or `ALLOW_WITH_REDACTION`, calls `authorize_execution()`.
- **Durable Issuance Gate:** Immediately invokes `ExecutionAuthorizationRepository.create(authorization)`.
- **Failure Exit:** If DB insert fails:
  - Exception is caught and logged.
  - NO `QueueTicket` is generated.
  - NO reservation is acquired.
  - Client receives HTTP 500/503. Zero unpersisted authority is issued.

### Step 2: Admission Reservation & Queueing
- **Action:** `AdmissionController.reserve_execution()` checks semaphores.
- **Enqueuing:** A lightweight `QueueTicket` is enqueued to `FairExecutionScheduler`.
  - Contents: `execution_id`, `authorization_id`, `organization_id`, `principal_id`, `action_digest`, `enqueued_at`.
- **Response:** Client receives HTTP 202 with `execution_id`.

### Step 3: Dequeue & Early Invalidation (Stage 1)
- **Actor:** Worker Dispatcher.
- **Action:** Dequeues next `QueueTicket` in round-robin tenant fairness.
- **Early Invalidation Checks:**
  1. `now < authorization.expires_at` (derived expiration).
  2. `authorization.status == ISSUED`.
  3. `organization_id` active in `OrgRepository` (not suspended, deleted, or tombstoned).
- **Failure Exit:** If any check fails, ticket is discarded / sent to dead-letter. **No worker lease is acquired, no nonce is burned.**

### Step 4: Exclusive Worker Lease Acquisition
- **Actor:** Worker Dispatcher.
- **Action:** Inserts a lease record in `runtime_worker_leases` (`status = ACTIVE`).
- **Enforcement:** PostgreSQL partial unique index `idx_runtime_worker_leases_active_execution` on `(execution_id) WHERE status = ACTIVE`.
- **Failure Exit:** If another worker already holds an `ACTIVE` lease, `IntegrityError` is raised and the loser aborts cleanly.

### Step 5: Worker Pre-Flight Binding Revalidation
- **Actor:** Execution Worker.
- **Action:**
  1. Verifies `compute_action_digest(action) == authorization.action_digest`.
  2. Verifies principal identity matches `authorization.principal_id`.
  3. Verifies session validity via `SessionService` (if session-bound).
  4. If BreakGlass: queries `iam_break_glass_sessions` to verify session is `ACTIVE` and unexpired.
  5. If target requires drift verification: invokes `check_target_fingerprint()`.
- **Failure Exit:** On mismatch, transitions lease to `FAILED`, releases capacity, and exits.

### Step 6: Final Canonical Admission (`admit_execution`)
- **Actor:** Execution Worker invoking `src/responsibleai/governance/execution.py:admit_execution()`.
- **Transaction Owner:** `ExecutionNonceRepository.consume()` in `src/responsibleai/db/execution_nonce_repository.py`.
- **Atomic Sequence (Single Connection, Single Transaction):**
  1. `lock_epoch(conn, organization_id)` (`SELECT ... FOR UPDATE`).
  2. Verify `current_epoch == expected_epoch`. (Mismatch raises `StaleRevocationEpochError`).
  3. `INSERT INTO governance_execution_nonces (nonce, authorization_id, organization_id, consumed_at)`. (Duplicate raises `NonceAlreadyConsumedError`).
  4. `UPDATE governance_execution_authorizations SET status = CONSUMED, consumed_at = :now, updated_at = :now WHERE authorization_id = :id AND organization_id = :org_id AND status = ISSUED AND expires_at > :now`.
  5. Assert `rowcount == 1`. If `rowcount == 0`, raises `AuthorizationAlreadyConsumedError`.
  6. Commit transaction.
- **Failure Exit:** If any check fails, the transaction rolls back completely. Nonce is NOT inserted, authorization is NOT consumed.

### Step 7: Isolated Container Execution
- **Actor:** `ContainerIsolationBackend`.
- **Action:** Ephemeral container launched with `--network=none`, `--memory=256m`, `--cpus=0.5`, `--pids-limit=32`, timeout 15.0s.
- **Heartbeat:** Periodically updates `runtime_worker_leases.heartbeat_at`.

### Step 8: Evidence Recording & Lease Finalization
- **Actor:** Execution Worker.
- **Action:**
  1. Records outcome in `governance_evidence` and `governance_outcomes`.
  2. Updates `runtime_worker_leases` to `COMPLETED` (`completed_at = now()`).
  3. Calls `AdmissionController.release_execution()`.
