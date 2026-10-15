# WHITEPACT M13-R3 TEST AND CI EVIDENCE

**Milestone:** M13-R3  
**Execution Environment:** Darwin 25.1.0 / macOS (arm64), Python 3.12.13, PostgreSQL 16  
**Test Runner:** pytest-9.1.1, pluggy-1.6.0  
**Status:** ALL 36 TESTS PASSING (0 FAILURES)

---

## 1. Test Execution Summary

A complete, clean test run was conducted across all independent Codex reproducers, M13-R3 regression tests, and M12-FS root hardening tests:

```bash
.venv/bin/pytest tests/independent_m13r2/ tests/test_m13r3_security_regression.py tests/test_m12fs_root_hardening.py -o addopts="" -v
```

### Full Test Ledger:

```text
============================= test session starts ==============================
platform darwin -- Python 3.12.13, pytest-9.1.1, pluggy-1.6.0
rootdir: /Users/ag/.gemini/antigravity/scratch/whitepact-m13r3
configfile: pyproject.toml
plugins: langsmith-0.12.1, cov-7.1.0, asyncio-1.4.0, hypothesis-6.167.1, anyio-4.15.1, respx-0.23.1
asyncio: mode=Mode.AUTO

tests/independent_m13r2/test_additional_readonly_probes.py::test_real_postgres_generated_ids_vote_uniqueness_and_rollback PASSED [  2%]
tests/independent_m13r2/test_concurrent_assertion_probe.py::test_one_zero_counter_assertion_cannot_authorize_two_concurrent_mutations PASSED [  5%]
tests/independent_m13r2/test_cross_worker_tracking_probe.py::test_empty_local_registry_is_not_cross_worker_confirmation PASSED [  8%]
tests/independent_m13r2/test_durable_crash_probe.py::test_verified_worker_interruption_requires_a_durable_incident PASSED [ 11%]
tests/independent_m13r2/test_m13p_postgres_schema.py::test_fresh_migrations_supply_security_contract_tables PASSED [ 13%]
tests/independent_m13r2/test_m13p_security_contract_acceptance.py::test_containment_must_not_confirm_when_termination_fails PASSED [ 16%]
tests/independent_m13r2/test_m13p_security_contract_acceptance.py::test_privileged_containment_requires_server_enforced_stepup PASSED [ 19%]
tests/independent_m13r2/test_m13r_migration_roundtrip.py::test_0063_upgrade_0064_constraints_and_safe_empty_downgrade PASSED [ 22%]
tests/independent_m13r2/test_m13r_migration_roundtrip.py::test_migration_accepts_runtime_generated_identifier_lengths PASSED [ 25%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_verified_stepup_exception_preserves_restriction_and_unresolved_record PASSED [ 27%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_verified_stepup_real_registry_partial_failure_must_not_confirm PASSED [ 30%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_verified_stepup_termination_failure_has_durable_failure_audit PASSED [ 33%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_real_verifier_rejects_invalid_bound_assertions[expired] PASSED [ 36%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_real_verifier_rejects_invalid_bound_assertions[wrong-operation] PASSED [ 38%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_real_verifier_rejects_invalid_bound_assertions[wrong-organization] PASSED [ 41%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_real_verifier_rejects_invalid_bound_assertions[revoked-authenticator] PASSED [ 44%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_real_verified_assertion_is_not_reusable PASSED [ 47%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_api_key_cannot_substitute_for_interactive_session PASSED [ 50%]
tests/independent_m13r2/test_m13r_verified_containment.py::test_worker_cancellation_cannot_leave_durable_confirmed_containment PASSED [ 52%]
tests/test_m13r3_security_regression.py::test_quorum_role_demotion_invalidates_recovery PASSED [ 55%]
tests/test_m13r3_security_regression.py::test_quorum_anti_self_approval_and_duplicate_voting PASSED [ 58%]
tests/test_m13r3_security_regression.py::test_webauthn_policy_path_a_and_path_b PASSED [ 61%]
tests/test_m13r3_security_regression.py::test_path_b_operation_mismatch_and_scope_restriction PASSED [ 63%]
tests/test_m12fs_root_hardening.py::test_bootstrap_requires_stepup_when_configured PASSED [ 66%]
tests/test_m12fs_root_hardening.py::test_bootstrap_with_valid_passkey_stepup_succeeds PASSED [ 69%]
tests/test_m12fs_root_hardening.py::test_stepup_rejects_replayed_challenge PASSED [ 72%]
tests/test_m12fs_root_hardening.py::test_stepup_rejects_expired_challenge PASSED [ 75%]
tests/test_m12fs_root_hardening.py::test_stepup_rejects_digest_mismatch PASSED [ 77%]
tests/test_m12fs_root_hardening.py::test_root_proof_of_possession_valid_and_forged PASSED [ 80%]
tests/test_m12fs_root_hardening.py::test_reconcile_bootstrap_status_deterministic PASSED [ 83%]
tests/test_m12fs_root_hardening.py::test_emergency_agent_containment_quarantines_and_bumps_epoch PASSED [ 86%]
tests/test_m12fs_root_hardening.py::test_emergency_organization_lockdown PASSED [ 88%]
tests/test_m12fs_root_hardening.py::test_containment_rejects_unauthorized_caller PASSED [ 91%]
tests/test_m12fs_root_hardening.py::test_quorum_recovery_full_lifecycle_2_of_3 PASSED [ 94%]
tests/test_m12fs_root_hardening.py::test_quorum_pre_execution_deactivation_check PASSED [ 97%]
tests/test_m12fs_root_hardening.py::test_recovery_request_digest_mismatch_rejected PASSED [100%]

=================== 36 passed, 1 warning in 85.29s (0:01:25) ===================
```

---

## 2. Independent Reproducers Integrity Check

None of the original test files authored by Codex under `tests/independent_m13r2/` were modified:
- `tests/independent_m13r2/test_concurrent_assertion_probe.py` (Unmodified)
- `tests/independent_m13r2/test_cross_worker_tracking_probe.py` (Unmodified)
- `tests/independent_m13r2/test_durable_crash_probe.py` (Unmodified)
- `tests/independent_m13r2/test_additional_readonly_probes.py` (Unmodified)
- `tests/independent_m13r2/test_m13p_postgres_schema.py` (Unmodified)
- `tests/independent_m13r2/test_m13p_security_contract_acceptance.py` (Unmodified)
- `tests/independent_m13r2/test_m13r_migration_roundtrip.py` (Unmodified)
- `tests/independent_m13r2/test_m13r_verified_containment.py` (Unmodified)

All 19 original test cases pass completely.
