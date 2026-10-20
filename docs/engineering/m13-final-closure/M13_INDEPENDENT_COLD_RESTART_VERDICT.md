# WHITEPACT — M13 INDEPENDENT COLD RESTART VERDICT
## Comprehensive Adversarial Evaluation of Lost-Metadata Scenarios, Runtime Reconciliation & Detached Container Containment

**Author:** Antigravity FORTRESS  
**Role:** Independent Principal Security Auditor & Runtime Red-Team Lead  
**Evaluated Commit:** `bff5f143933d518e921592361f0171d7cf7ff6ef` (Candidate Tree: `4c4d519b532fb36ca02f9bf2ee7919a2e6f49635`)  
**Audit Priority:** P0 — Top Architectural Security Challenge  
**Ruling:** **CORRECTION REQUIRED (READY-STATE DETACHED RECOVERY BLOCKER CONFIRMED)**  

---

### 1. EXECUTIVE AUDIT DETERMINATION

```
========================================================================================
                      CAMPAIGN A VERDICT: CORRECTION REQUIRED
========================================================================================
Threat Model:      Host worker process crashes via SIGKILL (`kill -9`) with a detached
                   real Docker container executing; local tracking metadata is wiped.
Evaluation State:  Application restarts in normal operational mode (READY state) with
                   Store B and database operational.
Observed Result:   WhitePact evaluates startup authority as NORMAL READY, finds 0 active
                   workers for the tenant in the empty tracking directory, and ADMITS
                   new consequential execution while the detached container is still
                   running in Docker.
Constitutional Status: FAILS INVARIANT ("cannot act outside independently enforced authority").
Disposition:       BLOCKING P0 DEFECT. Correction required before M13 closure.
========================================================================================
```

---

### 2. MANDATORY SCENARIO TEST EXECUTION & EVIDENCE

The mandatory end-to-end scenario was executed against real native Docker (`python:3.12-slim`) on candidate `bff5f143`:

1. **Workload Initialization:** Real container `wp_iso_org-leak-42988a_detached-action_exec-leak-d6a78e` spawned with labels `wp_tenant=org-leak-42988a` and `wp_execution=exec-leak-d6a78e`.
2. **Abrupt Worker Death:** Application worker process abruptly terminated via `SIGKILL` (`kill -9`).
3. **Detached Container Survival:** Real container verified alive and executing detached in Docker daemon via `docker inspect` (`State.Running == True`).
4. **Disposable Metadata Deletion:** Local registry directory `_DISTRIBUTED_REGISTRY_DIR` completely wiped (simulating ephemeral disk recreation, pod restart, or filesystem loss).
5. **Operational State Preserved:** Database and Store B remained in operational `READY` state.
6. **Clean Process Restart:** Clean application process initialized. `evaluate_startup_authority(gate)` returned:
   ```
   mode: NORMAL
   readiness_state: READY
   reason: "Normal startup with established authority"
   ```
7. **Consequential Admission Attempt:** Tenant `org-leak-42988a` attempted a new consequential execution. `in_flight._check_remote_worker_active("org-leak-42988a")` returned `[]` (0 active workers).
8. **Admission Result:** WhitePact admitted the new execution.
9. **Empirical Finding:**
   ```
   VULNERABILITY CONFIRMED: WhitePact in READY state did NOT detect the surviving
   detached container and has 0 active workers recorded for tenant!
   ```

---

### 3. FIVE-SCENARIO DETAILED STATE MATRIX

| Scenario ID | State Conditions | Detection Mechanism | Observed Behavior | Security Status |
| :--- | :--- | :--- | :--- | :--- |
| **A-01** | Tracking record exists, worker alive | `_check_remote_worker_active()` | Active PID verified; registration blocked | **QUALIFIED (PASS)** |
| **A-02** | Tracking record exists, worker dead (`ESRCH`) | `_check_remote_worker_active()` | `Worker exited; containment unconfirmed`; registration blocked | **QUALIFIED (PASS)** |
| **A-03** | Tracking record corrupted | `_check_remote_worker_active()` | JSON parse failure; record retained as unresolved; blocked | **QUALIFIED (PASS)** |
| **A-04** | Tracking wiped, startup in `RESTORE_PENDING` | `RestoreReadinessGate` | Startup authority detects recovery mode; blocks fail-closed | **QUALIFIED (PASS)** |
| **A-05** | Tracking wiped, startup in normal `READY` | Startup Authority / Registry | **NO DETECTION.** Detached container ignored; new traffic admitted | **VULNERABLE (BLOCKER)** |

---

### 4. REQUIRED CODEX ENGINEERING REMEDIATION

To resolve this blocking defect, WhitePact must implement an authoritative startup OCI reconciliation:

1. **Pre-Ready OCI Daemon Sweep:**
   Before transitioning from `STARTUP` to `READY`, `DockerContainerBackend` must query the local Docker daemon:
   ```bash
   docker ps -q --filter "name=wp_iso_"
   ```
2. **Orphaned Container Reconciliation:**
   For every running container discovered:
   - Read container labels `wp_tenant` and `wp_execution`.
   - Verify whether an active in-memory owner exists in the registry.
   - If no active owner exists, the container is an orphaned detached execution from a previous process crash.
   - The startup sequence must either:
     (a) Authoritatively terminate the orphaned container via `_remove_containers_uninterruptible()`, or
     (b) Populate `InFlightExecutionRegistry._unresolved` and persist `containment_status = "unresolved"` to disk, preventing new tenant admission until operator recovery.
3. **Fail-Closed on Unreachable Docker:**
   If the Docker daemon is unreachable or returns an inspection error during the startup sweep, the startup authority must evaluate to `UNCERTAIN` / `FAILED` and refuse consequential admission.
