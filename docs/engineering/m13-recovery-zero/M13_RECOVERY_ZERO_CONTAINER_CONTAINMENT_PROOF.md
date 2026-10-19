# M13 RECOVERY ZERO — CONTAINER CONTAINMENT PROOF
## Strict Unresolved In-Flight Execution Fencing and Quarantined Tenant Containment

- **Date:** 2026-10-19
- **Author:** Antigravity FORTRESS
- **Milestone:** WhitePact M13 — Operation Recovery Zero
- **Commit Baseline:** `b896b1efb4406c03205522dce7c69855391d305b`
- **Component:** `src/responsibleai/data_governance/backup_defense.py`

---

### 1. Problem Statement & Vulnerability Analysis (P0-02)

In commit `b896b1efb4406c03205522dce7c69855391d305b`, `reconcile_post_restore()` implemented quarantined tenant containment using the following flawed logic:

```python
# VULNERABLE CODE IN b896b1efb4406c03205522dce7c69855391d305b
active_restored_orgs = set(store_a_org_map.keys()) - set(quarantined_orgs)
for q_org in quarantined_orgs:
    unresolved_detail = registry.get_unresolved_executions(q_org)
    if any(
        "terminate_callback did not confirm target termination" in err
        for err in unresolved_detail.values()
    ):
        raise RestoreQuarantineError(...)
```

#### Adversarial Failure Modes:
1. **Ad-Hoc String Matching:** If a detached container was tracked in the in-flight registry, but its worker process died (`worker_pid` not alive) and had no registered termination callback, `err` was empty string `""` or a generic diagnostic string. The `in err` check evaluated to `False`.
2. **Exclusion from Active Checks:** Because `quarantined_orgs` were subtracted from `active_restored_orgs`, the active tenant checks were never executed for them.
3. **Premature READY Transition:** As a result, the recovery engine declared `READY` while a detached agent container for a quarantined organization was still executing in the background!

---

### 2. Required Security Invariant & Remediation

#### Invariant:
> *The global recovery gate must NOT become READY while ANY recovery-relevant consequential execution remains active or its required containment is unconfirmed.*

#### Remediation in `reconcile_post_restore`:
1. **Zero Unresolved for Quarantined Tenants:**
   ```python
   for q_org in quarantined_orgs:
       unresolved_count = registry.count_unresolved(q_org)
       if unresolved_count > 0:
           unresolved_detail = registry.get_unresolved_executions(q_org)
           raise RestoreQuarantineError(
               f"Quarantined organization {q_org} has {unresolved_count} unresolved executions: "
               f"{list(unresolved_detail.keys())}"
           )
   ```
2. **Zero Unresolved Across All Tenants in Store A:**
   ```python
   for org_id in store_a_org_map.keys():
       unresolved_count = registry.count_unresolved(org_id)
       if unresolved_count > 0:
           raise RestoreQuarantineError(
               f"Organization {org_id} has {unresolved_count} unresolved executions post-reconciliation"
           )
   ```
3. **No Private State Manipulation:** No private registry state (`_unresolved`) is cleared or forged by the recovery orchestrator. Containment must be authoritatively verified by the registry itself.

---

### 3. Empirical Verification & Evidence

Test case: `test_p0_02_quarantined_tenant_detached_unresolved_execution_blocks_recovery` in `tests/test_m13_recovery_zero_p0_reproducers.py`.

#### Scenario Setup:
- Tenant A: Active in Store A, TOMBSTONED in Store B. Marked DISABLED in PostgreSQL.
- In-flight registry contains an active execution `detached-exec-1` for Tenant A.
- Termination callback: None.
- Worker PID: 999999 (dead PID).
- `last_termination_error`: `""` (no `"terminate_callback did not confirm target termination"` text).

#### Empirical Result:
- Invoking `engine.reconcile_post_restore()`:
  - Immediately raises `RestoreQuarantineError` with message matching `"has 1 unresolved executions"`.
  - Recovery gate remains in `FAILED` state (`is_admitted() == False`).
  - No transition to `READY` occurs.

---

### 4. Architectural Limitations & Boundaries

- **Container Runtime Daemon Reachability:** The in-flight registry relies on Docker/containerd daemon communication to kill containers for dead worker PIDs. If the daemon is unresponsive, executions transition to `UNRESOLVED`, safely blocking recovery rather than failing open.
- **Operator Action on Unresolved Executions:** An unresolved container requires operator intervention (e.g., node drain, host-level SIGKILL) before re-running reconciliation to achieve `READY`.
