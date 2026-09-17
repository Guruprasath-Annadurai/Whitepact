# WhitePact Phase 7A Design Reconciliation

**Document Status:** CANDIDATE IMPLEMENTATION PLAN (PENDING INDEPENDENT REVIEW)
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01` (Worktree: `/Users/ag/whitepact-phase7a-runtime-preparation`)
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c` (Auth Candidate Under Codex Review)
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Assumed Alembic Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`, conditional upon Codex approval of `13e8de0`)

---

## 1. Executive Summary

This document provides a systematic, item-by-item reconciliation between the Phase 7A Master Design (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`) and the current authentication candidate under Codex review (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

Between the initial candidate `4ac9550ee2c16078e295620a6c77c9be51f5b6b4` and `13e8de034f8b31bd7cae4f47398f71b24c923c3c`, two security remediations were applied to Paddle webhook ingestion and concurrency:
1. `a08de3794b776b8fbebb8cadc91c7a018e904ecc`: Enforced database-level atomic unique constraints on Paddle subscription bindings via migration `0048` and row-level locking.
2. `13e8de034f8b31bd7cae4f47398f71b24c923c3c`: Closed equal-timestamp commercial entitlement widening (`WP-AUTH-PDL-01-R1`), established explicit plan ranking (`PLAN_RANK`), and restored canonical migration lifecycle test assertions.

This reconciliation confirms the exact boundary conditions for Phase 7A. In this correction pass, all commercial/governance couplings have been excised: **commercial entitlement does not equal governance authority**, and tenant lifecycle is decoupled entirely from billing subscription status.

---

## 2. Invariant Reconciliation Matrix

| Subsystem / Dimension | Status | Detailed Findings & Adaptations |
| :--- | :--- | :--- |
| **ExecutionAuthorization** | UNCHANGED | `ExecutionAuthorization` remains immutable in `src/responsibleai/governance/execution.py`. Neither Paddle webhooks, admission tokens, queue tickets, nor worker leases can issue or modify an `ExecutionAuthorization`. |
| **Tenant Lifecycle** | SECURITY-RELEVANT ADAPTATION | Tenant lifecycle relies strictly on canonical tenant records (`OrgRepository.get_org(org_id)` returning non-None, verified active account status, non-tombstoned). `organizations.subscription_status` is a commercial billing field and MUST NOT be used as a proxy for tenant existence or governance authority. |
| **Principal / Session Lifecycle** | UNCHANGED | Session-binding token checks in `iam_step_up_nonces.session_id` (migration `0047`) remain intact. Queued execution revalidation verifies principal and session validity where required by the canonical contract. |
| **BreakGlass** | UNCHANGED | BreakGlass sessions in `iam_break_glass_sessions` remain strictly bounded by TTL. Expired BreakGlass sessions while queued reject execution dispatch. Commercial status has zero effect on BreakGlass validity. |
| **Policy Evaluation** | UNCHANGED | Deterministic lattice evaluation and explicit DENY precedence remain immutable. Admission capacity never overrides policy decisions. An already-issued `ExecutionAuthorization` is not re-evaluated against policy at worker dispatch unless explicitly required by canonical design. |
| **Organization Model** | MINOR PLAN ADAPTATION | Organization table schema includes unique indexes for `paddle_subscription_id` and `paddle_customer_id` via migration `0048`. Concurrency controllers read org state under read committed isolation. |
| **Commercial Plan Model** | SECURITY-RELEVANT ADAPTATION | `src/responsibleai/rbac/models.py` defines commercial `PLAN_RANK` and statuses. **Phase 7A fairness is strictly plan-neutral.** Commercial tier does not alter governance authority, admission priority, or queue scheduling in Phase 7A. Commercial features may affect service availability in subsequent commercial releases, but never governance semantics. |
| **PostgreSQL Migration Head** | MINOR PLAN ADAPTATION | Migration head is assumed `0048` (`0048_enforce_paddle_binding_atomicity.py`). Phase 7A migration `0049` is strictly conditional upon Codex approving `13e8de0`. If the approved auth SHA differs, migration ancestry must be reconciled before implementation. |
| **Shutdown / Lifespan** | UNCHANGED | FastAPI lifespan handlers in `src/responsibleai/dashboard/app.py` remain the designated integration point for the Phase 7A two-phase graceful shutdown supervisor. |
| **Execution Dispatcher** | SECURITY-RELEVANT ADAPTATION | Worker dispatch must remain disabled behind an integration boundary until Redis distributed coordination and fail-closed behaviors are installed and verified. Process-local capacity enforcement cannot be active across multi-worker deployments. |
| **Docker Isolation** | UNCHANGED | `ContainerIsolationBackend` in `src/responsibleai/isolation/container_backend.py` enforces `--network=none`. WP-ISO-01 starting bounds (10MB workspace, 100 files) will insert into existing parameter builder methods. |
| **Egress** | UNCHANGED | Proxy-mediated egress enforcement in `src/responsibleai/net/egress.py` remains active for non-isolated workloads. Container isolation remains strictly air-gapped (`--network=none`). |
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

### 3.2 Queue Authorization Contract
The queue structures (`QueueTicket`, `QueuedPayload`) must never hold reusable credentials:
- **Allowed Fields:** `execution_id`, `authorization_id`, `org_id`, `principal_id`, `action_ref`, `idempotency_key`, `enqueued_at`.
- **Prohibited Fields:** Cryptographic signing keys, step-up proof secrets, full authority delegations.
- **Contract:** `QueueTicket != authority`. Holding an `authorization_id` reference is merely a database pointer and does not constitute an authorization grant by itself. The worker must revalidate the actual `ExecutionAuthorization` from durable PostgreSQL storage at the execution boundary.

### 3.3 Worker Lease Identity
- **Rejection of `UNIQUE(authorization_id)`:** The previous draft proposed `UNIQUE(authorization_id)` on `runtime_worker_leases`. This is architecturally incorrect if an authorization is mapped to an execution that undergoes retries or distinct execution attempts.
- **Correct Lease Identity:** The lease identity is based on `execution_id` and `attempt`.
  The required binding contains:
  ```
  lease_id, execution_id, authorization_id, org_id, worker_id, attempt, issued_at, expires_at, heartbeat_at
  ```
- **Invariant:** At most one worker can hold an `ACTIVE` lease for a given `execution_id` at any time.

### 3.4 Side-Effect Safety and Uncertainty
To prevent blind replays of external network side effects upon worker crash:
- The runtime explicitly separates:
  - `execution_id`: The overall execution workflow instance.
  - `attempt_id`: The specific attempt executed by a worker under a lease.
  - `effect_id`: The unique identifier for external side-effect operations.
  - `idempotency_key`: The client/agent idempotency token.
- If a worker crashes after initiating an external effect but before local acknowledgement, the reaper records state `UNCERTAIN`. Automatic replay is strictly forbidden. Worker lease expiry does NOT grant permission to repeat an uncertain external effect.

### 3.5 Migration Ancestry Conditionality
- Migration `0049` is strictly conditional upon Codex approving candidate `13e8de034f8b31bd7cae4f47398f71b24c923c3c` with head `0048`.
- If the final approved canonical auth SHA or head differs, implementation must STOP and reconcile migration ancestry before creating any migration.
