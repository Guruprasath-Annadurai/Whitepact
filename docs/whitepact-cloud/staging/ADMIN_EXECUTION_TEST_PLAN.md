# Administrative Execution Boundary — Test Plan

SHA: `caf539b`

## Implementation reference

| Component | Behavior | Status |
|-----------|----------|--------|
| `PrivilegedOperationExecutor` | Calls `verify_for_execution` before callback | **VERIFIED_AUTOMATED_TESTS** |
| `PRIVILEGED_EXECUTOR_ENABLED` | Default `False` | **IMPLEMENTED** |
| `AdminGrantService.issue_and_persist` | Requires enrolled active employee | **VERIFIED_AUTOMATED_TESTS** |
| `verify_and_consume_transactional` | FOR UPDATE; grant + employee + policy | **VERIFIED_AUTOMATED_TESTS** |
| Provider credentials | Not loaded in executor unit tests; not on SaaS in design | **IMPLEMENTED** |

**Production rule:** Do not enable executor until live wiring proves SaaS cannot read Hetzner token files.

## Automated coverage (already green on `caf539b` CI)

| Control | Test |
|---------|------|
| Unknown employee cannot issue grant | `test_issue_rejects_unknown_employee` |
| Terminated cannot issue | `test_issue_rejects_terminated_employee` |
| Permission in grant + employee | `test_execution_requires_permission_in_employee_allowlist` |
| Concurrent single consume | `test_postgres_atomic_consume_single_winner` |
| Revoked / expired | `test_postgres_revoked_grant_cannot_execute`, `test_postgres_expired_grant_rejected` |
| Executor disabled | `test_disabled_executor_refuses` |
| Executor verifies before op | `test_executor_verifies_before_operation` |

Status: **VERIFIED_AUTOMATED_TESTS**

## Live staging sequence (Phase 3)

```
Employee identity (Access JWT)
  → enroll / role (DB)
  → policy active
  → approval recorded
  → issue_and_persist (signed grant)
  → verify_for_execution (transactional consume)
  → [executor disabled] OR executor → provider API (staging token)
  → audit row / evidence export
```

| ID | Scenario | Expected | Status |
|----|----------|----------|--------|
| A-01 | Full happy path (executor **off**) | Verify succeeds once; second fails replay | **AWAITING_LIVE_STAGING** |
| A-02 | Enable executor with mock provider | Op runs only after verify | **AWAITING_LIVE_STAGING** |
| A-03 | Tampered grant signature | `bad_signature` | **VERIFIED_AUTOMATED_TESTS** |
| A-04 | Wrong provider/resource at verify | `provider_mismatch` / `resource_mismatch` | **VERIFIED_AUTOMATED_TESTS** |
| A-05 | Suspend employee between issue and verify | `employee_not_active` | **AWAITING_LIVE_STAGING** |
| A-06 | Policy deactivated mid-flight | `policy_inactive` | **AWAITING_LIVE_STAGING** |
| A-07 | SaaS container env has no `HCLOUD_TOKEN` | Absent | **AWAITING_LIVE_STAGING** |
| A-08 | Concurrent verify (2 workers) | Exactly one consume | **VERIFIED_AUTOMATED_TESTS** (CI Postgres) |

## Pass criteria

Live A-01–A-02, A-05–A-07 executed with executor enablement explicitly approved in writing.
