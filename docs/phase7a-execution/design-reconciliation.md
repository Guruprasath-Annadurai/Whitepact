# WhitePact Phase 7A Design Reconciliation

**Document Status:** CANONICAL SPECIFICATION PASS 3 (FINAL CALL-PATH & SINGLE-ADMISSION CLOSURE)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (`ENTERPRISE_AUTH_CANONICAL_SHA` — APPROVED)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary

This document provides a systematic reconciliation between the Phase 7A Master Design (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`) and the approved canonical enterprise authentication baseline (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

This Pass 3 correction definitively resolves call-path closure and admission ownership:
1. **Centralized Durable Issuance Integration:** Assigned to `DurableExecutionAuthorizationIssuer.issue()`. All 3 production `authorize_execution()` call sites (`execute_governed_action`, `resolve_approval_and_execute` in `governance_integration.py`, and `dispatch_upstream_action` in `upstream_dispatch.py`) must persist `ExecutionAuthorization` in PostgreSQL (`governance_execution_authorizations`, migration `0049`) before any `QueueTicket` is generated. Upstream dispatch issuance gap is completely closed.
2. **Single Canonical Admission Gate (Option A):** Assigned exclusively to the worker process immediately before execution. The worker calls `admit_execution()`, which returns an unforgeable `AdmittedExecution` context.
3. **Downstream Executor Adaptation:** `InternalToolExecutor.execute()` and `UpstreamServer.execute()` are adapted to accept `AdmittedExecution` context and do NOT call `admit_execution()` again, eliminating double-admission and duplicate nonce consumption.
4. **Atomic Admission Transaction:** Assigned to `src/responsibleai/db/execution_nonce_repository.py`. `ExecutionNonceRepository.consume()` executes a single PostgreSQL transaction combining the tenant epoch lock, nonce insertion, and conditional authorization status update (`ISSUED -> CONSUMED` with `rowcount == 1`).
5. **Preservation of Safe Network & Isolation:** Upstream target drift validation and `SafeNetworkBackend` remain mandatory for remote MCP calls. Ephemeral container execution (`--network=none`, limits) remains mandatory for local tool calls.

---

## 2. Invariant Reconciliation Matrix

| Subsystem / Dimension | Status | Detailed Findings & Adaptations |
| :--- | :--- | :--- |
| **ExecutionAuthorization Issuance** | SECURITY-RELEVANT ADAPTATION | Centralized in `DurableExecutionAuthorizationIssuer.issue()`. Persisted durably in PostgreSQL (`governance_execution_authorizations`, migration `0049`) at decision time for all 3 call sites (`governance_integration.py` and `upstream_dispatch.py`). If DB write fails, request fails closed; zero queue tickets created. |
| **Admission Ownership** | SECURITY-RELEVANT ADAPTATION | Option A chosen: Worker owns canonical `admit_execution()`. Emits typed `AdmittedExecution` context. `InternalToolExecutor` and `UpstreamServer` consume context without re-admission, eliminating double-admission bugs. |
| **Canonical Admission Transaction** | SECURITY-RELEVANT ADAPTATION | `ExecutionNonceRepository.consume()` in `db/execution_nonce_repository.py` owns the single transaction combining epoch lock, nonce insert, and conditional authorization update (`rowcount == 1`). Zero nested transactions. |
| **admit_execution() API** | PRESERVED AS GATEKEEPER | `src/responsibleai/governance/execution.py:admit_execution(authorization, action, nonce_repo)` remains the non-bypassable admission API called before any container launch or tool dispatch. Returns `AdmittedExecution`. |
| **Worker Lease Exclusivity** | SECURITY-RELEVANT ADAPTATION | Enforced at the PostgreSQL database level using a partial unique index: `CREATE UNIQUE INDEX idx_runtime_worker_leases_active_execution ON runtime_worker_leases (execution_id) WHERE status = 'ACTIVE'` (migration `0050`). |
| **Revocation Architecture** | RECONCILED & HARDENED | Tenant-wide epoch revocation via `governance_revocation_epochs` and `lock_epoch()` is the singular authoritative revocation mechanism. Individual authorization `REVOKED` state is eliminated to prevent dual-source ambiguity. |
| **Expiration Architecture** | RECONCILED & DERIVED | Expiration is derived dynamically from `now >= expires_at`. No background mutation daemon updates rows to `EXPIRED`. Atomic query guard `WHERE expires_at > :now` prevents expired permit consumption. |
| **Parallelization & Dispatcher** | RESOLVED & ORDERED | Tasks 8A (Issuance) and 8B (Atomic Admission) precede Task 10 (Dispatcher Gate). Lane C2 (Recovery & Side-Effects) strictly depends on Task 10. Task 10 activation requires all 3 issuance paths closed and single admission proven. |
| **Tenant Lifecycle** | PRESERVED & ENFORCED | Tenant liveness relies strictly on canonical tenant records (`OrgRepository.get_org(org_id)`). `organizations.subscription_status` is explicitly ignored. |
| **PostgreSQL Migration Sequence** | RESOLVED & ADAPTED | Canonical head `0048` -> `0049_runtime_execution_authorizations.py` -> `0050_runtime_worker_leases.py`. |
| **Docker Isolation** | UNCHANGED | Ephemeral container execution with `--network=none`, CPU 0.5, RAM 256MB, PID 32, and WP-ISO-01 workspace limits (10MB, 100 files). |

---

## 3. Critical Architectural Clarifications

### 3.1 Centralized Durable Issuance Gate
```
ActionRequest (Local or Upstream MCP) -> Policy Evaluation -> authorize_execution()
                                             │
                                             ▼
                     [DurableExecutionAuthorizationIssuer.issue()]
                                             │
                               [PostgreSQL INSERT 0049]
                                             │
                        ┌────────────────────┴────────────────────┐
                        │ DB Failure                              │ DB Success
                        ▼                                         ▼
             [Fail Closed: 500/503]                  [AdmissionController.reserve()]
             [Zero Queue Tickets]                                 │
                                                                  ▼
                                                        [Enqueue QueueTicket]
```

### 3.2 Single Admission Ownership & Downstream Execution
```
QueueTicket Dequeued -> Acquire Lease -> Pre-Flight Revalidation
                                               │
                                               ▼
                              [Worker: admit_execution()]
                                               │
                                 [PostgreSQL Transaction]
                               (Lock Epoch + Nonce + Update)
                                               │
                                               ▼
                                  [AdmittedExecution Context]
                                               │
                        ┌──────────────────────┴──────────────────────┐
                        ▼                                             ▼
           [InternalToolExecutor.execute()]              [UpstreamServer.execute()]
           (Receives AdmittedExecution)                  (Receives AdmittedExecution)
           (Zero Re-Admission)                           (Zero Re-Admission)
                        │                                             │
                        ▼                                             ▼
           [Container Isolation Backend]                     [SafeNetworkBackend]
           (--network=none, limits)                          (SSRF & DNS Pinning)
```
