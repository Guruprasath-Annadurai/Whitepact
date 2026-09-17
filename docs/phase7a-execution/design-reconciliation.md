# WhitePact Phase 7A Design Reconciliation

**Document Status:** CANONICAL SPECIFICATION PASS 2 (POST-CODEX REVIEW REMEDIATION)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary

This document provides a systematic, item-by-item reconciliation between the Phase 7A Master Design (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`) and the approved canonical enterprise authentication baseline (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

Codex's independent review of candidate plan `89079f8d2da80e59533c52e621c24b4f2ad2ec32` identified five critical specification gaps:
- **P0-1:** Durable `ExecutionAuthorization` storage missing (in-memory dataclass today, requiring durable storage for async worker execution).
- **P0-2:** Worker dispatcher could bypass canonical durable `admit_execution()` / nonce / epoch boundary.
- **P0-3:** Worker lease active exclusivity was not database-enforced.
- **P1-1:** Revalidation was incomplete across canonical authority properties.
- **P1-2:** Parallelization map contradicted the task dependency graph regarding worker dispatch and crash recovery.

This Pass 2 specification resolves all five findings while maintaining strict truth synchronization: `13e8de034f8b31bd7cae4f47398f71b24c923c3c` is the approved canonical foundation, migration head is `0048`, and commercial entitlement remains strictly decoupled from governance authority.

---

## 2. Invariant Reconciliation Matrix

| Subsystem / Dimension | Status | Detailed Findings & Adaptations |
| :--- | :--- | :--- |
| **ExecutionAuthorization** | SECURITY-RELEVANT ADAPTATION (P0-1) | `ExecutionAuthorization` is an in-memory dataclass today (`src/responsibleai/governance/execution.py`). For asynchronous worker execution, it is persisted durably in PostgreSQL table `governance_execution_authorizations` (migration `0049`) at decision time with status `ISSUED`. Workers load authority from DB, preserving all 11 security fields losslessly. |
| **Canonical Admission** | SECURITY-RELEVANT ADAPTATION (P0-2) | The dispatcher and worker loop MUST NOT bypass `admit_execution()`. Immediately prior to tool/container execution under an active lease, `admit_execution()` executes an atomic PostgreSQL transaction: locking `governance_revocation_epochs`, inserting single-use nonce in `governance_execution_nonces`, and updating `governance_execution_authorizations.status` to `CONSUMED`. |
| **Worker Lease Exclusivity** | SECURITY-RELEVANT ADAPTATION (P0-3) | Mutual exclusion is strictly enforced at the PostgreSQL database level using a partial unique index: `CREATE UNIQUE INDEX idx_runtime_worker_leases_active_execution ON runtime_worker_leases (execution_id) WHERE status = 'ACTIVE'` (migration `0050`). Application-level select-then-insert is eliminated. |
| **Two-Stage Revalidation** | SECURITY-RELEVANT ADAPTATION (P1-1) | Revalidation is explicitly partitioned into: (1) Early Queue Invalidation (fast abort on expired/revoked EA or inactive tenant before acquiring lease or burning nonce); and (2) Final Canonical Admission (`admit_execution` with atomic nonce/epoch lock). All 11 security dimensions (epoch, principal, session, tenant, action, target, arguments, purpose, BreakGlass, delegation, consent) are fully covered. |
| **Parallelization & Dispatcher** | SECURITY-RELEVANT ADAPTATION (P1-2) | Lane C is split into Lane C1 (Task 9: Worker lease schema `0050` and repository) and Lane C2 (Tasks 11 & 12: Crash recovery, reaper, side-effect safety). Task 10 (Dispatcher & Worker Execution Loop) serves as the non-bypassable Integration Gate between Lane A + Lane C1 and Lane C2. |
| **Tenant Lifecycle** | PRESERVED & ENFORCED | Tenant lifecycle relies strictly on canonical tenant records (`OrgRepository.get_org(org_id)` returning non-None, active account status, non-tombstoned). `organizations.subscription_status` is a commercial billing field and MUST NOT be used as a proxy for tenant existence or governance authority. |
| **Principal / Session Lifecycle** | PRESERVED & ENFORCED | Session-binding token checks in `iam_step_up_nonces.session_id` (migration `0047`) and `iam_sessions` remain intact. Queued execution revalidation verifies principal and session validity where required by the canonical contract. |
| **BreakGlass** | PRESERVED & ENFORCED | BreakGlass sessions in `iam_break_glass_sessions` remain strictly bounded by TTL (max 60m). Expired or terminated BreakGlass sessions while queued reject execution dispatch. Commercial status has zero effect on BreakGlass validity. |
| **Policy Evaluation** | PRESERVED & IMMUTABLE | Deterministic lattice evaluation and explicit DENY precedence remain immutable. Admission capacity never overrides policy decisions. An already-issued `ExecutionAuthorization` is not re-evaluated against policy at worker dispatch. |
| **PostgreSQL Migration Sequence** | RESOLVED & ADAPTED | Canonical head is `0048` (`0048_enforce_paddle_binding_atomicity.py`). Phase 7A introduces two clean, independently reversible migrations: `0049_runtime_execution_authorizations.py` (authorizations table) and `0050_runtime_worker_leases.py` (worker leases table with partial unique index). |
| **Docker Isolation** | UNCHANGED | `ContainerIsolationBackend` in `src/responsibleai/isolation/container_backend.py` enforces unconditional air-gap (`--network=none`), compute limits (CPU 0.5, RAM 256MB, PID 32), and WP-ISO-01 workspace limits (10MB, 100 files). |
| **Evidence Ledger** | UNCHANGED | SHA-256 hash chaining and tamper-evident append logging in `src/responsibleai/audit/evidence.py` remain canonical. Admission and execution events append to this ledger. |

---

## 3. Critical Architectural Clarifications

### 3.1 Strict Decoupling of Commercial Status from Governance and Lifecycle
The following architectural separations are absolute:
```
commercial entitlement           ≠ governance authority
commercial plan                  ≠ tenant lifecycle
commercial subscription_status   ≠ tenant deletion / tombstone
commercial status                ≠ ExecutionAuthorization validity
commercial status                ≠ policy result
commercial status                ≠ approval state
commercial status                ≠ BreakGlass validity
```
1. **Tenant Liveness:** Tenant existence and liveness is verified by querying `OrgRepository.get_org(org_id)`. If the record is absent, soft-deleted, or marked tombstoned, the tenant is invalid. A tenant with commercial status `"inactive"` or `"canceled"` (e.g., standard FREE tier organization) remains a fully valid tenant unless deleted in the account repository.
2. **Plan-Neutral Fairness:** Default Phase 7A admission queue fairness is round-robin per-tenant, completely plan-neutral. No tenant receives priority dispatch or starvation immunity based on commercial plan.

### 3.2 Durable Authority Storage Architecture (P0-1)
- **Table:** `governance_execution_authorizations` (created in migration `0049`).
- **Fields:** `authorization_id` (PK, UUIDv4), `organization_id` (FK to `organizations.id`), `principal_id`, `action_digest`, `target_fingerprint`, `decision`, `revocation_epoch`, `nonce` (UNIQUE), `issued_at`, `expires_at`, `status` (`ISSUED`, `CONSUMED`, `REVOKED`, `EXPIRED`), `consumed_at`, `created_at`, `updated_at`.
- **Queue Payload Security:** Queue tickets carry only `authorization_id`, `execution_id`, `organization_id`, `principal_id`, and `action_digest`. Zero reusable credentials exist in queue payloads or Redis.

### 3.3 Worker Lease Exclusivity Contract (P0-3)
- **Table:** `runtime_worker_leases` (created in migration `0050`).
- **Fields:** `lease_id` (PK, UUIDv4), `execution_id`, `authorization_id` (FK to `governance_execution_authorizations`), `organization_id` (FK to `organizations.id`), `worker_id`, `attempt`, `status` (`ACTIVE`, `EXPIRED`, `COMPLETED`, `FAILED`, `CANCELLED`), `issued_at`, `expires_at`, `heartbeat_at`, `completed_at`.
- **Constraint:**
  ```sql
  CREATE UNIQUE INDEX idx_runtime_worker_leases_active_execution
  ON runtime_worker_leases (execution_id)
  WHERE status = 'ACTIVE';
  ```
- **Concurrency Invariant:** At most one worker can hold an `ACTIVE` lease for a given `execution_id`. Concurrent acquisition attempts by racing workers fail immediately at the database constraint level.

### 3.4 Canonical Admission and Nonce Replay Prevention (P0-2)
- Worker dispatcher must invoke canonical `admit_execution()` in `src/responsibleai/governance/execution.py`.
- Admission executes in a single PostgreSQL transaction:
  1. `lock_epoch(conn, organization_id)` (`SELECT ... FOR UPDATE`).
  2. Verify `current_epoch == expected_epoch`.
  3. `INSERT INTO governance_execution_nonces (nonce, authorization_id, organization_id, consumed_at)`.
  4. `UPDATE governance_execution_authorizations SET status = 'CONSUMED', consumed_at = now() WHERE authorization_id = :id AND status = 'ISSUED'`.
- Nonce uniqueness in `governance_execution_nonces` remains the singular linearizing source of replay prevention.

### 3.5 Side-Effect Safety and Uncertainty
To prevent blind replays of external network side effects upon worker crash:
- The runtime explicitly separates:
  - `execution_id`: The overall execution workflow instance.
  - `attempt_id`: The specific attempt executed by a worker under a lease.
  - `effect_id`: The unique identifier for external side-effect operations.
  - `idempotency_key`: The client/agent idempotency token.
- If a worker crashes after initiating an external effect but before local acknowledgement, the reaper records state `UNCERTAIN`. Automatic replay is strictly forbidden. Worker lease expiry does NOT grant permission to repeat an uncertain external effect.

### 3.6 Migration Ancestry
- The canonical migration head is `0048` (`0048_enforce_paddle_binding_atomicity.py`).
- Phase 7A migrations sequence strictly from `0048`:
  - `0049_runtime_execution_authorizations.py` (down_revision: `0048`)
  - `0050_runtime_worker_leases.py` (down_revision: `0049`)
