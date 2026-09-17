# WhitePact Phase 7A Design Reconciliation

**Document Status:** CANONICAL SPECIFICATION PASS 2 (ATOMIC AUTHORITY INTEGRATION CORRECTION)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary

This document provides a systematic reconciliation between the Phase 7A Master Design (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`) and the approved canonical enterprise authentication baseline (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

This Pass 2 correction explicitly binds the durable authorization lifecycle into the canonical codebase:
1. **Durable Issuance Integration:** Assigned to `src/responsibleai/mcp/governance_integration.py`. No `QueueTicket` can be generated until its `ExecutionAuthorization` is committed in PostgreSQL (`governance_execution_authorizations`, migration `0049`).
2. **Atomic Admission Transaction:** Assigned to `src/responsibleai/db/execution_nonce_repository.py`. `ExecutionNonceRepository.consume()` executes a single PostgreSQL transaction combining the tenant epoch lock, nonce insertion, and conditional authorization status update (`ISSUED -> CONSUMED` with `rowcount == 1`).
3. **Canonical Admission Gate:** `src/responsibleai/governance/execution.py:admit_execution()` remains the singular non-bypassable admission API.
4. **Single-Source Revocation & Derived Expiration:** Per-authorization `REVOKED` state is eliminated in favor of canonical epoch revocation (`governance_revocation_epochs`), avoiding dual-source ambiguity. Expiration is purely derived (`now >= expires_at`).

---

## 2. Invariant Reconciliation Matrix

| Subsystem / Dimension | Status | Detailed Findings & Adaptations |
| :--- | :--- | :--- |
| **ExecutionAuthorization Issuance** | SECURITY-RELEVANT ADAPTATION | Persisted durably in PostgreSQL (`governance_execution_authorizations`, migration `0049`) at decision time by `mcp/governance_integration.py`. If DB write fails, request fails closed; zero queue tickets created. |
| **Canonical Admission Transaction** | SECURITY-RELEVANT ADAPTATION | `ExecutionNonceRepository.consume()` in `db/execution_nonce_repository.py` owns the single transaction combining epoch lock, nonce insert, and conditional authorization update (`rowcount == 1`). Zero nested transactions. |
| **admit_execution() API** | PRESERVED AS GATEKEEPER | `src/responsibleai/governance/execution.py:admit_execution(authorization, action, nonce_repo)` remains the non-bypassable admission API called before any container launch or tool dispatch. |
| **Worker Lease Exclusivity** | SECURITY-RELEVANT ADAPTATION | Enforced at the PostgreSQL database level using a partial unique index: `CREATE UNIQUE INDEX idx_runtime_worker_leases_active_execution ON runtime_worker_leases (execution_id) WHERE status = 'ACTIVE'` (migration `0050`). |
| **Revocation Architecture** | RECONCILED & HARDENED | Tenant-wide epoch revocation via `governance_revocation_epochs` and `lock_epoch()` is the singular authoritative revocation mechanism. Individual authorization `REVOKED` state is eliminated to prevent dual-source ambiguity. |
| **Expiration Architecture** | RECONCILED & DERIVED | Expiration is derived dynamically from `now >= expires_at`. No background mutation daemon updates rows to `EXPIRED`. Atomic query guard `WHERE expires_at > :now` prevents expired permit consumption. |
| **Parallelization & Dispatcher** | RESOLVED & ORDERED | Tasks 8A (Issuance) and 8B (Atomic Admission) precede Task 10 (Dispatcher Gate). Lane C2 (Recovery & Side-Effects) strictly depends on Task 10. |
| **Tenant Lifecycle** | PRESERVED & ENFORCED | Tenant liveness relies strictly on canonical tenant records (`OrgRepository.get_org(org_id)`). `organizations.subscription_status` is explicitly ignored. |
| **PostgreSQL Migration Sequence** | RESOLVED & ADAPTED | Canonical head `0048` -> `0049_runtime_execution_authorizations.py` -> `0050_runtime_worker_leases.py`. |
| **Docker Isolation** | UNCHANGED | Ephemeral container execution with `--network=none`, CPU 0.5, RAM 256MB, PID 32, and WP-ISO-01 workspace limits (10MB, 100 files). |

---

## 3. Critical Architectural Clarifications

### 3.1 Durable Issuance Gate (`mcp/governance_integration.py`)
```
ActionRequest -> Policy Evaluation -> authorize_execution()
                     │
                     ▼
       [ExecutionAuthRepository.create()]
                     │
       ┌─────────────┴─────────────┐
       │ DB Failure                │ DB Success
       ▼                           ▼
[Fail Closed: 500/503]    [AdmissionController.reserve()]
[Zero Queue Tickets]               │
                                   ▼
                         [Enqueue QueueTicket]
```

### 3.2 Atomic Admission Transaction (`db/execution_nonce_repository.py`)
```sql
BEGIN TRANSACTION;
  -- 1. Lock tenant revocation counter
  SELECT epoch FROM governance_revocation_epochs
  WHERE organization_id = :org_id FOR UPDATE;

  -- Verify expected_epoch == current_epoch (Rollback if mismatch)

  -- 2. Insert single-use nonce
  INSERT INTO governance_execution_nonces (nonce, authorization_id, organization_id, consumed_at)
  VALUES (:nonce, :auth_id, :org_id, :now);

  -- 3. Conditional update of durable authorization
  UPDATE governance_execution_authorizations
  SET status = CONSUMED, consumed_at = :now, updated_at = :now
  WHERE authorization_id = :auth_id
    AND organization_id = :org_id
    AND status = ISSUED
    AND expires_at > :now;

  -- Verify rowcount == 1 (Rollback if rowcount == 0)
COMMIT;
```

### 3.3 Worker Lease Database Exclusivity (`0050_runtime_worker_leases.py`)
```sql
CREATE UNIQUE INDEX idx_runtime_worker_leases_active_execution
ON runtime_worker_leases (execution_id)
WHERE status = ACTIVE;
```
