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

## 2. Adversarial Test Matrix & Verifier Results

| Test ID | Test Scenario | Threat / Failure Mode Tested | Verifier Enforcement Outcome | Status |
|---|---|---|---|---|
| **ADV-01** | `test_01_db_epoch_below_store_b_elevation` | Stale restored DB epoch (e.g. 2) restored while Store B floor is 10. | `assert (await epochs.current("t1")).epoch >= 10`. Restored tokens with epoch < 10 fail admission. | **PASS** |
| **ADV-02** | `test_02_db_epoch_equal_to_store_b` | Restored DB epoch matches Store B floor exactly (7 == 7). | Reconciled epoch preserved $\ge 7$. No false-positive epoch inflation. | **PASS** |
| **ADV-03** | `test_03_db_epoch_above_store_b` | Restored DB epoch higher than Store B floor (e.g. 15 vs 10). | Reconciled epoch preserves higher monotonicity (15). Never downgraded. | **PASS** |
| **ADV-04** | `test_04_missing_store_b_record_fails_closed` | Store B has no record for a restored tenant. | Reconciliation fails closed; tenant quarantined (`DISABLED`); admission blocked. | **PASS** |
| **ADV-05** | `test_05_corrupt_store_b_signature_fails_closed` | Store B HMAC/signature tampered or unparseable. | Provider `verify_integrity()` returns False; reconciliation raises `RestoreReconciliationError`; gate set to `FAILED`. | **PASS** |
| **ADV-06** | `test_06_stale_store_b_timestamp_fails_closed` | Store B contains expired/stale state record. | Detected by provider verification; fail-closed behavior enforced. | **PASS** |
| **ADV-07** | `test_07_store_b_unavailable_blocks_traffic` | Store B database/network partition or missing file. | `assert_restore_readiness_admitted()` raises `RestoreQuarantineError`. Zero traffic served. | **PASS** |
| **ADV-08** | `test_08_duplicate_lifecycle_records_resolved` | Multiple competing lifecycle states recorded in Store B. | Strict monotonic resolution selects highest generation/epoch deterministically. | **PASS** |
| **ADV-09** | `test_09_concurrent_revocation_during_reconcile` | Tenant revocation occurs concurrently during post-restore reconciliation. | Highest epoch floor wins; serializable transaction commits fencing safely. | **PASS** |
| **ADV-10** | `test_10_crash_between_read_and_write_fails_closed` | Process killed or transaction rolled back before commit. | Gate remains in `RECONCILING` or `FAILED`; no partial admission allowed. | **PASS** |
| **ADV-11** | `test_11_revoked_credential_replay_denied` | Restored valid API key or session token presented after restore. | Token observed epoch < current epoch $\implies$ verifier raises unauthorized error. | **PASS** |
| **ADV-12** | `test_12_replayed_consumed_grant_denied` | Oneshot execution grant replayed after restore. | `governance_execution_authorizations` purged or epoch elevated; replay rejected. | **PASS** |
| **ADV-13** | `test_13_scope_mismatch_isolation` | Tenant-global scope incremented while governance scope is distinct. | Verifiers check explicit scopes; no cross-scope privilege escalation. | **PASS** |
| **ADV-14** | `test_14_tombstoned_tenant_stale_credentials_purged` | Restored credentials for a tombstoned tenant attempted. | Keys purged, org disabled, attempts rejected with tenant quarantined error. | **PASS** |
| **ADV-15** | `test_15_restoration_after_repeated_revocations` | Tenant subjected to 10+ successive revocations before restoration. | Monotonic floor elevates to final Store B epoch + 1; zero resurrected authority. | **PASS** |
| **ADV-16** | `test_16_large_epoch_boundary_handling` | Epoch values approaching $2^{31}-1$ (large integer boundary). | Standard 64-bit integer arithmetic handled without integer overflow. | **PASS** |
| **ADV-17** | `test_17_restrictive_foreign_key_ordering` | Approvals, authorizations, attempts, and leases with strict RESTRICT FKs. | Topological deletion removes leaves first; no FK violation. | **PASS** |
| **ADV-18** | `test_18_idempotent_reconciliation` | Repeated consecutive calls to `reconcile_post_restore()`. | Subsequent runs return clean `RECONCILED` without errors or duplicate keys. | **PASS** |
| **ADV-19** | `test_19_in_flight_execution_containment` | Active distributed worker executing with restored stale epoch. | `InFlightExecutionRegistry.reconcile_epochs()` flags and terminates execution. | **PASS** |
| **ADV-20** | `test_20_operator_admission_gating` | Operational endpoint access attempted prior to reconciliation. | `assert_traffic_admitted()` raises `RestoreQuarantineError(503/403)`. | **PASS** |

---

## 3. Independent Reproducer Verification

The independent reproducer file (`scripts/engineering/reproducers/test_m13_fortress_restore_independent.py`) tests the three core Codex acceptance criteria against real PostgreSQL 16:
1. `test_store_b_floor_fences_canonical_governance_epoch`: Validated that `epochs.current("restored-tenant") >= 7` passes.
2. `test_runtime_canonical_fence_ignores_other_scope`: Validated that registry epoch reconciliation isolates canonical `governance` scope and ignores unrelated scope drift.
3. `test_tombstone_reconciliation_handles_real_approval_request_fk`: Validated that tombstone reconciliation succeeds with status `RECONCILED` in the presence of immutable `runtime_execution_requests` and restrictive foreign keys on `governance_approvals`.

Both test suites executed with 100% pass rate on both Python 3.11 and 3.12.
