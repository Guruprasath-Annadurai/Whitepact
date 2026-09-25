# Gate 2 — Threat Review (domain layer)

| Threat | Gate 2 mitigation |
|--------|-------------------|
| Cross-tenant graph edge | `CrossTenantReference` on add |
| Stale grant at commit | `CommitFence` + `VersionMismatch` |
| Capability→authority confusion | `INV_CAPABILITY_NOT_AUTHORITY` |
| INFERRED edge as proof | `is_authoritative_for_hard_proof` |
| Graph mutation after eval | `graph_version` pin on trace events |

Runtime integration threats (DB race, cache) deferred to Gate 3+.
