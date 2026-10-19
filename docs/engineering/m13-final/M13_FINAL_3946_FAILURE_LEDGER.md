# Exact 39461fec failed-case ledger

Predecessor evidence only. Current source851f5288 is not qualified by these receipts.

Run39258774395: Python3.11 actual JUnit has 8077 cases, 8077 unique IDs, 83 failures, zero errors, 34 skips. Both interpreters independently report the same83 failure IDs. Protected originals are unchanged. No failing assertion is waived by this table.

| Exact failed case | Baseline relation | Actual error excerpt |
| --- | --- | --- |
| `tests.independent_m13r2.test_m13r_migration_roundtrip::test_0063_upgrade_0064_constraints_and_safe_empty_downgrade` | original baseline | AssertionError: assert '0065' == '0064'      - 0064   ?    ^   + 0065   ?    ^ |
| `tests.test_auth_real_postgres::test_one_canonical_alembic_head` | original baseline | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -     '0063',   ?         ^   +     '0065',   ?         ^     ] |
| `tests.test_customer_real_approval_journey::test_real_database_outage_blocks_new_admission_and_recovers` | additional failure | sdk.python.rai_client.governance.GovernanceRequestError: governance request failed [503]: {"error":"restore_quarantine","message":"Operational traffic blocked: system is in FAILED  |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_concurrent_bootstrap_attempts_single_winner` | original baseline | assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_empty_consent_fails_closed` | original baseline | KeyError: 'token' |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_end_to_end_customer_authority_bootstrap_journey` | original baseline | assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_expired_bootstrap_token_rejected` | original baseline | assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_nonce_substitution_rejected` | original baseline | KeyError: 'token' |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_replayed_bootstrap_token_rejected` | original baseline | KeyError: 'token' |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_stolen_bootstrap_token_fails_closed` | original baseline | assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code |
| `tests.test_data_inventory::test_complete_table_classification_coverage` | original baseline | AssertionError: Unclassified tables found: ['authority_containment_records', 'authority_recovery_requests', 'authority_recovery_votes', 'authority_step_up_challenges'] assert 4 ==  |
| `tests.test_dco_historical_exception::test_candidate_range_passes_with_only_those_exceptions` | original baseline | AssertionError: ::error::Commit 5291cc6d4e750c6ec5ec0688f8bfc9e3b72a8558 is missing a 'Signed-off-by:' trailer.     Subject: test(product): prepare exact-candidate acceptance and b |
| `tests.test_final_coverage_batch12::test_execute_mock_timeout` | original baseline | assert False is True  +  where False = ExecutionOutcome(action_id='act-timeout', exit_code=-9, result_payload=None, stdout='', stderr="Execution authorization for tenant 'org-1' ha |
| `tests.test_h1_collision_invariance::test_07_slashes_and_traversal_attempts` | original baseline | AssertionError: assert 2 == 1  +  where 2 = len([PosixPath('/tmp/pytest-of-runner/pytest-1/test_07_slashes_and_traversal_0/distributed_tracking/.registry.lock'), PosixPath('/tmp/py |
| `tests.test_h1_collision_invariance::test_10_unicode_normalization_nfc` | original baseline | AssertionError: assert 'trk_v2_4a4631f362abd552633fcdcabaf5f4b3e05d4ae39a8756dcd617b7587364c841_cc5badcf59cf5227e824c23d69a1720641def9d44d5250292cad26f44839c79d.json' == 'trk_v2_db |
| `tests.test_h1_reproducers::test_reproduce_distributed_tracking_prefix_ambiguity` | original baseline | AssertionError: VULNERABILITY CONFIRMED: Tenant 'org' inspected and was poisoned by 'org_corp' file: [{'execution_id': 'corp_exec999', 'organization_id': 'org', 'action_id': 'unkno |
| `tests.test_h1_tenant_isolation_adversarial::test_10_tenant_prefix_ambiguity_worker_tracking` | original baseline | AssertionError: Tenant 'org' was falsely poisoned by 'org_corp': [{'execution_id': 'trk_v2_cfef9a259eb0164e138b40a35d4c9603aff2d08e6c70c7575d42aa32dbb7e5d6_bda95de5b3b515307271b0a7 |
| `tests.test_h1_tenant_isolation_adversarial::test_14_concurrent_cross_tenant_operations` | additional failure | assert 0 == 10  +  where 0 = len([]) |
| `tests.test_h4_backup_recovery_adversarial::test_07_active_container_detected_and_fenced` | original baseline | AssertionError: assert 'exec-orphan-1' in [] |
| `tests.test_h4_backup_recovery_adversarial::test_11_restored_deleted_tenant_quarantined_and_authority_purged` | original baseline | AssertionError: assert 'DISABLED' == 'QUARANTINED'      - QUARANTINED   + DISABLED |
| `tests.test_historical_postgres_migrations::test_downgrade_and_reupgrade_idempotence` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_historical_postgres_migrations::test_fresh_install_to_head_postgres` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_historical_postgres_migrations::test_one_canonical_alembic_head` | original baseline | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -     '0063',   ?         ^   +     '0065',   ?         ^     ] |
| `tests.test_historical_postgres_migrations::test_upgrade_0042_to_head_preserves_data_and_invariants` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_historical_postgres_migrations::test_upgrade_0043_to_head_preserves_trust_fabric_and_invariants` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_historical_postgres_migrations::test_upgrade_0044_to_head_preserves_iam_and_invariants` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_inflight_liveness_adversarial::test_kill_esrch_unlinks_dead_worker_tracking` | original baseline | AssertionError: Dead worker must not be reported as active assert 1 == 0  +  where 1 = len([{'execution_id': 'exec_esrch_40ce2083', 'organization_id': 'org_esrch_0d2c2d4c', 'action |
| `tests.test_isolation_egress_boundary::test_execution_boundary_production_same_process_forbidden` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_isolation_egress_boundary::test_execution_boundary_restore_readiness_failure_rejects_sandbox` | additional failure | Failed: DID NOT RAISE PermissionError |
| `tests.test_isolation_fail_closed_default.TestExecutorDefaultsClosed::test_production_ignores_the_opt_in` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_isolation_real_tool_e2e.TestSyntheticFixtureIsTheOnlyHostSideTool::test_production_never_runs_it_host_side` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_m12fs_root_hardening::test_bootstrap_requires_stepup_when_configured` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_bootstrap_with_valid_passkey_stepup_succeeds` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_emergency_agent_containment_quarantines_and_bumps_epoch` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_emergency_organization_lockdown` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_quorum_pre_execution_deactivation_check` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_quorum_recovery_full_lifecycle_2_of_3` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_reconcile_bootstrap_status_deterministic` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_root_proof_of_possession_valid_and_forged` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_stepup_rejects_replayed_challenge` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_recovery_zero_p0_reproducers::test_adversarial_p0_01_detached_alive_container_without_tracking_fails_closed` | additional failure | assert 0 == 1  +  where 0 = len([]) |
| `tests.test_m13_titan_authority_closure::test_cross_tenant_and_privilege_escalation_containment` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_authority_closure::test_full_consequential_authority_chain` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_authority_closure::test_multi_admin_quorum_recovery_adversarial` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_concurrent_race_serializes_cleanly` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_genuine_unseeded_customer_enrollment_and_bridging` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_identifier_collision_fails_closed` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_identifier_recycling_after_revocation` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_pending_principal_promotion` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_pending_quorum_recovery_blocks_out_of_band_bootstrap` | original baseline | AssertionError: assert 'A2_AUTHENTICATION_REQUIRED' == 'ROOT_ALREADY_EXISTS'      - ROOT_ALREADY_EXISTS   + A2_AUTHENTICATION_REQUIRED |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_transaction_rollback_preserves_clean_state` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_unicode_domain_idna_consistency_and_collision` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_webauthn_adversarial_paths` | original baseline | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m4_postgres_assault_campaign::test_m4_postgres_assault_battery` | additional failure | AssertionError: ......F..                                                                [100%]   =================================== FAILURES ===================================   |
| `tests.test_migration_ownership_canonical::test_alembic_single_head_is_0063_api_key_mfa_timestep` | original baseline | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -     '0063',   ?         ^   +     '0065',   ?         ^     ] |
| `tests.test_phase1_migrations::test_one_canonical_head` | original baseline | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -     '0063',   ?         ^   +     '0065',   ?         ^     ] |
| `tests.test_phase1_migrations::test_postgres_upgrade_paths[0029]` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_postgres_upgrade_paths[0032]` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_postgres_upgrade_paths[base]` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_supported_upgrade_paths[0029]` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_supported_upgrade_paths[0032]` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_supported_upgrade_paths[base]` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase4_migrations::test_one_canonical_alembic_head` | original baseline | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -     '0063',   ?         ^   +     '0065',   ?         ^     ] |
| `tests.test_phase5_migrations::test_fresh_schema_to_0045_postgres` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase5_migrations::test_one_canonical_alembic_head` | original baseline | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -     '0063',   ?         ^   +     '0065',   ?         ^     ] |
| `tests.test_phase5_postgres_concurrency::test_concurrent_restore_reconciliation_workers` | additional failure | AssertionError: assert <RestoreReadinessState.FAILED: 'FAILED'> == <RestoreReadinessState.READY: 'READY'>      - READY   + FAILED |
| `tests.test_phase7a_migrations::test_single_head_0053` | original baseline | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -     '0063',   ?         ^   +     '0065',   ?         ^     ] |
| `tests.test_phase7a_migrations::test_upgrade_downgrade_0050_0053_when_empty` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_postgres_migrations::test_one_canonical_alembic_head` | original baseline | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -     '0063',   ?         ^   +     '0065',   ?         ^     ] |
| `tests.test_production_environment_resolution.TestNoProductionConfigurationCanEnableUnisolatedExecution::test_the_executor_refuses_a_real_tool_without_a_broker[ENVIRONMENT]` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_production_environment_resolution.TestNoProductionConfigurationCanEnableUnisolatedExecution::test_the_executor_refuses_a_real_tool_without_a_broker[ENV]` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_production_environment_resolution.TestNoProductionConfigurationCanEnableUnisolatedExecution::test_the_executor_refuses_a_real_tool_without_a_broker[RAI_ENVIRONMENT]` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_production_environment_resolution.TestNoProductionConfigurationCanEnableUnisolatedExecution::test_the_executor_refuses_a_real_tool_without_a_broker[RAI_ENV]` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_production_environment_resolution.TestNoProductionConfigurationCanEnableUnisolatedExecution::test_the_executor_refuses_a_real_tool_without_a_broker[WHITEPACT_ENVIRONMENT]` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_production_environment_resolution.TestNoProductionConfigurationCanEnableUnisolatedExecution::test_the_executor_refuses_a_real_tool_without_a_broker[WHITEPACT_ENV]` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_restore_admission_chokepoint::test_startup_safety_default_not_ready` | additional failure | AssertionError: assert <RestoreReadinessState.FAILED: 'FAILED'> == <RestoreReadinessState.RESTORE_PENDING: 'RESTORE_PENDING'>      - RESTORE_PENDING   + FAILED |
| `tests.test_runtime_isolation_hardgate.TestEvidenceBoundaryIntegration::test_production_internal_tool_executor_fails_closed_without_broker` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |
| `tests.test_security_alert_triage::test_restore_reconcile_does_not_return_internal_exception_text` | original baseline | AssertionError: {"error":"RESTORE_SECURITY_QUALIFICATION_REQUIRED","message":"Restore admission requires independently qualified operator authorization and reconciliation."} assert |
| `tests.test_upstream_gateway.TestUpstreamServerRepository::test_disable_between_lookup_and_admission_dispatches_zero_times` | original baseline | responsibleai.db.execution_nonce_repository.OrganizationNotGovernableError: Organization is not ACTIVE for governed execution |
| `tests.test_v1_customer_journey::test_fresh_postgres_health_ready_and_nonprod_preflight` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_v1_customer_journey::test_historical_0057_upgrade_then_signup` | original baseline | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_wp_aud_015_revoke_branch::test_revoke_branch_uses_single_transaction_boundary` | original baseline | assert 'bump_epoch_on_connection' in '    async def revoke_branch(\n        self, org_id: str, identity_id: str, *, revoked_by: str, reason: str\n    ) -> list[str]:\n        """Ca |
| `tests.test_ws2_isolation_child_admission::test_production_internal_executor_refuses_without_broker` | additional failure | responsibleai.data_governance.backup_defense.RestoreQuarantineError: Operational traffic blocked: system is in FAILED state. |

## Aggregate skip reasons (not passes)

| Actual reason | Count |
| --- | --- |
| BENCH_NOT_REQUESTED set WHITEPACT_RUN_BENCH=1. A skip is not a measurement. | 1 |
| DOC_EXAMPLE_NOT_EXECUTED BiasBusterRunner: needs a live OpenAI API key. A skip is not a pass. | 1 |
| DOC_EXAMPLE_NOT_EXECUTED CostTracker: writes a database under the user's home directory. A skip is not a pass. | 1 |
| DOC_EXAMPLE_NOT_EXECUTED FederatedClient: needs the reader's own provider class (MyProvider). A skip is not a pass. | 1 |
| No Bash 3.2 executable found. Set WHITEPACT_BASH32, or provide Bash 3.2 at /opt/bash32/bin/bash or /bin/bash. | 2 |
| QUALIFICATION_SKIP platform=linux purpose=fail-closed path when ACL and root are both unavailable. This host can grant container UID access. The stubbed test test_prepare_does_not_chmod_world_readable_even_if_acl_missing covers the refusal. The skip is not a pass. | 1 |
| Qualified M5 object not present (shallow CI checkout) | 1 |
| could not import 'crewai': No module named 'crewai' | 11 |
| could not import 'llama_index.core': No module named 'llama_index' | 11 |
| covered in async boundary tests | 1 |
| terraform CLI not installed | 3 |

65 of the original67 remain failed. The two original passes are H4 stale revocation epoch advancement and organization admin cross-tenant endpoint isolation. Separate installed framework tests do not relabel the optional22 full-matrix skips.

