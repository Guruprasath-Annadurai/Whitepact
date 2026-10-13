# Disaster Recovery Policy (initial)

## Definitions

- **RPO (target):** 24 hours for relational DB without external managed backup — **achievable only if** scheduled `backup-postgres.sh` runs and off-site copy exists. **Currently UNVERIFIED** in Launch Cell B.
- **RTO (target):** 4 hours for full stack restore on fresh VMs — **engineering target**, not proven.

## Achievable today (honest)

| Capability | Status |
|------------|--------|
| Logical Postgres backup script | REAL_BUT_PARTIAL |
| Restore script with confirmation | REAL_BUT_PARTIAL |
| Restore admission gate + reconciliation | REAL_AND_TESTED (in-app) |
| Multi-AZ Kubernetes failover | UNVERIFIED |
| Zero data loss | **Not claimed** |

## Failure scenarios

| Scenario | Expected behavior |
|----------|-------------------|
| DB loss | Fail closed; restore from backup + run reconciliation |
| Cache (Redis) loss | Rate limits degrade per-process unless Redis restored; authority DB remains source of truth |
| Bad release | Roll back artifact; schema may require forward-only migration plan |
| Secret compromise | Security incident runbook; rotate keys; bump revocation epochs |
| Operator mistake on restore | `RESTORE_PENDING` blocks traffic until reconciliation |

## Unproven

- Zone/region loss with automated failover
- Object storage unavailable (if added later)
- Certificate expiry automation in all deployment paths
