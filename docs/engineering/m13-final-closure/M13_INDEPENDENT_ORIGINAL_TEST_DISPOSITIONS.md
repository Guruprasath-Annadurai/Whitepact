# WHITEPACT — M13 INDEPENDENT ORIGINAL TEST DISPOSITIONS
## Forensic Review of Protected Test Provenance, Conflicting Specifications, Formal Founder Approval & Commit 84710b8d Integration

**Author:** Antigravity FORTRESS  
**Role:** Independent Principal Security Auditor & Reliability Lead  
**Evaluated Primary Candidate:** PR #223 (`origin/codex/whitepact-m13-final-convergence`)  
**Evaluated Candidate Commit:** `55fcb8015abca2bb8ac94826a30c270bb1c73a49`  
**Subsequent Remote Head:** `d1f6f748b3f296e94505330d1f30a243bf159680`  
**Ruling:** **FORMAL DISPOSITIONS INTEGRATED IN COMMIT 84710b8d & FULLY VERIFIED**  

---

### 1. SUMMARY OF HISTORICAL TEST CONFLICTS

During M13 convergence, eight specific historical test expectations were identified where original assertions conflicted with production reality, container runtime isolation, or database integrity.

In commit `84710b8d` (`test: incorporate founder-approved dispositions for conflicting assertions`), Codex formally incorporated the founder-approved dispositions into PR #223.

---

### 2. DETAILED TEST-BY-TEST DISPOSITION RECORD

#### 1. Dead-Worker ESRCH Tracking Retention
- **File & Location:** `tests/test_inflight_liveness_adversarial.py::test_kill_esrch_unlinks_dead_worker_tracking`
- **Original Assertion:** `assert not file_path.exists()` on `ProcessLookupError` (ESRCH).
- **Security Analysis:** In containerized runtimes (Docker/Kubernetes), host worker process exit does NOT prove container death. Unlinking the file allows detached containers to escape tracking.
- **Current Contract:** Dead workers must retain their tracking records marked `Worker exited; containment unconfirmed`.
- **Disposition:** Formally updated in `84710b8d` to verify tracking retention and unconfirmed status. Verified in `tests/test_m13_closure_pr224_contracts.py`.

#### 2. Unicode NFC vs Raw Byte Tenant ID Invariance
- **File & Location:** `tests/test_h1_collision_invariance.py::test_10`
- **Original Assertion:** `assert _tracking_filename(nfc) == _tracking_filename(nfd)`
- **Security Analysis:** Relational databases treat raw UTF-8 bytes as distinct primary keys (`café` vs `cafe\u0301`). Normalizing tenant IDs creates cross-tenant tracking collisions.
- **Current Contract:** Hashing exact raw UTF-8 bytes with domain separation (`WP-INFLIGHT-V2-TENANT\x00`).
- **Disposition:** NFC equality assertion replaced with exact raw byte digest verification. Verified in `tests/test_m13_closure_pr224_contracts.py`.

#### 3. Restored Tenant Status: QUARANTINED vs DISABLED
- **File & Location:** `tests/test_h4_backup_recovery_adversarial.py:460`
- **Original Assertion:** `assert org.governance_status == "QUARANTINED"`
- **Security Analysis:** PostgreSQL Migration `0049` enforces constraint `chk_org_governance_status CHECK (governance_status IN ('ACTIVE', 'SUSPENDED', 'DISABLED'))`. Inserting `"QUARANTINED"` triggers a `CheckViolation` SQL error.
- **Current Contract:** Reconciler sets `governance_status = "DISABLED"` and appends `_RESTORE_QUARANTINED` to `org.name`.
- **Disposition:** Updated to assert `org.governance_status == "DISABLED"` and `_RESTORE_QUARANTINED` suffix. Verified in `tests/test_m13_closure_pr224_contracts.py`.

#### 4. Container Creation & Timeout Soak Protocol
- **File & Location:** `tests/test_docker_ownership_regression.py::test_repeated_sequential_timeout_soak`
- **Original Behavior:** Single-phase `docker run` timeout raised ambiguous creation settlement.
- **Current Contract:** Two-phase deterministic creation protocol (`docker create` followed by CID write and `docker start`).
- **Disposition:** Implemented in `55fcb801`. Timeout soak passes reliably without false registry contamination.

#### 5. Plugin-Absence Assertion & Mocked Absence Loop
- **File & Location:** `scripts/engineering/reproducers/test_m13_absolute_runtime.py::test_execute_termination_callback_rejects_plugin_absence_error`
- **Original Mechanism:** Mocked `_remove_containers` to `return_value=None`, then asserted that `_terminate_container()` failed.
- **Current Contract:** Production `_remove_containers()` already catches plugin errors and raises `RuntimeError`.
- **Disposition:** Retired mock reproducer in favor of real native Docker fault injection suite.

#### 6. Root/WebAuthn Session Verification
- **File & Location:** `scripts/engineering/reproducers/test_m13_dual_titan_root.py`
- **Original Mechanism:** Test helper constructed `Actor(...)` without `session_id`.
- **Current Contract:** Mandatory WebAuthn user verification session strictly enforced by `require_recent_owner()`.
- **Disposition:** Updated test helper annotation in commit `d62f0925` to supply valid session ID.

#### 7. PostgreSQL Schema Compatibility Fence: Schema 0066
- **File & Location:** `src/responsibleai/db/runtime_compatibility.py`
- **Current Contract:** `SUPPORTED_POSTGRES_REVISIONS = frozenset({"0066"})`.
- **Disposition:** Strict operational fence active. All older revisions (0064, 0065) and downgrade attempts fail closed.

#### 8. Restore Admission Asynchronous Hook
- **File & Location:** `src/responsibleai/data_governance/backup_defense.py:773`
- **Contested Hunk:** PR #224's synchronous bypass hook excluded.
- **Current Contract:** Strict asynchronous enforcement whenever `_db_engine` is configured.
- **Disposition:** Unsafe bypass permanently rejected; strict async verification maintained.

---

### 3. CONCLUSION

All founder-approved dispositions have been formally incorporated and verified across Python 3.11 and Python 3.12. No conflicting specifications remain in active production code.
