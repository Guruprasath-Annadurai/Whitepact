# M13 RECOVERY ZERO — CRASH CONSISTENCY PROOF
## PostgreSQL Transaction Boundaries, Two-Phase Reconciliation Status, and Crash Resiliency

- **Date:** 2026-10-19
- **Author:** Antigravity FORTRESS
- **Milestone:** WhitePact M13 — Operation Recovery Zero
- **Commit Baseline:** `b896b1efb4406c03205522dce7c69855391d305b`
- **Component:** `src/responsibleai/data_governance/backup_defense.py`

---

### 1. Problem Statement & Vulnerability Analysis (P0-04)

In commit `b896b1efb4406c03205522dce7c69855391d305b`, `reconcile_post_restore()` contained a severe transactional ordering defect:

```python
# VULNERABLE CODE IN b896b1efb4406c03205522dce7c69855391d305b
with self.engine.begin() as conn:
    # ... update orgs, API keys, policies, revoke tokens ...
    conn.execute(
        insert(restore_reconciliation_records).values(
            record_id=rec_id,
            status="RECONCILED",  # <--- PREMATURELY MARKED RECONCILED!
            # ...
        )
    )
# Database transaction COMMITS here.
# Runtime containment runs AFTER commit:
registry = in_flight.get_in_flight_registry()
# ... If containment raises exception:
except Exception as e:
    with self.engine.begin() as conn:
        conn.execute(
            insert(restore_reconciliation_records).values(
                record_id=rec_id, # <--- DUPLICATE PRIMARY KEY ERROR!
                status="FAILED",
            )
        )
```

#### Dual Failure Mode:
1. **Premature Record Commitment:** If the process was terminated (OOM, SIGKILL, power failure) immediately after the database transaction committed, PostgreSQL recorded `status = "RECONCILED"`. A subsequent startup check reading `restore_reconciliation_records` concluded that reconciliation had completed successfully, even though containment never executed.
2. **Exception Duplicate Key Swallowing:** If containment failed (e.g., active execution detected), the error handler attempted to `INSERT` a row with the same `rec_id`. PostgreSQL raised `UniqueViolation` / `IntegrityError`, which was caught by `except Exception: pass`. The record in PostgreSQL remained `status = "RECONCILED"`!

---

### 2. Remediation Contract & Implementation

#### Two-Phase Reconciliation Commit:
1. **Phase 1: Transaction Commit with `CONTAINMENT_PENDING`:**
   ```python
   with self.engine.begin() as conn:
       # ... synchronize store A and store B, advance revocation epochs ...
       conn.execute(
           insert(restore_reconciliation_records).values(
               record_id=rec_id,
               status="CONTAINMENT_PENDING",  # Staged state
               reconciled_at=datetime.now(UTC),
               details=json.dumps({"store_b_rev": store_b_rev, "stage": "database_sync"}),
           )
       )
   ```
2. **Phase 2: Post-Containment Promotion to `RECONCILED`:**
   Only after in-flight containment has confirmed zero active and zero unresolved executions across all tenants:
   ```python
   with self.engine.begin() as conn:
       conn.execute(
           update(restore_reconciliation_records)
           .where(restore_reconciliation_records.c.record_id == rec_id)
           .values(
               status="RECONCILED",
               details=json.dumps({"store_b_rev": store_b_rev, "stage": "containment_verified"}),
           )
       )
   ```
3. **Phase 3: Resilient Failure Handling:**
   If any exception occurs:
   ```python
   try:
       with self.engine.begin() as conn:
           res = conn.execute(
               update(restore_reconciliation_records)
               .where(restore_reconciliation_records.c.record_id == rec_id)
               .values(status="FAILED", details=json.dumps({"error": str(e)}))
           )
           if res.rowcount == 0:
               conn.execute(
                   insert(restore_reconciliation_records).values(
                       record_id=rec_id,
                       status="FAILED",
                       reconciled_at=datetime.now(UTC),
                       details=json.dumps({"error": str(e)}),
                   )
               )
   except Exception:
       pass
   ```

---

### 3. Empirical Verification & Evidence

Test case: `test_p0_04_containment_failure_updates_record_to_failed_no_pk_violation` in `tests/test_m13_recovery_zero_p0_reproducers.py`.

#### Empirical Results:
1. During containment failure, the record in PostgreSQL was successfully updated to `status = "FAILED"`.
2. No primary key collision or duplicate key error occurred.
3. If an uncontained crash interrupts Phase 1, the row status remains `"CONTAINMENT_PENDING"`, which fails all queries searching for valid `"RECONCILED"` records (`assert_database_restore_consistent()` correctly identifies non-reconciled state).

---

### 4. Architectural Limitations & Boundaries

- **Crash In-Between Phase 1 and 2:** A crash during in-flight containment leaves a `"CONTAINMENT_PENDING"` record. A subsequent startup will not consider this database reconciled; reconciliation must be re-run by the operator.
- **Rollback on Partial Execution:** All database mutations (disabling orgs, clearing API keys, bumping revocation epochs) are executed within a single ACID transaction. If an error occurs prior to Phase 1 commit, all changes are rolled back cleanly.
