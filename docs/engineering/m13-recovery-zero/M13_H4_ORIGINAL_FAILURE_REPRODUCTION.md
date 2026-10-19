# M13-H4 ORIGINAL INDEPENDENT FAILURE REPRODUCTION REPORT
**Subsystem:** H4 Backup, Disaster Recovery & Authority Reconciliation  
**Target:** Operation M13 Recovery Zero  
**Date:** 2026-10-19  
**Security Classification:** P0 Critical  
**Author:** Antigravity FORTRESS Lead  

---

## 1. Executive Summary

Prior to implementing any corrective fixes in `src/responsibleai/data_governance/backup_defense.py`, the independent negative reproducer suite (`scripts/engineering/reproducers/test_m13_fortress_restore_independent.py`) was executed against an actual PostgreSQL 16 container (`postgresql://wp:wp@127.0.0.1:55432/postgres`) running the canonical Alembic migration schema.

The independent negative baseline reported exactly:
**1 PASS / 2 FAIL per Python interpreter (Python 3.11 and Python 3.12).**

This conclusively verified the Codex integration rejection findings:
1. **Failure 1 (Revocation-Security Floor):** Canonical Store B revocation floors were not synchronized to the canonical `scope="governance"` in `governance_revocation_epochs`, resulting in stale epochs being trusted and failing `assert (await epochs.current("restored-tenant")).epoch >= 7`.
2. **Failure 2 (PostgreSQL Restrictive FK & Trigger Invariant):** Attempting to execute `DELETE` against `runtime_execution_requests` violated PostgreSQL's trigger `reject_execution_request_mutation()` prohibiting mutation of immutable evidence, and attempting to delete `governance_approvals` violated the `ON DELETE RESTRICT` foreign key constraint `runtime_execution_requests_approval_id_fkey`.

---

## 2. Independent Reproduction Environment Matrix

| Parameter | Specification |
|---|---|
| Repository Base SHA | `7939341fd9d98d0f1fa39ce4421318dbc1dac33e` |
| Working Branch | `antigravity/whitepact-m13-recovery-zero` |
| Database Engine | PostgreSQL 16.10 on TCP port 55432 |
| Dialect Driver | `asyncpg` via SQLAlchemy 2.0+ async engine |
| Schema State | Alembic migration head (`0059_widen_audit_log_key_id.py`) |
| Python Interpreters | CPython 3.11.13 & CPython 3.12.13 |
| Reproducer Test File | `scripts/engineering/reproducers/test_m13_fortress_restore_independent.py` |

---

## 3. Dissected Failure 1: Store B Floor Synchronization Failure

### 3.1 Failing Test
`test_store_b_floor_fences_canonical_governance_epoch(restored)`

### 3.2 Counterexample Scenario
- Restored tenant `restored-tenant` had a restored epoch of `2`.
- Store B lifecycle record specified `security_epoch=7, revocation_floor=7`.
- Restoration reconciliation was invoked via `RestoreReconciliationEngine(restored, lifecycle_provider=provider).reconcile_post_restore(...)`.
- The verifier queried `RevocationEpochRepository.current("restored-tenant")`, which checks `scope="governance"`.

### 3.3 Stack Trace and Assertion Failure
```text
FAILED scripts/engineering/reproducers/test_m13_fortress_restore_independent.py::test_store_b_floor_fences_canonical_governance_epoch - assert 2 >= 7
+  where 2 = RevocationEpochRecord(organization_id='restored-tenant', scope='governance', epoch=2, updated_at='...').epoch
```

### 3.4 Root Cause
The legacy reconciliation logic only queried and elevated epochs where `scope == "tenant_global"`, or failed to synchronize active tenants that were not tombstoned. The canonical verifier in `RevocationEpochRepository` defaults to `scope="governance"`. When Store B dictates a revocation floor of `7`, but the database epoch remains `2`, any execution authorization issued prior to disaster recovery with epoch `2` would be incorrectly accepted by the runtime verifiers, resurrecting stale authority.

---

## 4. Dissected Failure 2: Restrictive Foreign Key & Immutable Trigger Failure

### 4.1 Failing Test
`test_tombstone_reconciliation_handles_real_approval_request_fk(restored)`

### 4.2 Counterexample Scenario
- Test creates a pending `governance_approvals` row (`id="approval", org_id="restored-tenant"`).
- Test creates an immutable `runtime_execution_requests` row (`request_id="request", organization_id="restored-tenant", approval_id="approval"`).
- Store B records `restored-tenant` as `TOMBSTONED`.
- `RestoreReconciliationEngine.reconcile_post_restore` executes topological purge.

### 4.3 Trigger Constraint
Migration `0050_runtime_execution_requests.py` defines:
```sql
CREATE OR REPLACE FUNCTION reject_execution_request_mutation()
RETURNS TRIGGER AS $$
BEGIN
    RAISE EXCEPTION
        'runtime_execution_requests is immutable and append-only: UPDATE and DELETE are prohibited';
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER prevent_execution_request_mutation
BEFORE UPDATE OR DELETE ON runtime_execution_requests
FOR EACH ROW EXECUTE FUNCTION reject_execution_request_mutation();
```

### 4.4 Foreign Key Constraint
```sql
sa.ForeignKey("governance_approvals.id", ondelete="RESTRICT")
```

### 4.5 Stack Trace and Database Error
When `delete(runtime_execution_requests)` was invoked:
```text
sqlalchemy.dialects.postgresql.asyncpg.Error: <class 'asyncpg.exceptions.RaiseException'>: runtime_execution_requests is immutable and append-only: UPDATE and DELETE are prohibited
```
When `runtime_execution_requests` deletion was skipped, but `delete(governance_approvals)` was directly attempted:
```text
sqlalchemy.dialects.postgresql.asyncpg.Error: <class 'asyncpg.exceptions.ForeignKeyViolationError'>: update or delete on table "governance_approvals" violates foreign key constraint "runtime_execution_requests_approval_id_fkey" on table "runtime_execution_requests"
DETAIL: Key (id)=(approval) is still referenced from table "runtime_execution_requests".
```

### 4.6 Root Cause
`runtime_execution_requests` is immutable audit evidence and admission state. It must NEVER be deleted.
Because `runtime_execution_requests.approval_id` references `governance_approvals.id` with `ON DELETE RESTRICT`, any approval referenced by a recorded execution request CANNOT be deleted without violating PostgreSQL's relational integrity. Attempting ad hoc raw deletions without partitioning referenced vs. unreferenced approvals breaks on real PostgreSQL schemas.

---

## 5. Third Test Verification: Runtime Canonical Fence Scope Isolation
`test_runtime_canonical_fence_ignores_other_scope(restored, tmp_path, monkeypatch)`
- Verified that `InFlightExecutionRegistry.reconcile_epochs()` strictly observes canonical `scope="governance"` and terminates out-of-epoch in-flight executions even when unrelated scopes (such as `tenant_global`) have drifted.
- This test passed consistently, confirming the isolation boundary required between canonical governance epoch and external scopes.

---

## 6. Reproduction Verdict
The independent negative reproducer suite was valid, reproducible, and strictly demonstrated the two architectural defects identified by Codex integration review. Remediation required zero compromise on database constraints or immutable evidence.
