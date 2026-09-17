# WhitePact Phase 7A: Canonical Execution Authority Codebase Audit

**Document Status:** CANONICAL SPECIFICATION PASS 4 (SECURITY REMEDIATION)
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
   - `runtime_execution_requests` (Migration 0049): RFC 8785 canonical JSON action payload, append-only, tenant-scoped idempotency.
   - `governance_execution_authorizations` (Migration 0050): Losslessly persists all 11 fields; `UNIQUE(approval_id)`.
   - `runtime_execution_attempts` (Migration 0051): Durable attempt and effect lifecycle, one-shot backend-start transition (`ADMITTED -> BACKEND_STARTING`).
   - `runtime_worker_leases` (Migration 0052): Monotonic `lease_generation` fencing tokens, DB-enforced active exclusivity.
5. **Universal Epoch Revocation:** All 14 authority mutations advance `governance_revocation_epochs.epoch` under a row lock, closing TOCTOU windows between issuance and admission.

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
- **Elimination of `status = REVOKED`:** The epoch repository remains the singular source of truth for revocation. All 14 authority mutations advance `governance_revocation_epochs.epoch` under row lock.
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

- **Issuance Boundary:** `DurableExecutionAuthorizationIssuer.issue()` persists `runtime_execution_requests` and `governance_execution_authorizations` in ONE transaction before calling `AdmissionController.reserve_execution()` or enqueueing a `QueueTicket`.
- **Single Admission Owner:** The worker process owns canonical `admit_execution()`, burning the single-use nonce and emitting an in-process `AdmissionReceipt`.
- **One-Shot Backend Start:** Before delegating to `InternalToolExecutor.execute()` or `UpstreamMCPExecutor.execute()`, the worker atomically transitions `runtime_execution_attempts` from `ADMITTED` to `BACKEND_STARTING` with `rowcount == 1`. Downstream executors consume `AdmissionReceipt` without re-admission.
