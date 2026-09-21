# Release runbooks (DRAFT templates)

Mark **UNAVAILABLE** where infrastructure does not exist.

| Runbook | Status |
|---------|--------|
| Deployment | Template — see `DEPLOY_RUNBOOK.md` |
| Rollback | Template — Render/host-specific; capture prior SHA |
| Migration failure | `alembic current` / restore DB snapshot |
| Database outage | Fail closed; no dispatcher |
| MCP outage | Health 200 / MCP 401 baseline checks |
| Authentication outage | OAuth/API key rotation per ops |
| UNKNOWN reconciliation | Operator reviews outcome + evidence IDs |
| Revocation emergency | Governance revocation kernel procedures |
| Evidence integrity | Audit log + evidence repository |
| Secret rotation | **UNAVAILABLE** in prep — document in ops vault |
| Incident containment | Standard founder-led response |

Provenance: capture git SHA, branch, builder image, artifact digest at release time (see `DRAFT-provenance.md`).
