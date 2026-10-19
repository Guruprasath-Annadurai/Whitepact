# IRONCLAD root A2 qualification

Reviewed source checkpoint: 47fc55a1591890f18c06333b4f187d091535719d; tree b57b0e46f388cce8a01690e986fde2be6783a967; parent d480e8c87882a7fc5d353961a6fe22048380ab9f. Initial baseline: 7939341fd9d98d0f1fa39ce4421318dbc1dac33e. Draft PR #221 targets codex/whitepact-m13-absolute-convergence. This is an interim engineering record. Completed d9ddf44a CI is historical relative to this successor; new exact-head CI remains pending.

## Independently reproduced defects

Root completion read a PENDING_VERIFICATION principal before acquiring the revocable owner locks. An independently committed transition to REVOKED, SUSPENDED, DISABLED or DELETED before the locked authorization check was ignored; completion promoted the stale pending row to ACTIVE and granted root authority. New genuine enrolled/authenticated owner ceremonies produced **4 FAIL** on original `7939341f`,69.43 s. Negative-state fixtures create only a pending principal; they are not customer-success receipts. Original protected tests remain unchanged.

Corrective source locks the owner context before identity snapshots, then the tenant epoch and principal, and holds those locks through completion. A second current-context check immediately precedes mutation, after cryptographic verification. Owner lock order now precedes epoch, consistent with organization-before-epoch execution admission. Root key PoP, operation-bound server-issued UV challenge, consent, tenant binding and mandatory verified email remain enforced.

Enterprise transfer initially authorized outside its write transaction and then locked memberships before organization. New committed-suspension cases were RED:2 FAIL/2 PASS in50.70 s. Both ownership APIs now lock organization before memberships and require active state at mutation. Web transfer also requires active source/target membership and updates organizations.owner_user_id. Corrected real PostgreSQL ownership suite: **11 PASS in135.69 s**, including deterministic observation of a competing PostgreSQL organization lock, then membership acquisition by the organization-first transaction. No root fixture is seeded by these administrative workspace tests.

Corrected root+existing signed A2/B1 local run is pending at this checkpoint. Linux exact-head authority job39206376358 is pending. No security closure is claimed from pending results.

## Protected28 failing gates

Every original failing gate remains FAIL. Individual review found all 28 stop before their principal later invariant because the actor lacks recent session-bound server-verified UV, or HTTP initialization403 causes missing-token errors. This does not establish later security behavior. Earlier assertions reached by some tests are retained as partial evidence.

| Protected test | Original stopping point / invariant still requiring counterpart |
|---|---|
| `tests/test_m13_titan_authority_closure.py::test_full_consequential_authority_chain` | Initiation A2 denial; unverified email denial and real token verification already reached; downstream delegation/containment unqualified by this test |
| `tests/test_m13_titan_authority_closure.py::test_multi_admin_quorum_recovery_adversarial` | A2 initiation; no quorum assertion reached |
| `tests/test_m13_titan_authority_closure.py::test_cross_tenant_and_privilege_escalation_containment` | Cross-tenant and developer denials reached; owner A2 initiation blocks containment/replay |
| `tests/test_m12fs_root_hardening.py::test_bootstrap_requires_stepup_when_configured` | A2 initiation; mandatory completion assertion unreached |
| `tests/test_m12fs_root_hardening.py::test_bootstrap_with_valid_passkey_stepup_succeeds` | Manually inserted credential does not establish recent authenticated session |
| `tests/test_m12fs_root_hardening.py::test_stepup_rejects_replayed_challenge` | A2 initiation; replay unreached |
| `tests/test_m12fs_root_hardening.py::test_root_proof_of_possession_valid_and_forged` | A2 initiation; PoP assertions unreached |
| `tests/test_m12fs_root_hardening.py::test_reconcile_bootstrap_status_deterministic` | NOT_FOUND already passed; pending/completed status unreached |
| `tests/test_m12fs_root_hardening.py::test_emergency_agent_containment_quarantines_and_bumps_epoch` | A2 initiation; containment/epoch unreached |
| `tests/test_m12fs_root_hardening.py::test_emergency_organization_lockdown` | A2 initiation; lockdown unreached |
| `tests/test_m12fs_root_hardening.py::test_quorum_recovery_full_lifecycle_2_of_3` | A2 initiation; quorum lifecycle unreached |
| `tests/test_m12fs_root_hardening.py::test_quorum_pre_execution_deactivation_check` | A2 initiation; eligible-voter revalidation unreached |
| `tests/test_m13_titan_root_adversarial.py::test_root_bootstrap_pending_quorum_recovery_blocks_out_of_band_bootstrap` | Denied A2, expected ROOT_ALREADY_EXISTS; recovery-specific precedence unreached |
| `tests/test_m13_titan_root_adversarial.py::test_root_bootstrap_webauthn_adversarial_paths` | A2 initiation; challenge expiry/digest assertions unreached |
| `tests/test_m13_titan_root_adversarial.py::test_root_bootstrap_concurrent_race_serializes_cleanly` | A2 initiation; race unreached |
| `tests/test_m13_titan_root_adversarial.py::test_root_bootstrap_genuine_unseeded_customer_enrollment_and_bridging` | Initial principal absence proved; A2 initiation blocks bridge |
| `tests/test_m13_titan_root_adversarial.py::test_root_bootstrap_identifier_collision_fails_closed` | Collision fixture exists; A2 initiation blocks collision-specific denial |
| `tests/test_m13_titan_root_adversarial.py::test_root_bootstrap_transaction_rollback_preserves_clean_state` | A2 initiation; forged-PoP rollback unreached |
| `tests/test_m13_titan_root_adversarial.py::test_root_bootstrap_identifier_recycling_after_revocation` | A2 initiation; lifecycle policy decision and qualified counterpart required |
| `tests/test_m13_titan_root_adversarial.py::test_root_bootstrap_pending_principal_promotion` | Pending fixture exists; A2 initiation blocks qualified promotion |
| `tests/test_m13_titan_root_adversarial.py::test_root_bootstrap_unicode_domain_idna_consistency_and_collision` | A2 initiation; Unicode/A-label collision assertions unreached |
| `tests/test_customer_root_authority_bootstrap.py::TestCustomerRootAuthorityBootstrap::test_end_to_end_customer_authority_bootstrap_journey` | Empty status proved; HTTP initiation403 vs200 |
| `tests/test_customer_root_authority_bootstrap.py::TestCustomerRootAuthorityBootstrap::test_concurrent_bootstrap_attempts_single_winner` | HTTP initiation403; concurrency unreached |
| `tests/test_customer_root_authority_bootstrap.py::TestCustomerRootAuthorityBootstrap::test_replayed_bootstrap_token_rejected` | KeyError token after denied initiation; replay unreached |
| `tests/test_customer_root_authority_bootstrap.py::TestCustomerRootAuthorityBootstrap::test_empty_consent_fails_closed` | KeyError token after denied initiation; consent unreached |
| `tests/test_customer_root_authority_bootstrap.py::TestCustomerRootAuthorityBootstrap::test_stolen_bootstrap_token_fails_closed` | HTTP initiation403; stolen-token binding unreached |
| `tests/test_customer_root_authority_bootstrap.py::TestCustomerRootAuthorityBootstrap::test_nonce_substitution_rejected` | KeyError token after denied initiation; nonce assertion unreached |
| `tests/test_customer_root_authority_bootstrap.py::TestCustomerRootAuthorityBootstrap::test_expired_bootstrap_token_rejected` | HTTP initiation403; expiry unreached |

The table preserves all 28 exact pytest IDs; no assertion or exclusion changed. Required counterparts use genuine enrollment/authentication and preserve final invariant assertions. Public recovery stays disabled; service-level tests cannot certify enabled recovery. Founder-controlled legal identity assurance and identifier recycling remain unresolved. No downgrade to password-only bootstrap is accepted.

## Subsequent focused verification

The original four-state root reproducer and two observer contracts passed: **6 PASS in92.85 s**, Python 3.11/macOS, JUnit /private/tmp/m13-ironclad-a2-focused.xml. The broader local A2/B1 run hit its300-second outer bound and is NOT a passing run. After preserving explicit unverified-email denial precedence through lock-only context acquisition, the four races, two observer contracts and original unverified-email test passed **7 PASS in99.45 s** (/private/tmp/m13-ironclad-a2-precedence.xml).

Exact published d9ddf44a targeted Linux authority scope: **63 PASS on each of Python 3.11 and3.12**. Workflow 39206376358 completed; its reference cohort failed three preserved tracking assertions plus an omitted browser-cache environment setting in the diagnostic workflow. The setting is corrected in the working candidate, pending committed-head repetition.

Policy-compatible counterpart additions:14 genuine owner authority contracts PASS72.86 s, including rollback after valid UV, exact assertion reuse after rollback, replay denial, actual root/agent delegation revocation and selective application disablement.11 identity/capability contracts PASS67.08 s, including actual IDNA registration/verification/authentication, same-tenant collision rollback, pending identity controls, fresh signed root replacement and persisted policy/ceiling restrictions. These are component tests, not a replacement for exact-head full CI or public recovery qualification.

An additional actual793 counterexample exposed nested connection checkout in authority status: SQLite supported pool size1 exhausted after30 seconds. Baseline test1 FAIL34.50 s. Current status and bootstrap reconciliation reuse the caller's connection through current_epoch_on_connection; the14-case component run includes SQLite and PostgreSQL revocation/status success. Source-wide mypy:385 files clean on the working changes; full Ruff remains141 inherited/owner findings.
