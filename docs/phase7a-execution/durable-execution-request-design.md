# WhitePact Phase 7A: Durable Immutable Execution Request Design

**Document Status:** CANONICAL SPECIFICATION PASS 4.1 (SECURITY CONSISTENCY REMEDIATION)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Proposed Migrations:** `0050_runtime_execution_requests.py` (down-revision: `0049`) and `0053_runtime_worker_leases.py` (for execution fences)

**Canonical migration ownership:** `docs/phase7a-execution/migration-ownership.md` (implemented `0049` = org governance lifecycle).

---

## 1. Problem Statement & Threat Model

In asynchronous and distributed execution, in-memory actions or lightweight digests alone are insufficient for safe execution:
1. **Digest Irreversibility:** A cryptographic hash (`action_digest`) proves integrity but cannot reconstruct the action arguments, target, or purpose when a worker process executes the task seconds or minutes later.
2. **Policy Re-Evaluation Prohibition:** A worker MUST NOT re-evaluate governance policies at dequeue time to "re-derive" the action. Doing so violates policy immutability, introduces temporal inconsistency, and breaks auditability.
3. **Queue Payload Exposure:** Storing raw action arguments, authentication tokens, or credentials in Redis queues violates the zero-trust principle and exposes sensitive payload data to queue interception.
4. **Idempotency & Duplicate Minting:** Client retries following network timeouts must not produce multiple distinct execution permits for the same logical operation.
5. **Separation of Input from Progress:** The execution request is an immutable historical record of approved inputs. Operational lifecycle progress belongs strictly in `runtime_execution_attempts`, and permit validity belongs strictly in `governance_execution_authorizations`. The request table contains zero mutable lifecycle status.

---

## 2. Table Schema: `runtime_execution_requests`

Migration `0050_runtime_execution_requests.py` establishes the durable, append-only store for canonical execution inputs:

```sql
CREATE TABLE runtime_execution_requests (
    execution_id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    principal_id VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) NOT NULL,
    action_type VARCHAR(128) NOT NULL,
    target VARCHAR(256) NOT NULL,
    server_id VARCHAR(128) NULL,
    approved_arguments JSONB NOT NULL,
    declared_purpose TEXT NOT NULL,
    agent_id VARCHAR(64) NOT NULL,
    identity_id VARCHAR(64) NOT NULL,
    approval_id VARCHAR(64) NULL,
    target_fingerprint VARCHAR(64) NULL,
    canonical_action_payload TEXT NOT NULL,
    action_digest VARCHAR(64) NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_exec_req_org
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_exec_req_approval
        FOREIGN KEY (approval_id)
        REFERENCES governance_approvals(id)
        ON DELETE RESTRICT
);

-- Tenant-scoped idempotency constraint (every hosted request has an idempotency key)
CREATE UNIQUE INDEX idx_exec_req_org_idempotency
ON runtime_execution_requests (organization_id, idempotency_key);

-- Action digest verification index
CREATE INDEX idx_exec_req_action_digest
ON runtime_execution_requests (organization_id, action_digest);

-- Tenant chronological lookup
CREATE INDEX idx_exec_req_org_created
ON runtime_execution_requests (organization_id, created_at DESC);
```

### Deletion and Foreign Key Semantics
- `organization_id` uses `ON DELETE RESTRICT`: organizations with execution history cannot be casually deleted.
- `approval_id` uses `ON DELETE RESTRICT`: human approvals linked to execution requests cannot be deleted.
- All timestamps use timezone-aware `TIMESTAMPTZ`.
- No `status` column: operational status belongs exclusively in `runtime_execution_attempts`.

---

## 3. Canonical Serialization & Action Digest Computation

To guarantee deterministic, byte-identical representations across all system replicas:
1. **Serialization Format:** Strict RFC 8785 JSON Canonicalization Scheme (JCS).
   - Keys are sorted lexicographically by UTF-16 code units.
   - Whitespace is strictly eliminated (separators are `,` and `:`).
   - Floats and integers follow strict ECMA-262 JSON formatting.
   - Strings are UTF-8 encoded without unescaped control characters.
2. **Canonical Action Payload Construction:**
   - The serialized dictionary contains all fields evaluated by policy: `action_type`, `target`, `arguments` (with approved redactions applied), `purpose`, `agent` (`agent_id`, `organization_id`, `identity_id`, `principal_id`), and `target_fingerprint`.
   - `canonical_action_bytes = rfc8785_canonical_json(canonical_dict).encode("utf-8")`.
3. **Action Digest:**
   - `action_digest = hashlib.sha256(canonical_action_bytes).hexdigest()`.
4. **Worker Verification:** When the worker process dequeues a task, it loads `canonical_action_payload` from PostgreSQL, recomputes `SHA-256(canonical_action_payload.encode("utf-8"))`, and strictly asserts that it matches `action_digest` and the durable authorization. If a mismatch occurs, execution aborts immediately with `SecurityBindingMismatchError`.

---

## 4. Complete Immutability Enforcement

Security-critical action fields MUST NOT be altered once written. Immutability is enforced at three defense layers:
1. **Database Role Privileges:** The runtime application database role is granted only `SELECT` and `INSERT` on `runtime_execution_requests`. `UPDATE` and `DELETE` privileges are explicitly revoked via `REVOKE UPDATE, DELETE ON runtime_execution_requests FROM app_role`.
2. **PostgreSQL Immutability Trigger:**
   All `UPDATE` and `DELETE` operations are unconditionally rejected by a database trigger:
   ```sql
   CREATE OR REPLACE FUNCTION reject_execution_request_mutation()
   RETURNS TRIGGER AS $$
   BEGIN
       RAISE EXCEPTION 'runtime_execution_requests is immutable and append-only: UPDATE and DELETE are prohibited';
   END;
   $$ LANGUAGE plpgsql;

   CREATE TRIGGER prevent_execution_request_mutation
   BEFORE UPDATE OR DELETE ON runtime_execution_requests
   FOR EACH ROW EXECUTE FUNCTION reject_execution_request_mutation();
   ```
   This prevents forgetting newly added security columns later and ensures defense in depth even if database user privileges are misconfigured.
3. **Repository Interface:** The `ExecutionRequestRepository` provides only `create()` and `get()` methods. No update or delete methods exist in the repository interface.

---

## 5. Tenant-Scoped Concurrency-Safe Idempotency Semantics

To prevent duplicate execution permits from being minted on client retries:
1. **Universal Idempotency Key Requirement:** Every hosted consequential `ActionRequest` receives a stable idempotency key.
   - If the client supplies an `idempotency_key` header/parameter, that key is used.
   - If the client omits `idempotency_key`, the hosted gateway generates a cryptographically secure UUIDv4 key (`idempotency_key = f"gen_idemp_{uuid.uuid4().hex}"`) BEFORE beginning the first durable transaction. This key is stored in `runtime_execution_requests` and returned in the HTTP response (`X-Idempotency-Key` and response body) alongside `execution_id`.
   - **Documented Limitation:** If a client request disconnects or times out before receiving the gateway's response containing the generated key, a subsequent client retry without a key cannot be deduplicated and will create a distinct execution. Therefore, clients executing consequential mutating actions SHOULD provide a client-generated idempotency key on their initial request.
2. **Atomic Concurrency-Safe Insertion:**
   The gateway does NOT use an unsafe check-then-insert pattern (`SELECT` followed by `INSERT`). Instead:
   - The gateway attempts `INSERT INTO runtime_execution_requests (...)`.
   - Under concurrent requests submitting the same `(organization_id, idempotency_key)`, PostgreSQL raises a `UniqueViolation` on `idx_exec_req_org_idempotency`.
   - Upon catching `UniqueViolation`:
     - The transaction rolls back and queries:
       `SELECT execution_id, action_digest FROM runtime_execution_requests WHERE organization_id = :org_id AND idempotency_key = :key;`
     - Compares `existing.action_digest == incoming.action_digest`:
       - **Identical Digest:** Deduplication succeeds. Returns the existing `execution_id` and existing authorization state without re-evaluating policy, minting new authorizations, or queueing duplicate work.
       - **Different Digest:** Fails closed immediately by raising `IdempotencyConflictError` (HTTP 409 Conflict). An idempotency key cannot be reused with a different action payload.

---

## 6. Dedicated Execution Fence Counter Table

To support strictly monotonic, concurrency-safe worker fencing without race conditions, Migration `0053_runtime_worker_leases.py` creates `runtime_execution_fences`:

```sql
CREATE TABLE runtime_execution_fences (
    execution_id VARCHAR(64) PRIMARY KEY,
    current_generation BIGINT NOT NULL DEFAULT 0,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_fence_exec_req
        FOREIGN KEY (execution_id)
        REFERENCES runtime_execution_requests(execution_id)
        ON DELETE RESTRICT
);
```

During the initial centralized issuance transaction, a fence row is inserted with `current_generation = 0`. When a worker acquires or reassigns a lease, it executes:
```sql
UPDATE runtime_execution_fences
SET current_generation = current_generation + 1
WHERE execution_id = :execution_id
RETURNING current_generation;
```
This guarantees strictly monotonic, race-free generation allocation under high concurrency.

---

## 7. Queue Isolation: Non-Privileged Queue Tickets

The queue (`BoundedMultiTenantQueue` backed by Redis or in-memory) holds strictly non-authoritative pointers:

```python
@dataclass(frozen=True)
class QueueTicket:
    """Non-privileged pointer enqueued for fair scheduling.
    Contains zero authority credentials, zero tokens, and zero action arguments.
    Possession of a QueueTicket grants no execution authority.
    """
    execution_id: str
    organization_id: str
    authorization_id: str
    attempt_id: str
    enqueued_at: datetime
```

- Redis stores only `QueueTicket` JSON primitives.
- No sensitive arguments, passwords, or tokens ever enter Redis.
- If Redis is intercepted or corrupted, no execution permit is compromised because all authority checks and payloads reside exclusively in PostgreSQL.

---

## 8. Canonical Transactional Dispatch Outbox (`runtime_execution_dispatch_outbox`)

To eliminate the crash window between PostgreSQL durable authorization issuance and Redis/memory queue publication (Finding `7A-F01`), Migration `0053_runtime_worker_leases.py` creates `runtime_execution_dispatch_outbox`:

```sql
CREATE TABLE runtime_execution_dispatch_outbox (
    outbox_id VARCHAR(64) PRIMARY KEY,
    execution_id VARCHAR(64) NOT NULL,
    organization_id VARCHAR(64) NOT NULL,
    authorization_id VARCHAR(64) NOT NULL,
    attempt_id VARCHAR(64) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'PENDING',
    publish_attempts INTEGER NOT NULL DEFAULT 0,
    last_attempted_at TIMESTAMPTZ NULL,
    published_at TIMESTAMPTZ NULL,
    acknowledged_at TIMESTAMPTZ NULL,
    error_detail TEXT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,

    CONSTRAINT fk_outbox_exec_req
        FOREIGN KEY (execution_id)
        REFERENCES runtime_execution_requests(execution_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_outbox_auth
        FOREIGN KEY (authorization_id)
        REFERENCES governance_execution_authorizations(authorization_id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_outbox_attempt
        FOREIGN KEY (attempt_id)
        REFERENCES runtime_execution_attempts(attempt_id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_outbox_status
        CHECK (status IN ('PENDING', 'PUBLISHING', 'PUBLISHED', 'ACKNOWLEDGED', 'CANCELLED', 'EXPIRED'))
);

CREATE INDEX idx_outbox_pending ON runtime_execution_dispatch_outbox (status, created_at)
WHERE status IN ('PENDING', 'PUBLISHED');

CREATE UNIQUE INDEX uq_outbox_execution ON runtime_execution_dispatch_outbox (execution_id);
```

### Outbox Lifecycle & Invariants:
1. **Atomic Issuance Insertion:** An outbox row is inserted with `status = 'PENDING'` inside the EXACT SAME transaction that inserts `runtime_execution_requests`, `governance_execution_authorizations`, initial `runtime_execution_attempts`, and `runtime_execution_fences`.
2. **Publisher claim:** A publisher atomically CAS `PENDING -> PUBLISHING` with `publisher_id`, `claimed_at`, and a claim timeout (or `SELECT … FOR UPDATE SKIP LOCKED` then the same CAS). Only the claimant may enqueue Redis. Duplicate QueueTicket delivery can still occur and must be tolerated by durable admission/CAS. Redis is not authority.
3. **Confirmed enqueue:** After Redis accept, CAS `PUBLISHING -> PUBLISHED`. If the process dies after Redis and before this CAS, another publisher may reclaim a timed-out `PUBLISHING` row; downstream CAS still admits at most once.
4. **Capacity:** `AdmissionController.reserve_execution` uses one atomic Redis Lua EVAL (see `runtime/capacity_reservation.py`). NX+INCR as two commands is forbidden.
3. **Outbox Reconciler (Crash Recovery):** A background daemon scans `idx_outbox_pending` for rows with `status = 'PENDING'` older than 5 seconds. If the initial attempt is still `PENDING`, it idempotently reserves capacity, publishes `QueueTicket`, and marks `PUBLISHED`.
4. **Worker Acknowledgement:** When a worker acquires the lease and transitions attempt `PENDING -> LEASED` (or at admission `LEASED -> ADMITTED`), it updates outbox `status = 'ACKNOWLEDGED'`.
5. **Infrastructure State Only:** Outbox possession or row presence NEVER authorizes execution; only the complete cryptographic authorization chain in PostgreSQL permits admission.
