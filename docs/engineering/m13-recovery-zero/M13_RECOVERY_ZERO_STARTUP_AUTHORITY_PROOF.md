# M13 RECOVERY ZERO — STARTUP AUTHORITY PROOF
## Fail-Closed Admission, Cryptographic Store B Verification, and Evaluation Contract

- **Date:** 2026-10-19
- **Author:** Antigravity FORTRESS
- **Milestone:** WhitePact M13 — Operation Recovery Zero
- **Commit Baseline:** `b896b1efb4406c03205522dce7c69855391d305b`
- **Component:** `src/responsibleai/data_governance/backup_defense.py`

---

### 1. Problem Statement & Vulnerability Analysis (P0-01)

Prior to this remediation, `get_restore_readiness_gate()` initialized the singleton `RestoreReadinessGate` using:

```python
# VULNERABLE CODE IN b896b1efb4406c03205522dce7c69855391d305b
if provider is None:
    store_b_path = os.environ.get("WHITEPACT_STORE_B_PATH")
    if store_b_path:
        try:
            provider = DurableLifecycleStateProvider(store_b_path)
        except Exception:
            provider = None
```

When `WHITEPACT_STORE_B_PATH` pointed to a non-existent file, a corrupt SQLite database, a file with denied permissions, or an unparseable schema, the constructor threw an exception. The exception was swallowed, `provider` was set to `None`, and because `WHITEPACT_RESTORE_MODE` was absent, the gate defaulted to `initial_state = RestoreReadinessState.READY`.

**Adversarial Consequence:** A restored application process booting against a damaged or compromised Store B authority store immediately authorized production traffic, bypassing all recovery fences.

---

### 2. Remediation Contract & Implementation

The startup authority contract establishes three distinct startup authority modes:

```python
class StartupAuthorityMode(str, Enum):
    NORMAL = "NORMAL"          # Normal startup: established DB, no active recovery event
    RECOVERY = "RECOVERY"      # Active recovery: reconciliation required
    UNCERTAIN = "UNCERTAIN"    # Ambiguous or compromised state: FAIL CLOSED
```

#### Key Architecture Changes in `RestoreReadinessGate`:

1. **Provider Error Capture:** If `DurableLifecycleStateProvider(store_b_path)` fails during instantiation, the exact error is captured in `_provider_error` on the gate.
2. **Fail-Closed State Property:**
   ```python
   @property
   def state(self) -> RestoreReadinessState:
       if self._provider_error is not None:
           return RestoreReadinessState.FAILED
       if self._provider is not None:
           if not self._provider.verify_integrity():
               return RestoreReadinessState.FAILED
           return self._provider.get_state()
       return self._state
   ```
3. **Cryptographic Verification on Every Evaluation:** If the durable provider fails HMAC verification or data integrity checks, `state` immediately resolves to `FAILED`.
4. **Universal Surface Enforcement:** Any attempt to check `is_admitted()` returns `False`. Any call to `assert_restore_readiness_admitted()` raises `RestoreQuarantineError("Disaster recovery readiness gate is in FAILED state")`.
5. **Startup Authority Evaluation API:** Added `evaluate_startup_authority(store_b_path, restore_mode, engine)` and `assert_database_restore_consistent(engine)`.

---

### 3. Empirical Verification & Evidence

Test case: `test_p0_01_corrupt_or_inaccessible_store_b_fails_closed_across_all_callers` in `tests/test_m13_recovery_zero_p0_reproducers.py`.

#### Empirical Results:
1. **Corrupt File:** Store B file containing random garbage (`b"CORRUPTED_STORE_B_DATA_GARBAGE"`):
   - Gate state: `RestoreReadinessState.FAILED`
   - Gate admitted: `False`
   - Guard call raises: `RestoreQuarantineError` with match `"FAILED"`
2. **Permission Denied File:** Store B file with `chmod 000`:
   - Gate state: `RestoreReadinessState.FAILED`
   - Gate admitted: `False`
   - Guard call raises: `RestoreQuarantineError` with match `"FAILED"`
3. **IAM Surface Guard Protection:** `PrivilegedSurfaceGuard.assert_admitted()` fails closed and blocks caller.
4. **Authority Kernel Consequential Execution Protection:** `Phase7AAuthorityKernel.evaluate_authorization()` rejects new authorization requests with `RestoreQuarantineError`.

---

### 4. Architectural Limitations & Boundaries

- **Out-of-Band Restore Marker:** A raw physical snapshot restore performed directly on the PostgreSQL volume without updating Store B or setting `WHITEPACT_RESTORE_MODE` cannot be detected purely from PostgreSQL metadata if no migration or marker table was stamped. In such architectures, operations must configure `WHITEPACT_RESTORE_MODE=1` or initialize Store B prior to unfreezing traffic.
- **HMAC Key Provisioning:** When HMAC integrity checking is activated via `WHITEPACT_STORE_B_HMAC_KEY`, the key must be consistently provisioned across all workers. An absent or mismatched key triggers immediate fail-closed state (`FAILED`).
