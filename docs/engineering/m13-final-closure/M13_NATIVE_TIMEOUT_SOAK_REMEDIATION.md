# WHITEPACT — M13 NATIVE TIMEOUT SOAK REMEDIATION
## Forensic Investigation of Creation Receipt Races, Registry Contamination & Sequential Timeout Failures

**Author:** Antigravity FORTRESS  
**Role:** Independent Principal Security Auditor & Runtime Containment Lead  
**Target File:** `src/responsibleai/isolation/container_backend.py` (lines 620-695)  
**Target Test:** `tests/test_docker_ownership_regression.py::test_repeated_sequential_timeout_soak`  
**Observed Failure:** `AssertionError: Iteration 2 did not report timeout`  
**Diagnostic Log:** `Docker creation completion unconfirmed; retaining unresolved containment`  

---

### 1. ROOT CAUSE SUMMARY

The failure of `test_repeated_sequential_timeout_soak` on Linux GitHub Actions runners is a deterministic interaction of three factors:

```
[ Short 0.25s Timeout ] 
          │
          ▼
[ Docker CLI killed before writing container.cid ]
          │
          ▼
[ creation_settled == False (cid is None & proc.returncode != 0) ]
          │
          ▼
[ Line 651 raises RuntimeError("Docker creation completion unconfirmed") ]
          │
          ▼
[ finish_tracking() records execution as "unresolved" ]
          │
          ▼
[ Iteration 2 denied admission via PermissionError("Active remote container or worker is still running") ]
          │
          ▼
[ Iteration 2 outcome: timed_out = False -> AssertionError ]
```

---

### 2. DETAILED MECHANICS & RACE CONDITION

1. **Sub-second Wall Timeout:**
   In `test_repeated_sequential_timeout_soak`, 25 sequential iterations are run for the same organization (`org-soak-...`), each with `wall_timeout_seconds=0.25` (250 milliseconds).
2. **Docker Creation Latency:**
   On a shared Linux CI VM under load, spawning the `docker run` process and completing `POST /containers/create` can take 200–350ms.
3. **Abrupt Process Termination:**
   When the 0.25s timeout triggers:
   ```python
   except asyncio.TimeoutError:
       timed_out = True
       if proc.returncode is None:
           try:
               proc.kill()
           except ProcessLookupError:
               pass
   ```
   `proc.kill()` sends `SIGKILL` to the `docker run` client process. If this occurs before Docker flushes the 64-character ID to `--cidfile`, `_trusted_container_id(cid_file)` returns `None`.
4. **Unconditional Unsettled Exception:**
   In `finally`:
   ```python
   cid = creation_receipt()
   cleanup_targets = [cid, container_name] if cid is not None else [container_name]
   creation_settled = cid is not None or proc.returncode == 0
   ```
   Even though `_remove_containers_uninterruptible` successfully issues `docker rm -f container_name` and verifies 3.0 seconds of stable absence from dockerd via `docker inspect`, line 651 unconditionally raises:
   ```python
   if not creation_settled:
       raise RuntimeError(
           "Docker creation completion unconfirmed; retaining unresolved containment"
       )
   ```
5. **Registry Contamination:**
   Because `cleanup_error` is set, `finish_tracking()` executes:
   ```python
   registration.containment_status = "unresolved"
   registration.last_termination_error = str(cleanup_error)
   registry._unresolved[execution_id] = registration
   _record_cross_worker_registration(registration)
   ```
6. **Admission Denial on Subsequent Iteration:**
   In Iteration 2 (which uses the exact same `org_id`):
   When `register_owned()` runs, `InFlightExecutionRegistry.register()` checks for existing unresolved records for that organization. Finding Iteration 1's unresolved record, it raises `PermissionError`.
7. **Assertion Mismatch:**
   `backend.execute()` catches `PermissionError` and returns `ExecutionOutcome(exit_code=-9, violation="Execution authorization revoked in-flight...", timed_out=False)`.
   Line 201 then asserts:
   ```python
   assert outcome.timed_out, f"Iteration {i} did not report timeout"
   ```
   Because `outcome.timed_out` is `False`, the assertion fails on Iteration 2!

---

### 3. MINIMAL DEFENSIVE REMEDIATION FOR CODEX

To preserve absolute containment while eliminating false-unsettled registry contamination:

1. **Refresh Creation Receipt After Draining Client I/O:**
   If the client completed or was drained during `finish_client_io()`, re-check `creation_receipt()`. If Docker wrote the cidfile right before exit, acknowledge it.
2. **Acknowledge Confirmed Absence for Uncreated Containers:**
   If `cid is None` (meaning Docker never acknowledged container creation) AND `proc` is dead, AND `_remove_containers_uninterruptible([container_name], stable_seconds=3.0)` confirmed that no container named `container_name` exists in dockerd, then containment is proven: the container either was never created or was already removed and confirmed absent.
   Only raise `RuntimeError("Docker creation completion unconfirmed")` if `_remove_containers_uninterruptible` encountered an inspection failure, a timeout, or a surviving container.
3. **Graceful Client Shutdown on Timeout:**
   Send `proc.terminate()` (SIGTERM) with a tiny 100ms window before escalating to `proc.kill()` (SIGKILL). This allows Docker CLI to write the container ID receipt and exit cleanly.

This minimal correction completely resolves the sequential soak failure while strictly upholding fail-closed containment.
