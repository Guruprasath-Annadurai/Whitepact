# WhitePact V1 — Canonical Alembic / Phase 7A Migration Ownership

**Status:** CANONICAL. Implemented database history is authoritative.

**Implemented Alembic head:** `0053`
**File:** `migrations/versions/0053_runtime_worker_leases.py`
**Down-revision:** `0052` → `0051` → `0050` → `0049` → `0048`

There is one linear chain. There is no branch split and no orphan
revision. `alembic heads` must equal `0053`.

| Revision | Ownership | Status |
| :--- | :--- | :--- |
| `0049` | Organization governance lifecycle (`organizations.governance_status` ACTIVE / SUSPENDED / DISABLED) | **Implemented** |
| `0050` | `runtime_execution_requests` (append-only durable requests) | **Implemented** |
| `0051` | `governance_execution_authorizations` (`ISSUED` / `CONSUMED` only) | **Implemented** |
| `0052` | `runtime_execution_attempts` | **Implemented** |
| `0053` | Worker leases + `runtime_execution_fences` + `runtime_execution_dispatch_outbox` | **Implemented** |

Pass 4.4 numbering (obsolete):

| Old revision | Old ownership |
| :--- | :--- |
| 0049 | runtime_execution_requests |
| 0050 | governance_execution_authorizations |
| 0051 | runtime_execution_attempts |
| 0052 | worker leases / fences / outbox |
| 0053 | organization governance lifecycle |

Production Gate B remains CLOSED. `PHASE7A_DISPATCHER_ENABLED` defaults to
false. Schema presence is not dispatcher activation.
