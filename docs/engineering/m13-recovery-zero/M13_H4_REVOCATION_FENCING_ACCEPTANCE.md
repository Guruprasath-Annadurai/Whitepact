# M13-H4 REVOCATION FENCING AND ADVERSARIAL ACCEPTANCE REPORT
**Subsystem:** H4 Backup, Disaster Recovery & Authority Reconciliation  
**Target:** Operation M13 Recovery Zero  
**Date:** 2026-10-19  
**Security Classification:** P0 Critical  
**Author:** Antigravity FORTRESS Lead  

---

## 1. Acceptance Scope & Test Harness

This document records the adversarial validation of the post-restore revocation fencing subsystem across real PostgreSQL 16 and SQLite backends using `tests/test_h4_backup_recovery_adversarial.py` and `scripts/engineering/reproducers/test_m13_fortress_restore_independent.py`.

All 20 adversarial tests in `test_h4_backup_recovery_adversarial.py` and all 3 independent reproducer tests passed cleanly with zero skips and zero failures across both Python 3.11 and Python 3.12.

---

## 2. Adversarial Test Matrix (ADV-01 through ADV-20)

The 20 adversarial scenarios implemented in `tests/test_h4_backup_recovery_adversarial.py` directly validate disaster recovery, cryptographic integrity, tenant isolation, and containment fencing:

| Test ID | Actual Test Function | Threat / Failure Mode Tested | Verifier Enforcement Outcome | Status |
|---|---|---|---|---|
| **ADV-01** | `test_01_complete_database_restoration_from_cold_backup` | Cold backup restoration integrity to fresh database instance. | Restored DB fully queryable; `verify_chain("org-cold-1") is True`. | **PASS** |
| **ADV-02** | `test_02_selective_single_tenant_restoration` | Selective single-tenant restore wipes and restores tenant A. | Tenant B evidence chain intact during and after tenant A restore. Zero cross-tenant leakage. | **PASS** |
| **ADV-03** | `test_03_restored_database_stale_revocation_epoch_advanced` | Restored DB backup has stale revocation epoch (2) vs Store B floor (7). | `reconcile_post_restore()` elevates Store A epoch to 7; stale grants blocked. | **PASS** |
| **ADV-04** | `test_04_restored_database_replayed_nonces_rejected` | Replay of previously consumed execution nonce after restore. | Primary key constraint on `governance_execution_nonces` rejects duplicate nonce. | **PASS** |
| **ADV-05** | `test_05_evidence_chain_verification_after_restore` | Evidence hash chain consistency across 5 sequentially chained records. | `verify_chain(org_id) is True`; cryptographic head and parent links unbroken. | **PASS** |
| **ADV-06** | `test_06_witness_publication_divergence_detected` | DB rolled back to sequence 1 while external witness published sequence 2. | `verify_published_head()` raises `WitnessPublicationError("database head rolled back behind the publication")`. | **PASS** |
| **ADV-07** | `test_07_active_container_detected_and_fenced` | Active container running when DB restored to earlier state. | Registry detects in-flight container, invokes termination callback, confirms containment. | **PASS** |
| **ADV-08** | `test_08_concurrent_execution_during_backup_snapshot` | 10 concurrent execution appends during database backup snapshot. | All 10 records committed; post-restore evidence chain valid. | **PASS** |
| **ADV-09** | `test_09_restoration_onto_fresh_instance` | Cold restore onto freshly initialized instance with empty state. | Readiness gate passes admission (`is_admitted() is True`, status `RECONCILED`). | **PASS** |
| **ADV-10** | `test_10_key_rotation_after_backup_before_restore` | Witness key rotated after backup but prior to disaster recovery. | Current key advances; historical public keys preserved for forensic validation. | **PASS** |
| **ADV-11** | `test_11_restored_deleted_tenant_quarantined_and_authority_purged` | Restored tenant was tombstoned in Store B before backup. | Tenant quarantined (`DISABLED`, `RESTORE_QUARANTINED` name suffix); API keys and delegations erased. | **PASS** |
| **ADV-12** | `test_12_cross_tenant_isolation_preserved_across_backup` | Shared backup archive contains multiple tenants. | Evidence query for tenant Beta scoped to tenant Alpha returns `None`. Cross-tenant isolation enforced. | **PASS** |
| **ADV-13** | `test_13_corrupted_backup_archive_detected` | Corrupted / non-database archive header or payload supplied to restore engine. | Database connection and query execution aborts with error; zero corrupted data admitted. | **PASS** |
| **ADV-14** | `test_14_incomplete_restore_fail_closed` | Store B provider unavailable or network partitioned during restore reconciliation. | `reconcile_post_restore()` raises `RestoreReconciliationError`; gate set to `FAILED`; traffic blocked. | **PASS** |
| **ADV-15** | `test_15_post_restore_in_flight_executions_fail_closed` | Pre-restore in-flight execution running under epoch 2 when Store B has floor 5. | Registry marks epoch 2 as revoked (`is_revoked(admission_epoch=2) is True`); new runs admitted. | **PASS** |
| **ADV-16** | `test_16_unenforced_restored_policy_cannot_override_authority` | Restored DB policy exists but runtime authority context lacks action grant. | `WhitePactRuntimeGateway().evaluate()` denies action (`GovernanceDecision.DENY`). Authority invariants prevail. | **PASS** |
| **ADV-17** | `test_17_root_authority_continuity_after_dr` | Root authority delegation chain survives disaster recovery failover. | Root authority record preserved in Store A; `ENTERPRISE_ROOT` authority intact. | **PASS** |
| **ADV-18** | `test_18_split_brain_epoch_conflict_detected` | Competing region attempts to record older epoch 3 over current epoch 5 in Store B. | `LifecycleRollbackError("Security epoch rollback rejected")` raised; split-brain aborted. | **PASS** |
| **ADV-19** | `test_19_witness_log_continuity_across_disaster_recovery` | Append-only witness log continuity across disaster recovery. | Unbroken monotonic sequence walk over witness log entries. | **PASS** |
| **ADV-20** | `test_20_audit_evidence_reconciliation_validates_complete_history` | Audit evidence chain verified against tamper-evident store post-DR. | `verify_chain_status(org_id)` returns `VALID`; audit history verified intact. | **PASS** |

---

## 3. Dedicated P0 Recovery Zero Test Matrix

Implemented in `tests/test_m13_recovery_zero_p0_reproducers.py` against real PostgreSQL 16:

| Test ID | Test Function | Target Vulnerability / Invariant | Result | Status |
|---|---|---|---|---|
| **P0-C01** | `test_reproducer_containment_terminate_in_flight_raises_blocks_ready` | `terminate_in_flight()` exception swallowed into `READY`. | Gate moves to `FAILED`; `RestoreReconciliationError` raised. | **PASS** |
| **P0-C02** | `test_reproducer_unconfirmed_container_termination_blocks_ready` | Callback returns False (unconfirmed termination). | Gate moves to `FAILED`; unconfirmed container blocks `READY`. | **PASS** |
| **P0-C03** | `test_reproducer_reconcile_epochs_raises_blocks_ready` | `reconcile_epochs()` raises database connectivity error. | Gate moves to `FAILED`; zero false-positive claims of containment. | **PASS** |
| **P0-C04** | `test_reproducer_detached_alive_container_blocks_ready` | Detached container process remains alive on host/worker. | Pre-existing unresolved container detected; gate moves to `FAILED`. | **PASS** |
| **P0-C05** | `test_reproducer_corrupted_registry_directory_blocks_ready` | Corrupt or unparseable tracking JSON file in registry directory. | File unreadable $\implies$ containment unconfirmed $\implies$ gate `FAILED`. | **PASS** |
| **P0-C06** | `test_reproducer_unresolved_legacy_execution_blocks_ready` | Unattributed legacy execution remains in tracking directory. | Unattributed unresolved execution detected; gate moves to `FAILED`. | **PASS** |
| **P0-SB01** | `test_reproducer_store_a_active_org_missing_from_store_b_fails_closed` | Store A contains ACTIVE org missing from authoritative Store B. | Tenant quarantined (`DISABLED`); admission blocked; gate `FAILED`. | **PASS** |
| **P0-SB02** | `test_reproducer_sibling_tenant_isolation_under_store_b` | Cross-tenant mutation from sibling Store B records. | Sibling tenant epochs isolated; non-existent Store B tenants ignored. | **PASS** |
| **P0-SB03** | `test_reproducer_corrupt_and_stale_store_b_records` | Stale epoch downgrade and corrupt provider HMAC integrity. | Lower epoch ignored (monotonic); corrupt provider marks gate `FAILED`. | **PASS** |
| **P0-VER01** | `test_reproducer_credential_fencing_matrix_full_verification` | `Phase7AAuthorityKernel` verifier testing across 7 DR scenarios. | Full 7-scenario matrix verified: valid unrevoked admits; epoch mismatch, tombstone, consumed grant, and stale auth strictly rejected. | **PASS** |

---

## 3. Independent Reproducer Verification

The independent reproducer file (`scripts/engineering/reproducers/test_m13_fortress_restore_independent.py`) tests the three core Codex acceptance criteria against real PostgreSQL 16:
1. `test_store_b_floor_fences_canonical_governance_epoch`: Validated that `epochs.current("restored-tenant") >= 7` passes.
2. `test_runtime_canonical_fence_ignores_other_scope`: Validated that registry epoch reconciliation isolates canonical `governance` scope and ignores unrelated scope drift.
3. `test_tombstone_reconciliation_handles_real_approval_request_fk`: Validated that tombstone reconciliation succeeds with status `RECONCILED` in the presence of immutable `runtime_execution_requests` and restrictive foreign keys on `governance_approvals`.

Both test suites executed with 100% pass rate on both Python 3.11 and 3.12.
