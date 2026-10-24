# M13 Cursor integration report — P0 referenced-approval deletion

**Milestone:** M13 remains OPEN.
**M14:** not authorized.
**Production:** not authorized. No protected merge, no deployment, and no spending.

This addendum records the tenant-deletion failure where `governance_approvals` rows are referenced by immutable `runtime_execution_requests`, and the remedy in `src/responsibleai/data_governance/deletion_orchestrator.py`.

Codex owns the offline floor-repair and signed R1 workstream on `codex/whitepact-m13-r1-operator-recovery` (`41e2cacbfcfa813e433686ee65523d9172124766`). This change does not edit `backup_defense.py`, `operator_recovery.py`, `operator_recovery_control.py`, floor-fence tests, or recovery signatures.

## Failure before

PostgreSQL 16.15. Python 3.12.3. Orchestrator at `41e2cacb`, before this remedy. The same scenario as `tests/test_m13_referenced_approval_deletion.py::test_referenced_approval_deletion_preserves_requests_and_isolates_tenants`.

`TenantDeletionOrchestrator.delete_tenant` issued:

```sql
DELETE FROM governance_approvals WHERE governance_approvals.org_id = $1::VARCHAR
```

PostgreSQL rejected it:

```text
asyncpg.exceptions.ForeignKeyViolationError: update or delete on table "governance_approvals" violates foreign key constraint "runtime_execution_requests_approval_id_fkey" on table "runtime_execution_requests"
DETAIL:  Key (id)=(victim-ref-approval) is still referenced from table "runtime_execution_requests".
sqlalchemy.exc.IntegrityError: (sqlalchemy.dialects.postgresql.asyncpg.ForeignKeyViolationError) ...
```

The erasure transaction rolled back. The restrictive foreign key and the immutable request row stayed in place, and the approval remained deletable authority because the delete never committed a revocation. Pytest exit code: 1.

## Remedy

1. Immutable `runtime_execution_requests` rows are not updated or deleted. `approval_id` stays `ON DELETE RESTRICT`.
2. Approvals referenced by `runtime_execution_requests` or `governance_execution_authorizations` are set to `REVOKED` in a committed transaction. A later retry does not write `APPROVED` back over `REVOKED`.
3. Unreferenced approvals are deleted only after their `governance_approval_votes` rows, and only when no restrictive reference remains.
4. Quarantine sets `organizations.governance_status` to `DISABLED` and does not write `ACTIVE` again. Issued authorizations for that tenant are consumed, `PENDING`/`LEASED` attempts move to `FAILED_PRE_EXECUTION`, active leases are revoked, and pending dispatch rows are cancelled. A crash after that commit cannot restore execution authority or reopen admission by rolling back the erasure transaction.
5. An interrupted `DELETION_IN_PROGRESS` lifecycle keeps the protected generation, retries erasure, and records `TOMBSTONED` only after verification. An existing tombstone for that generation is reused. A different generation is refused.
6. Legal hold is still checked before quarantine or revocation. Deletion still requires an established Store B lifecycle and keeps that generation. Signed R1 recovery tests were not rewritten.

## Success after

| Run | Interpreter | Result |
| --- | --- | --- |
| Referenced approvals, cross-tenant isolation, crash/restart, retry, tombstone, legal hold, existing tenant-deletion tests | Python 3.12.3 | `5 passed` (`tests/test_m13_referenced_approval_deletion.py`, `tests/test_tenant_deletion.py`) |
| Signed R1 fortress recovery, including `test_fortress_r1_tombstone_real_approval_fk` | Python 3.12.3 | `5 passed` (`tests/test_stage3_fortress_signed_recovery.py`) |
| The same ten tests | Python 3.11.17 | `10 passed` |

PostgreSQL 16.15 in each run. Disposable databases via `WHITEPACT_TEST_PG_ADMIN_URL` on `127.0.0.1:5432`. Times are 24 Oct 2026, afternoon IST (UTC+5:30).

After the remedy the referenced approval is `REVOKED`, the unreferenced approval and its vote are gone, the execution request row is unchanged, `ON DELETE RESTRICT` remains, `DELETE` on `runtime_execution_requests` still raises the immutability error, the other tenant's approval stays `APPROVED` and its authorization stays `ISSUED`, and admission raises `Organization is not ACTIVE`. A simulated crash leaves `DELETION_IN_PROGRESS`, `DISABLED`, and `REVOKED` with no tombstone; the retry completes one tombstone for the original generation and does not restore the first resolver or `ACTIVE`. A legal hold still blocks before any revocation.

## Verdict

P0 referenced-approval deletion is remediated on this branch. **M13 remains OPEN.** M14 is not started. This is not a production deployment and not a protected merge.
