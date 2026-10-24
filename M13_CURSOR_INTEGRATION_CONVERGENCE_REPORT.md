# M13 Cursor integration convergence report

**Verdict: C — SECURITY CONTRACT BLOCKED**

Enterprise provisioning fixtures that were failing before their security assertions now run on PostgreSQL 16 through the protected controller. The positive first-deployment gate, Sovereign onboarding, and the three Fortress recovery tests remain blocked on human Security Owner or Codex recovery authority. Introduced-commit DCO is a separate human/compliance block (verdict D for that item only).

M13 remains OPEN. M14 is not authorized. Production remains a global no-go. Budget remains ₹0.

## 1. Starting and final exact SHA / TREE / PARENT

Starting candidate, draft PR #227 head `codex/whitepact-m13-r1-operator-recovery`, commit time 24 Oct 2026, 12:21 IST:

| | |
|---|---|
| HEAD | `41e2cacbfcfa813e433686ee65523d9172124766` |
| TREE | `b05776d57595413fce7f6150bea365c075e2f003` |
| PARENT | `51e93b0fea3a0514e0fd4a350cd92d8d550db421` |

Cursor branch: `cursor/m13-integration-convergence-0f76`, created from that HEAD. No Codex recovery commit was rewritten.

Implementation commits, each with `Signed-off-by: Cursor Agent <cursoragent@cursor.com>`:

| HEAD | TREE | PARENT | Subject |
|---|---|---|---|
| `04ea372ace4a28720e46458d56bf4b1b01fed46b` | `1afd8eb77950b43fb46f99f85add88e4fde20f17` | `41e2cacbfcfa813e433686ee65523d9172124766` | fix: refuse inactive workspace creators before session mismatch |
| `3ecf181937d7ef77fbd8ae8d83702275ab72304a` | `b4c773b74eec933bcf73fc2e6483e59f68ce4f12` | `04ea372ace4a28720e46458d56bf4b1b01fed46b` | fix: store OAuth scope denial in the pinned audit column |
| `bb1161ce9386f7e29cefd95d706059bfa016ddfb` | `6906711f8d39587e534e82c509509576862d1558` | `3ecf181937d7ef77fbd8ae8d83702275ab72304a` | test: provision enterprise and MCP fixtures through the protected controller |

The review tip is the latest commit on this branch after this report is committed. Section 11 is updated when hosted checks for that tip are terminal. This file does not rewrite `41e2cac`.

## 2. Full original failure inventory

Hosted pull_request CI at the starting SHA, recorded 24 Oct 2026, 12:21 IST (`2026-10-24T06:51:47Z`):

| Workflow | Run | Result |
|---|---|---|
| M13 Absolute Runtime Review | `40071871640` | FAIL. `unit` 3.11 job `120806863067` and 3.12 job `120806863082`. `native` 3.11 and 3.12 passed. |
| M13 Sovereign Authority Development Qualification | `40071871646` | FAIL. `development-qualification` 3.11 job `120806863132` and 3.12 job `120806863108`. |
| M13-P4 Product Candidate Review | `40071871648` | PASS (console, contracts 3.11 and 3.12). |
| M13 R1 Offline Operator Recovery | `40071871630` (and push run `40071869013`) | PASS for recovery 3.11 and 3.12. |
| M13-I1 Independent Integration Review | `40071871662` | FAIL. `independent-security` 3.11 job `120806863195` and 3.12 job `120806863159`. `introduced-dco` job `120806863193`. `real-customer-journey` job `120806862953`. `native-container-scope` and `inherited-policy-gates` passed. |

I1 `independent-security` failures were the same 219 tests on Python 3.11 and 3.12 (438 results). Classification is historical setup incompatibility: the tests died in tenant setup, before the assertion the test was written to make.

| Tests | Error | Files |
|---:|---|---|
| 157 | `Tenant creation cannot assign paid entitlement` | `test_mcp_authority_tools` 40, `test_mcp_server_authority_batch10` 33, `test_mcp_oauth_authorization_server` 20, `test_mcp_oauth_claude_callback` 18, `test_mcp_oauth` 10, `test_mcp_verified_principal` 10, `test_mcp_http_transport` 9, `test_mcp_transport_security` 7, `test_mcp_intent_contract` 4, `test_mcp_org_status_live` 4, `test_mcp_protocol_matrix` 1, `test_mcp_ws2_live_invalidation_matrix` 1 |
| 43 | `Authenticated workspace creator mismatch` | `test_enterprise_security_branch_campaign_batch2` 28, `test_enterprise_security_branch_campaign` 8, `test_enterprise_layer2_identity_security` 4, `scripts/engineering/reproducers/test_m13_dual_titan_root.py` 3 |
| 19 | `Verified session and CSRF are required for tenant creation` | `test_mcp_ws2_failclosed_dependency_matrix` 9, `test_mcp_ws2_live_invalidation_matrix` 7, `test_mcp_ws2_authority_matrix` 2, `test_mcp_ws2_upstream_reconciliation` 1 |

`PytestUnhandledThreadExceptionWarning` / "Event loop is closed" followed those setup exceptions. They are not a separate root cause.

Absolute Runtime unit failures, both Python versions, unresolved security contract / Codex R1 obligation:

- `test_m13_fortress_restore_independent.py::test_store_b_floor_fences_canonical_governance_epoch`
- `test_m13_fortress_restore_independent.py::test_tombstone_reconciliation_retains_uncertain_execution`
- `test_m13_fortress_restore_independent.py::test_tombstone_reconciliation_handles_real_approval_request_fk`

Each raises `RecoveryAuthorizationError: Verified offline operator recovery session required`.

Sovereign and `real-customer-journey`: default journey `acceptance=BLOCKED` at `organization_onboarding` with `TENANT_CREATION_NOT_AUTHORIZED`. The workflow requires default journey exit code 2 and exactly 17 PASS / 1 BLOCKED / 7 NOT_EXECUTED, and the development prototype requires 25 PASS. Observed sovereign artifacts for 3.12: PASS 4 (signup, email verification, password login, logout), BLOCKED 1 (onboarding), NOT_EXECUTED 20. `durable_store_b_state` was null and `controller_context_verified` was true. Unresolved security contract. Not reclassified as a passing earlier rejection.

`introduced-dco`: `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` lacks `Signed-off-by`. The job scans `5291cc6d4e750c6ec5ec0688f8bfc9e3b72a8558..HEAD`. External human approval / compliance. This campaign did not rewrite that commit.

## 3. Common root causes

1. **Paid plan at creation.** `OrgRepository.create_org` refuses `plan != FREE` before insert. Historical MCP fixtures called `create_org(..., plan=ENTERPRISE)` on PostgreSQL. One fix unblocks the paid-entitlement family: create FREE through the controller, then `set_plan_status`.
2. **No verified session or CSRF.** `provision_organization` requires both, aimed at a private UDS controller. WS2 fixtures called `create_org` without them.
3. **Creator mismatch.** `EnterpriseIAM.create_workspace` requires `principal.user_id == actor_user_id`. Enterprise and dual-titan completion tests called it with a verified user and no session.
4. **Disabled-account ordering.** A disabled creator with no session raised creator mismatch (`TenantCreationDeniedError`) before the test's `EnterpriseError FORBIDDEN` assertion. Production ordering now checks the account first.
5. **Global restore gate not bound to component Store B.** After provisioning succeeded, MCP tools returned `Tenant authority remains quarantined` because `assert_tenant_provisioning_complete` requires the global gate provider to be the durable Store B that is READY. The component fixture now binds that gate. This is the existing structural Stage 3 fixture, not first-deployment bootstrap.
6. **PostgreSQL type strictness.** `governance_evidence.authority_version` and `consent_version` are strings. The upstream reconciliation fixture had used integers, which SQLite coerced.
7. **OAuth audit width.** `insufficient_scope` is 18 characters. Revision 0067 pins `oauth_auth_events.outcome` at `VARCHAR(16)`. The scope-denial request died on the audit insert instead of returning HTTP 403.
8. **Second tenant without a controller process.** Protocol-matrix cross-tenant proof used HTTP provisioning while the governance fixture had created the first tenant in-process and had not published `WHITEPACT_TENANT_CONTROLLER_UID`.
9. **No READY publication from empty Store B.** Customer onboarding and the sovereign prototype stop because the strict journey does not have qualified installation evidence. `scripts/engineering/m13_bootstrap_authorization.py` still refuses to publish READY. That is intentional.
10. **Fortress recovery session.** The three unit failures stop on the R1 verified-session requirement. Left untouched.

## 4. Production defects fixed

- `src/responsibleai/enterprise/service.py`: `create_workspace` loads `web_users.disabled` for `actor_user_id`. A missing or disabled account raises `EnterpriseError` code `FORBIDDEN` ("Workspace creator is not an active account.") before the session check. Enabled users without a matching session still get `Authenticated workspace creator mismatch`. Kind `TEAM` still fails the kind check first. No session is created inside this method.
- `src/responsibleai/auth/mcp_oauth.py`: audit storage maps `insufficient_scope` to `scope_missing` (13 characters). The HTTP body and challenge still say `insufficient_scope`. Outcomes longer than 16 characters with no mapping raise `server_error` instead of being truncated. Revision 0067 was not edited. `SUPPORTED_POSTGRES_REVISIONS` stays `{0067}`.

## 5. Historical fixtures modernized

`tests/protected_component_tenant.py` is the shared disposable setup: PostgreSQL 16 template at Alembic `0067`, Ed25519 provisioner trust, signed Store B publication ledger, protected controller process, verified user, CSRF session, FREE creation, then `set_plan_status` when the caller needs ENTERPRISE. `attach_component_controller` binds `RestoreReadinessGate` to that Store B and restores the previous gate afterwards.

Migrated to that setup, without changing the denial assertions those tests were written to reach:

- MCP: authority tools, HTTP transport, intent contract, OAuth, OAuth authorization server (Claude callback uses the same fixture), org status, protocol matrix, server authority batch 10, transport security, verified principal, WS2 authority / fail-closed / live invalidation / upstream reconciliation.
- `tests/org_http_fixtures.py`: PostgreSQL callers use the helper. SQLite callers still use `create_org` and stay fail-closed. They were not bulk-migrated.
- Enterprise: layer 2 identity, security branch campaign, campaign batch 2. Success paths use `authorized_workspace`. Kind and disabled-account negatives still call `create_workspace` without a manufactured success.
- `test_m13_dual_titan_root.py::test_completion_rechecks_persisted_owner_qualification` only. Revocation assertions in that test were not rewritten.
- `tests/test_mcp_governance_dispatch.py`: the governed app now also starts `controller_process` so a later test can provision another tenant on the same database and Store B.

`tests/test_mcp_ws2_upstream_reconciliation.py` stores `authority_version` and `consent_version` as `"1"`.

## 6. Test security objectives preserved

`tests/test_protected_component_tenant.py::test_protected_prerequisites_keep_creation_denials_and_tenant_boundary` passed on Python 3.12:

- direct ENTERPRISE `create_org` denied (`paid entitlement`)
- `create_org` without CSRF denied
- `create_workspace` without a session is creator mismatch
- Bob's session cannot create Alice's workspace
- Alice's authorized workspace stays FREE
- Bob's ENTERPRISE plan is applied only by `set_plan_status`
- Alice `authorize` against Bob's org is `WRONG_TENANT`
- disabling Alice makes a later `create_workspace` `EnterpriseError` `FORBIDDEN` even if another session is presented

OAuth `test_forged_bearer_and_missing_scope_are_denied` still requires HTTP 401 for a forged bearer and HTTP 403 with `error=insufficient_scope`. It now also requires an audit row `scope_missing`, no stored `insufficient_scope`, and no outcome longer than 16 characters.

Paid creation is still attempted, and must raise, inside `provision_component_organization` before the billing transition.

No security test was skipped, deleted, xfailed, or renamed. Workflow files, DCO policy, migrations, and security triggers were not edited.

## 7. Real authorized onboarding outcomes

Not qualified. The strict customer journey still blocks at organization onboarding because Store B is not READY and this campaign does not seed READY into that harness. Register, verify, login, and logout were already PASS at the starting SHA. Protected tenant activation, policy evaluation, execution grant, SDK execution, and revocation were NOT_EXECUTED. Identity verification was not fabricated. No API success was mocked.

## 8. Authorized bootstrap qualification or blockers

Positive gate: **BLOCKED**.

`tests/test_stage3_bootstrap_authorization_poc.py` passed together with `tests/test_operator_recovery_authorization.py` (40 passed, 24 Oct 2026, about 14:15 IST, Python 3.12). The POC still consumes a valid authorization once and leaves readiness false. `require_ready_verified` is not implemented. No installation record was manufactured. No Security Owner decision was self-approved. No production bootstrap was activated. Missing or unverifiable history continues to fail closed.

## 9. Sovereign Authority results

Not re-run as a journey on this tip. Starting hosted result stands: both Python versions fail the development-qualification job because onboarding is BLOCKED and the prototype is not 25 PASS. The pytest portion of that workflow was not the cited failure mode. Re-running it without a human installation approval would either repeat the block or require seeding READY, which is out of authority. Assertion counts in `.github/workflows/m13-sovereign-authority.yml` were not changed.

Preserved, by not editing them: principal identity, tenant boundaries, cross-tenant denial, database-outage fail-closed behavior, recovery after outage, approval and grant revocation, privilege resurrection checks, and audit assertions inside `tests/test_sovereign_authority.py`.

## 10. R1 non-regression evidence

Codex recovery implementation was not modified. Local Python 3.12, PostgreSQL 16:

- `tests/test_operator_recovery_authorization.py` passed (included in the 40).
- `tests/test_stage3_bootstrap_authorization_poc.py` passed. Ready publication remains absent.

The full R1 matrix (`tests/test_operator_recovery_*.py`, `tests/test_stage3_*.py`, neighbors, native Docker image `python:3.12-slim@sha256:7a8b475003c4fe15a2cd4e55e5cfc2f3560bdc9333d624f24cdd6d4340fd7a17`) was not re-executed here. Docker is not available in this environment (`docker` missing). Hosted R1 at `41e2cac` was PASS. This branch does not touch `operator_recovery*.py`, `backup_defense.py`, or `ops/operator_recovery.py`, so the R1 path filter will not schedule that workflow on a pull request against the R1 branch. That PASS remains the hosted baseline. It is not a new exact-head rerun.

The three Fortress conflicts stay outstanding obligations. The verified-session requirement was not bypassed.

## 11. Complete mandatory hosted CI results

Exact head `fc07c1790e48333671377f17e840d4e38dd4a53f`, pull request #228, checks started 24 Oct 2026, 14:21 IST (`2026-10-24T08:51:26Z`). Absolute Runtime, P4, and R1 did not schedule: this diff does not touch their path filters. Hosted R1 and P4 remain the starting-SHA passes in section 2. Fortress was not re-run.

| Check | Run / job | Result |
|---|---|---|
| I1 `independent-security` Python 3.11 | `40079662155` / `120830372225` | PASS, 23m43s, finished 14:45 IST. Includes the MCP suite and the enterprise identity step. |
| I1 `independent-security` Python 3.12 | `40079662155` / `120830372017` | CANCELLED at the 25-minute job limit, 14:46 IST. MCP transport, passkey rollback, and root-email steps had already succeeded. The WebAuthn/enterprise step was cancelled before it finished. Not an assertion failure. |
| I1 `native-container-scope` | same run / `120830372294` | PASS, 1m52s. |
| I1 `inherited-policy-gates` | same run / `120830372310` | PASS, 9s. |
| I1 `introduced-dco` | same run / `120830372240` | FAIL, 6s. Same unsigned commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`. |
| I1 `real-customer-journey` | same run / `120830372213` | FAIL, 1m47s. Journey pytest files passed (13 and 6). Browser onboarding returned HTTP 503 and stopped. APEX journey onboarding returned HTTP 403 from the provisioning controller. Both scripts exited 2. |
| Sovereign `development-qualification` 3.11 | `40079662084` / `120830371714` | FAIL, 6m31s. Journey script exit 1 (stage counts are not 17/1/7) and prototype exit 2. |
| Sovereign `development-qualification` 3.12 | `40079662084` / `120830371644` | FAIL, 5m55s. Log shows register 202, verify 200, login 200, onboarding 403, logout 200, session 401. Default-journey assertion exited 1. Prototype exited 2. |

A follow-up on this branch starts the protected controller process only in the cross-tenant protocol test, so the governed-app suite no longer pays that process on every test. That is aimed at the Python 3.12 timeout. It does not change the onboarding or DCO results.

Local Python 3.12 evidence already collected, `WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:5432/postgres`, PostgreSQL 16.15:

| Run | When (IST) | Result |
|---|---|---|
| MCP `tests/test_mcp*.py`, lifecycle, SSE binding, enterprise layer 2, both enterprise campaign modules, component proof, apex origin | 24 Oct 2026, 13:55–14:05 | 601 passed, 2 failed. Failures: OAuth scope audit width; protocol-matrix second tenant had no controller process. |
| Those two tests after the fixes | 24 Oct 2026, ~14:20 | 2 passed. |
| Governance dispatch, protocol matrix, live invalidation, HTTP credential negatives, wave 1, M13-P4 MCP lifecycle, OAuth review class, dual-titan `-k 'unverified or completion'` | 24 Oct 2026, ~14:25, 300s | 88 passed. |
| Bootstrap POC, operator recovery authorization, component proof | 24 Oct 2026, ~14:15 | 40 passed. |

Python 3.11 is not installed on this machine. Hosted 3.11 is the 3.11 evidence. No test was weakened to avoid that gap.

## 12. Remaining engineering failures

Hosted Python 3.11 `independent-security` passed, so the original 219 setup failures are cleared on that runner. Hosted Python 3.12 completed the same MCP, passkey, and root-email steps, then the job limit cancelled the enterprise step. That timeout is the remaining engineering item on this branch.

Still red, and not claimed as fixed:

- Three Fortress tests (both Python versions at the starting SHA).
- Sovereign default journey and development prototype.
- I1 `real-customer-journey` (exit code 2 at onboarding).
- I1 `introduced-dco` for historical commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`.
- Full R1 Docker matrix and native container jobs were not re-run locally.

## 13. Human-owned DCO / security decisions

- Sign-off disposition for `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` and any other unsigned commit in `5291cc6d4e750c6ec5ec0688f8bfc9e3b72a8558..HEAD`. This agent did not forge trailers or rewrite history.
- Security Owner approval if a future change is to publish Store B READY for a genuinely new deployment. This campaign did not supply that evidence.
- Codex / CTO disposition of the three Fortress tests that require a verified offline operator recovery session.
- Any change to the sovereign 17/1/7 or 25-PASS expectations. Not made.

## 14. Known limitations and unqualified claims

- Local verification is Python 3.12.3 only.
- Docker-backed native isolation and the R1 image pull were not run.
- Customer journey, SDK execution, and revocation after a real onboarding were not executed. Passing login does not imply an execution grant.
- Component Store B READY is a structural test fixture. It is not installation authority, customer acceptance, or a production credential.
- `scope_missing` is the durable audit token for the OAuth error `insufficient_scope` because the pinned column cannot store the protocol string. The HTTP denial string did not change.
- SQLite unit tests that still call `create_org(plan=ENTERPRISE)` were left fail-closed on purpose.
- M13 is not closed. M14 was not started. Nothing was deployed.

## 15. Exact code ready for independent review

Review only the commits in section 1 on `cursor/m13-integration-convergence-0f76`. Suggested base: `codex/whitepact-m13-r1-operator-recovery` (`41e2cac`), so the diff is these commits and not the 501-commit distance from `main`.

Production:

- `src/responsibleai/enterprise/service.py`
- `src/responsibleai/auth/mcp_oauth.py`

Tests and fixture:

- `tests/protected_component_tenant.py`
- `tests/test_protected_component_tenant.py`
- `tests/org_http_fixtures.py`
- `tests/test_enterprise_layer2_identity_security.py`
- `tests/test_enterprise_security_branch_campaign.py`
- `tests/test_enterprise_security_branch_campaign_batch2.py`
- `tests/test_mcp_authority_tools.py`
- `tests/test_mcp_governance_dispatch.py`
- `tests/test_mcp_http_transport.py`
- `tests/test_mcp_intent_contract.py`
- `tests/test_mcp_oauth.py`
- `tests/test_mcp_oauth_authorization_server.py`
- `tests/test_mcp_org_status_live.py`
- `tests/test_mcp_protocol_matrix.py`
- `tests/test_mcp_server_authority_batch10.py`
- `tests/test_mcp_transport_security.py`
- `tests/test_mcp_verified_principal.py`
- `tests/test_mcp_ws2_authority_matrix.py`
- `tests/test_mcp_ws2_failclosed_dependency_matrix.py`
- `tests/test_mcp_ws2_live_invalidation_matrix.py`
- `tests/test_mcp_ws2_upstream_reconciliation.py`
- `scripts/engineering/reproducers/test_m13_dual_titan_root.py`

## Concise summary

- Original failing tests: 219 per Python version in I1 (157 paid entitlement, 43 creator mismatch, 19 missing session/CSRF), plus 3 Fortress tests per Python version, plus Sovereign/customer-journey onboarding BLOCKED, plus one unsigned historical commit.
- Corrected on hosted Python 3.11: the 219 setup failures (`independent-security` PASS at `fc07c179`). Local Python 3.12 suites passed. Hosted Python 3.12 passed those same MCP and root-email steps, then the 25-minute job cancelled the last enterprise step.
- Remaining failures: Fortress verified-session requirement, READY publication / onboarding (HTTP 403 or 503), historical DCO, and the Python 3.12 job-limit cancellation.
- Independent verification: hosted PostgreSQL 16 on Ubuntu 24.04 for the checks in section 11, plus local Python 3.12.3.
- Required external approvals: Security Owner for any READY publication, Codex/CTO for the three Fortress conflicts, repository owner for historical DCO sign-off.
