# WHITEPACT — M13 INDEPENDENT RESTORE & MIGRATION SECURITY
## PostgreSQL 16 Authority Re-check, Store B Durability, Revocation Fencing, Schema 0066 Upgrade & Registry Singleton Isolation

**Author:** Antigravity FORTRESS  
**Role:** Independent Principal Security Auditor & Database Recovery Auditor  
**Evaluated Primary Candidate:** PR #223 (`origin/codex/whitepact-m13-final-convergence`)  
**Evaluated Candidate Commit:** `55fcb8015abca2bb8ac94826a30c270bb1c73a49`  
**Subsequent Remote Head:** `d1f6f748b3f296e94505330d1f30a243bf159680`  
**Database Backend:** PostgreSQL 16 (`postgresql+asyncpg://wp:wp@127.0.0.1:55432/postgres`)  
**Ruling:** **QUALIFIED (POSTGRESQL 16, SCHEMA 0066 & STORE B VERIFIED; REGISTRY ISOLATION IDENTIFIED)**  

---

### 1. LIVE RESTORE AUTHORITY & ZERO-LATENCY INVALIDATION (CAMPAIGN C)

Testing on live PostgreSQL 16 evaluated whether any synchronous or asynchronous admission path could admit traffic while an unresolved recovery marker existed:

```
[ Gate Initialized in READY ] ──► [ Query PG: Valid Reconciled ] ──► [ Admission PASS ]
                                                  │
                                                  ▼
                         [ Commit Marker: CONTAINMENT_PENDING ]
                                                  │
                                                  ▼
[ Next Consequential Call: assert_current_traffic_admitted() ] ──► [ FAIL-CLOSED (0ms Staleness) ]
```

#### Test Execution Receipts
1. **Synchronous Execution Denial:** Calling `gate.assert_traffic_admitted()` when a database engine is attached strictly raises:
   ```
   RestoreQuarantineError: Current database authority requires asynchronous admission verification.
   ```
   Synchronous execution paths cannot bypass live database state.
2. **Marker Insertion & Immediate Transition:** Inserting `status = "CONTAINMENT_PENDING"` into `restore_reconciliation_records` immediately caused `await gate.assert_current_traffic_admitted()` to raise:
   ```
   RestoreQuarantineError: Operational traffic blocked: system is in FAILED state.
   ```
   The gate state transitioned to `FAILED` with zero cache staleness.
3. **MCP Tool Interception:** Tool execution through `_call_tool()` checked gate state and returned a structured quarantine response.
4. **Contract Verification:** All 5 tests in `tests/test_m13_closure_pr224_contracts.py` PASSED cleanly against candidate `55fcb801`.

---

### 2. FORENSIC ROOT CAUSE OF RESTORE CI RUNTIME FAILURE

In GitHub Actions workflow `M13 Absolute Runtime Review` (Run ID `39733087713` on commit `55fcb801`):
- `scripts/engineering/reproducers/test_m13_fortress_restore_independent.py::test_tombstone_reconciliation_handles_real_approval_request_fk` failed.

#### Forensic Analysis
1. Test 2 in that module (`test_runtime_canonical_fence_ignores_other_scope`) invoked `epochs.bump("restored-tenant")`.
2. `epochs.bump()` invokes `InFlightExecutionRegistry.get_instance().terminate_in_flight("restored-tenant")`.
3. However, Test 2 had registered its tracking record in a separately constructed registry instance rather than the singleton returned by `get_instance()`.
4. When `terminate_in_flight()` swept the filesystem tracking directory, it encountered the tracking file on disk without an in-memory owner, classifying it as an unmanaged remote worker and setting `_instance._unresolved["execution"] = ...`.
5. In Test 3 (`test_tombstone_reconciliation_handles_real_approval_request_fk`), `reconcile_post_restore` checked tenant `"restored-tenant"`, detected the residual `_unresolved` entry left in the singleton, and failed closed.
6. **Resolution:** Codex resolved this cross-test singleton pollution in commit `890ad7a0` (`test: isolate restore registries and reach contended cleanup phase`). In workflow run `39735888158` on `d1f6f748`, `test_m13_fortress_restore_independent.py` PASSED.

---

### 3. DATABASE RECOVERY & STORE B RESILIENCE (CAMPAIGN E)

The following adversarial recovery conditions were evaluated on PostgreSQL 16:

| Attack Scenario | Injected Condition | Observed Behavior | Security Status |
| :--- | :--- | :--- | :--- |
| **E-01** | Cross-tenant approval reference | Child execution references another tenant's approval ID | Foreign key rejected; transaction rolled back (`851f5288`) | **PASS** |
| **E-02** | Revocation epoch rollback | Store B restores an earlier epoch than current PostgreSQL | Detected by reconciler; rejected fail-closed | **PASS** |
| **E-03** | Tombstone resurrection | Deleted tenant restored from Store B backup | Reconciler marks tenant `DISABLED` with `_RESTORE_QUARANTINED` suffix | **PASS** |
| **E-04** | Partial transaction crash | Process killed midway through multi-stage reconciliation | Database transactions atomic; uncommitted state rolled back | **PASS** |
| **E-05** | Store B cryptographic tampering | Backup file modified on disk (checksum mismatch) | `provider.verify_integrity()` fails; startup evaluates to `UNCERTAIN` / `FAILED` | **PASS** |
| **E-06** | Store B total outage | Store B file deleted or unreadable | Startup evaluates to `UNCERTAIN` / `FAILED`; traffic blocked | **PASS** |
| **E-07** | Concurrent reconciliation | Two workers reconcile the same restored tenant | Database row-level locks serialize workers; single winner | **PASS** |

---

### 4. POSTGRESQL 16 SCHEMA UPGRADE (`0065 → 0066`) & FENCING

In candidate `55fcb801`, Alembic migration `0066_runtime_containment_records.py` introduces:
- Table `runtime_containment_records`: Stores durable execution journals, linking `execution_id`, `tenant_id`, `container_id`, `generation_token`, and `state`.
- Schema Version Fence: `src/responsibleai/db/runtime_compatibility.py` updates `SUPPORTED_POSTGRES_REVISIONS = frozenset({"0066"})`.

#### Tested Schema Guard Behavior
- Upgrading from `0065` to `0066` on PostgreSQL 16 creates `runtime_containment_records` with proper foreign keys and indexes.
- Old application binary expecting `0065` connecting to `0066` raises `RuntimeError("Startup refused: incompatible PostgreSQL schema revision")`.
- New application binary running against `0065` raises `RuntimeError("Startup refused: incompatible PostgreSQL schema revision")`.
- Downgrading `0066` is strictly guarded.

All 13 schema tests across `tests/test_m13_convergence3_schema_contract.py`, `tests/test_m13_convergence3_schema_postgres.py`, and `tests/test_m13_runtime_schema_compatibility.py` pass across Python 3.11 and 3.12.
