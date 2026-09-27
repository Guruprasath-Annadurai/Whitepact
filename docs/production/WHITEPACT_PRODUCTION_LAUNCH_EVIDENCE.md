# WhitePact Production Launch Evidence Pack

**Rule:** Do not mark a row **COMPLETE** without a linked artifact.

| Evidence item | Status | Link / command |
|---------------|--------|----------------|
| Deployment procedure | PARTIAL | `docs/production/DEPLOYMENT_RUNBOOK.md` |
| Config validation | PARTIAL | `python -m responsibleai.operations.config_validate` |
| Migration head | PARTIAL | `0061_sovereign_shadow_observations.py` |
| Backup procedure | PARTIAL | `scripts/backup-postgres.sh` |
| Restore rehearsal | **NOT_TESTED** | — |
| Health checks | PARTIAL | `tests/test_v1_api.py` |
| Observability standard | PARTIAL | `docs/operations/OBSERVABILITY_STANDARD.md` |
| Alerts | PARTIAL | `docs/operations/ALERT_CATALOG.md` |
| Incident runbooks | PARTIAL | `docs/operations/INCIDENT_RESPONSE_RUNBOOK.md` |
| Load test | **NOT_TESTED** | — |
| Soak test | **NOT_TESTED** | — |
| Tenant isolation | PARTIAL | CI `tests/test_tenant_*` |
| Security scans | PARTIAL | CI workflows (exact run IDs on PR) |
| Artifact identity | PARTIAL | Reproducible build job when CI green |

## Machine-readable manifest

See `launch-manifest.example.json` — fill only with real CI run IDs and digests after qualification.
