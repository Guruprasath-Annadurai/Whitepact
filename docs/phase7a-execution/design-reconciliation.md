# WhitePact Phase 7A Design Reconciliation

**Document Status:** Approved Architecture Reconciliation
**Source Design SHA:** `dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`
**Target Runtime Base SHA:** `13e8de034f8b31bd7cae4f47398f71b24c923c3c`
**Reconciled Core Ancestor SHA:** `12810825c407960ca2aa9ada94fbae056db37290`
**Current Alembic Migration Head:** `0048` (`migrations/versions/0048_enforce_paddle_binding_atomicity.py`)

---

## 1. Executive Summary

This document provides a systematic, item-by-item reconciliation between the Phase 7A Master Design (`dfbeb2e6d9fad575fc45b64789c63b1c1c0b5b01`) and the current authentication candidate under Codex review (`13e8de034f8b31bd7cae4f47398f71b24c923c3c`).

Between the initial candidate `4ac9550ee2c16078e295620a6c77c9be51f5b6b4` and `13e8de034f8b31bd7cae4f47398f71b24c923c3c`, two security remediations were applied to Paddle webhook ingestion and concurrency:
1. `a08de3794b776b8fbebb8cadc91c7a018e904ecc`: Enforced database-level atomic unique constraints on Paddle subscription bindings via migration `0048` and row-level locking.
2. `13e8de034f8b31bd7cae4f47398f71b24c923c3c`: Closed equal-timestamp commercial entitlement widening (`WP-AUTH-PDL-01-R1`), established explicit plan ranking (`PLAN_RANK`), and restored canonical migration lifecycle test assertions.

This reconciliation confirms that **0 blockers** exist for Phase 7A execution. All Phase 7A design assumptions are verified and updated to align with migration head `0048` and the newly hardened commercial plan models.

---

## 2. Invariant Reconciliation Matrix

| Subsystem / Dimension | Status | Detailed Findings & Adaptations |
| :--- | :--- | :--- |
| **ExecutionAuthorization** | UNCHANGED | `ExecutionAuthorization` remains immutable in `src/responsibleai/governance/models.py`. Neither Paddle webhooks nor admission tokens can issue or modify an `ExecutionAuthorization`. |
| **Tenant Lifecycle** | UNCHANGED | Tenant status checks (`organizations.subscription_status`, soft-deletion, tombstones) remain authoritative in PostgreSQL. Queued requests must recheck tenant liveness before execution dispatch. |
| **Principal / Session Lifecycle** | UNCHANGED | Session-binding token checks in `iam_step_up_nonces.session_id` (migration `0047`) remain intact. Queued execution revalidation must verify principal and session validity. |
| **BreakGlass** | UNCHANGED | BreakGlass sessions in `iam_break_glass_sessions` remain strictly bounded by TTL. Expired BreakGlass sessions while queued reject execution dispatch. |
| **Policy Evaluation** | UNCHANGED | Deterministic lattice evaluation and explicit DENY precedence remain immutable. Admission capacity never overrides policy decisions. |
| **Organization Model** | MINOR PLAN ADAPTATION | Organization table now includes strict unique indexes for `paddle_subscription_id` and `paddle_customer_id` via migration `0048`. Concurrency controllers must read org state under read committed isolation. |
| **Paddle Plan Model** | MINOR PLAN ADAPTATION | `src/responsibleai/rbac/models.py` defines `PLAN_RANK` (`FREE: 0`, `PRO: 1`, `ENTERPRISE: 2`) and status groupings (`ACTIVE_LIKE_STATUSES`, `RESTRICTIVE_STATUSES`). Phase 7A admission queue fairness must treat commercial plan only as a service-class parameter if configured, never as governance authority. |
| **PostgreSQL Migration Head** | MINOR PLAN ADAPTATION | Migration head is `0048` (`0048_enforce_paddle_binding_atomicity.py`). Phase 7A worker lease migrations must specify `down_revision = "0048"`. Head `0047` references are updated. |
| **Shutdown / Lifespan** | UNCHANGED | FastAPI lifespan handlers in `src/responsibleai/api/app.py` remain the designated integration point for the Phase 7A two-phase graceful shutdown supervisor. |
| **Execution Dispatcher** | UNCHANGED | `src/responsibleai/isolation/` backends remain the execution target. The direct execution path in `execution_gateway.py` will be decoupled behind the admission controller and worker lease manager. |
| **Docker Isolation** | UNCHANGED | `ContainerIsolationBackend` in `src/responsibleai/isolation/container_backend.py` enforces `--network=none`. WP-ISO-01 limits will insert into existing parameter builder methods. |
| **Egress** | UNCHANGED | Proxy-mediated egress enforcement in `src/responsibleai/net/egress.py` remains active for non-isolated workloads. Container isolation remains strictly air-gapped (`--network=none`). |
| **Evidence Ledger** | UNCHANGED | SHA-256 hash chaining and tamper-evident append logging in `src/responsibleai/audit/evidence.py` remain canonical. Admission and execution events append to this ledger. |

---

## 3. Detailed Architectural Reconciliations

### 3.1 Migration Head Alignment (0047 → 0048)
- **Previous Design Assumption:** Initial Phase 7A planning assumed Alembic revision `0047` (`0047_auth_entitlement_seam_closure.py`) as the database head.
- **Runtime Truth:** The current candidate repository is at revision `0048` (`0048_enforce_paddle_binding_atomicity.py`), which added uniqueness constraints on `idx_org_paddle_subscription`.
- **Adaptation Required:**
  1. Any new database migration required by Phase 7A (specifically migration `0049` for `runtime_worker_leases` and `runtime_admission_queue` if durable queue persistence is used) must set `down_revision = "0048"`.
  2. Health check verification routines (`/readyz`) must verify `0048` or subsequent as the current revision.
  3. No migration files prior to `0048` may be modified.

### 3.2 Commercial Plan Ordering Separation
- **Previous Design Assumption:** The Phase 7A Master Design stated that commercial plan must not influence governance authority, but allowed optional tier-based fairness weights.
- **Runtime Truth:** `src/responsibleai/rbac/models.py` now explicitly standardizes:
  ```python
  PLAN_RANK: dict[Plan, int] = {
      Plan.FREE: 0,
      Plan.PRO: 1,
      Plan.ENTERPRISE: 2,
  }
  ACTIVE_LIKE_STATUSES = frozenset({"active", "trialing"})
  RESTRICTIVE_STATUSES = frozenset({"canceled", "paused", "past_due", "inactive", "dissolved"})
  ```
- **Adaptation Required:**
  1. The admission controller must strictly maintain separation between `Plan` tier and `Authority`. A tenant with `Plan.ENTERPRISE` receives bounded compute queue concurrency (e.g., higher worker concurrency cap), but **zero** elevation in governance permissions, policy evaluation, or approval requirements.
  2. If a tenant transitions to a restrictive status (`canceled`, `paused`, `past_due`, `inactive`, `dissolved`), active and queued execution requests for that tenant must immediately abort with `AdmissionRejectionReason.TENANT_RESTRICTED`.

### 3.3 Strict Governance Boundary Verification
The fundamental security doctrine established across Phases 1–5 remains unchanged:
```
Governance Authorization (ExecutionAuthorization)
       ≠ Admission Decision (AdmissionResult)
       ≠ Queue Slot (QueueTicket)
       ≠ Worker Lease (WorkerLease)
```
1. **Admission is Not Authorization:** Obtaining an admission slot grants only system capacity (CPU, RAM, container slot). It never bestows execution rights.
2. **Revalidation at Dispatch:** When a worker acquires a lease for a queued request, it must re-verify the canonical `ExecutionAuthorization` record in PostgreSQL before spawning a container.
3. **Fail-Closed Redis Coordination:** If Redis semaphores or queue locks are unavailable, the system defaults to HTTP 503 (Capacity Unavailable). It never bypasses the admission controller to execute unmetered workloads.

---

## 4. Reconciliation Verification Checklist

- [x] Base commit `13e8de034f8b31bd7cae4f47398f71b24c923c3c` verified clean and operational.
- [x] All 3,581 canonical tests pass on the base candidate across two independent runs.
- [x] Migration revision `0048` confirmed as the single Alembic head.
- [x] Docker isolation air-gap (`--network=none`) confirmed untouched.
- [x] ExecutionAuthorization schema and lifetime rules confirmed intact.
- [x] Zero architectural blockers identified for Phase 7A.
