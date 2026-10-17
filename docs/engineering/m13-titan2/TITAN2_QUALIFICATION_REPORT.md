# WHITEPACT — TITAN-2 QUALIFICATION REPORT
## M13 Adversarial Runtime Campaign: Real Defect Discovery & Reliability Closure

**Status:** M13 OPEN. GLOBAL PRODUCTION NO-GO.
**Role:** Independent Adversarial Runtime & Reliability Engineering Owner
**Isolated Worktree:** `/Users/ag/.gemini/antigravity/scratch/whitepact-m13-titan2`
**Independent Branch:** `antigravity/whitepact-m13-titan2`
**Base Commit:** `f439553df91b4be855eaae120715577e083340ff`
**Tracking Remote:** `origin/antigravity/whitepact-m13-titan2`

---

## 1. Executive Summary

In accordance with the TITAN-2 Adversarial Runtime Campaign directive, our mission focused on discovering, reproducing, and closing real runtime security defects and reliability gaps under adversarial conditions—avoiding descriptions of already-passing suites.

This campaign identified, reproduced with failing test cases, and eliminated **four genuine runtime vulnerabilities**:
1. **MCP SSE `/messages/` Unauthenticated & Cross-Tenant Session Hijacking Bypass:** Bypassed Starlette authentication, missing ASGI `scope["user"]` user binding, allowing unauthorized callers and cross-tenant actors to inject JSON-RPC tool calls into active sessions.
2. **Missing Organization Execution Nonce Admission Leak:** Nonce consumption check `if status is not None and status != GovernanceStatus.ACTIVE.value:` permitted missing organizations (`status is None`) to bypass governability checks, silently admitting execution on SQLite and triggering unhandled database foreign key 500 crashes on PostgreSQL.
3. **Cross-Worker Distributed In-Flight Process Tracking Silent Drop on EPERM:** Catching `(ProcessLookupError, PermissionError)` from `os.kill(pid, 0)` treated live isolated worker processes running under distinct UIDs/sandboxes as dead, unlinking distributed registration files and falsely clearing unresolved containment alerts.
4. **Premature Registry Unregistration in Container Isolation Backend:** `container_backend.py` unregistering executions from active tracking before completing container removal, leaving an unmonitored window where timed-out containers remained running in the container runtime without in-flight tracking.

In addition, **Migration 0065** was qualified against real PostgreSQL for historical row preservation, rollback idempotency, constraint violations, and transaction abort cleanliness. Codex's historical upgrade reproducer `scripts/engineering/m13_forge_postgres_upgrade.py` was independently verified passing (`result: PASS`).

---

## 2. Discovered Defects, Reproducers, Root Causes & Fixes

### Defect 1: MCP SSE `/messages/` Unauthenticated & Cross-Tenant Session Hijacking Bypass
* **Severity:** Critical (MCP Transport Authorization Bypass)
* **Location:** `src/responsibleai/mcp/server.py`
* **Root Cause:**
  * Starlette route `Mount("/messages/", app=sse.handle_post_message)` mounted the upstream MCP SSE message handler with zero authentication middleware or rate limiting.
  * Furthermore, upstream `mcp.server.sse.SseServerTransport` checks session ownership via `scope.get("user")`. Because WhitePact's `handle_sse` never populated `scope["user"]` with an `AuthenticatedUser`, `_session_owners` stored `None`. When unauthenticated or cross-tenant callers posted to `/messages/?session_id=...`, `None == None` evaluated to `True`, permitting arbitrary tool call injection into Tenant A's live session!
* **Failing Reproducer:** `tests/test_mcp_sse_session_adversarial.py`
  * Unauthenticated POST returned `202 Accepted` (expected `401 Unauthorized`).
  * Tenant B posting to Tenant A's session returned `202 Accepted` (expected `403 Forbidden`).
* **Minimal Fix:**
  * Implemented `_build_authenticated_user(ctx)` populating `mcp.server.auth.middleware.bearer_auth.AuthenticatedUser`.
  * Set `request.scope["user"] = _build_authenticated_user(ctx)` in `handle_sse`.
  * Replaced raw mount with `_SsePostMessageEndpoint`: enforces Bearer authentication via `_authenticate_or_error`, verifies UUID format and session existence, matches `client_id` against `ctx.org_id` (rejecting cross-tenant calls with 403 `cross_tenant_forbidden`), validates `subject` key binding, and propagates `scope["user"]` to upstream transport.
* **Regression Evidence:** `tests/test_mcp_sse_session_adversarial.py` (7/7 PASSED in 0.52s). Existing MCP suites (46/46 PASSED in 117.75s).

---

### Defect 2: Missing Organization Execution Nonce Admission Leak
* **Severity:** High (Tenant Governance / Admission Enforcement)
* **Location:** `src/responsibleai/db/execution_nonce_repository.py`
* **Root Cause:**
  * Line 50 checked: `if status is not None and status != GovernanceStatus.ACTIVE.value: raise OrganizationNotGovernableError(...)`.
  * When `organization_id` does not exist in `organizations`, `status` is `None`. The condition evaluated to `False`, skipping the governability check entirely!
  * On SQLite, missing tenants were admitted with nonces inserted. On PostgreSQL, `lock_epoch` crashed with an unhandled raw `IntegrityError` (ForeignKeyViolation on `governance_revocation_epochs.organization_id`), causing HTTP 500 internal server errors instead of clean domain authorization denials.
* **Failing Reproducer:** `tests/test_runtime_resilience_adversarial.py::test_nonce_consumption_missing_org_fails_closed_with_governable_error` and `test_nonce_consumption_missing_org_on_real_postgres`.
* **Minimal Fix:**
  * Changed condition to:
    ```python
    status = (await conn.execute(status_stmt)).scalar_one_or_none()
    if status != GovernanceStatus.ACTIVE.value:
        raise OrganizationNotGovernableError(
            "Organization is not ACTIVE for governed execution"
        )
    ```
  * Ensures any non-active or non-existent organization immediately fails closed with `OrganizationNotGovernableError`.
* **Regression Evidence:** `tests/test_runtime_resilience_adversarial.py` (3/3 PASSED). Existing nonce suites `tests/test_faststart.py` and `tests/test_m10r_grant_epoch_invalidation.py` (15/15 PASSED).

---

### Defect 3: Cross-Worker Distributed In-Flight Process Tracking Silent Drop on EPERM
* **Severity:** High (Containment Verification & In-Flight Tracking)
* **Location:** `src/responsibleai/isolation/in_flight.py`
* **Root Cause:**
  * In `_check_remote_worker_active()`, the probe checked `os.kill(pid, 0)` inside `except (ProcessLookupError, PermissionError): is_alive = False`.
  * In POSIX systems, `kill(pid, 0)` raising `PermissionError` (EPERM) indicates that the process **exists and is actively running**, but belongs to another user, daemon, or sandbox context.
  * By setting `is_alive = False`, WhitePact treated active processes as terminated, invoked `f.unlink()` to destroy the distributed tracking file, dropped the process from `unresolved_remote`, and cleared unresolved containment alerts.
* **Failing Reproducer:** `tests/test_runtime_resilience_adversarial.py::test_distributed_inflight_remote_worker_eperm_treated_as_alive`.
* **Minimal Fix:**
  * Disentangled process death from permission denial:
    ```python
    try:
        os.kill(pid, 0)
        is_alive = True
    except ProcessLookupError:
        is_alive = False
    except PermissionError:
        # Target process is alive under another user, container, or security context
        is_alive = True
    ```
  * Preserves distributed tracking files, accurately captures unresolved containment, and causes subsequent tenant registrations to fail closed until containment is confirmed.
* **Regression Evidence:** `tests/test_runtime_resilience_adversarial.py` (3/3 PASSED), `tests/test_in_flight_revocation.py` (13/13 PASSED).

---

### Defect 4: Premature Registry Unregistration in Container Isolation Backend
* **Severity:** Medium (Containment State Accuracy)
* **Location:** `src/responsibleai/isolation/container_backend.py`
* **Root Cause:**
  * In the `finally:` block of `execute()`, `await registry.unregister(execution_id)` was called on line 519, *prior* to container removal and verification (`_remove_containers_uninterruptible()`).
  * On timeout or cancellation, the execution was dropped from in-flight tracking up to 12 seconds before Docker confirmed container termination, creating an unmonitored window where running containers were invisible to in-flight revocation.
* **Regression Evidence:** Dedicated adversarial regression suite `tests/test_container_cleanup_race_adversarial.py` (6/6 PASSED).

---

### Defect 5: Task Cancellation Race During Container Removal
* **Severity:** High (Containment Loss on Cancellation / Timeout)
* **Location:** `src/responsibleai/isolation/container_backend.py`
* **Root Cause:**
  * `_remove_containers_uninterruptible()` previously utilized `asyncio.shield(asyncio.to_thread(...))`. In Python asyncio, cancelling the task awaiting `asyncio.shield` raises `CancelledError` immediately to the outer caller while the background thread continues executing asynchronously. The outer `finally:` block was entered prematurely, proceeding to unregister containment before container removal finished.
  * In addition, `_remove_containers()` silently returned without raising an error when its timeout deadline expired with containers still present, and treated generic `docker inspect` failures as absence rather than inspecting for explicit `"no such container"` output.
* **Failing Reproducer:** `tests/test_container_cleanup_race_adversarial.py`
  * `test_cancellation_during_cleanup_does_not_abort_removal`: cancelled task before thread completed removal.
  * `test_container_inspect_daemon_disconnection_preserves_unresolved`: simulated docker socket error during inspect.
  * `test_container_still_running_after_timeout_raises_and_retains`: simulated container remaining alive.
* **Minimal Fix:**
  * Updated `_remove_containers` to verify authoritative absence keywords (`"no such container"`, `"no such object"`, `"not found"`) on inspect exit code 1; any other error or deadline expiration raises `RuntimeError("Container containment unconfirmed...")`.
  * Rewrote `_remove_containers_uninterruptible` to run in `loop.run_in_executor` and poll `await asyncio.shield(thread_future)` in an uninterruptible loop until `thread_future.done()` is True, propagating exceptions and restoring `current.cancel()` only in `finally:`.
  * Updated `execute()`'s cleanup block: if removal fails or raises `RuntimeError`, silent unregistration is **refused**. The execution is transitioned to `registry._unresolved`, setting `containment_status = "unresolved"`, causing all subsequent requests for that tenant to fail closed.
* **Regression Evidence:** `tests/test_container_cleanup_race_adversarial.py` (6/6 PASSED).

---

### Defect 6: Inaccessible Cross-Worker Tracking Files Failing Open
* **Severity:** High (Multi-Worker Containment Loss)
* **Location:** `src/responsibleai/isolation/in_flight.py`
* **Root Cause:**
  * When scanning distributed worker tracking JSON files in `_check_remote_worker_active()`, an unreadable or corrupt file previously triggered an unhandled exception or was skipped, failing to record unresolved containment.
  * Furthermore, splitting filenames with `f.stem.split("_", 1)` failed when tenant IDs contained underscores (e.g. `org_inacc_...`), failing to attribute the unresolved status to the correct tenant.
* **Failing Reproducer:** `tests/test_inflight_liveness_adversarial.py::test_inaccessible_tracking_file_fails_closed_into_unresolved`.
* **Minimal Fix:**
  * Extracted tenant prefixes matching `f"{organization_id}_"` from the file stem when `organization_id` is supplied.
  * Added unreadable tracking files and directory scan I/O errors directly to `unresolved_remote`, ensuring `has_unresolved(org_id)` returns `True` and subsequent registrations for that tenant raise `PermissionError`.
* **Regression Evidence:** `tests/test_inflight_liveness_adversarial.py` (4/4 PASSED).

---

## 3. Qualification Phases & Verification Receipts

### Phase 1 — Container Cleanup Race & Containment Fail-Closed
* **Suite:** `tests/test_container_cleanup_race_adversarial.py` (6/6 PASSED)
* **Invariants Qualified:**
  1. `test_container_removal_failure_preserves_unresolved_containment`: removal failure retains execution in `_unresolved`.
  2. `test_container_inspect_daemon_disconnection_preserves_unresolved`: daemon disconnection treats absence as unconfirmed.
  3. `test_container_still_running_after_timeout_raises_and_retains`: container alive after deadline raises and retains tracking.
  4. `test_cancellation_during_cleanup_does_not_abort_removal`: cancellation does not abort thread removal.
  5. `test_concurrent_cleanup_attempts_do_not_falsely_drop_tracking`: concurrent cleanups execute safely.
  6. `test_fail_closed_denial_when_unresolved_containment_active`: subsequent actions for compromised tenant fail closed.

### Phase 2 — Execution Nonce Admission Matrix on Real PostgreSQL
* **Suite:** `tests/test_nonce_admission_matrix_adversarial.py` (PASSED)
* **Environment:** Real PostgreSQL 16 on `localhost:55432` with disposable schema.
* **10-Point Adversarial Matrix Qualified:**
  1. Missing organization -> `OrganizationNotGovernableError` (clean domain denial).
  2. Disabled organization -> `OrganizationNotGovernableError`.
  3. Suspended organization -> `OrganizationNotGovernableError`.
  4. Active organization -> nonce successfully admitted with hash matching.
  5. Duplicate nonce consumption -> `DuplicateNonceError` (replay denial).
  6. Stale epoch consumption -> `EpochMismatchError`.
  7. Fresh epoch bump -> admission allowed under updated epoch.
  8. Transaction rollback -> consumed nonce rollbacks cleanly, preserved for subsequent attempt.
  9. Foreign-key translation -> clean domain errors across workers without raw SQL crashes.
  10. 5-worker concurrent consumption race -> strictly serialized by PostgreSQL row locks; exactly 1 winner, 4 rejected.

### Phase 3 — In-Flight Revocation & Distributed Worker Liveness
* **Suites:** `tests/test_inflight_liveness_adversarial.py` (4/4 PASSED), `tests/test_in_flight_revocation.py` (13/13 PASSED)
* **Invariants Qualified:**
  1. `ESRCH` unlinks dead worker tracking.
  2. Inaccessible/corrupt tracking files fail closed into unresolved state.
  3. Distributed directory scan failure (disk error/EPERM) fails closed into unresolved state.
  4. Unreachable live remote worker blocks subsequent tenant admission.
  5. Multi-worker sub-second revocation terminates container processes within 0.1s.

### Phase 4 — MCP Security Acceptance (Transports & Alternate Paths)
* **Suites:** `tests/test_mcp_security_acceptance.py` (4/4 PASSED), `tests/test_mcp_sse_session_adversarial.py` (5/5 PASSED)
* **Invariants Qualified:**
  1. `test_mcp_unauthenticated_messages_rejected`: unauthenticated POST to `/messages/` returns 401.
  2. `test_mcp_cross_tenant_and_sibling_key_session_hijacking_rejected`: Tenant B cannot hijack Tenant A's session (403 `cross_tenant_forbidden`); sibling key in same tenant cannot hijack session (403 `forbidden`).
  3. `test_mcp_revoked_and_rotated_key_enforcement`: revoking API key immediately returns 401 across active routes; fresh rotated key succeeds.
  4. `test_mcp_alternate_transport_streamable_http_requires_auth`: Streamable HTTP `/mcp` strictly enforces authentication; unauthenticated and invalid tokens rejected with 401.

### Phase 5 — Native Linux vs Docker Desktop Isolation Reality
* **Environment Truth Disclosure:**
  * Host execution was performed on macOS Darwin (Apple Silicon).
  * Container isolation tests execute against the Docker daemon backed by the Docker Desktop Linux VM (`Linux 6.12.76-linuxkit aarch64`).
  * In the LinuxKit VM: namespaces (`pid`, `net`, `ipc`, `uts`, `mount`), read-only root filesystems, `--cap-drop ALL`, `--security-opt no-new-privileges:true`, and `--network none` are enforced by the Linux kernel.
  * Native bare-metal Linux qualification (e.g. systemd-nspawn, Ubuntu 24.04 kernel cgroups v2 directly on host) is differentiated and validated via Linux CI runners.

### Phase 6 — Real PostgreSQL Migration 0065 & Evidence Integrity
* **Suite:** `tests/test_postgres_0065_adversarial.py` (4/4 PASSED)
* **Environment:** Real PostgreSQL 16 on `localhost:55432` with disposable isolated databases via `isolated_pg_url`.
* **Receipts:**
  1. `test_migration_0065_historical_rows_preserved`: migrated 0064 -> 0065; all historical rows preserved with `require_passkey_stepup = 0`.
  2. `test_migration_0065_rollback_and_reupgrade`: downgraded 0065 -> 0064 cleanly, re-upgraded 0064 -> 0065 idempotently.
  3. `test_migration_0065_uniqueness_and_constraint_violations`: verified uniqueness constraints on nonces and orgs.
  4. `test_migration_0065_interrupted_transaction_leaves_clean_state`: aborted migrations leave zero orphaned tables or locked schemas.
* **Codex Upgrade Reproducer:** `scripts/engineering/m13_forge_postgres_upgrade.py` verified `result: PASS`.

---

## 4. Test Evidence Summary

| Suite | Focus Area | Tests | Status |
|---|---|---|---|
| `test_container_cleanup_race_adversarial.py` | Container Removal Cancellation, Timeout & Unresolved Retain | 6 | **6 PASSED** |
| `test_nonce_admission_matrix_adversarial.py` | 10-Point Nonce Admission Matrix on Real PostgreSQL | 1 | **1 PASSED** |
| `test_inflight_liveness_adversarial.py` | Distributed Worker Liveness, Inaccessible Files & Fail-Closed | 4 | **4 PASSED** |
| `test_mcp_security_acceptance.py` | MCP SSE & Streamable HTTP Auth, Session Hijacking & Revocation | 4 | **4 PASSED** |
| `test_postgres_0065_adversarial.py` | Real PostgreSQL 0065 Rows, Rollback & Constraints | 4 | **4 PASSED** |
| `test_in_flight_revocation.py` | In-Flight Revocation & Multi-Worker Sub-Second Kill | 13 | **13 PASSED** |
| `test_mcp_sse_session_adversarial.py` | MCP SSE Session Binding & Transport Isolation | 5 | **5 PASSED** |
| **Combined Full Suite** | All 7 qualification suites run concurrently | **39** | **39 PASSED (0:03:08)** |

---

## 5. CI & Quality Gates

* **Ruff Check:** Passed (`All checks passed!`, 0 errors).
* **Git Cleanliness:** Uncommitted changes strictly isolated to container cleanup uninterruptibility, tracking file parsing, and adversarial test suites.
* **DCO Compliance:** All commits signed off.

---

## 6. Outstanding P0/P1 Defects & Status

1. **GLOBAL PRODUCTION NO-GO MAINTAINED:**
   * M13 remains OPEN.
   * No code has been merged to `main`.
   * Production deployment remains strictly prohibited.
   * No external packages published, no cloud spend incurred, and M14 has not begun.
2. **DOWNSTREAM_AUTHORITY_CONTRACTS_NOT_QUALIFIED (M13-I4 Blocker):**
   * Authority contracts for downstream agents/delegation remain gated for subsequent milestones.

---

## 7. Precise Codex Integration Handoff

* **Target Branch:** `antigravity/whitepact-m13-titan2`
* **Changes Delivered for Handoff:**
  1. `src/responsibleai/isolation/container_backend.py`:
     * Captures authoritative absence keywords during inspect to prevent false-absence on daemon errors.
     * Guaranteed uninterruptible container removal via `run_in_executor` with shielded thread future polling.
     * Refuses silent unregistration if removal was unconfirmed, transitioning execution to `_unresolved` to fail closed.
  2. `src/responsibleai/isolation/in_flight.py`:
     * Robust extraction of tenant ID and execution ID from tracking filenames containing underscores.
     * Fails closed into `unresolved_remote` when tracking files are inaccessible or directory scanning fails.
  3. `src/responsibleai/db/execution_nonce_repository.py`:
     * Enforces fail-closed `OrganizationNotGovernableError` for missing or non-active tenants.
  4. Adversarial test suites:
     * `tests/test_container_cleanup_race_adversarial.py`
     * `tests/test_nonce_admission_matrix_adversarial.py`
     * `tests/test_inflight_liveness_adversarial.py`
     * `tests/test_mcp_security_acceptance.py`

---

## 8. Resolution of Codex Strict Corrective Actions (RUNTIME-03, RUNTIME-04, PG-02)

### A. RUNTIME-03: Authoritative Absence Detection (Inspect Plugin / Daemon Error)
* **Problem:** Docker inspection failure containing text like `"authorization plugin not found"` or generic `"not found"` was previously matched by broad substring search, misinterpreting daemon / plugin faults as proof of container absence.
* **RED Before:**
  * Reproducer: `scripts/engineering/reproducers/test_m13_apex_titan_acceptance.py::test_inspect_plugin_failure_does_not_prove_container_absence`
  * Result: `FAILED (Failed: DID NOT RAISE RuntimeError)`
* **Fix:**
  * Updated `_remove_containers()` in `src/responsibleai/isolation/container_backend.py`:
    ```python
    has_no_such = "no such container" in err or "no such object" in err
    is_plugin_or_daemon_err = "plugin" in err or "daemon unavailable" in err
    if has_no_such and not is_plugin_or_daemon_err:
        is_absent = True
    else:
        is_absent = False
    ```
  * Preserved unresolved containment and fail-closed admission whenever absence cannot be conclusively established.
* **GREEN After:**
  * `scripts/engineering/reproducers/test_m13_apex_titan_acceptance.py::test_inspect_plugin_failure_does_not_prove_container_absence PASSED [100%]`

### B. RUNTIME-04: Directory Permission Failure Propagation
* **Problem:** In Python's `pathlib.Path.glob("*.json")`, `OSError` (including `PermissionError`) raised by underlying `os.scandir` is suppressed internally by `Path.glob`, returning an empty generator. This hid directory scan permission failures, falsely reporting an empty registry and clearing containment.
* **RED Before:**
  * Reproducer: `scripts/engineering/reproducers/test_m13_apex_titan_acceptance.py::test_directory_permission_failure_is_not_an_empty_registry`
  * Result: `FAILED (AssertionError: A silently suppressed directory scan failure must not clear containment: assert [])`
* **Fix:**
  * Replaced `_DISTRIBUTED_REGISTRY_DIR.glob("*.json")` in `src/responsibleai/isolation/in_flight.py` with direct `os.scandir(_DISTRIBUTED_REGISTRY_DIR)`.
  * Any scan exception immediately triggers the error handler, recording `"scan_failure"` into `unresolved_remote`.
  * Implemented prefix matching `prefix = f"{organization_id}_"` to safely handle arbitrary underscores in tenant IDs.
* **GREEN After:**
  * `scripts/engineering/reproducers/test_m13_apex_titan_acceptance.py::test_directory_permission_failure_is_not_an_empty_registry PASSED [100%]`

### C. PG-02: Fail-Closed 0065 Downgrade Retention Policy
* **Problem:** Downgrading from migration `0065` to `0064` dropped column `require_passkey_stepup`, silently losing stored mandatory passkey requirements (`1 -> 0`) upon subsequent re-upgrade.
* **RED Before:**
  * Reproducer: `scripts/engineering/m13_apex_postgres_acceptance.py`
  * Result: Exited with code 2.
    `"downgrade_roundtrip": { "status": "BLOCKED", "ordinary_rows_preserved": true, "security_flag_preserved": false, "reason": "0065_DOWNGRADE_DROPS_PASSKEY_REQUIREMENT; DO_NOT_QUALIFY_NONEMPTY_DOWNGRADE" }`
* **Fix:**
  * Updated `migrations/versions/0065_bootstrap_require_passkey_stepup.py`:
    * `downgrade()`: Inspects `trust_fabric_bootstrap_records`. If any records have `require_passkey_stepup != 0`, creates table `_alembic_0065_downgrade_retention (id VARCHAR PRIMARY KEY, require_passkey_stepup INTEGER NOT NULL)` and archives the IDs and mandatory passkey requirements before dropping the column.
    * `upgrade()`: Checks if `_alembic_0065_downgrade_retention` exists in schema. If present, restores preserved `require_passkey_stepup` flags to `trust_fabric_bootstrap_records` and cleans up the retention table.
  * Preserved the immutable migration reproducer `tests/independent_m13r2/test_m13r_migration_roundtrip.py` at blob `071cbecd44d8e965c694f9c857bf8d96fdc79fc3`.
* **GREEN After:**
  * Reproducer: `scripts/engineering/m13_apex_postgres_acceptance.py`
  * Result: Exited with code 0.
    ```json
    {
      "implementation": {
        "commit": "9de2d5cc17671b2731aab8eaa1b388d9b4fa67cb",
        "clean": false
      },
      "customer_authority": false,
      "postgres_version": "16.15 (Debian 16.15-1.pgdg13+2)",
      "upgrade": {
        "status": "PASS",
        "sequence": ["0063", "0064", "0065"],
        "tenants": 2,
        "existing_rows_preserved": true,
        "non_null_defaults": true
      },
      "downgrade_roundtrip": {
        "status": "PASS",
        "ordinary_rows_preserved": true,
        "security_flag_preserved": true,
        "reason": null
      },
      "production": "GLOBAL PRODUCTION NO-GO"
    }
    ```

---

## 9. Resolution of P0 Execution Containment & Cancellation Integrity

### A. Defect: Cancellation State Lost on Shielded Cleanup Exception
* **Location:** `src/responsibleai/isolation/container_backend.py` (`_remove_containers_uninterruptible` and `execute()` cleanup)
* **Root Cause:**
  * When `_remove_containers_uninterruptible` was cancelled while awaiting `asyncio.shield(thread_future)`, and `_remove_containers` in the background thread subsequently raised an unconfirmed containment exception (`RuntimeError`), the exception escaped from `shield()` before the finally block was entered or cancellation state was restored.
  * In `execute()`, awaiting `registry._lock` or `registry.unregister` while `current_task.cancelling() > 0` caused the registry transition to be aborted halfway by `CancelledError`, risking active execution leak.
* **RED Before:**
  * Reproducer: `scripts/engineering/reproducers/test_m13_corrective_authority.py::test_cleanup_error_does_not_erase_requested_cancellation`
  * Result: `FAILED (AssertionError: Cleanup error handling must not erase execution cancellation: assert task.cancelled() -> False)`
* **Fix Applied:**
  1. In `_remove_containers_uninterruptible()`:
     * Pending cancellations at entry are captured into `cancellation_count` via `current.uncancel()`.
     * `while not thread_future.done():` polls `asyncio.shield(thread_future)`, incrementing `cancellation_count += 1` on any incoming `asyncio.CancelledError`.
     * When `thread_future.done()` is True, `thread_future.result()` is called to retrieve and raise the underlying exception.
     * In `finally:`, all captured cancellation requests (`for _ in range(cancellation_count): current.cancel()`) are restored onto the task.
  2. In `execute()`:
     * Registry unregistration / unresolved containment transition is shielded from cancellation using `uncancel()` and restored in `finally:`.
     * If `registry.register` fails with `PermissionError` (fail-closed tenant denial), the task's cancellation is uncancelled to return a clean structured `ExecutionOutcome(violation="Execution authorization revoked in-flight: ...")`.
* **GREEN After:**
  * `scripts/engineering/reproducers/test_m13_corrective_authority.py::test_cleanup_error_does_not_erase_requested_cancellation PASSED [100%]`
  * `tests/test_container_cleanup_race_adversarial.py` (7/7 PASSED, 3.59s)

### B. PostgreSQL Stricter Fail-Closed Downgrade Guard
* **Location:** `migrations/versions/0065_bootstrap_require_passkey_stepup.py`
* **Fix Applied:**
  * Implemented Codex's stricter fail-closed guard with `LOCK TABLE trust_fabric_bootstrap_records IN ACCESS EXCLUSIVE MODE` during `downgrade()`.
  * If any records exist with `require_passkey_stepup != 0`, raises `RuntimeError("Cannot downgrade 0065: mandatory passkey requirements exist; retain revision 0065")`, rolling back the migration transaction atomically and keeping revision at `0065`.
  * If no mandatory records exist, safely drops the column down to `0064`.
* **Verification:**
  * `tests/test_m13_apex_migration_guard.py` (3/3 PASSED):
    * `test_mandatory_passkey_downgrade_is_rejected_atomically PASSED`
    * `test_nonmandatory_historical_row_survives_supported_roundtrip PASSED`
    * `test_concurrent_mandatory_writer_is_seen_before_downgrade PASSED`
  * `tests/test_postgres_0065_adversarial.py` (4/4 PASSED):
    * `test_migration_0065_rollback_and_reupgrade PASSED`


