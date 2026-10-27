# M13 Cursor First Enrollment exact-head remediation

**Status: M13 OPEN. PRODUCTION NO-GO.**

Owner: Cursor — Identity & Enterprise Integration.
Handoff: Antigravity, for an independent First Enrollment retest of the candidate below.
No merge, DCO waiver, synthetic identity proofing, production activation, or spending is requested or performed.

## Candidate

| | |
|---|---|
| Recovery baseline | `3e1a32a855c84108d93e22efa0c01b6e7a6404eb` (`origin/codex/m13-secure-antigravity-integration`) |
| Qualified code commit | `c108663ff56e661c047bd0cfaff7c80cd76d4539` |
| Qualified tree | `2cd8c6e62daf02b24be4134a596a69aea53b9857` |
| Parent | `3e1a32a855c84108d93e22efa0c01b6e7a6404eb` |
| Failed workflow | [Absolute First Enrollment `40305744249`](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/40305744249) at that baseline |

The documentation commit that adds this file does not change executable tests. Antigravity should retest the pull-request head.

Codex recovery files are unchanged. `git diff 3e1a32a855c84108d93e22efa0c01b6e7a6404eb c108663ff56e661c047bd0cfaff7c80cd76d4539` is only `scripts/engineering/reproducers/test_m13_absolute_first_passkey.py`. Production authentication, CSRF, root authority, and the protected tenant controller are unchanged.

## Reproduced defects

Hosted run `40305744249`, both Python 3.11 and 3.12, PostgreSQL 16 (`postgres:16-alpine@sha256:cf78e76683b9ca8c5733cbbdce6c9262b45b6767934dd0a95e671f9a0fc20685`):

| Interpreter | Result | When (Asia/Calcutta) |
|---|---|---|
| 3.11 | 20 failed, 78 passed, 15 errors, 270.23s | 26 Oct 2026, 3:49 PM |
| 3.12 | 20 failed, 78 passed, 4 warnings, 15 errors, 275.31s | 26 Oct 2026, 3:51 PM |

Local raw pytest of the same command, clean baseline, `PYTHONPATH=src:.`, `addopts` cleared:

| Interpreter | PostgreSQL | Result |
|---|---|---|
| CPython 3.12.3 | 16.15 (Ubuntu 16.15-0ubuntu0.24.04.1), `postgresql://wp@127.0.0.1:5432/postgres` | 20 failed, 78 passed, 2 warnings, 15 errors, 0 skipped, 188.42s |

Every error and failure is `TenantCreationDeniedError: Authenticated workspace creator mismatch` at `EnterpriseIAM.create_workspace` (`src/responsibleai/enterprise/service.py`).

The 15 errors are setup of `scripts/engineering/reproducers/test_m13_absolute_first_passkey.py`:

- `test_first_enrollment_does_not_elevate_session_or_create_root` on sqlite and postgres
- `test_first_enrollment_rechecks_revocation_at_credential_write` for organization, membership, session, email, absolute_expiry, and idle_expiry, on sqlite and postgres
- `test_concurrent_initial_enrollment_has_one_winner` on postgres

The 20 failures are historical neighbors that call `create_workspace` with a verified user and no session. They are listed under Remaining failures.

### PostgreSQL evidence

Database `wp_titan_disabled_user_67f78654febd` was left by the baseline failure of `test_root_bootstrap_disabled_and_suspended_accounts_rejected` (the generator did not reach its drop). Query on 26 Oct 2026:

| orgs | users | sessions | memberships | provisioning records | email verified |
|---:|---:|---:|---:|---:|---|
| 0 | 1 | 0 | 0 | 0 | true |

The same shape was still present after the candidate runs in `wp_titan_disabled_user_e1cab48c5cd9` and `wp_titan_disabled_user_fe46a23bff50`. The account is verified. No creator session, membership, organization, or provisioning record exists. The denial fires before `provision_organization`.

## Root cause

`create_workspace` loads the account, refuses a missing or disabled account with `EnterpriseError` `FORBIDDEN`, then requires `WebIdentityRepository.get_principal(session_token).user_id == actor_user_id`. An empty default `session_token` yields no principal, so the method raises `Authenticated workspace creator mismatch`.

`create_session` accepts `org_id=None`. `get_principal` does not require a membership when the session has no organization. `provision_organization` then requires that session and its CSRF, a trusted Unix socket (`WHITEPACT_TENANT_CONTROLLER_SOCKET` and `WHITEPACT_TENANT_CONTROLLER_UID`, socket mode with no other-access bits), and the separate controller process. The controller authenticates the session and CSRF, inserts the organization and the owner membership, and activates the tenant. Membership is not created before that call.

The First Enrollment fixture registered and verified the user, then called `create_workspace` with no session and no controller. SQLite `engine.init()` cannot satisfy `ProtectedTenantController`, which refuses a non-PostgreSQL engine.

This is fixture setup. It is not a defect in the mismatch check, CSRF check, socket trust, request binding, or fail-closed controller.

## Corrected fixture setup

`scripts/engineering/reproducers/test_m13_absolute_first_passkey.py` now:

1. Starts the existing disposable controller (`tests.protected_component_tenant.component_controller`): PostgreSQL 16 cloned from the Alembic `0067` template, private Store B, Ed25519 provisioner trust, and a real UDS controller process. Socket mode and UID checks in `provision_organization` stay in force.
2. Registers the user and consumes the product email-verification token.
3. Calls `create_session(user)` with no organization id.
4. Asserts `organizations` and `web_memberships` are empty.
5. Calls `create_workspace` with that session token and CSRF.
6. Opens a separate organization-bound session for the historical passkey ceremony.

The assertion ASTs of these three historical tests are unchanged:

- `test_first_enrollment_does_not_elevate_session_or_create_root` (3 asserts)
- `test_first_enrollment_rechecks_revocation_at_credential_write` (2 asserts)
- `test_concurrent_initial_enrollment_has_one_winner` (4 asserts)

The fixture parameter is `postgres` only. The seven sqlite executions of those same assertions are no longer collected. A sqlite engine cannot pass the controller's PostgreSQL role, schema, and socket contract. Restoring sqlite success would require a controller bypass, which was not added.

Eight denial tests were added. Each requires zero organizations, zero memberships, and zero `tenant_provisioning_records` after the denial:

| Case | Gate that denies |
|---|---|
| Missing session | `Authenticated workspace creator mismatch` |
| Invalid session | `Authenticated workspace creator mismatch` |
| Expired session (`expires_at` in the past), presented with its CSRF | `Authenticated workspace creator mismatch` |
| Other verified user's session and CSRF used as this actor | `Authenticated workspace creator mismatch` |
| Valid session, missing CSRF | `Verified session and CSRF are required for tenant creation` |
| Valid session, invalid CSRF | Controller `403`, `Tenant creation authorization was rejected` |
| Idle-expired session, original CSRF (CSRF lifetime is the session lifetime) | `Authenticated workspace creator mismatch` |
| Valid session, CSRF from a different live session of the same user | Controller `403`, `Tenant creation authorization was rejected` |

Disabled-account ordering is unchanged: a missing or disabled account is still `EnterpriseError` `FORBIDDEN` before the session check. Kind `TEAM` is still rejected before the session check.

## Qualification after the fixture correction

Same pytest command as the workflow. Local PostgreSQL 16.15. `WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:5432/postgres`. Completed 26 Oct 2026, 10:52 PM Asia/Calcutta, at `c108663ff56e661c047bd0cfaff7c80cd76d4539`.

| Interpreter | Result |
|---|---|
| CPython 3.11.17 | 20 failed, 94 passed, 0 errors, 0 skipped, 114 tests, 182.54s |
| CPython 3.12.3 | 20 failed, 94 passed, 0 errors, 0 skipped, 114 tests, 191.62s |

The 15 setup errors are gone. The eight historical PostgreSQL First Enrollment cases and the eight new denial cases pass. Neighbor files that already used `authorized_workspace` still pass: layer 2 identity, both enterprise security branch campaigns, and convergence fixture integrity.

On this clean commit, Ruff accepted `src/responsibleai/enterprise/security/service.py` and the First Enrollment reproducer. Pinned-action, license-header, and non-SLSA trust checks passed. The Titan acceptance blob pin `7e3500ca714701553e69afb2de12174a72d08a22` still matches. Local `m13p4_security_acceptance.py` returned `REFUSED` / `BLOCKED` because this checkout's origin is not the canonical Whitepact remote. That refusal is environmental. It is not a source change.

## Remaining failures

These 20 tests still fail, on both interpreters, with the same creator mismatch. Their files were not edited.

`tests/test_m13_titan_root_adversarial.py`

- `test_root_bootstrap_disabled_and_suspended_accounts_rejected`
- `test_root_bootstrap_revoked_principal_rejected`
- `test_root_bootstrap_pending_quorum_recovery_blocks_out_of_band_bootstrap`
- `test_root_bootstrap_webauthn_adversarial_paths`
- `test_root_bootstrap_concurrent_race_serializes_cleanly`
- `test_root_bootstrap_genuine_unseeded_customer_enrollment_and_bridging`
- `test_root_bootstrap_cross_tenant_isolation_strictly_enforced`
- `test_root_bootstrap_identifier_collision_fails_closed`
- `test_root_bootstrap_disabled_or_suspended_organization_fails_closed`
- `test_root_bootstrap_revoked_membership_or_non_owner_fails_closed`
- `test_root_bootstrap_transaction_rollback_preserves_clean_state`
- `test_root_bootstrap_identifier_recycling_after_revocation`
- `test_root_bootstrap_unverified_email_does_not_imply_external_identity_proofing`
- `test_root_bootstrap_forged_or_stale_identity_qualifications_rejected`
- `test_root_bootstrap_pending_principal_promotion`
- `test_root_bootstrap_unicode_domain_idna_consistency_and_collision`

`tests/test_m13_titan_authority_closure.py`

- `test_full_consequential_authority_chain`
- `test_multi_admin_quorum_recovery_adversarial`
- `test_cross_tenant_and_privilege_escalation_containment`

`tests/test_m13_root_real_concurrency.py`

- `test_independent_operation_bound_completions_commit_only_one_root`

The Absolute First Enrollment workflow stays red until these are authorized and retested. This candidate does not make that workflow green.

## Founder approval required — proposal, not applied

The four founder-approved Fortress recovery tests in `scripts/engineering/reproducers/test_m13_fortress_restore_independent.py`, qualified at `5cea9def`, are outside this failure set and were left unchanged:

- `test_store_b_floor_fences_canonical_governance_epoch`
- `test_tombstone_reconciliation_retains_uncertain_execution`
- `test_runtime_canonical_fence_ignores_other_scope`
- `test_tombstone_reconciliation_handles_real_approval_request_fk`

The 20 remaining tests are protected historical authorization setup outside those four. Security Owner approval is required before any edit. The change is stopped here.

### Before

Each failing test migrates an isolated database, registers a user, verifies email, and creates the workspace with no session:

```python
org = await iam.create_workspace(
    actor_user_id=uid,
    name=name,
    slug=slug,
    kind="ORGANIZATION",
)
```

There are 18 such calls in `tests/test_m13_titan_root_adversarial.py`, 5 in `tests/test_m13_titan_authority_closure.py`, and 1 in `tests/test_m13_root_real_concurrency.py`.

### After, pending approval

Keep every existing assertion. Do not insert an organization or membership before creation. Do not weaken `create_workspace`, `create_session`, `provision_organization`, or the controller.

For each test, bind the already-migrated PostgreSQL database to the existing disposable controller process used by the passing enterprise fixtures in this workflow (`component_controller` / `attach_component_controller`). After email verification and before `create_workspace`:

```python
token, csrf = await identities.create_session(actor_user_id)
org = await iam.create_workspace(
    actor_user_id=actor_user_id,
    name=name,
    slug=slug,
    kind="ORGANIZATION",
    session_token=token,
    csrf=csrf,
)
```

`create_session` is called with no organization id. The session user must be the `actor_user_id` for that call. A second organization in the same test needs its own creator session for its own user. The controller remains responsible for the membership insert, Unix socket trust, CSRF compare, request binding, and fail-closed response.

## What Antigravity should retest

1. Exact pull-request head.
2. Workflow command from `.github/workflows/m13-absolute-enrollment-review.yml` on Python 3.11 and 3.12 with PostgreSQL 16.
3. Expect the First Enrollment file, including the eight denial tests, to pass, and the 20 historical tests above to keep failing until the proposal is approved.
4. Confirm no change under Codex recovery paths, `src/responsibleai/enterprise/security/service.py`, `src/responsibleai/data_governance/tenant_controller.py`, or `src/responsibleai/data_governance/tenant_client.py`.

M13 remains OPEN. Production remains NO-GO.
