# WhitePact Phase 7A: Canonical Execution Authority Codebase Audit

**Document Status:** CANONICAL SPECIFICATION PASS 4.3 (SECURITY BOUNDARY CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Proposed Migrations:** `0049_runtime_execution_requests.py` through `0052_runtime_worker_leases.py`

---

## 1. Executive Summary & Codebase Reality

This audit verifies the physical reality of `ExecutionAuthorization` and all related execution-authority call sites and repositories in the canonical WhitePact codebase (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

### Verified Production Call Sites
1. **`authorize_execution()` Call Sites:**
   - `src/responsibleai/mcp/governance_integration.py`: line 468 (in `execute_governed_action`)
   - `src/responsibleai/mcp/governance_integration.py`: line 816 (in `resolve_approval_and_execute`)
   - `src/responsibleai/mcp/upstream_dispatch.py`: line 322 (in `dispatch_upstream_action`)
2. **`admit_execution()` Call Sites:**
   - `src/responsibleai/governance/execution.py`: line 334 (in `InternalToolExecutor.execute`)
   - `src/responsibleai/governance/upstream_executor.py`: line 226 (in `UpstreamMCPExecutor.execute`)

### Key Findings
1. **`ExecutionAuthorization` is an in-memory dataclass today:** Defined in `src/responsibleai/governance/execution.py` (lines 129–176).
2. **Missing Action Payload Storage:** Prior to Phase 7A, no table persisted the serialized action payload for asynchronous execution. Digest hashing was present, but payloads could not be reconstructed without re-evaluating policies.
3. **Approval Consumption Was Disconnected:** Approval consumption was handled in a separate transaction from authorization issuance, risking split state.
4. **Durable Architecture Introduced:**
   - `runtime_execution_requests` (Migration 0049): RFC 8785 canonical JSON action payload, append-only, trigger rejects UPDATE/DELETE, universal idempotency key.
   - `governance_execution_authorizations` (Migration 0050): Losslessly persists all 11 fields; `UNIQUE(approval_id)`.
   - `runtime_execution_attempts` (Migration 0051): Durable attempt and effect lifecycle, nullable lease fields in `PENDING`, state CHECK constraints, active partial unique index.
   - `runtime_worker_leases`, `runtime_execution_fences`, and `runtime_execution_dispatch_outbox` (Migration 0052): Monotonic generation counter, synchronous expiry fencing, transactional dispatch outbox, DB-enforced active exclusivity.
5. **Universal Epoch Revocation:** All 26 audited authority mutations across 13 domain subsystems advance `governance_revocation_epochs.epoch` under a row lock, closing TOCTOU windows between issuance and admission.

---

## 2. Classification of `ExecutionAuthorization` Properties

| Field Name | Type | Current Codebase Reality | Classification | Durability / Source of Truth |
| :--- | :--- | :--- | :--- | :--- |
| `authorization_id` | `str` (UUIDv4) | Generated in memory. Recorded in `governance_execution_nonces` only *after* admission. | **IN MEMORY TODAY** | Primary key in `governance_execution_authorizations` (Mig 0050). |
| `organization_id` | `str | None` | Extracted from `action.agent.organization_id`. Verified in `admit_execution()`. | **IN MEMORY TODAY** (Tenant is durable) | Stored in `governance_execution_authorizations` with `ForeignKey("organizations.id", ondelete="RESTRICT")`. |
| `principal_id` | `str | None` | Extracted from `action.agent.identity.identity_id`. Used in `matches_action()`. | **IN MEMORY TODAY** (Principal is durable) | Stored in `governance_execution_authorizations` to bind subject authority. |
| `action_digest` | `str` | Computed via `compute_action_digest(action)` (SHA-256 hex). | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (VARCHAR(64)) to guarantee tamper-proof action immutability. |
| `target_fingerprint` | `str | None` | Execution Permit v2 hash of resolved target. Checked via `check_target_fingerprint()`. | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (VARCHAR(64), nullable) to detect target drift. |
| `decision` | `GovernanceDecision` | Must be `ALLOW` or `ALLOW_WITH_REDACTION`. | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (VARCHAR(32)) for judgment provenance. |
| `revocation_epoch` | `int | None` | Stamped from `governance_revocation_epochs.epoch`. Verified under lock at admission. | **DERIVED FROM DURABLE STATE** | Stored in `governance_execution_authorizations` (INTEGER) to lock expected epoch. |
| `nonce` | `str` (UUIDv4 hex) | Generated in memory. Inserted into `governance_execution_nonces` at admission. | **IN MEMORY TODAY** (Becomes durable at admission) | Stored in `governance_execution_authorizations` (VARCHAR(64), UNIQUE) at issuance. |
| `issued_at` | `datetime` | Stamped at construction (`datetime.now(UTC)`). | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (TIMESTAMPTZ). |
| `expires_at` | `datetime` | Stamped at construction (`issued_at + timedelta(seconds=ttl)`). | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (TIMESTAMPTZ). |
| `consumed` | `bool` | In-memory flag set to `True` at end of `admit_execution()`. | **IN MEMORY TODAY** | Reflected as durable state machine in `governance_execution_authorizations.status` (`ISSUED`, `CONSUMED`). |

---

## 3. Revocation & Expiration Semantics

### 3.1 Revocation: Singular Epoch Architecture (No Dual-Source Ambiguity)
- **Elimination of `status = REVOKED`:** The epoch repository remains the singular source of truth for revocation. All 26 audited authority mutations across 13 domain subsystems advance `governance_revocation_epochs.epoch` under row lock.
- **Admission Enforcement:** `admit_execution()` verifies `expected_epoch == current_epoch` under a row lock in `lock_epoch()`. If the epoch was bumped while a request waited in queue, admission fails closed immediately with `StaleRevocationEpochError`.

### 3.2 Expiration: Purely Derived (Zero Background Mutation)
- **Derived Invariant:** An authorization is expired if and only if `datetime.now(UTC) >= expires_at`.
- **Zero Background Churn:** There is no background worker mutating database rows to `EXPIRED`.
- **Database Status Lifecycle:** Exactly two states in `governance_execution_authorizations`:
  - `ISSUED`: Created at decision time, valid for consumption until `expires_at`.
  - `CONSUMED`: Atomically transitioned during `admit_execution()` under lock.
- **Conditional Query Guard:**
  ```sql
  WHERE status = 'ISSUED' AND expires_at > CURRENT_TIMESTAMP
  ```

---

## 4. Centralized Durable Issuance & Single Admission

- **Issuance Boundary:** `DurableExecutionAuthorizationIssuer.issue()` persists `runtime_execution_requests`, `governance_execution_authorizations`, initial `runtime_execution_attempts` (`PENDING`, `evidence_status=PENDING`), `runtime_execution_fences`, and `runtime_execution_dispatch_outbox` (`PENDING`) in ONE transaction before calling `AdmissionController.reserve_execution()` or enqueueing a `QueueTicket`.
- **Single Admission Owner (F4.2-01):** The worker process owns canonical `admit_execution()`, executing an atomic PostgreSQL transaction in `ExecutionNonceRepository.consume()` that burns the single-use nonce, updates authorization `ISSUED -> CONSUMED` (`rowcount == 1`), and transitions the attempt from `LEASED` to `ADMITTED` (`rowcount == 1`). Emits in-process `AdmissionReceipt`.
- **Backend-Start Claim & Secret Token Hash (F4.3-02):** The worker calls `claim_backend_start()` to verify lease validity/generation under lock and transition the attempt to `BACKEND_STARTING` (`rowcount == 1`). A cryptographically secure random token (`backend_start_token`) is generated and returned raw in `BackendExecutionClaim`, with only `backend_start_token_hash` stored in PostgreSQL.
- **Pre-Effect CAS with Synchronous Lease Revalidation (F4.3-01, F4.3-02, F4.3-03):** Downstream executors require `BackendExecutionClaim` and execute an atomic CAS transaction (`claim_local_effect_start()` or `claim_external_effect_transmission()`) with `rowcount == 1` immediately prior to container or socket invocation. The transaction synchronously revalidates the active unexpired lease under row lock, asserts immutable durable request `action_digest` (and `target_fingerprint`), validates and clears `backend_start_token_hash = NULL`, and transitions attempt state to `RUNNING`. Fencing correctness does not depend on reaper timing; zombie workers fail closed.
- **Evidence Precedence & Crash Consistency (F4.2-04, F4.3-04):** Evidence persistence in EvidenceStore strictly precedes normal attempt completion while attempt `evidence_status` remains `PENDING`. Terminal attempt CAS sets `evidence_status = 'COMMITTED'`. Crash Point O is deterministically reconciled by supervisor inspecting EvidenceStore.
