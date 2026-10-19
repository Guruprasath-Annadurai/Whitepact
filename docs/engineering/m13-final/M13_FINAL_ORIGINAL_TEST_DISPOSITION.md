# M13 original test disposition register

## Current checkpoint: ed1eb770 (2026-10-19)

The authoritative current evidence and limitations are in
[M13_FINAL_CORRECTIVE_CHECKPOINT.md](M13_FINAL_CORRECTIVE_CHECKPOINT.md).
Candidate HEAD is `ed1eb7705b69bef30fbbacb3717219ea995f41a6`, tree
`a576376ddbc46843f7cd90cba6ac057cc7d1a823`, parent
`851f52888a57df35619b9d75ab3d6f61c4f53bc7`. Exact-head CI is complete and failed;
completed predecessor receipts must not be transferred to it. Subsequent
historical/interim sections retain their original checkpoint scope.
**BLOCKED — ENGINEERING OR SECURITY GATES REMAIN. M13 OPEN. GLOBAL PRODUCTION NO-GO.**

Status: IN PROGRESS. M13 OPEN. GLOBAL PRODUCTION NO-GO.

Candidate under qualification: HEAD `bb6e263fc271a07f58484ce1fd1445cc201b24b0`,
tree `93f36747cd00610850c8cf0ace13de107b145da5`, parent
`2bde48d4abe20312dd6408cf62366d68ca69746e`.
Draft PR223: https://github.com/Guruprasath-Annadurai/Whitepact/pull/223

## Independently retained baseline:67 original failures each interpreter

This table is historical evidence from exact IRONCLADccf4, full run
https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39243226832 .
It is not a copied result for the integrated candidate. The same full cohort
is being rerun; each current result/disposition must be appended after extraction.
Original test blobs and assertions are preserved. No original gate is accepted
merely because a new counterpart passes.

| Exact original test ID | Baseline category | Exact failure message excerpt |
|---|---|---|
| `tests.independent_m13r2.test_m13r_migration_roundtrip::test_0063_upgrade_0064_constraints_and_safe_empty_downgrade` | Historical migration head | AssertionError: assert '0065' == '0064'      - 0064   ?    ^   + 0065   ?    ^ |
| `tests.test_auth_real_postgres::test_one_canonical_alembic_head` | Historical migration head | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -   |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_concurrent_bootstrap_attempts_single_winner` | A2/root historical contract | assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_empty_consent_fails_closed` | A2/root historical contract | KeyError: 'token' |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_end_to_end_customer_authority_bootstrap_journey` | A2/root historical contract | assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_expired_bootstrap_token_rejected` | A2/root historical contract | assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_nonce_substitution_rejected` | A2/root historical contract | KeyError: 'token' |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_replayed_bootstrap_token_rejected` | A2/root historical contract | KeyError: 'token' |
| `tests.test_customer_root_authority_bootstrap.TestCustomerRootAuthorityBootstrap::test_stolen_bootstrap_token_fails_closed` | A2/root historical contract | assert 403 == 200  +  where 403 = <Response [403 Forbidden]>.status_code |
| `tests.test_data_inventory::test_complete_table_classification_coverage` | Other governance/fixture/compliance | AssertionError: Unclassified tables found: ['authority_containment_records', 'authority_recovery_requests', 'a |
| `tests.test_dco_historical_exception::test_candidate_range_passes_with_only_those_exceptions` | Other governance/fixture/compliance | AssertionError: ::error::Commit 5291cc6d4e750c6ec5ec0688f8bfc9e3b72a8558 is missing a 'Signed-off-by:' trailer |
| `tests.test_final_coverage_batch12::test_execute_mock_timeout` | Other governance/fixture/compliance | assert False is True  +  where False = ExecutionOutcome(action_id='act-timeout', exit_code=-9, result_payload= |
| `tests.test_h1_collision_invariance::test_07_slashes_and_traversal_attempts` | Tracking specification conflict | AssertionError: assert 2 == 1  +  where 2 = len([PosixPath('/tmp/pytest-of-runner/pytest-1/test_07_slashes_and |
| `tests.test_h1_collision_invariance::test_10_unicode_normalization_nfc` | Tracking specification conflict | AssertionError: assert 'trk_v2_4a4631f362abd552633fcdcabaf5f4b3e05d4ae39a8756dcd617b7587364c841_cc5badcf59cf52 |
| `tests.test_h1_reproducers::test_reproduce_distributed_tracking_prefix_ambiguity` | Tracking specification conflict | AssertionError: VULNERABILITY CONFIRMED: Tenant 'org' inspected and was poisoned by 'org_corp' file: [{'execut |
| `tests.test_h1_tenant_isolation_adversarial::test_10_tenant_prefix_ambiguity_worker_tracking` | Tracking specification conflict | AssertionError: Tenant 'org' was falsely poisoned by 'org_corp': [{'execution_id': 'trk_v2_cfef9a259eb0164e138 |
| `tests.test_h4_backup_recovery_adversarial::test_03_restored_database_stale_revocation_epoch_advanced` | H4 recovery | AssertionError: assert 2 == 7  +  where 2 = ('org-stale-epoch', 'tenant_global', 2, '2026-01-01T00:00:00Z').ep |
| `tests.test_h4_backup_recovery_adversarial::test_07_active_container_detected_and_fenced` | H4 recovery | AssertionError: assert 'exec-orphan-1' in [] |
| `tests.test_h4_backup_recovery_adversarial::test_11_restored_deleted_tenant_quarantined_and_authority_purged` | H4 recovery | AssertionError: assert 'ACTIVE' == 'QUARANTINED'      - QUARANTINED   + ACTIVE |
| `tests.test_historical_postgres_migrations::test_downgrade_and_reupgrade_idempotence` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_historical_postgres_migrations::test_fresh_install_to_head_postgres` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_historical_postgres_migrations::test_one_canonical_alembic_head` | Historical migration head | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -   |
| `tests.test_historical_postgres_migrations::test_upgrade_0042_to_head_preserves_data_and_invariants` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_historical_postgres_migrations::test_upgrade_0043_to_head_preserves_trust_fabric_and_invariants` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_historical_postgres_migrations::test_upgrade_0044_to_head_preserves_iam_and_invariants` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_inflight_liveness_adversarial::test_kill_esrch_unlinks_dead_worker_tracking` | Tracking specification conflict | AssertionError: Dead worker must not be reported as active assert 1 == 0  +  where 1 = len([{'execution_id': ' |
| `tests.test_m12fs_root_hardening::test_bootstrap_requires_stepup_when_configured` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_bootstrap_with_valid_passkey_stepup_succeeds` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_emergency_agent_containment_quarantines_and_bumps_epoch` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_emergency_organization_lockdown` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_quorum_pre_execution_deactivation_check` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_quorum_recovery_full_lifecycle_2_of_3` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_reconcile_bootstrap_status_deterministic` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_root_proof_of_possession_valid_and_forged` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m12fs_root_hardening::test_stepup_rejects_replayed_challenge` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_authority_closure::test_cross_tenant_and_privilege_escalation_containment` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_authority_closure::test_full_consequential_authority_chain` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_authority_closure::test_multi_admin_quorum_recovery_adversarial` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_concurrent_race_serializes_cleanly` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_genuine_unseeded_customer_enrollment_and_bridging` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_identifier_collision_fails_closed` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_identifier_recycling_after_revocation` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_pending_principal_promotion` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_pending_quorum_recovery_blocks_out_of_band_bootstrap` | A2/root historical contract | AssertionError: assert 'A2_AUTHENTICATION_REQUIRED' == 'ROOT_ALREADY_EXISTS'      - ROOT_ALREADY_EXISTS   + A2 |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_transaction_rollback_preserves_clean_state` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_unicode_domain_idna_consistency_and_collision` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_m13_titan_root_adversarial::test_root_bootstrap_webauthn_adversarial_paths` | A2/root historical contract | responsibleai.enterprise.errors.EnterpriseError: Recent verified owner WebAuthn UV is required. |
| `tests.test_migration_ownership_canonical::test_alembic_single_head_is_0063_api_key_mfa_timestep` | Historical migration head | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -   |
| `tests.test_phase1_migrations::test_one_canonical_head` | Historical migration head | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -   |
| `tests.test_phase1_migrations::test_postgres_upgrade_paths[0029]` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_postgres_upgrade_paths[0032]` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_postgres_upgrade_paths[base]` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_supported_upgrade_paths[0029]` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_supported_upgrade_paths[0032]` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase1_migrations::test_supported_upgrade_paths[base]` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase4_migrations::test_one_canonical_alembic_head` | Historical migration head | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -   |
| `tests.test_phase5_migrations::test_fresh_schema_to_0045_postgres` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_phase5_migrations::test_one_canonical_alembic_head` | Historical migration head | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -   |
| `tests.test_phase7a_migrations::test_single_head_0053` | Historical migration head | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -   |
| `tests.test_phase7a_migrations::test_upgrade_downgrade_0050_0053_when_empty` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_postgres_migrations::test_one_canonical_alembic_head` | Historical migration head | AssertionError: assert ['0065'] == ['0063']      At index 0 diff: '0065' != '0063'      Full diff:     [   -   |
| `tests.test_security_alert_triage::test_restore_reconcile_does_not_return_internal_exception_text` | Other governance/fixture/compliance | AssertionError: {"error":"RESTORE_SECURITY_QUALIFICATION_REQUIRED","message":"Restore admission requires indep |
| `tests.test_tenant_isolation_org_admin::test_cross_tenant_isolation_on_org_endpoints` | Other governance/fixture/compliance | assert 400 == 200  +  where 400 = <Response [400 Bad Request]>.status_code |
| `tests.test_upstream_gateway.TestUpstreamServerRepository::test_disable_between_lookup_and_admission_dispatches_zero_times` | Other governance/fixture/compliance | responsibleai.db.execution_nonce_repository.OrganizationNotGovernableError: Organization is not ACTIVE for gov |
| `tests.test_v1_customer_journey::test_fresh_postgres_health_ready_and_nonprod_preflight` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_v1_customer_journey::test_historical_0057_upgrade_then_signup` | Historical migration head | AssertionError: assert '0065' == '0063'      - 0063   ?    ^   + 0065   ?    ^ |
| `tests.test_wp_aud_015_revoke_branch::test_revoke_branch_uses_single_transaction_boundary` | Other governance/fixture/compliance | assert 'bump_epoch_on_connection' in '    async def revoke_branch(\n        self, org_id: str, identity_id: st |

## Current policy-compatible disposition rules

-28 A2/root fixtures cannot bypass verified email, active persisted ownership,
recent server UV and proof-of-possession. Historical setup acceptance requires an
explicit maintainer specification decision; negative expectations stay intact.
-24 historical schema-head assertions cannot force a downgrade from0065.
Mandatory passkey downgrade refusal stays enforced; historical compatibility
counterparts and real PostgreSQL must be separately qualified.
-Five tracking conflicts cannot justify deleting unknown containment, NFC-aliasing
database tenant identifiers, trusting dead PID as containment, or attributing
corrupt records by filename alone.
-H4 owner changes to temporary-directory isolation/singleton resets are reviewed
as fixture changes; returningTrue from termination mocks changes attestation.
Broadening QUARANTINED to DISABLED changes semantics and requires approval.
-Other seven cases retain exact failing evidence. Source-introspection assertions
need behavior-based specification disposition; missing DCO needs actual authors;
data classification needs an authorized policy decision. Restore503 remains
disabled rather than meeting an old500 assertion. Upstream missing-org denial
cannot dispatch. MFA400 and shared-registry timeout precedence need actual diagnosis.

## Independent owner-source original replay

Exact Recovery Zeroe7e24dee:20 PASS/3 FAIL66.86s on unchanged historical H4
and PostgreSQL originals. Its separate focused new cases20 PASS223.40s.
Original H4 test07, test11 and PostgreSQL tombstone/FK test remain failed.
Initial mixed-root collection raised ImportPathMismatchError; ERROR retained,
then rerun with one test root. No collection error is called a test pass.

## Required next evidence

Integrated full unique-ID accounting; each failed original's actual new result;
owner-updated test assessment separate from original unchanged replay; fresh
SQLite/PostgreSQL behavior and actual Linux where applicable. No undisposed
mandatory FAIL may be called M13 completion.

