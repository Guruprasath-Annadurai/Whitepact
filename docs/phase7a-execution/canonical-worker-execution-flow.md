# WhitePact Phase 7A: Canonical Worker Execution Flow

**Document Status:** CANONICAL SPECIFICATION PASS 4.3 (SECURITY BOUNDARY CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Proposed Migrations:** `0050_runtime_execution_requests.py` through `0053_runtime_worker_leases.py`

**Canonical migration ownership:** `docs/phase7a-execution/migration-ownership.md` (implemented `0049` = org governance lifecycle).

---

## 1. Overview and Control Chain Invariants

This document specifies the authoritative, end-to-end execution control chain for Phase 7A.

### Core Architectural Invariants:
1. **Durable Issuance Precedes Queueing:** No `QueueTicket` may be generated until `runtime_execution_requests`, `governance_execution_authorizations`, initial `runtime_execution_attempts` (state=`PENDING`), and `runtime_execution_fences` are durably committed in PostgreSQL.
2. **Atomic Canonical Admission (F4.2-01):** `admit_execution()` executes an atomic transaction combining: (1) epoch lock/verification; (2) single-use nonce insertion; (3) authorization transition `ISSUED -> CONSUMED`; (4) attempt transition `LEASED -> ADMITTED` (rowcount == 1). Emits in-process `AdmissionReceipt`.
3. **One-Shot Backend Start & Token Generation (F4.3-02):** Worker calls `claim_backend_start()` to verify active unexpired lease under row lock, generate raw single-use `backend_start_token`, store its SHA-256 hash in `runtime_execution_attempts`, and transition `ADMITTED -> BACKEND_STARTING` (rowcount == 1). Returns `BackendExecutionClaim` carrying raw token and immutable `target_fingerprint`.
4. **Final Pre-Effect Atomic CAS with Lease Revalidation (F4.3-01, F4.3-02, F4.3-03):** Eliminates all check-then-write races, zombie worker executions, and fabricated claim replays. Executors invoke `claim_local_effect_start()` or `claim_external_effect_transmission()` immediately before side-effect execution. The transaction synchronously revalidates the active unexpired lease under row lock, asserts immutable durable request action/fingerprint binding, validates and consumes the token hash, and transitions attempt state to `RUNNING` asserting `rowcount == 1`. Fencing correctness does NOT depend on reaper timing.
5. **Strict Evidence Precedence & Crash Consistency (F4.2-04, F4.3-04):** Normal successful execution requires: Result -> Durable outcome -> Evidence store -> Attempt `COMPLETED` (`evidence_status = 'COMMITTED'`) -> Lease `COMPLETED` -> Capacity released. While attempt is `RUNNING`, `evidence_status` remains `PENDING`. If a crash occurs after EvidenceStore commit before attempt terminalization (Crash Point O), supervisor detects the committed evidence and terminalizes the attempt.
6. **No Blind Replay:** If an external side-effect is interrupted or fails after `EFFECT_TRANSMITTING`, the attempt is marked `UNCERTAIN`; automatic blind replay is strictly prohibited.
7. **Universal Capacity Release:** Every capacity reservation made at enqueue time has an explicit terminal release path.

---

## 2. End-to-End Control Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    participant Client
    participant Gateway as Policy Gateway / Upstream Dispatch
    participant Issuer as DurableExecutionAuthorizationIssuer
    participant DB as PostgreSQL (Requests, Auths, Nonces, Attempts, Fences, Leases)
    participant AdmCtrl as Admission Controller & Queue
    participant Dispatcher as Worker Dispatcher
    participant Worker as Execution Worker
    participant Executor as InternalToolExecutor / UpstreamMCPExecutor
    participant Backend as Container / SafeNetworkBackend

    Client->>Gateway: Submit ActionRequest (Local Tool or Upstream MCP)
    Gateway->>Gateway: Resolve / Generate Idempotency Key
    Gateway->>Gateway: Evaluate Policies, Ceilings & Passports
    Note over Gateway: Decision: ALLOW or ALLOW_WITH_REDACTION

    Gateway->>Issuer: issue(authorization, action)
    Issuer->>DB: BEGIN TRANSACTION
    Issuer->>DB: INSERT runtime_execution_requests (RFC 8785 Canonical JSON, Append-Only)
    Issuer->>DB: INSERT governance_execution_authorizations (status=ISSUED, UNIQUE approval_id)
    Issuer->>DB: INSERT runtime_execution_attempts (state=PENDING, lease fields NULL, evidence_status=PENDING)
    Issuer->>DB: INSERT runtime_execution_fences (current_generation=0)
    Issuer->>DB: COMMIT TRANSACTION

    Gateway->>AdmCtrl: reserve_execution() & enqueue(QueueTicket)
    AdmCtrl-->>Client: Return 202 Accepted (execution_id, idempotency_key)

    loop Fair Dequeue Loop
        Dispatcher->>AdmCtrl: Dequeue Next Ticket (Round-Robin Tenant)
    end

    Note over Dispatcher: Stage 1: Early Invalidation
    Dispatcher->>DB: Read Authorization Status & Expiration
    Dispatcher->>DB: Check Org Governance Lifecycle (organizations.governance_status == 'ACTIVE') & now < expires_at
    alt Early Invalidation Fails (e.g. Expired or Revoked)
        Dispatcher->>DB: UPDATE runtime_execution_attempts SET state=FAILED_PRE_EXECUTION
        Dispatcher->>AdmCtrl: release_execution()
        Note over Dispatcher: Abort dispatch; ticket dropped cleanly
    end

    Dispatcher->>DB: Atomically Increment runtime_execution_fences & INSERT runtime_worker_leases (status=ACTIVE, gen=N)
    Dispatcher->>DB: UPDATE runtime_execution_attempts SET state=LEASED, worker_id=W, lease_id=L, lease_generation=N WHERE state=PENDING
    Dispatcher->>Worker: Dispatch to Worker Process with Lease Token

    Note over Worker: Stage 2: Canonical Admission (Atomic Auth & Attempt Transition)
    Worker->>DB: Load Canonical Action Payload & Recompute Digest Match
    Worker->>Worker: Pre-Flight Checks: Principal, Session, BreakGlass, Delegation
    alt Preflight Checks Fail
        Worker->>DB: Mark Lease FAILED & Attempt FAILED_PRE_EXECUTION
        Worker->>AdmCtrl: release_execution()
    end

    Worker->>DB: admit_execution(authorization, action, nonce_repo)
    rect rgb(240, 248, 255)
        Note over DB: Atomic Admission Transaction in ExecutionNonceRepository.consume()
        DB->>DB: SELECT epoch FROM governance_revocation_epochs FOR UPDATE (Assert match)
        DB->>DB: INSERT INTO governance_execution_nonces
        DB->>DB: UPDATE governance_execution_authorizations SET status = CONSUMED WHERE status = ISSUED (Assert rowcount == 1)
        DB->>DB: UPDATE runtime_execution_attempts SET state = ADMITTED WHERE state = LEASED (Assert rowcount == 1)
    end
    DB-->>Worker: Admission Confirmed -> Returns in-process AdmissionReceipt

    Note over Worker: Stage 3: One-Shot Backend Start & Secret Token Generation (F4.3-02)
    Worker->>DB: ExecutionAttemptRepository.claim_backend_start(receipt, W, L, N)
    rect rgb(255, 248, 240)
        Note over DB: Atomic Backend-Start Claim Transaction
        DB->>DB: SELECT lease_generation, expires_at FROM runtime_worker_leases WHERE status=ACTIVE AND expires_at > now FOR UPDATE
        DB->>DB: Assert active lease_generation == N (Fail if Stale / Fenced / Expired)
        DB->>DB: UPDATE runtime_execution_attempts SET state = BACKEND_STARTING, effect_state = EFFECT_STARTING, backend_start_token_hash = hash(token) WHERE state = ADMITTED (Assert rowcount == 1)
    end
    DB-->>Worker: Backend Start Confirmed -> Returns BackendExecutionClaim (with raw token & target_fingerprint)

    Note over Worker,Executor: Stage 4: Executor Pre-Effect Atomic CAS & Invocation (F4.3-01, F4.3-02, F4.3-03)
    Worker->>Executor: execute(action, claim=BackendExecutionClaim)
    alt Local Execution
        Executor->>DB: ExecutionAttemptRepository.claim_local_effect_start(claim)
        rect rgb(245, 255, 250)
            Note over DB: Atomic Pre-Effect CAS Transaction
            DB->>DB: SELECT lease FROM runtime_worker_leases WHERE status=ACTIVE AND expires_at > now FOR UPDATE (Assert 1 row)
            DB->>DB: SELECT action_digest FROM runtime_execution_requests (Assert match)
            DB->>DB: UPDATE runtime_execution_attempts SET state = RUNNING, backend_start_token_hash = NULL WHERE state = BACKEND_STARTING AND hash = hash(token) (Assert rowcount == 1)
        end
        Executor->>Backend: ContainerIsolationBackend.execute(--network=none)
    else External Network Execution
        Executor->>Backend: SafeNetworkBackend target verification & DNS resolution
        Backend->>Backend: Pin IP address & compare target fingerprint
        Executor->>DB: ExecutionAttemptRepository.claim_external_effect_transmission(claim)
        rect rgb(245, 255, 250)
            Note over DB: Atomic Pre-Effect CAS Transaction
            DB->>DB: SELECT lease FROM runtime_worker_leases WHERE status=ACTIVE AND expires_at > now FOR UPDATE (Assert 1 row)
            DB->>DB: SELECT action_digest, target_fingerprint FROM runtime_execution_requests (Assert match)
            DB->>DB: UPDATE runtime_execution_attempts SET state = RUNNING, effect_state = EFFECT_TRANSMITTING, backend_start_token_hash = NULL WHERE state = BACKEND_STARTING AND hash = hash(token) (Assert rowcount == 1)
        end
        Backend->>Backend: Transmit HTTP socket bytes to pinned IP with effect_id header
    end
    Backend-->>Executor: Return Result / exit_code
    Executor-->>Worker: Forward Result

    Note over Worker: Stage 5: Evidence & Finalization (Strict Precedence - F4.2-04, F4.3-04)
    Worker->>DB: Record Durable Outcome Row
    Worker->>DB: Record Durable Evidence in EvidenceStore (attempt evidence_status remains PENDING)
    alt Evidence Persistence Succeeded
        Worker->>DB: UPDATE runtime_execution_attempts SET state=COMPLETED, effect_state=EFFECT_CONFIRMED, evidence_status=COMMITTED
    else Evidence Persistence Failed After Confirmed Effect
        Worker->>DB: UPDATE runtime_execution_attempts SET state=COMPLETED, effect_state=EFFECT_CONFIRMED, evidence_status=INCOMPLETE
    end
    Worker->>DB: Finalize Lease (status = COMPLETED)
    Worker->>AdmCtrl: Release Capacity Reservation
```

---

## 3. Step-by-Step State Transitions and Failure Exits

### Step 1: Decision & Centralized Durable Issuance
- **Action:** In ONE atomic transaction:
  1. Append-only `runtime_execution_requests` row.
  2. `governance_execution_authorizations` row (`status = 'ISSUED'`, `UNIQUE(approval_id)`).
  3. `runtime_execution_attempts` row (`state = 'PENDING'`, lease fields NULL, `evidence_status = 'PENDING'`).
  4. `runtime_execution_fences` row (`current_generation = 0`).

### Step 2: Admission Reservation & Queueing
- **Action:** `AdmissionController.reserve_execution()` acquires capacity slot. `QueueTicket` enqueued. Client receives HTTP 202.

### Step 3: Dequeue & Early Invalidation (Stage 1)
- **Action:** Dispatcher checks authorization expiration and organization governance lifecycle (`organizations.governance_status == 'ACTIVE'`). Billing subscription status (`plan`, `subscription_status`) is strictly excluded from governance validity. On failure, attempt marked `FAILED_PRE_EXECUTION`, outbox marked `CANCELLED`, capacity released. On success, fence incremented to generation N, lease acquired (`status = 'ACTIVE'`), attempt updated to `state = 'LEASED'`, outbox updated to `status = 'ACKNOWLEDGED'`.

### Step 4: Canonical Admission & Attempt Admission (Stage 2 - F4.2-01)
- **Action:** Single PostgreSQL transaction in `ExecutionNonceRepository.consume()`:
  1. `lock_epoch()` validates current epoch.
  2. Nonce inserted into `governance_execution_nonces`.
  3. Authorization updated to `CONSUMED` (`rowcount == 1`).
  4. Attempt updated from `LEASED` to `ADMITTED` (`rowcount == 1`, binding worker_id, lease_id, lease_generation).
  5. Commit -> emits in-process `AdmissionReceipt`.

### Step 5: One-Shot Backend Start Claim & Secret Token Generation (Stage 3 - F4.3-02)
- **Action:** `ExecutionAttemptRepository.claim_backend_start(receipt, ...)` verifies unexpired active lease under row lock, generates raw `backend_start_token`, stores its SHA-256 hash in `runtime_execution_attempts`, transitions attempt `ADMITTED -> BACKEND_STARTING` with `rowcount == 1`, and returns `BackendExecutionClaim` carrying raw token and immutable `target_fingerprint`.

### Step 6: Atomic Pre-Effect CAS with Lease Revalidation (Stage 4 - F4.3-01, F4.3-02, F4.3-03)
- **Local:** In ONE PostgreSQL transaction: (1) revalidates and locks active unexpired lease `FOR UPDATE`; (2) validates durable request `action_digest`; (3) updates attempt `BACKEND_STARTING -> RUNNING`, verifies `backend_start_token_hash`, clears token hash to `NULL` (`rowcount == 1`). Invokes container.
- **Remote:** SafeNetworkBackend resolves DNS, pins IP, validates `target_fingerprint`. In ONE PostgreSQL transaction: (1) revalidates and locks active unexpired lease `FOR UPDATE`; (2) validates durable request `action_digest` and `target_fingerprint`; (3) updates attempt `BACKEND_STARTING -> RUNNING / EFFECT_TRANSMITTING`, verifies `backend_start_token_hash`, clears token hash to `NULL` (`rowcount == 1`). Transmits socket bytes to pinned IP.
- **Fencing Invariant:** If the lease expired or generation was replaced during worker stall, the lease query returns 0 rows and fails closed. Does NOT depend on reaper timing.
- **Race Condition Closed:** Concurrent duplicate calls match 0 rows and fail closed with `ExecutionSecurityError` before any side-effect.

### Step 7: Evidence Persistence & Lease Finalization (Stage 5 - F4.2-04, F4.3-04)
- **Order:** Result -> Outcome row -> Evidence store -> Attempt terminal update (with `evidence_status = 'COMMITTED'` or `'INCOMPLETE'`) -> Lease `COMPLETED` -> Capacity released.
- **Crash Point O:** If a crash occurs after EvidenceStore commit before attempt terminalization, reconciler inspects EvidenceStore, finds the committed evidence, and terminalizes attempt with `evidence_status = 'COMMITTED'`.
