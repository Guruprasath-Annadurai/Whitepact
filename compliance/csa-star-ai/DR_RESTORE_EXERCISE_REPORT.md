# Disaster recovery / restore exercise report

**Scope:** Application-level restore drill using **SQLite** (development engine).  
**Not claimed:** Production PostgreSQL RPO/RTO on live hosting — requires OA-002 + `scripts/backup-postgres.sh` execution on real infrastructure.

## Procedure

```bash
bash compliance/csa-star-ai/exercises/run_sqlite_restore_drill.sh
```

## Latest run (2026-09-23)

```
backup_file=.../drill-20260923T085750Z.sql
restore_start=2026-09-23T08:57:50Z
restore_end=2026-09-23T08:57:51Z
integrity_note=pre-backup
result=PASS
```

Full log: `compliance/csa-star-ai/evidence/dr/last_drill.log`

| Field | Value |
|-------|-------|
| Environment | Agent VM / non-production |
| Backup method | `sqlite3 .dump` |
| Integrity check | `dr_marker.note == pre-backup` |
| Production Postgres | **Not exercised** — owner must run `scripts/backup-postgres.sh` and document RPO/RTO |

## Gaps

- Off-host backup storage (owner/provider)
- Encrypted backup at rest (provider)
- Restore admission checks on production (`tests/test_restore_admission_chokepoint.py` covers logic; production run pending)
