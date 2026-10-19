# M13-H4 OPERATOR ADMISSION CONTRACT AND QUARANTINE SPECIFICATION
**Subsystem:** H4 Backup, Disaster Recovery & Authority Reconciliation  
**Target:** Operation M13 Recovery Zero  
**Date:** 2026-10-19  
**Security Classification:** P0 Critical  
**Author:** Antigravity FORTRESS Lead  

---

## 1. Fail-Closed Readiness State Machine

WhitePact enforces a strict fail-closed operator admission gate (`RestoreReadinessGate`) protecting all ingress traffic and worker task loops:

```
[RESTORE_PENDING] (Default upon restore)
       |
       |  Operator triggers authenticated reconcile
       v
 [RECONCILING]
    /        \
   / (success)\ (any error or integrity failure)
  v            v
[READY]     [FAILED]
 (Traffic     (Traffic
 Admitted)   Quarantined)
```

### 1.1 State Definitions
- **`RESTORE_PENDING`**: Database has been restored from snapshot; no authority reconciliation has taken place. All operational requests raise `RestoreQuarantineError(503 Service Unavailable)`.
- **`RECONCILING`**: Reconciliation is currently executing within an active ACID transaction. Ingress remains completely blocked.
- **`READY`**: All tenants have been reconciled against Store B, tombstoned tenants have been quarantined, all authority epochs have been fenced, and in-flight executions contained. Traffic is admitted.
- **`FAILED`**: Store B integrity check failed, Store B is unavailable, or a database constraint error occurred. System halts in complete quarantine.

---

## 2. PostgreSQL Supported Governance Status

In earlier revisions, reconciliation attempted to set `governance_status = "QUARANTINED"`, which failed under PostgreSQL check constraint `chk_org_governance_status`:
```sql
CHECK (governance_status IN ('ACTIVE', 'SUSPENDED', 'DISABLED'))
```
Under M13 Recovery Zero, the quarantine status is canonically represented as:
$$\text{governance\_status} = \text{GovernanceStatus.DISABLED.value} \quad (\text{"DISABLED"})$$
with:
$$\text{name} = \text{original\_name} + \text{"-RESTORE_QUARANTINED"}$$
$$\text{deactivated\_at} = \text{now()}$$

This satisfies PostgreSQL schema constraints without requiring unauthorized schema migrations, while unambiguously disabling all tenant routing and authorization lookups across all microservices.

---

## 3. Public Mutation Endpoint Protection

Per CTO Directives and Codex integration contracts:
- Public restore mutation endpoints in `src/responsibleai/dashboard/app.py` (`POST /api/v1/system/restore`, etc.) **remain disabled and return HTTP 503 Service Unavailable**.
- Database restoration is strictly a disaster recovery infrastructure operation executed via authenticated administrative CLI / operator tooling.
- Post-restore reconciliation must be explicitly invoked by an authenticated operator or automated disaster recovery orchestrator with cryptographic credentials for Store B.

---

## 4. Verification Checkpoints Before Admission

Consequential execution for any tenant is admitted IF AND ONLY IF:
1. `RestoreReadinessGate.state == RestoreReadinessState.READY`.
2. Restored database passes relational consistency checks.
3. Authoritative Store B HMAC signatures and generation counters verify cleanly.
4. Tenant governance status is `'ACTIVE'`.
5. Canonical `scope="governance"` epoch in `governance_revocation_epochs` $\ge \text{Store B floor}$.
6. Present credential/token issuer epoch $== \text{current governance epoch}$.
7. In-flight execution registry has terminated any processes executing under stale epochs.
