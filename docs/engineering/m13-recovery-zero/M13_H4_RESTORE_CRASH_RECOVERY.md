# M13-H4 RESTORATION TRANSACTION AND CRASH RECOVERY SPECIFICATION
**Subsystem:** H4 Backup, Disaster Recovery & Authority Reconciliation  
**Target:** Operation M13 Recovery Zero  
**Date:** 2026-10-19  
**Security Classification:** P0 Critical  
**Author:** Antigravity FORTRESS Lead  

---

## 1. Transaction Boundaries and Atomicity

Post-restore reconciliation executes within strict ACID transaction boundaries to guarantee that a partially completed restore or unexpected crash never leaves the database in an inconsistent or partially admitted state.

```
       [Start Reconciliation]
                 |
                 v
   Gate -> RECONCILING (in-memory & durable)
                 |
                 v
      BEGIN TRANSACTION (Store A)
        |-- Check & Quarantining Orgs
        |-- Topological Cascade Purge
        |-- Monotonic Epoch Elevation (governance & tenant_global)
        |-- Forensic Revocation of Root & Consent Records
        |-- Tombstone Ledger Synchronization
        |-- Audit Record Insertion (restore_reconciliation_records)
      COMMIT TRANSACTION (Store A)
                 |
                 v
   Gate -> READY (Operational traffic admitted)
```

---

## 2. Crash Point Analysis & Fail-Closed Behavior

| Crash Phase | Scenario | Transaction State | Gate State | Recovery Behavior |
|---|---|---|---|---|
| **Phase 0** | Database restored from backup; application starts up. | No transaction open. | `RESTORE_PENDING` | `assert_traffic_admitted()` raises `RestoreQuarantineError(503)`. Application serves zero traffic until operator triggers reconciliation. |
| **Phase 1** | Crash while reading or cryptographically validating Store B. | No transaction open. | `FAILED` or `RESTORE_PENDING` | Fail-closed. Reconciliation aborted. Operator alert emitted. |
| **Phase 2** | Crash during topological cascade purge or foreign key operations. | `ROLLBACK` executed by SQLAlchemy context manager / PostgreSQL abort. | `FAILED` | Zero database mutations persist. Stale authority is NOT partially deleted. Traffic remains completely quarantined. |
| **Phase 3** | Crash during epoch elevation or forensic root revocation. | `ROLLBACK` executed automatically. | `FAILED` | Rollback returns database to initial restored state. Gate remains in `FAILED`. |
| **Phase 4** | Process killed immediately after DB `COMMIT` but before memory gate advances to `READY`. | `COMMITTED` in PostgreSQL. | `RECONCILING` or persistent gate marker | On process restart, `is_restore_pending_default()` or startup check re-reads persistent state. A restart runs `reconcile_post_restore()`, which is strictly idempotent. |

---

## 3. Idempotency Proof

Post-restore reconciliation is strictly idempotent:
1. **Organization Quarantine:** Updating `governance_status = 'DISABLED'` and suffixing `-RESTORE_QUARANTINED` checks `if "-RESTORE_QUARANTINED" not in name`, avoiding repeated name mangling.
2. **Topological Deletion:** `delete().where(...)` statements on already-purged tables succeed with `rowcount == 0` without error.
3. **Approval Partitioning:** Updating `status = 'REVOKED'` checks `where(status != 'REVOKED')`, executing cleanly without duplicate side effects.
4. **Epoch Elevation:** Evaluates $\max(\text{current\_epoch}, \text{target\_floor})$. On second run, $\text{current\_epoch} \ge \text{target\_floor}$, so no unnecessary increments occur.
5. **Ledger & Audit Logging:** Reconciliation records are inserted with unique UUIDs and timestamps, creating a clean forensic ledger of each execution.

Adversarial test `test_18_idempotent_reconciliation` verified that repeated consecutive executions of `reconcile_post_restore()` on PostgreSQL 16 complete with zero errors and maintain identical authority invariants.
