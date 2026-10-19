# M13 Final PostgreSQL Restore Retest

**Assigned Agent:** Antigravity FORTRESS  
**Role:** PostgreSQL Recovery Engineer & Reliability Lead  
**Date:** October 19, 2026  
**Milestone:** WhitePact M13  
**Target:** `scripts/engineering/reproducers/test_m13_fortress_restore_independent.py`  
**Database:** PostgreSQL 16.10 on 127.0.0.1:55432  
**Status:** DRAFT • M13 OPEN • GLOBAL PRODUCTION NO-GO • RELEASE AUTHORIZATION NOT GRANTED

---

## 1. Test Overview

The `test_m13_fortress_restore_independent.py` reproducer validates:
1. `test_store_b_floor_fences_canonical_governance_epoch`: Verifies that Store B revocation floors correctly fence canonical governance epochs in PostgreSQL after a disaster recovery event.
2. `test_runtime_canonical_fence_ignores_other_scope`: Verifies that runtime epoch reconciliation fences only the governance scope and ignores unrelated tenant scopes.
3. `test_tombstone_reconciliation_handles_real_approval_request_fk`: Verifies that tombstoning a restored tenant with active approval request foreign keys correctly terminates executions, cleans up foreign keys, and establishes reconciled status without integrity violations.

---

## 2. Failure Diagnosis & Resolution

### Symptom:
Test 3 failed during post-restore reconciliation:
```
RestoreReconciliationError: Post-reconciliation containment unconfirmed:
... remote alive workers [pid 2973/3227]
```

### Root Cause:
Test isolation leak. Test 2 created an isolated tracking directory via monkeypatch, but Test 3 fell back to the shared default `_DISTRIBUTED_REGISTRY_DIR`. Earlier test runs on the host had left tracking files in `/tmp/whitepact_inflight`, which were detected by the post-reconciliation sweep as uncontained executions.

### Corrective Action:
Added an autouse fixture `isolated_tracking_environment` to `scripts/engineering/reproducers/test_m13_fortress_restore_independent.py`:
```python
@pytest.fixture(autouse=True)
def isolated_tracking_environment(tmp_path, monkeypatch):
    t_dir = tmp_path / "tracking"
    t_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", t_dir)
    tracking.InFlightExecutionRegistry.reset_instance()
    yield
    tracking.InFlightExecutionRegistry.reset_instance()
```

---

## 3. Retest Execution Log & Evidence

Command:
```bash
PYTHONPATH=src:. python3 -m pytest -o addopts="" scripts/engineering/reproducers/test_m13_fortress_restore_independent.py
```

Result:
```
============================= test session starts ==============================
platform darwin -- Python 3.14.6, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/ag/whitepact-m13-final-red-to-green
configfile: pyproject.toml
plugins: langsmith-0.14.11, cov-7.1.0, anyio-4.14.1, asyncio-1.4.0, hypothesis-6.170.0, respx-0.23.1
asyncio: mode=Mode.AUTO, debug=False, asyncio_default_fixture_loop_scope=None, asyncio_default_test_loop_scope=function
collected 3 items

scripts/engineering/reproducers/test_m13_fortress_restore_independent.py . [ 33%]
..                                                                       [100%]

============================== 3 passed in 49.07s ==============================
```

Conclusion: **3/3 passed (100%)**. PostgreSQL structural restore and tombstone reconciliation with foreign key relationships are completely functional and verified on real PostgreSQL 16.
