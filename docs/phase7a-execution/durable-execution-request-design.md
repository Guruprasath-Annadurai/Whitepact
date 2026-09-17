# WhitePact Phase 7A: Durable Immutable Execution Request Design

**Document Status:** CANONICAL SPECIFICATION PASS 4 (SECURITY REMEDIATION)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Proposed Migration:** `0049_runtime_execution_requests.py` (down-revision: `0048`)

---

## 1. Problem Statement & Threat Model

In asynchronous and distributed execution, in-memory actions or lightweight digests alone are insufficient for safe execution:
1. **Digest Irreversibility:** A cryptographic hash (`action_digest`) proves integrity but cannot reconstruct the action arguments, target, or purpose when a worker process executes the task seconds or minutes later.
2. **Policy Re-Evaluation Prohibition:** A worker MUST NOT re-evaluate governance policies at dequeue time to "re-derive" the action. Doing so violates policy immutability, introduces temporal inconsistency, and breaks auditability.
3. **Queue Payload Exposure:** Storing raw action arguments, authentication tokens, or credentials in Redis queues violates the zero-trust principle and exposes sensitive payload data to queue interception.
4. **Idempotency & Duplicate Minting:** Client retries following network timeouts must not produce multiple distinct execution permits for the same logical operation.

---

## 2. Table Schema: `runtime_execution_requests`

Migration `0049_runtime_execution_requests.py` establishes the durable, append-only store for canonical execution inputs:

```sql
CREATE TABLE runtime_execution_requests (
    execution_id VARCHAR(64) PRIMARY KEY,
    organization_id VARCHAR(64) NOT NULL,
    principal_id VARCHAR(64) NOT NULL,
    idempotency_key VARCHAR(128) NULL,
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
    status VARCHAR(32) NOT NULL DEFAULT 'COMMITTED',

    CONSTRAINT fk_exec_req_org
        FOREIGN KEY (organization_id)
        REFERENCES organizations(id)
        ON DELETE RESTRICT,

    CONSTRAINT fk_exec_req_approval
        FOREIGN KEY (approval_id)
        REFERENCES governance_approvals(id)
        ON DELETE RESTRICT,

    CONSTRAINT chk_exec_req_status
        CHECK (status IN ('COMMITTED', 'TERMINATED'))
);

-- Tenant-scoped idempotency constraint
CREATE UNIQUE INDEX idx_exec_req_org_idempotency
ON runtime_execution_requests (organization_id, idempotency_key)
WHERE idempotency_key IS NOT NULL;

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

## 4. Immutability Enforcement

Security-critical action fields MUST NOT be altered once written. Immutability is enforced at three defense layers:
1. **Database Role Privileges:** The runtime application database role is granted only `SELECT` and `INSERT` on `runtime_execution_requests`. `UPDATE` and `DELETE` privileges are explicitly revoked.
2. **PostgreSQL Immutability Trigger:**
   ```sql
   CREATE OR REPLACE FUNCTION trg_prevent_execution_request_update()
   RETURNS TRIGGER AS $$
   BEGIN
       IF (NEW.execution_id <> OLD.execution_id OR
           NEW.organization_id <> OLD.organization_id OR
           NEW.principal_id <> OLD.principal_id OR
           NEW.action_digest <> OLD.action_digest OR
           NEW.canonical_action_payload <> OLD.canonical_action_payload OR
           NEW.approved_arguments <> OLD.approved_arguments) THEN
           RAISE EXCEPTION 'Modification of immutable execution request fields is forbidden';
       END IF;
       RETURN NEW;
   END;
   $$ LANGUAGE plpgsql;

   CREATE TRIGGER enforce_execution_request_immutability
   BEFORE UPDATE ON runtime_execution_requests
   FOR EACH ROW EXECUTE FUNCTION trg_prevent_execution_request_update();
   ```
3. **Repository Interface:** The `ExecutionRequestRepository` provides only `create()` and `get()` methods. No update method is implemented.

---

## 5. Tenant-Scoped Idempotent Issuance Semantics

To prevent duplicate execution permits from being minted on client retries:
1. **Idempotency Key Scope:** The partial unique index `(organization_id, idempotency_key)` guarantees that idempotency keys are strictly isolated per tenant.
2. **Atomic Get-or-Create Logic:**
   - When a client submits an `ActionRequest` with an `idempotency_key`:
     - Gateway queries `runtime_execution_requests` for `(organization_id, idempotency_key)`.
     - **Match Found & Same Digest:** Returns the existing `execution_id` and durable authorization state. Zero duplicate authorizations or queue tickets are emitted.
     - **Match Found & Different Digest:** Fails closed immediately with HTTP 409 Conflict (`IdempotencyConflictError`). An idempotency key cannot be reused for a different payload.
     - **No Match Found:** Begins transaction, inserts request, inserts authorization, and commits.
3. **Missing Idempotency Key:** If the client provides no idempotency key:
   - The gateway generates a cryptographically secure random UUIDv4 correlation key (`req_corr_<uuid4>`) bound to the HTTP session, or treats the operation as explicitly non-idempotent (`idempotency_key = NULL`).

---

## 6. Queue Isolation: Non-Privileged Queue Tickets

The queue (`BoundedMultiTenantQueue` backed by Redis or in-memory) holds strictly non-authoritative pointers:

```python
class QueueTicket:
    # Non-privileged pointer enqueued for fair scheduling.
    # Contains zero authority credentials, zero tokens, and zero action arguments.
    # Possession of a QueueTicket grants no execution authority.
    execution_id: str
    organization_id: str
    authorization_id: str
    enqueued_at: datetime
```

- Redis stores only `QueueTicket` JSON primitives.
- No sensitive arguments, passwords, or tokens ever enter Redis.
- If Redis is intercepted or corrupted, no execution permit is compromised because all authority checks and payloads reside exclusively in PostgreSQL.
