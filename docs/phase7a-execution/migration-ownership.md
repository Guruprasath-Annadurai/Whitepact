# WhitePact V1 — Canonical Alembic / Phase 7A Migration Ownership

**Status:** CANONICAL at candidate HEAD. Implemented database history is
authoritative. Pass 4.4 planning documents that assigned `0049` to
`runtime_execution_requests` are superseded.

**Implemented Alembic head:** `0049`
**File:** `migrations/versions/0049_add_organization_governance_status.py`
**Down-revision:** `0048`

Phase 7A runtime table migrations `0050`–`0053` are **planned and not
created**. Do not invent files until the independent implementation gate
authorizes non-activated foundations.

| Revision | Ownership | Status |
| :--- | :--- | :--- |
| `0049` | Organization governance lifecycle (`organizations.governance_status` ACTIVE / SUSPENDED / DISABLED) | **Implemented** |
| `0050` | `runtime_execution_requests` (append-only durable requests) | Planned, not created |
| `0051` | `governance_execution_authorizations` (`UNIQUE(approval_id)`) | Planned, not created |
| `0052` | `runtime_execution_attempts` | Planned, not created |
| `0053` | Worker leases + `runtime_execution_fences` + `runtime_execution_dispatch_outbox` | Planned, not created |

Pass 4.4 numbering (obsolete):

| Old revision | Old ownership |
| :--- | :--- |
| 0049 | runtime_execution_requests |
| 0050 | governance_execution_authorizations |
| 0051 | runtime_execution_attempts |
| 0052 | worker leases / fences / outbox |
| 0053 | organization governance lifecycle |

There is one linear chain. There is no branch split and no orphan
revision. `alembic heads` must equal `0049`.
