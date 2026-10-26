# WHITEPACT M13-R3 DISTRIBUTED CONTAINMENT

**Milestone:** M13-R3  
**Vulnerability Class:** False Positive Containment / Ghost Worker Ambiguity  
**CWE:** CWE-390 (Detection of Error Condition Without Action), CWE-693 (Protection Mechanism Failure)  
**Status:** FULLY REMEDIATED & ENFORCED

---

## 1. Problem Definition & The Local Registry Fallacy

In previous iterations, process-local memory registries (`InFlightExecutionRegistry._active`) were treated as definitive truth for containment status. If a containment request was processed by Worker Process A, and Worker Process A had 0 local processes registered for Tenant T, it concluded that 0 executions were active and declared `status = "CONTAINED"`.

However, in multi-worker, clustered, or containerized deployments:
- Worker Process B may be actively executing long-running agent workloads for Tenant T.
- Process A cannot see Process B's memory.
- Claiming `CONTAINED` when remote executions continue running is a catastrophic false-positive containment event.

---

## 2. Distributed Cross-Worker Architecture

WhitePact M13-R3 enforces distributed truthfulness across the worker fleet:

1. **Worker Registration Barrier:**
   When any worker process admits and starts an execution container/process, it writes a registration record containing:
   - `execution_id`
   - `organization_id`
   - `admission_epoch`
   - `pid`
   - `created_at`
2. **Epoch Revocation Propagation:**
   When emergency containment bumps the authoritative revocation epoch in PostgreSQL (`governance_revocation_epochs`), that epoch is immediately broadcast to the local registry and persistent state.
3. **Cross-Worker Active Inspection:**
   When `terminate_in_flight` is invoked:
   - Local processes are terminated and verified.
   - Remote worker state is inspected. Any registered executions on other PIDs are checked for process liveness (`os.kill(pid, 0)`).
   - If any remote execution is alive and has not acknowledged termination or cannot be directly terminated across process boundaries, it is tracked in `_unresolved`.
4. **Honest Status Reporting:**
   - If any execution remains unresolved (local or remote), `InFlightExecutionRegistry.count_unresolved(org_id) > 0`.
   - The containment service detects this condition and sets:
     `containment_status = "UNRESOLVED"`
   - The response returns `status = "UNRESOLVED"` and the database records this state.
   - **Under no circumstances does the system claim `CONTAINED` unless all matching executions are verified terminated.**

---

## 3. Empirical Test Evidence

Codex's original reproducer (`tests/independent_m13r2/test_cross_worker_tracking_probe.py`) was executed unchanged:

```bash
.venv/bin/pytest tests/independent_m13r2/test_cross_worker_tracking_probe.py -o addopts="" -v
```

**Result:** `PASSED` [100%]
- An active execution was registered under an isolated subprocess (simulating a remote worker).
- The local in-flight execution registry was empty in the test process.
- `execute_emergency_containment` was invoked.
- Returned result:
  `result["status"] == "UNRESOLVED"` (NOT `"CONTAINED"`).
- Verified that empty local state never produces a false confirmed containment claim.
