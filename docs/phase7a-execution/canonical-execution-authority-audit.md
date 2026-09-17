# WhitePact Phase 7A: Canonical Execution Authority Codebase Audit

**Document Status:** CANONICAL SPECIFICATION PASS 3 (FINAL CALL-PATH & SINGLE-ADMISSION CLOSURE)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

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
   - `src/responsibleai/governance/upstream_executor.py`: line 226 (in `UpstreamServer.execute`)

### Key Findings
1. **`ExecutionAuthorization` is an in-memory dataclass today:** Defined in `src/responsibleai/governance/execution.py` (lines 129–176).
2. **No table stores `ExecutionAuthorization` at issuance:** Unlike `REQUIRE_APPROVAL` decisions (which persist an `ApprovalRequest` row in `governance_approvals`), direct `ALLOW` decisions have no persistent database representation prior to execution.
3. **Only the single-use `nonce` is durably stored at admission:** `ExecutionNonceRepository.consume()` in `src/responsibleai/db/execution_nonce_repository.py` inserts into `governance_execution_nonces` and verifies against `governance_revocation_epochs` inside `self._engine.raw.begin()`.
4. **Deterministic reconstruction from existing tables is IMPOSSIBLE for queued async executions:** A worker process cannot reconstruct an in-memory `ExecutionAuthorization` without re-evaluating policy (which violates policy immutability and temporal auditability).
5. **Centralized Durable Issuance Owner:** All 3 `authorize_execution()` call sites (`execute_governed_action`, `resolve_approval_and_execute` in `governance_integration.py`, and `dispatch_upstream_action` in `upstream_dispatch.py`) must route through `DurableExecutionAuthorizationIssuer.issue()` to persist `ExecutionAuthorization` in PostgreSQL (`governance_execution_authorizations`) BEFORE creating a `QueueTicket`. If DB persistence fails, queueing is aborted immediately (HTTP 500/503).
6. **Atomic Consumption Owner:** `src/responsibleai/db/execution_nonce_repository.py` owns the singular PostgreSQL transaction combining the revocation epoch lock, nonce insertion, and conditional authorization status update (`ISSUED -> CONSUMED` with `rowcount == 1`).
7. **Single Admission Ownership & Admitted Context:** Canonical `admit_execution()` is owned exclusively by the execution worker immediately prior to container or network side effects. Successful admission returns a typed `AdmittedExecution` context. Downstream executors (`InternalToolExecutor.execute` and `UpstreamServer.execute`) accept this context and do not re-invoke `admit_execution()`, eliminating double-admission.

---

## 2. Classification of `ExecutionAuthorization` Properties

| Field Name | Type | Current Codebase Reality | Classification | Durability / Source of Truth |
| :--- | :--- | :--- | :--- | :--- |
| `authorization_id` | `str` (UUIDv4) | Generated in memory. Recorded in `governance_execution_nonces` only *after* admission. | **IN MEMORY TODAY** | Primary key in `governance_execution_authorizations`. |
| `organization_id` | `str | None` | Extracted from `action.agent.organization_id`. Verified in `admit_execution()`. | **IN MEMORY TODAY** (Tenant is durable) | Stored in `governance_execution_authorizations` with `ForeignKey("organizations.id", ondelete="RESTRICT")`. |
| `principal_id` | `str | None` | Extracted from `action.agent.identity.identity_id`. Used in `matches_action()`. | **IN MEMORY TODAY** (Principal is durable) | Stored in `governance_execution_authorizations` to bind subject authority. |
| `action_digest` | `str` | Computed via `compute_action_digest(action)` (SHA-256 hex). | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (VARCHAR(64)) to guarantee tamper-proof action immutability. |
| `target_fingerprint` | `str | None` | Execution Permit v2 hash of resolved target. Checked via `check_target_fingerprint()`. | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (VARCHAR(64), nullable) to detect target drift. |
| `decision` | `GovernanceDecision` | Must be `ALLOW` or `ALLOW_WITH_REDACTION`. | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (VARCHAR(32)) for judgment provenance. |
| `revocation_epoch` | `int | None` | Stamped from `governance_revocation_epochs.epoch`. Verified under lock at admission. | **DERIVED FROM DURABLE STATE** | Stored in `governance_execution_authorizations` (INTEGER) to lock expected epoch. |
| `nonce` | `str` (UUIDv4 hex) | Generated in memory. Inserted into `governance_execution_nonces` at admission. | **IN MEMORY TODAY** (Becomes durable at admission) | Stored in `governance_execution_authorizations` (VARCHAR(64), UNIQUE) at issuance. |
| `issued_at` | `datetime` | Stamped at construction (`datetime.now(UTC)`). | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (VARCHAR(32), ISO-8601 UTC). |
| `expires_at` | `datetime` | Stamped at construction (`issued_at + timedelta(seconds=ttl)`). | **IN MEMORY TODAY** | Stored in `governance_execution_authorizations` (VARCHAR(32), ISO-8601 UTC). |
| `consumed` | `bool` | In-memory flag set to `True` at end of `admit_execution()`. | **IN MEMORY TODAY** | Reflected as durable state machine in `governance_execution_authorizations.status` (`ISSUED`, `CONSUMED`). |

---

## 3. Revocation & Expiration Semantics

### 3.1 Revocation: Singular Epoch Architecture (No Dual-Source Ambiguity)
- **Elimination of `status = REVOKED`:** The candidate draft considered an explicit `REVOKED` state on individual authorizations. However, there is no product or runtime requirement for per-authorization manual revocation.
- **Authoritative Revocation Engine:** Tenant-wide authority invalidation is already canonically implemented via `governance_revocation_epochs` and `lock_epoch()`. When any governance entity changes (policy, budget, trust score, ceiling, delegation), the epoch is bumped.
- **Admission Enforcement:** `admit_execution()` verifies `expected_epoch == current_epoch` under a row lock. If the epoch was bumped while a request waited in queue, admission fails closed immediately with `StaleRevocationEpochError`.
- **Verdict:** Removing `REVOKED` from the authorization status avoids dual-source ambiguity. The epoch repository remains the singular source of truth for revocation.

### 3.2 Expiration: Purely Derived (Zero Background Mutation)
- **Derived Invariant:** An authorization is expired if and only if `datetime.now(UTC) >= expires_at`.
- **Zero Background Churn:** There is no background worker mutating database rows to `EXPIRED`.
- **Database Status Lifecycle:** Exactly two states:
  - `ISSUED`: Created at decision time, valid for consumption until `expires_at`.
  - `CONSUMED`: Atomically transitioned during `admit_execution()` under lock.
- **Conditional Query Guard:**
  ```sql
  WHERE status = 'ISSUED' AND expires_at > :now
  ```

---

## 4. Durable Issuance Architecture

- **Centralized Service:** `src/responsibleai/governance/execution_issuer.py` (`DurableExecutionAuthorizationIssuer`).
- **Call Sites Covered:**
  1. `src/responsibleai/mcp/governance_integration.py` (`execute_governed_action`)
  2. `src/responsibleai/mcp/governance_integration.py` (`resolve_approval_and_execute`)
  3. `src/responsibleai/mcp/upstream_dispatch.py` (`dispatch_upstream_action`)
- **Control Flow:**
  1. `authorize_execution()` produces in-memory `ExecutionAuthorization`.
  2. `DurableExecutionAuthorizationIssuer.issue(authorization)` executes `INSERT INTO governance_execution_authorizations`.
  3. **Non-Bypassable Gate:** ONLY after successful database transaction commit may `AdmissionController.reserve_execution()` and `FairExecutionScheduler.enqueue(QueueTicket)` be called.
  4. If database insert fails (e.g. PostgreSQL disconnect or constraint failure):
     - Exception is raised immediately.
     - NO `QueueTicket` is created.
     - NO item is placed into Redis or memory queues.
     - Request fails closed with HTTP 500/503.

---

## 5. Atomic Admission Architecture

- **Transaction Owner:** `ExecutionNonceRepository.consume()` in `src/responsibleai/db/execution_nonce_repository.py`.
- **Single Connection / Single Transaction:**
  ```python
  async with self._engine.raw.begin() as conn:
      # 1. Lock tenant revocation epoch
      current = await lock_epoch(conn, organization_id)
      if current != expected_epoch:
          raise StaleRevocationEpochError("Permit revocation epoch is stale")

      # 2. Insert single-use nonce
      await conn.execute(
          insert(nonces).values(
              nonce=nonce,
              authorization_id=authorization_id,
              organization_id=organization_id,
              consumed_at=now_iso,
          )
      )

      # 3. Conditional update on durable authorization record
      result = await conn.execute(
          update(governance_execution_authorizations)
          .where(
              governance_execution_authorizations.c.authorization_id == authorization_id,
              governance_execution_authorizations.c.organization_id == organization_id,
              governance_execution_authorizations.c.status == "ISSUED",
              governance_execution_authorizations.c.expires_at > now_iso,
          )
          .values(
              status="CONSUMED",
              consumed_at=now_iso,
              updated_at=now_iso,
          )
      )
      if result.rowcount != 1:
          raise AuthorizationAlreadyConsumedError(authorization_id)
  ```
- **Atomicity Guarantees:**
  - If conditional update matches 0 rows (already consumed, expired, or wrong tenant), `AuthorizationAlreadyConsumedError` is raised.
  - The transaction aborts and PostgreSQL rolls back the nonce insert.
  - If nonce insert fails (e.g. duplicate nonce), `IntegrityError` is caught and rolls back the transaction.
  - Zero possibility of split state: nonce committed without authorization consumed, or authorization consumed without nonce committed.

---

## 6. Single Admission Ownership & Downstream Adaptation

- **Chosen Architecture:** Option A — Worker Owns Admission.
- **Worker Gatekeeper:** `ResponsibleWorker` invokes canonical `admit_execution()` immediately before side-effect execution.
- **Post-Admission Proof:** Successful admission returns an immutable, unforgeable `AdmittedExecution` context containing `execution_id`, `authorization_id`, `organization_id`, `principal_id`, `action_digest`, `lease_id`, and `nonce`.
- **Downstream Adaptation:**
  - `InternalToolExecutor.execute()`: modified to accept `AdmittedExecution` context and assert matching `action_digest` and `organization_id`. It does NOT call `admit_execution()`.
  - `UpstreamServer.execute()`: modified to accept `AdmittedExecution` context, assert matching `action_digest`, `organization_id`, and `target_fingerprint`. It does NOT call `admit_execution()`.
- **Zero Double Admission:** Because executors no longer invoke `admit_execution()`, double admission and duplicate nonce consumption bugs are eliminated entirely.
