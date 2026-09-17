# WhitePact Phase 7A: Canonical Worker Execution Flow

**Document Status:** CANONICAL SPECIFICATION PASS 4.1 (SECURITY CONSISTENCY REMEDIATION)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Proposed Migrations:** `0049_runtime_execution_requests.py` through `0052_runtime_worker_leases.py`

---

## 1. Overview and Control Chain Invariants

This document specifies the authoritative, end-to-end execution control chain for Phase 7A.

### Core Architectural Invariants:
1. **Durable Issuance Precedes Queueing:** No `QueueTicket` may be generated until `runtime_execution_requests`, `governance_execution_authorizations`, initial `runtime_execution_attempts` (state=`PENDING`), and `runtime_execution_fences` are durably committed in PostgreSQL.
2. **Single Canonical Admission Gate:** No worker may begin backend execution without successfully completing `admit_execution()` in `src/responsibleai/governance/execution.py`.
3. **One-Shot Backend Start Transition:** Possession of an `AdmissionReceipt` is insufficient to execute. Downstream execution requires calling `ExecutionAttemptRepository.claim_backend_start()` to atomically verify unexpired active lease status and transition `ADMITTED` to `BACKEND_STARTING` in `runtime_execution_attempts` with `rowcount == 1`, returning a `BackendExecutionClaim`.
4. **Direct Executor Verification:** Executors (`InternalToolExecutor`, `UpstreamMCPExecutor`) accept ONLY `BackendExecutionClaim` and MUST call `assert_backend_start_claim(claim)` against PostgreSQL before initiating any compute or network side-effect.
5. **Monotonic Worker Fencing:** Each lease acquisition increments `runtime_execution_fences.current_generation`. A stale worker holding an expired or superseded generation cannot start backend execution.
6. **Queue Isolation:** Queue tickets (`QueueTicket`) contain strictly non-privileged pointers (`execution_id`, `authorization_id`, `org_id`, `attempt_id`, `enqueued_at`). Zero credentials or arguments in Redis.
7. **Safe Network Boundary:** `SafeNetworkBackend` validates targets, checks target fingerprints, pins the socket IP, commits `effect_state = 'EFFECT_TRANSMITTING'`, and transmits socket bytes.
8. **No Blind Replay:** If an external side-effect is interrupted or fails after `EFFECT_TRANSMITTING`, the attempt is marked `UNCERTAIN`; automatic blind replay is strictly prohibited.
9. **Universal Capacity Release:** Every capacity reservation made at enqueue time has an explicit terminal release path (on completion, failure, rejection, or crash reconciliation).
10. **Evidence Precedes Lease Finalization:** Result captured -> durable effect/outcome state -> durable evidence write -> mark attempt terminal -> finalize lease -> release capacity.

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
    Issuer->>DB: INSERT runtime_execution_attempts (state=PENDING, lease fields NULL)
    Issuer->>DB: INSERT runtime_execution_fences (current_generation=0)
    Issuer->>DB: COMMIT TRANSACTION

    Gateway->>AdmCtrl: reserve_execution() & enqueue(QueueTicket)
    AdmCtrl-->>Client: Return 202 Accepted (execution_id, idempotency_key)

    loop Fair Dequeue Loop
        Dispatcher->>AdmCtrl: Dequeue Next Ticket (Round-Robin Tenant)
    end

    Note over Dispatcher: Stage 1: Early Invalidation
    Dispatcher->>DB: Read Authorization Status & Expiration
    Dispatcher->>DB: Check Tenant Active & now < expires_at
    alt Early Invalidation Fails (e.g. Expired or Revoked)
        Dispatcher->>DB: UPDATE runtime_execution_attempts SET state=FAILED_PRE_EXECUTION
        Dispatcher->>AdmCtrl: release_execution() [4.1-F13]
        Note over Dispatcher: Abort dispatch; ticket dropped cleanly
    end

    Dispatcher->>DB: Atomically Increment runtime_execution_fences & INSERT runtime_worker_leases (status=ACTIVE, gen=N)
    Dispatcher->>DB: UPDATE runtime_execution_attempts SET state=LEASED, worker_id=W, lease_id=L, lease_generation=N WHERE state=PENDING
    Dispatcher->>Worker: Dispatch to Worker Process with Lease Token

    Note over Worker: Stage 2: Canonical Admission
    Worker->>DB: Load Canonical Action Payload & Recompute Digest Match
    Worker->>Worker: Pre-Flight Checks: Principal, Session, BreakGlass, Delegation
    alt Preflight Checks Fail
        Worker->>DB: Mark Lease FAILED & Attempt FAILED_PRE_EXECUTION
        Worker->>AdmCtrl: release_execution() [4.1-F13]
    end

    Worker->>DB: admit_execution(authorization, action, nonce_repo)
    rect rgb(240, 248, 255)
        Note over DB: Atomic Admission Transaction in ExecutionNonceRepository.consume()
        DB->>DB: SELECT epoch FROM governance_revocation_epochs FOR UPDATE
        DB->>DB: Verify expected_epoch == current_epoch
        DB->>DB: INSERT INTO governance_execution_nonces
        DB->>DB: UPDATE governance_execution_authorizations SET status = CONSUMED WHERE status = ISSUED
        DB->>DB: Assert rowcount == 1 (Rollback if 0)
    end
    DB-->>Worker: Admission Confirmed -> Returns in-process AdmissionReceipt

    Note over Worker: Stage 3: One-Shot Backend Start & Fencing
    Worker->>DB: ExecutionAttemptRepository.claim_backend_start(receipt, W, L, N)
    rect rgb(255, 248, 240)
        Note over DB: Atomic Backend-Start Claim Transaction
        DB->>DB: SELECT lease_generation, expires_at FROM runtime_worker_leases WHERE status=ACTIVE AND expires_at > now FOR UPDATE
        DB->>DB: Assert active lease_generation == N (Fail if Stale / Fenced / Expired)
        DB->>DB: UPDATE runtime_execution_attempts SET state = BACKEND_STARTING, effect_state = EFFECT_STARTING WHERE state = ADMITTED
        DB->>DB: Assert rowcount == 1 (Fail if Already Started)
    end
    DB-->>Worker: Backend Start Confirmed -> Returns BackendExecutionClaim

    Note over Worker,Executor: Stage 4: Executor Verification & Side-Effect Invocation
    Worker->>Executor: execute(action, claim=BackendExecutionClaim)
    Executor->>DB: ExecutionAttemptRepository.assert_backend_start_claim(claim)
    Note over Executor,DB: Verifies attempt is BACKEND_STARTING, lease matches, digest matches
    alt Local Execution
        Executor->>DB: UPDATE runtime_execution_attempts SET state = RUNNING
        Executor->>Backend: ContainerIsolationBackend.execute(--network=none)
    else External Network Execution
        Executor->>Backend: SafeNetworkBackend target verification & DNS resolution
        Backend->>Backend: Pin IP address & compare target fingerprint
        Backend->>DB: UPDATE runtime_execution_attempts SET effect_state = EFFECT_TRANSMITTING, state = RUNNING
        Backend->>Backend: Transmit HTTP socket bytes with effect_id header
    end
    Backend-->>Executor: Return Result / exit_code
    Executor-->>Worker: Forward Result

    Note over Worker: Stage 5: Evidence & Finalization
    Worker->>DB: Record Durable Outcome & Attempt State (RUNNING -> COMPLETED)
    Worker->>DB: Record Durable Evidence & Compliance Attestation (EvidenceStore)
    Worker->>DB: Finalize Lease (status = COMPLETED)
    Worker->>AdmCtrl: Release Capacity Reservation
```

---

## 3. Step-by-Step State Transitions and Failure Exits

### Step 1: Decision & Centralized Durable Issuance
- **Actors:** `mcp/governance_integration.py` (`execute_governed_action`, `resolve_approval_and_execute`) and `mcp/upstream_dispatch.py` (`dispatch_upstream_action`).
- **Action:** Evaluates idempotency; if decision is `ALLOW` or `ALLOW_WITH_REDACTION`, issues in ONE atomic transaction:
  1. Append-only `runtime_execution_requests` row (RFC 8785 canonical JSON, trigger-protected).
  2. `governance_execution_authorizations` row (`status = 'ISSUED'`, `UNIQUE(approval_id)`).
  3. `runtime_execution_attempts` row (`state = 'PENDING'`, lease fields NULL).
  4. `runtime_execution_fences` row (`current_generation = 0`).
- **Failure Exit:** If DB write fails or idempotency conflict arises, request fails closed (HTTP 409 or 500). Zero `QueueTicket` records emitted.

### Step 2: Admission Reservation & Queueing
- **Action:** `AdmissionController.reserve_execution()` acquires capacity slot.
- **Enqueuing:** Lightweight `QueueTicket` enqueued to `FairExecutionScheduler`.
- **Response:** Client receives HTTP 202 with `execution_id` and `idempotency_key`.

### Step 3: Dequeue & Early Invalidation (Stage 1)
- **Actor:** Worker Dispatcher.
- **Early Checks:** `now < expires_at`, `status == 'ISSUED'`, tenant active.
- **Early Drop:** If checks fail, attempt marked `FAILED_PRE_EXECUTION`, capacity released, ticket dropped.
- **Lease Acquisition:** Atomically increments fence counter to generation N, acquires `runtime_worker_leases` row (`status = 'ACTIVE'`), transitions attempt to `LEASED`.

### Step 4: Canonical Admission (Stage 2)
- **Actor:** Execution Worker.
- **Pre-Flight Checks:** Recomputes action digest from `canonical_action_payload`, verifies principal/session/BreakGlass. If failed, marks lease `FAILED`, releases capacity.
- **Canonical Admission:** Calls `admit_execution()`, atomically locking epoch, burning nonce, updating authorization to `CONSUMED`.
- **Output:** In-process `AdmissionReceipt`.

### Step 5: One-Shot Backend Start & Fencing (Stage 3)
- **Actor:** Execution Worker.
- **API Call:** `ExecutionAttemptRepository.claim_backend_start(receipt, worker_id, lease_id, lease_generation)`.
- **Fence & Expiry Verification:** Synchronously verifies `status == 'ACTIVE' AND expires_at > now AND lease_generation == N` under row lock.
- **Atomic Transition:** Updates `runtime_execution_attempts` from `ADMITTED` to `BACKEND_STARTING` asserting `rowcount == 1`.
- **Output:** Returns `BackendExecutionClaim`.

### Step 6: Downstream Execution & Direct Bypass Closure (Stage 4)
- **Actors:** `InternalToolExecutor` or `UpstreamMCPExecutor`.
- **Signature:** Accepts `claim: BackendExecutionClaim` (rejects `AdmissionReceipt`).
- **Durable Check:** Calls `ExecutionAttemptRepository.assert_backend_start_claim(claim)` against PostgreSQL.
- **Local:** Sets state `RUNNING`, launches Docker container with `--network=none`.
- **Remote:** `SafeNetworkBackend` pins resolved IP, updates `effect_state = 'EFFECT_TRANSMITTING'`, and transmits socket bytes.

### Step 7: Evidence Persistence & Lease Finalization (Stage 5)
- **Order:** Result -> Outcome row -> Evidence store -> Attempt `COMPLETED` -> Lease `COMPLETED` -> Capacity released.
- **Failure Handling:** If evidence write fails after confirmed effect, attempt remains `COMPLETED` with `evidence_status = 'INCOMPLETE'` to prevent effect duplication; capacity is released.
