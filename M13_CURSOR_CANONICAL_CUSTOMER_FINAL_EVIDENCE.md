# M13 Cursor canonical customer final evidence

Verdict: **ENGINEERING COMPLETE — EXTERNAL/HUMAN BLOCKERS REMAIN**

This is not **I1 QUALIFIED — FULL DEFAULT CUSTOMER JOURNEY GREEN**.
The default 25-stage ceremony still stops at `judgment` because reusable API
credentials require canonical `IDENTITY_VERIFIED`. Historical DCO commit
`39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` still has no `Signed-off-by` and no
owner exception. M13 stays OPEN. Global production is NO-GO. M14 is not
authorized.

## Baseline and head

| Item | Value |
|---|---|
| Audited baseline | `b00e2a39aa47ae24e6a2a1de4d3f2d6b6ea81c15` |
| Implementation commit | `89b539e89b17650d7b1a0123fd1a7f3ea2c264c4` |
| Baseline tree | `ee9d89de0f161c8189ea585ad5d8c056e692d7ae` |
| Baseline parent | `c9fb547497156ac363735c8056ebde2c85b4b4be` |
| Branch | `cursor/m13-i1-customer-closure-0f76` |
| Base for review | `codex/m13-secure-antigravity-integration` |
| Draft PR #231 | unchanged Codex head; this work is a separate branch |
| Local journey git stamp | baseline SHA, `clean: false`, because the ceremony ran on the dirty worktree before `89b539e8` |
| Codex R1 / Fortress | not modified |

Python 3.12.3 and PostgreSQL 16 on `127.0.0.1:5432` produced the local receipts.
Python 3.11 was not installed in this environment. Hosted I1 and Sovereign
workflows run 3.11 and 3.12; their conclusions belong to the pull request head
after push and are not claimed here.

## 1. Canonical stages and the real default outcome

Ceremony: `python scripts/engineering/m13_apex_customer_journey.py --authorized-disposable-bootstrap`.
Harness: `tests/js/m13-apex-customer.mjs`. Chromium `151.0.7922.34`. Fresh
PostgreSQL. `authority_seeded: false`. `development_prototype: false`.
`production_enabled: false`. Exit code 2. Acceptance `BLOCKED`. Stop
`judgment`. Counts: 17 PASS, 1 BLOCKED, 7 NOT_EXECUTED. That is the same count
contract Sovereign already requires for the default journey.

Read-only diagnostics from that run: user exists, one canonical principal, one
root record, two consent records. The disposable installation diagnostic
reported `durable_store_b_state: READY` and `controller_context_verified: true`.
That reading is the authorized disposable bootstrap fixture. It is not a
production launch authorization and it did not issue `IDENTITY_VERIFIED`.

Identity projection at `legitimate_identity_qualification`: `reported_status`
`BASIC_VERIFIED`, `email_verified: true`, `provider_present: false`,
`assurance_present: false`. Email verification and WebAuthn UV were not written
as legal identity.

| # | Stage | HTTP evidence | Outcome |
|---|---|---|---|
| 1 | signup | POST `/api/v1/web/auth/register` 202 | PASS |
| 2 | email_verification | POST `/api/v1/web/auth/verify` 200 | PASS |
| 3 | password_login | POST `/api/v1/web/auth/login` 200 | PASS |
| 4 | organization_onboarding | POST `/api/v1/web/onboarding` 200, GET session 200, GET authority status 200 | PASS |
| 5 | passkey_enrollment | register begin/finish and step-up 200 | PASS |
| 6 | passkey_assertion_verification | authenticate begin/finish 200 | PASS |
| 7 | secure_elevated_session | prior session GET 401, new session GET 200, cookies rotated | PASS |
| 8 | legitimate_identity_qualification | GET `/api/enterprise/identity/verification` 200, BASIC_VERIFIED | PASS |
| 9 | explicit_customer_consent | persisted on bootstrap complete | PASS |
| 10 | root_initiation | POST bootstrap initiate 200 | PASS |
| 11 | root_proof_of_possession | WebAuthn challenge 200, bootstrap complete 200 | PASS |
| 12 | root_activation | GET authority status 200 | PASS |
| 13 | application_registration | POST/GET applications 200, `registration_authority: false` | PASS |
| 14 | agent_registration | POST agents 200, `registration_authority: false` | PASS |
| 15 | capability_delegation | POST delegations 200 | PASS |
| 16 | policy_assignment | POST `/api/web/policy/rules` 200, GET policy 200 | PASS |
| 17 | judgment | POST `/api/web/api-keys` 403 `IDENTITY_VERIFICATION_REQUIRED` | BLOCKED |
| 18 | human_approval | not called | NOT_EXECUTED |
| 19 | execution_grant | not called | NOT_EXECUTED |
| 20 | controlled_execution | not called | NOT_EXECUTED |
| 21 | evidence_verification | not called | NOT_EXECUTED |
| 22 | revocation | not called | NOT_EXECUTED |
| 23 | post_revocation_execution_attempt | not called | NOT_EXECUTED |
| 24 | post_revocation_denial | not called | NOT_EXECUTED |
| 25 | logout_session_invalidation | POST logout 200, GET session 401 | PASS |

The old default branch marked `judgment` BLOCKED even after HTTP 201 intent
admission (`INTENT_NARROWING_IS_NOT_CUSTOMER_JUDGMENT_OR_EXECUTION_GRANT`).
That branch is replaced. If a reusable key is actually issued, the harness now
declares an intent for the registered agent, calls
`POST /api/governance/tools/call` with that `agent_id`, and continues through
human approval, `resume_approval` execution, evidence verification, agent
disablement, a post-revocation tool call, and approval replay. This run never
entered that branch. The 403 identity denial remains the stop, so stages 18–24
stay NOT_EXECUTED. Sovereign's 17/1/7 assertion is unchanged.

Consent on the default path now names the real harmless tool
`rai_policy_check`, matching the tool catalog the continuation calls. That did
not change the stage statuses above.

`admit_registered_agent` binds `agent_id` only to an ACTIVE `AI_AGENT` in the
credential's organization. A foreign or disabled agent raises
`AGENT_NOT_ACTIVE_IN_ORGANIZATION`. The API key remains the caller. This is not
agent proof-of-possession and does not write `IDENTITY_VERIFIED`. The
development prototype (`--development-agent-prototype`, B1 `agent_pop`) is
still a separate ceremony.

## 2. Negative security evidence

Local, Python 3.12.3, PostgreSQL 16, 52 passed in 103.64s:

- `tests/test_stage3_persona_sandbox.py`
- `tests/test_governed_agent_admission.py`
- `tests/test_m13_apex_journey_evidence.py`

Covered refusals:

- Synthetic Persona approval stays `SANDBOX_SIMULATED`, `canonical_issuance_allowed` false, and does not set `web_users.verification_status` to `IDENTITY_VERIFIED`.
- Signature, stale timestamp, future timestamp, body mutation, replay conflict, decline-then-approval, expiry, template, environment, and provider reconciliation failures deny sandbox approval.
- Production Persona keys, `WHITEPACT_ENV=production`, and unrelated ledgers are refused.
- `evaluate_sandbox_nonproduction_credential` denies synthetic evidence, production and staging targets, a receipt that claims `canonical_issuance_allowed`, a mismatched policy version, a production provider environment, and a non-digest database identity. `credential_material` stays null. `production_valid` stays false.
- Malformed agent ids and legacy flat credentials are refused. A second tenant's agent and a DISABLED agent are refused.
- Receipt integrity tests still reject seeded authority, a PASS verdict that contradicts incomplete stages, and privileged PASS after an unqualified boundary.

Not executed on this default ceremony, because the identity gate returned 403 before them: cross-tenant tool execution, approval replay, grant expiry, and policy drift. Those denials remain the existing kernel's job. This run does not add a new execution receipt for them.

## 3. Identity-provider provenance

No Persona API key, webhook secret, or inquiry was enrolled. Every sandbox
receipt this code can emit locally uses provenance `SANDBOX_SIMULATED`.
Injected HTTP transports are `SYNTHETIC_PROTOCOL_FIXTURE`. A real enrolled
client with no test transport would be labeled `PROVIDER_NETWORK` and can reach
only `WITHHELD_PENDING_ENROLLED_PROVIDER`. That disposition does not mint a
credential, does not write `IDENTITY_VERIFIED`, and is invalid when
`WHITEPACT_ENV` is production or the target environment is not `DEVELOPMENT`.

Issuer trust constant: `persona-sandbox-development-issuer:v1`.
Audience: `whitepact:persona-sandbox-integration:v1`.
Policy version must match the enrolled `PersonaSandboxPolicy.policy_version`
and `^[a-z0-9][a-z0-9.-]{2,63}$`.

The customer journey's legal-identity provider was absent
(`provider_present: false`). Canonical issuance in
`CredentialIssuancePolicy` still requires `IDENTITY_VERIFIED` in development,
staging, and production. `BASIC_VERIFIED` is not enough.

## 4. Steps that require authorized Persona Sandbox access

Do not buy a subscription. An authorized operator, in a non-production
`WHITEPACT_ENV=development` deployment, must supply:

1. An API key whose prefix is `persona_sandbox_` and whose length is at least 40 characters.
2. One or two webhook HMAC secrets, each at least 32 bytes.
3. Persona sandbox environment id and organization id.
4. Inquiry template id `itmpl_…` and template version id `itmplv_…`.
5. An isolated PostgreSQL database whose name starts with `wp_persona_sandbox_`, matching `postgres_identity`.
6. A private mode `0600` ledger directory and a policy version enrolled with the audience above.

Even after a real `inquiry.approved` plus API reconciliation to
`SANDBOX_APPROVED`, the adapter must not call `VerificationService.apply_provider_event`.
Sandbox approval is not canonical identity and is not valid for production
credentials. No such enrolled access was available here.

## 5. Human DCO resolution

Commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`

| Field | Value |
|---|---|
| Author | Techezz Infos `<Techezzinfos@gmail.com>` |
| Committer | Techezz Infos `<Techezzinfos@gmail.com>` |
| Author and committer date | 2026-10-15T18:41:16+05:30 |
| Subject | `docs(security): publish WhitePact M13-S4 enterprise security qualification and Codex handoff suite` |
| Parent | `57c69344961196fd89b40e8ffec65c06a1898fce` |
| Tree | `06f9add5d47fe5af1a7a6c45f8955da5d9b57e9a` |
| Files | 14 files under `docs/security/m13s4/` only |
| Trailer | no `Signed-off-by`, no `Co-authored-by` |

Repository policy in `CONTRIBUTING.md` requires `Signed-off-by` on every commit
in a pull request. Existing history is not rewritten. Owner exceptions already
exist only for the object names listed in
`compliance/DCO_HISTORICAL_EXCEPTION_2026-10-09.md` and
`compliance/DCO_HISTORICAL_EXCEPTION_2026-10-11.md`. An exception is not a
sign-off. `.github/workflows/dco.yml` allowlists those exact object names.
`.github/workflows/m13i1-integration.yml` job `introduced-dco` does not. It
fails any non-merge commit from `5291cc6d4e750c6ec5ec0688f8bfc9e3b72a8558` to
HEAD that lacks the trailer. This closure does not add an exception, does not
amend `39619c4b`, and does not disable either check.

Owner action, one of these, by the true author or the repository owner:

1. Techezz Infos, or the owner acting with the author's agreement, adds a real
   `Signed-off-by: Techezz Infos <Techezzinfos@gmail.com>` without impersonation.
   Rewriting the published object requires explicit authorization. This agent
   did not rewrite it.
2. The owner publishes a new historical-exception record, limited to object
   name `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`, stating that the exception
   is not a sign-off. Then the owner adds that exact object name to the `case`
   statement in `.github/workflows/dco.yml` and to the same exact-match skip in
   `introduced-dco`. No date cutoff, author wildcard, or bot exemption.

Until one of those happens, `introduced-dco` stays red.

## 6. Code changes and local verification

- `src/responsibleai/enterprise/persona_sandbox.py`: nonproduction credential decision. Withheld only for an enrolled provider-network approval. Never mints credential material.
- `src/responsibleai/governance/agent_admission.py`: tenant-bound agent selection for a governed call.
- `src/responsibleai/dashboard/app.py`: `POST /api/governance/tools/call` accepts an optional registered `agent_id`.
- `tests/js/m13-apex-customer.mjs`: default path continues into approval, grant, execution, evidence, and revocation only after a real API key. The 403 identity denial still stops the ceremony.
- `tests/test_governed_agent_admission.py`, `tests/test_stage3_persona_sandbox.py`: the negatives above.

`ruff check` passed on the edited Python. License headers passed.
`node --check tests/js/m13-apex-customer.mjs` passed.

Hosted checks on evidence head `3d7dc2cf6dacdafd4d29ad6a7882c6a80377d7d4`
(tree `f3befc29ef91cbff7c06a987dbd5445f2d221ad1`, clean) started 02:11 IST on
26 October 2026. Fifteen of seventeen checks passed. The two failures are the
identity gate and the historical DCO commit.

| Check | Result |
|---|---|
| I1 `real-customer-journey` run `40231949872` job `121285360677` | FAIL, exit 2. Hosted artifact `m13apex-customer-evidence.json`: acceptance `BLOCKED`, stop `judgment`, 17 PASS / 1 BLOCKED / 7 NOT_EXECUTED / 0 FAIL. HTTP 403 `IDENTITY_VERIFICATION_REQUIRED`. Chromium 151.0.7922.34. Git stamp matches this head. |
| I1 `introduced-dco` job `121285360777` | FAIL. Only error: `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` lacks `Signed-off-by`. |
| I1 `independent-security` 3.11 and 3.12 | PASS, 10m41s and 11m39s |
| I1 `independent-mcp` 3.11 and 3.12 | PASS, 14m54s and 15m22s |
| I1 `persona-sandbox-protocol` 3.11 and 3.12 | PASS, 2m48s and 3m39s |
| I1 `virtual-authenticator-component` 3.11 and 3.12 | PASS |
| I1 `native-container-scope` | PASS, 1m49s |
| I1 `inherited-policy-gates` | PASS |
| I1 WebAuthn component artifact | `component_acceptance: PASS`, scope `WEBAUTHN_COMPONENT_ONLY`, production `GLOBAL PRODUCTION NO-GO` |
| Sovereign `development-qualification` 3.11 and 3.12, run `40231949870` | PASS, 8m50s and 9m30s. That job requires default exit 2 with 17/1/7 and prototype 25/25. |
| Product `console`, `contracts` 3.11 and 3.12, run `40231949886` | PASS |

Python 3.11 and 3.12 both ran the hosted security, MCP, Persona, authenticator, and Sovereign jobs.

## 7. Unresolved defects versus external dependencies

| Item | Class |
|---|---|
| Reusable credential 403 `IDENTITY_VERIFICATION_REQUIRED` | External. No enrolled identity provider. |
| Stages 18–24 on the default ceremony | Not executed. The new continuation waits on a real key. |
| Persona `PROVIDER_NETWORK` approval | External. No sandbox credentials. |
| `39619c4b` DCO | Human. Author or owner attestation. |
| Python 3.11 and the full hosted I1/Sovereign matrix | Hosted CI on this head. |
| Production agent proof-of-possession | Not authorized. B1 stays development-only. |

No engineering change in this branch fakes `IDENTITY_VERIFIED`, buys Persona,
or edits Codex recovery files.

## 8. Antigravity handoff

The I1 customer failure is the identity gate at stage 17, not a missing logout
or a failed WebAuthn ceremony. Stages 1–16 and 25 passed on fresh PostgreSQL
with Chromium. The harness no longer ends `judgment` merely because an intent
contract returned 201. Downstream approval, execution, evidence, and revocation
run only after canonical issuance. That issuance did not happen.
`BASIC_VERIFIED`, passkey UV, and `SANDBOX_SIMULATED` are not substitutes.

Do not mark I1 green. Do not merge. Do not open M14. The next human inputs are
an enrolled non-production Persona sandbox, a real provider event that is
allowed to drive `VerificationService`, and the DCO disposition in section 5.
