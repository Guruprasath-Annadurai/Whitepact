# WHITEPACT — M13 INDEPENDENT ORIGINAL TEST DISPOSITIONS
## Forensic Review of Protected Test Provenance, Conflicting Specifications & Formal Maintainer Dispositions

**Author:** Antigravity FORTRESS  
**Role:** Independent Principal Security Auditor & Reliability Lead  
**Evaluated Commit:** `bff5f143933d518e921592361f0171d7cf7ff6ef`  
**Base Commit:** `39461fec463768b2aa0dfa7bfe423fb886e012ec`  
**Ruling:** **FORMAL DISPOSITION PACKAGE PREPARED FOR MAINTAINER APPROVAL**  

---

### 1. SUMMARY OF HISTORICAL TEST CONFLICTS

During M13 convergence, eight specific historical test expectations were identified where original assertions conflicted with production reality, container runtime isolation, or database integrity:

```
[ Conflict Identified ] ──► [ Execute Unchanged Baseline ] ──► [ Forensic Root Cause ]
                                                                      │
                                                                      ▼
[ Formulate Safe Security Contract ] ◄── [ Assess Maintainer Approval Requirement ]
```

---

### 2. DETAILED TEST-BY-TEST DISPOSITION RECORD

#### 1. Dead-Worker ESRCH Tracking Unlink
- **File & Location:** `tests/test_inflight_liveness_adversarial.py::test_kill_esrch_unlinks_dead_worker_tracking`
- **Original Commit:** `39461fec463768b2aa0dfa7bfe423fb886e012ec`
- **Original Assertion:** `assert not file_path.exists()` on `ProcessLookupError` (ESRCH).
- **Security Analysis:** In containerized runtimes (Docker/Kubernetes), host worker process exit does NOT prove container death. Unlinking the file allows detached containers to escape tracking.
- **Current Contract:** Dead workers must retain their tracking records marked `Worker exited; containment unconfirmed`.
- **Disposition:** **OBSOLETE & UNSAFE.** Formally update assertion to verify file retention and unconfirmed status. Maintainer approval required.

#### 2. Unicode NFC Tenant ID Equivalence
- **File & Location:** `tests/test_h1_collision_invariance.py::test_10`
- **Original Commit:** `39461fec463768b2aa0dfa7bfe423fb886e012ec`
- **Original Assertion:** `assert _tracking_filename(nfc) == _tracking_filename(nfd)`
- **Security Analysis:** Relational databases treat raw UTF-8 bytes as distinct primary keys (`café` vs `cafe\u0301`). Normalizing tenant IDs creates cross-tenant tracking collisions.
- **Current Contract:** Hashing exact raw UTF-8 bytes with domain separation (`WP-INFLIGHT-V2-TENANT\x00`).
- **Disposition:** **UNSAFE.** Discard NFC equality assertion; enforce distinct tracking digests for distinct raw strings. Maintainer approval required.

#### 3. Restored Tenant Status: QUARANTINED vs DISABLED
- **File & Location:** `tests/test_h4_backup_recovery_adversarial.py:460`
- **Original Commit:** `39461fec463768b2aa0dfa7bfe423fb886e012ec`
- **Original Assertion:** `assert org.governance_status == "QUARANTINED"`
- **Security Analysis:** PostgreSQL Migration `0049` enforces constraint `chk_org_governance_status CHECK (governance_status IN ('ACTIVE', 'SUSPENDED', 'DISABLED'))`. Inserting `"QUARANTINED"` triggers a `CheckViolation` SQL error.
- **Current Contract:** Reconciler sets `governance_status = "DISABLED"` and appends `_RESTORE_QUARANTINED` to `org.name`.
- **Disposition:** **OBSOLETE SPECIFICATION.** Update test to assert `org.governance_status == "DISABLED"` and name suffix. Maintainer approval required.

#### 4. Container Cleanup Receipt Semantics
- **File & Location:** `tests/test_docker_ownership_regression.py::test_repeated_sequential_timeout_soak`
- **Original Commit:** `47fc55a1591890f18c06333b4f187d091535719d`
- **Original Assertion:** Unconditionally raises `RuntimeError("Docker creation completion unconfirmed")` when `creation_settled` is false, regardless of whether `_remove_containers` confirmed absence.
- **Security Analysis:** Causes false-unsettled registry contamination on sub-second timeouts, denying admission to subsequent iterations.
- **Current Contract:** If `_remove_containers` verified 3.0s continuous absence and client process is dead, containment is proven.
- **Disposition:** **DEFECTIVE ASSERTION.** Implement creation-settled guard improvement.

#### 5. Plugin-Absence Assertion & Mocked Absence Loop
- **File & Location:** `scripts/engineering/reproducers/test_m13_absolute_runtime.py::test_execute_termination_callback_rejects_plugin_absence_error`
- **Original Commit:** `e7e24dee0c828bbbe8c08db6e519aedf3cc0a0d2`
- **Original Mechanism:** Mocked `_remove_containers` to `return_value=None`, then asserted that `_terminate_container()` failed.
- **Security Analysis:** Artificial test mock that removed production absence checks, generating a false positive P0 diagnosis.
- **Current Contract:** Unmocked `_remove_containers()` already catches plugin errors and raises `RuntimeError`.
- **Disposition:** **INVALID REPRODUCER.** Retire mock-only test; retain unmocked negative fault injection suite.

#### 6. Root/WebAuthn Historical Fixtures
- **File & Location:** `tests/test_sovereign_authority.py`
- **Original Commit:** Pre-A2 baseline
- **Original Mechanism:** Allowed static API keys or unverified caller flags in test environments.
- **Current Contract:** Mandatory user verification (`uv=True`), single-use nonces, and cryptographic proof of possession.
- **Disposition:** **FORMALLY SUPERSEDED.** All tests now run against strict sovereign WebAuthn policies.

#### 7. Migration 0064 Expectations vs Revision 0065
- **File & Location:** `migrations/versions/0064_authority_security_contract_tables.py`
- **Current Contract:** Extended by revision `0065_bootstrap_require_passkey_stepup.py` with downgrade protection.
- **Disposition:** **BINDING.** Revision `0065` is active and enforced by `assert_runtime_schema_compatible()`.

#### 8. Restore Admission Synchronous Hook
- **File & Location:** `src/responsibleai/data_governance/backup_defense.py:773`
- **Contested Hunk:** PR #224's `and self._db_authority_status != "RECONCILED"`.
- **Security Analysis:** Allowed stale synchronous admission when database persisted an un-reconciled failure.
- **Current Contract:** Strict asynchronous enforcement whenever `_db_engine` is configured.
- **Disposition:** **UNSAFE HUNK EXCLUDED.** Codex's strict async requirement upheld.

---

### 3. RECOMMENDATIONS FOR FOUNDER / MAINTAINER

Antigravity FORTRESS recommends formal maintainer sign-off on the specification updates for Conflicts 1, 2, and 3, aligning historical test expectations with production PostgreSQL constraints and container isolation invariants.
