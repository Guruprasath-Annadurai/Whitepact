# Executor UNKNOWN / reconciliation required

**Trigger:** external effect uncertain after timeout, worker crash, or lost acknowledgement.

1. **Contain:** do not auto-retry consequential actions without idempotency key review.
2. **Verify:** classify outcome as `NOT_EXECUTED`, `EXECUTED`, or `UNKNOWN / RECONCILIATION_REQUIRED` per runtime reconciliation docs.
3. **Recover:** operator reconciles with upstream system; bump revocation epoch if authority must be invalidated.
4. **Evidence:** link execution attempt ID, lease generation, and evidence row (if any).
5. **Escalate:** repeated UNKNOWN for same integration → disable connector until root cause found.

Reference tests: `tests/test_mcp_ws2_upstream_reconciliation.py`, `tests/test_phase7a_authority_kernel.py`.
