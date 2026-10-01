# Alert Catalog (draft)

Each alert: **what** | **why** | **evidence** | **operator action**

| ID | Severity | Condition | Action |
|----|----------|-----------|--------|
| A-001 | SEV1 | `/readyz` failing > 5m | Check Postgres, migrations, restore gate |
| A-002 | SEV1 | 5xx rate > 5% for 10m | Rollback candidate; inspect logs |
| A-003 | SEV1 | Migration version mismatch at startup | Stop deploy; run `alembic current` |
| A-004 | SEV2 | Evidence write failures sustained | Fail closed for mutations; DB disk |
| A-005 | SEV2 | Redis unreachable (if configured) | Rate limit per-replica drift risk |
| A-006 | SEV2 | Backup job failed | Re-run backup; page if prod |
| A-007 | SEV3 | Certificate expiry < 14d | Renew cert |
| A-008 | SEV0 | Suspected authority bypass | Security incident runbook |

Paging integration: **NOT_IMPLEMENTED** (documentation only).
