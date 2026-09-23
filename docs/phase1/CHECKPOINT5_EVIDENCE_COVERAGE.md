# Checkpoint 5 consequential-path evidence inventory

| Path | Classification | Evidence semantics |
|---|---|---|
| Internal governed execution | CANONICAL EVIDENCE | Decision is persisted before the permit is admitted; outcome follows dispatch. |
| Hosted MCP | CANONICAL EVIDENCE | Uses the internal governed execution chokepoint with resolved tenant authority. |
| Upstream MCP | CANONICAL EVIDENCE | Persists target/request bindings before the upstream executor admits the permit. |
| Approval resume | CANONICAL EVIDENCE | Fresh authority resolution and approval reference are recorded before consume/dispatch. |
| Dashboard/REST consequential governance endpoints | CANONICAL EVIDENCE | Governed executor routes share tenant-scoped repositories; administrative CRUD is not an external execution claim. |
| Community local stdio | NOT APPLICABLE | Explicit local, operator-owned, database-free mode; not an official hosted production path. |

Official-production consequential evidence bypass count: **0**.

This inventory does not close the DNS-rebinding P1 release blocker and does not
claim comprehensive privileged-administrator auditing.
