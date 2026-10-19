# M13 Final Red-to-Green Failure Ledger

**Assigned Agent:** Antigravity FORTRESS  
**Role:** Principal Runtime Security Engineer, Recovery Engineer, Integration Debugger  
**Date:** October 19, 2026  
**Milestone:** WhitePact M13  
**Base Candidate:** PR #223 (`codex/whitepact-m13-final-convergence` at `39461fec883aeb18a14f486ba9d65a2c02b20d06`)  
**Corrective Branch:** `antigravity/m13-final-red-to-green`  
**Status:** DRAFT • M13 OPEN • GLOBAL PRODUCTION NO-GO • RELEASE AUTHORIZATION NOT GRANTED

---

## 1. Executive Summary

This failure ledger catalogs all failing CI checks and test suites investigated in the integrated M13 candidate (PR #223). Each issue is categorized by severity (P0 vs P1), root cause, authorized ownership boundary (Antigravity Recovery/Runtime vs Codex Integration/Platform), corrective actions taken, and verified outcomes.

---

## 2. Failure Inventory & Disposition Matrix

| ID | Suite / Test Case | Severity | Category | Ownership | Disposition / Outcome |
|---|---|---|---|---|---|
| **P0-A** | `scripts/engineering/reproducers/test_m13_absolute_runtime.py::test_execute_termination_callback_rejects_plugin_absence_error` | P0 | Runtime / Docker Containment | Antigravity | **FIXED & VERIFIED**. Added authoritative `docker inspect` verification in `_terminate_container()`. Ambiguous plugin/daemon errors fail closed. |
| **P0-B** | `tests/test_inflight_liveness_adversarial.py::test_kill_esrch_unlinks_dead_worker_tracking` | P0 | In-Flight Liveness / Registry | Antigravity | **FIXED & VERIFIED**. Differentiated dead worker liveness for non-container legacy records from unconfirmed container records; scoped tenant scans to tenant prefix; normalized digests to NFC. |
| **P0-C** | `scripts/engineering/reproducers/test_m13_fortress_restore_independent.py::test_tombstone_reconciliation_handles_real_approval_request_fk` | P0 | PostgreSQL Restore / Test Isolation | Antigravity | **FIXED & VERIFIED**. Added autouse `isolated_tracking_environment` fixture to ensure hermetic tracking directories per test. All 3 tests pass on PostgreSQL 16. |
| **P0-D1** | `tests/test_isolation_egress_boundary.py::test_execution_boundary_restore_readiness_failure_rejects_sandbox` | P0 | Recovery Gate / Execution Chokepoint | Antigravity | **FIXED & VERIFIED**. `assert_current_restore_readiness_admitted()` now invokes `assert_restore_readiness_admitted()` to respect test mocks and pre-exec chokepoints. |
| **P0-D2** | `tests/test_isolation_egress_boundary.py::test_execution_boundary_production_same_process_forbidden` | P0 | Isolation Policy / Production Boundary | Antigravity | **FIXED & VERIFIED**. In production without an `IsolationBroker`, same-process tool execution is immediately rejected with `IsolationError`. |
| **P1-01** | `tests/test_m12fs_root_hardening.py` & `test_m13_dual_titan_root.py` (Root WebAuthn UV) | P1 | A2 Security Policy / WebAuthn UV | Codex / Platform | **PRESERVED AS INTENDED**. Root operations require authentic verified WebAuthn User Verification. Must NOT be bypassed. |
| **P1-02** | `tests/independent_m13r2/test_m13r_migration_roundtrip.py::test_0063_upgrade_0064_constraints_and_safe_empty_downgrade` | P1 | Database Migration Schema | Codex / Database | **DIAGNOSED & DISPOSITIONED**. Test asserts Alembic head `0064`, but head `0065` is canonical. Downgrading 0065 is unsafe; test assertion requires Codex update. |
| **P1-03** | `real-customer-journey` (Stage 17: `POST /api/web/api-keys`) | P1 | Customer Journey / Session Auth | Codex / Journey | **DIAGNOSED & DISPOSITIONED**. Stage 17 receives 403 Forbidden because interactive session authentication lacks required owner elevation. |
| **P1-04** | DCO Check (Commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`) | P1 | Repository Compliance | Codex / Author | **DOCUMENTED**. Commit `39619c4b` lacks `Signed-off-by` trailer. Must be rebased/amended with `-s` by Codex. |

---

## 3. Detailed Technical Analyses

### 3.1 P0-A: Runtime Termination Callback & Ambiguous Plugin Absence
- **Test:** `scripts/engineering/reproducers/test_m13_absolute_runtime.py::test_execute_termination_callback_rejects_plugin_absence_error`
- **Symptom:** Mocking `backend._remove_containers` with `return_value=None` bypassed Docker inspection, failing to detect ambiguous Docker daemon/plugin absence errors.
- **Root Cause:** `_terminate_container()` in `src/responsibleai/isolation/container_backend.py` previously called `_remove_containers_uninterruptible()` without an authoritative inspect check when removal returned cleanly.
- **Resolution:** Added explicit `subprocess.run([self.docker_cmd, "inspect", "-f", "{{.State.Status}} {{.State.Running}}", container_name])`. If inspect indicates running/restarting/paused or returns an ambiguous plugin/daemon failure, a `RuntimeError` matching `"inspect"` is raised.
- **Verification:** 4/4 passing in `test_m13_absolute_runtime.py`.

### 3.2 P0-B: In-Flight Remote Worker Liveness vs Container Containment
- **Test:** `tests/test_inflight_liveness_adversarial.py::test_kill_esrch_unlinks_dead_worker_tracking`
- **Symptom:** Dead worker process (`ESRCH`) resulted in `AssertionError: Dead worker must not be reported as active (assert 1 == 0)`.
- **Root Cause:** A dead worker process cannot attest that its container terminated, so modern/container records are retained in `unresolved_remote`. However, pure process records without containers in legacy formats should be unlinked upon worker death. Furthermore, unscoped scans leaked records from other tenants when corrupted files were present.
- **Resolution:**
  1. In `src/responsibleai/isolation/in_flight.py`, differentiated dead worker handling: if the record has no container, is not marked unresolved, and does not start with `trk_v2_`, it is cleanly unlinked. Modern and container records remain unresolved.
  2. Scoped directory scans to tenant-specific prefixes when `organization_id` is supplied.
  3. Relocated registry lock file outside the tracking directory (`directory.parent / f".{directory.name}.lock"`).
  4. Normalized identity digests using Unicode NFC normalization.
- **Verification:** 4/4 in `test_inflight_liveness_adversarial.py`, 20/20 in `test_h1_collision_invariance.py`, 25/25 in `test_h2_linux_containment_adversarial.py`.

### 3.3 P0-C: PostgreSQL Structural Restore Test Isolation
- **Test:** `scripts/engineering/reproducers/test_m13_fortress_restore_independent.py::test_tombstone_reconciliation_handles_real_approval_request_fk`
- **Symptom:** Post-restore reconciliation failed with uncontained remote worker error.
- **Root Cause:** Cross-test filesystem pollution. An earlier test wrote in-flight tracking records to `/tmp/whitepact_inflight`. Test 3 did not isolate `_DISTRIBUTED_REGISTRY_DIR`, causing reconciliation to inspect orphaned tracking files.
- **Resolution:** Added autouse `isolated_tracking_environment` fixture to `test_m13_fortress_restore_independent.py` creating an isolated `tmp_path / "tracking"` directory per test and resetting registry singletons.
- **Verification:** 3/3 passing in 49.07s on PostgreSQL 16.

### 3.4 P0-D: Isolation and Restore Gate Boundary Precedence
- **Tests:** `test_execution_boundary_restore_readiness_failure_rejects_sandbox` & `test_execution_boundary_production_same_process_forbidden`
- **Symptoms:**
  1. Test 1: `Failed: DID NOT RAISE PermissionError` because `execute()` called async `assert_current_restore_readiness_admitted()` which bypassed patched sync `assert_restore_readiness_admitted()`.
  2. Test 2: `RestoreQuarantineError: Operational traffic blocked: system is in FAILED state` raised before reaching production same-process isolation check.
- **Resolution:**
  1. `assert_current_restore_readiness_admitted()` now calls `assert_restore_readiness_admitted()` first, ensuring mocked pre-exec admission chokepoints trigger.
  2. In `InternalToolExecutor.execute()`, added early rejection for production same-process tool execution when broker is absent (`IsolationError`).
- **Verification:** 50/50 passing in `test_isolation_egress_boundary.py`.
