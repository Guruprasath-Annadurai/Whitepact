# WhitePact — Canonical Alembic Migration Ownership

**Status:** CANONICAL. Implemented database history is authoritative.

**Phase 7A frozen runtime head:** `0053`
**File:** `migrations/versions/0053_runtime_worker_leases.py`

**Current implemented Alembic head:** `0056`
**File:** `migrations/versions/0056_identity_security_fortress.py`
**Down-revision:** `0055` → `0054` → `0053` → `0052` → `0051` → `0050` → `0049` → `0048`

There is one linear chain. There is no branch split and no orphan
revision. `alembic heads` must equal `0056`.

Phase 7A runtime schema (`0050`–`0053`) is frozen. Enterprise SaaS Layer 1
and Layer 2 extend administrative identity only. Production Gate B remains CLOSED.
`PHASE7A_DISPATCHER_ENABLED` defaults to false. Schema presence is not
dispatcher activation.

| Revision | Ownership | Status |
| :--- | :--- | :--- |
| `0049` | Organization governance lifecycle (`organizations.governance_status` ACTIVE / SUSPENDED / DISABLED) | **Implemented** |
| `0050` | `runtime_execution_requests` (append-only durable requests) | **Implemented (frozen)** |
| `0051` | `governance_execution_authorizations` (`ISSUED` / `CONSUMED` only) | **Implemented (frozen)** |
| `0052` | `runtime_execution_attempts` | **Implemented (frozen)** |
| `0053` | Worker leases + `runtime_execution_fences` + `runtime_execution_dispatch_outbox` | **Implemented (frozen)** |
| `0054` | Enterprise SaaS Layer 1 identity: workspace columns, membership lifecycle, environments, API-key provenance, service accounts, security audit | **Implemented** |
| `0055` | Verified principal gate: human/org verification + provider event replay protection | **Implemented** |
| `0056` | Enterprise SaaS Layer 2 identity security fortress: passkeys, TOTP, recovery, provider bindings, SSO, sessions, step-up | **Implemented** |

Pass 4.4 numbering (obsolete):

| Old revision | Old ownership |
| :--- | :--- |
| 0049 | runtime_execution_requests |
| 0050 | governance_execution_authorizations |
| 0051 | runtime_execution_attempts |
| 0052 | worker leases / fences / outbox |
| 0053 | organization governance lifecycle |
