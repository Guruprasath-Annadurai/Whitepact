# WhitePact Phase 7A: Canonical Execution Authority Codebase Audit

**Document Status:** CANONICAL SPECIFICATION PASS 2 (POST-CODEX REVIEW REMEDIATION)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary & Codebase Reality

This audit resolves Codex review finding **P0-1** by systematically verifying the physical reality of `ExecutionAuthorization` and all related execution-authority repositories in the canonical WhitePact codebase (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

### Key Findings
1. **`ExecutionAuthorization` is an in-memory dataclass today.** It is instantiated exclusively by `authorize_execution()` in `src/responsibleai/governance/execution.py` following an `ALLOW` or `ALLOW_WITH_REDACTION` policy decision.
2. **No table stores `ExecutionAuthorization` at issuance.** Unlike `REQUIRE_APPROVAL` decisions (which persist an `ApprovalRequest` row in `governance_approvals`), direct `ALLOW` decisions have no persistent database representation prior to execution.
3. **Only the single-use `nonce` is durably stored at admission.** When `admit_execution()` is invoked immediately before tool execution, `ExecutionNonceRepository.consume()` inserts a row into `governance_execution_nonces` and verifies against `governance_revocation_epochs`.
4. **Deterministic reconstruction from existing tables is IMPOSSIBLE for queued async executions.** When execution is decoupled into asynchronous worker queues (Phase 7A), the worker process cannot reconstruct the ephemeral in-memory `ExecutionAuthorization` object from existing tables without re-evaluating policy (which violates policy immutability and temporal auditability).
5. **Architectural Mandate:** A new PostgreSQL-backed durable authorization record and repository (`governance_execution_authorizations` / `ExecutionAuthorizationRepository`) is **REQUIRED**. Redis queues must hold only unprivileged references (`authorization_id`, `execution_id`, `organization_id`), never raw authority.

---

## 2. Classification of `ExecutionAuthorization` Properties

Every attribute of `ExecutionAuthorization` defined in `src/responsibleai/governance/execution.py` (lines 129–176) is classified below according to its persistence state in the canonical runtime:

| Field Name | Type | Current Codebase Reality | Classification | Durability / Source of Truth |
| :--- | :--- | :--- | :--- | :--- |
| `authorization_id` | `str` (UUIDv4) | Generated via `field(default_factory=lambda: str(uuid.uuid4()))` in memory. Recorded in `governance_execution_nonces` only *after* admission. | **IN MEMORY TODAY** | Must be made primary key in `governance_execution_authorizations`. |
| `organization_id` | `str | None` | Extracted from `action.agent.organization_id`. Verified in `admit_execution()` against `organizations.id`. | **IN MEMORY TODAY** (Tenant identity is durable) | Must be stored in `governance_execution_authorizations` with `ForeignKey("organizations.id", ondelete="RESTRICT")`. |
| `principal_id` | `str | None` | Extracted from `action.agent.identity.identity_id`. Used in `matches_action()`. | **IN MEMORY TODAY** (Principal identity exists in IAM) | Must be stored in `governance_execution_authorizations` to bind subject authority. |
| `action_digest` | `str` | Computed via `compute_action_digest(action)` (SHA-256 hex of canonical JSON). | **IN MEMORY TODAY** | Must be stored in `governance_execution_authorizations` (VARCHAR(64)) to guarantee tamper-proof action immutability. |
| `target_fingerprint` | `str | None` | Execution Permit v2 hash of resolved target (e.g. `UpstreamServer`). Checked via `check_target_fingerprint()`. | **IN MEMORY TODAY** | Must be stored in `governance_execution_authorizations` (VARCHAR(64), nullable) to detect target drift between decision and dispatch. |
| `decision` | `GovernanceDecision` | Must be `ALLOW` or `ALLOW_WITH_REDACTION`. Verified in `_validate_authorization()`. | **IN MEMORY TODAY** | Must be stored in `governance_execution_authorizations` (VARCHAR(32)) for judgment provenance. |
| `revocation_epoch` | `int | None` | Stamped from `governance_revocation_epochs.epoch` at decision time. Verified against DB under lock at admission. | **DERIVED FROM DURABLE STATE** (Epoch table is durable; permit binding is in memory) | Must be stored in `governance_execution_authorizations` (INTEGER) to lock expected epoch. |
| `nonce` | `str` (UUIDv4 hex) | Generated via `field(default_factory=lambda: uuid.uuid4().hex)`. Inserted into `governance_execution_nonces` at admission. | **IN MEMORY TODAY** (Becomes durable *only upon* consumption) | Must be stored in `governance_execution_authorizations` (VARCHAR(64), UNIQUE) at issuance. |
| `issued_at` | `datetime` | Stamped at construction (`datetime.now(UTC)`). | **IN MEMORY TODAY** | Must be stored in `governance_execution_authorizations` (VARCHAR(32), ISO-8601 UTC). |
| `expires_at` | `datetime` | Stamped at construction (`issued_at + timedelta(seconds=ttl)`). Evaluated via `is_expired`. | **IN MEMORY TODAY** | Must be stored in `governance_execution_authorizations` (VARCHAR(32), ISO-8601 UTC). |
| `consumed` | `bool` | In-memory flag set to `True` at the end of `admit_execution()`. | **IN MEMORY TODAY** (Durable nonces table tracks consumed nonces) | Must be reflected as durable state machine in `governance_execution_authorizations.status` (`ISSUED`, `CONSUMED`, `REVOKED`, `EXPIRED`). |

---

## 3. Durable Reality of Existing Governance Storage

The canonical repository provides the following existing durable tables and repositories:

### 3.1 `governance_execution_nonces` (`src/responsibleai/db/engine.py:1153-1166`)
- **Table Definition:**
  ```python
  Column("nonce", String(64), primary_key=True),
  Column("authorization_id", String(36), nullable=False),
  Column("organization_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), nullable=False),
  Column("consumed_at", String(32), nullable=False),
  Index("idx_execution_nonces_consumed_at", "consumed_at"),
  ```
- **Operational Reality:**
  - Written **only** when `admit_execution()` completes successfully.
  - Acts as an immutable append-only ledger of consumed permits.
  - Primary key on `nonce` guarantees that no nonce can ever be admitted twice across any replica.
  - **Limitation:** Does not store the action digest, principal, target fingerprint, decision, or validity window. It proves *that* a nonce was spent, but cannot reconstruct *what* was authorized.

### 3.2 `governance_revocation_epochs` (`src/responsibleai/db/engine.py:1139-1151`)
- **Table Definition:**
  ```python
  Column("organization_id", String(36), ForeignKey("organizations.id", ondelete="RESTRICT"), primary_key=True),
  Column("scope", String(64), primary_key=True),
  Column("epoch", Integer, nullable=False, server_default="0"),
  Column("updated_at", String(32), nullable=False),
  ```
- **Operational Reality:**
  - Manages tenant revocation epochs bumped by any governance configuration change (policies, delegations, trust scores, authority ceilings).
  - Locked during admission via `SELECT epoch FROM governance_revocation_epochs WHERE organization_id = :org_id FOR UPDATE` (`lock_epoch()`).
  - Guarantees immediate revocation linearization: any permit issued prior to an epoch bump is invalidated when checked against the locked epoch.

### 3.3 `admit_execution()` (`src/responsibleai/governance/execution.py:278-303`)
- **Operational Reality:**
  ```python
  async def admit_execution(
      authorization: ExecutionAuthorization,
      action: ActionRequest,
      nonce_repo: ExecutionNonceRepository | None,
  ) -> None:
      _validate_authorization(authorization, action)
      if nonce_repo is not None:
          if authorization.revocation_epoch is None or not authorization.organization_id:
              raise ExecutionNotAuthorizedError("Durable execution requires a tenant and epoch")
          await nonce_repo.consume(
              authorization.nonce,
              authorization_id=authorization.authorization_id,
              organization_id=authorization.organization_id,
              expected_epoch=authorization.revocation_epoch,
          )
          _validate_authorization(authorization, action)
      elif authorization.revocation_epoch is not None:
          raise ExecutionNotAuthorizedError("Durable admission repository is unavailable")
      authorization.consumed = True
  ```
  - **Invariants Enforced:**
    1. Revalidates authorization matches action before DB call.
    2. Atomically locks epoch and inserts nonce.
    3. Revalidates authorization matches action after DB call (defending against clock drift or concurrent modification during await).
    4. Marks in-memory `authorization.consumed = True`.
    5. Refuses fallback to local memory if epoch-bound.

### 3.4 `ApprovalRepository` (`src/responsibleai/db/approval_repository.py`)
- **Operational Reality:**
  - Manages `governance_approvals` table.
  - Used **strictly** for asynchronous human approval workflows (`REQUIRE_APPROVAL`).
  - Has its own durable `action_digest`, `purpose`, `arguments`, `status` (`PENDING`, `APPROVED`, `DENIED`, `CONSUMED`), and atomic `consume()` method.
  - **Distinction:** `ApprovalRequest` is human governance; `ExecutionAuthorization` is automated runtime execution permission. They are separate concepts.

### 3.5 `iam_break_glass_sessions` (`src/responsibleai/iam/break_glass.py`)
- **Operational Reality:**
  - Durable emergency sessions with `incident_id`, `capabilities`, `status` (`ACTIVE`, `TERMINATED`), and bounded `expires_at` (max 60 minutes).
  - Can be queried by `org_id` and `session_id` to verify active validity during pre-flight revalidation.

---

## 4. Why Existing Reconstruction Is Impossible

Option A (reconstructing `ExecutionAuthorization` from existing tables without a new table) was rigorously evaluated:
1. **Policy Decisions Are Not Logged as Permits:** When the Policy Gateway evaluates an action and returns `ALLOW`, it creates an in-memory `ExecutionAuthorization`. No row is inserted into `governance_evidence` that captures the short-lived `nonce` or unconsumed authority state before execution.
2. **Re-evaluation Is Forbidden:** A worker cannot simply "re-evaluate" the policy at dispatch time. Policy rules, autonomy budgets, and tool trust scores may have changed in ways that require human approval or deny the action, or the original evaluation may have included dynamic redactions (`ALLOW_WITH_REDACTION`) that must be preserved exactly as authorized.
3. **Redis Is Not a Trust Boundary:** Storing the `ExecutionAuthorization` dataclass as a JSON or pickle blob in Redis would violate WhitePact's security doctrine: Redis is an ephemeral cache/queue, not an authoritative governance ledger. Redis compromise or key eviction must never forge or corrupt execution authority.

**Conclusion:** Option B is mandatory. Phase 7A must specify a PostgreSQL table `governance_execution_authorizations` to bridge policy issuance to worker dispatch.

---

## 5. Single Source of Truth for Nonce Replay Prevention

To prevent dual-source inconsistency or split-brain replay protection:
- **`governance_execution_nonces` remains the singular canonical source of truth for single-use admission.**
- The new `governance_execution_authorizations` table acts as the durable authority record (what was permitted, for whom, and under what conditions).
- When `admit_execution()` executes, the transition of `governance_execution_authorizations.status` to `CONSUMED` and the insertion into `governance_execution_nonces` execute in the **exact same atomic database transaction**.
- There is zero opportunity for an authorization to be marked consumed without its nonce being locked in `governance_execution_nonces`, and zero opportunity for a nonce to be burned without the authorization status reflecting `CONSUMED`.
