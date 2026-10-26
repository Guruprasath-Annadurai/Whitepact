# M13 Cursor PR #232 adversarial correction

Verdict: **PARTIAL**

This is not I1 qualified, not a completed default customer journey, and not a
compliance waiver. The live 25-stage ceremony remains BLOCKED at `judgment`.
Historical DCO commit `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` remains
unsigned. M13 stays OPEN. Global production is NO-GO. M14 is not authorized.
No deployment, protected merge, or spending is authorized by this change.

Starting commit: `7f5d07da322182a33acd0bd4ade6fd1ac4f53ac1`.
Branch: `cursor/m13-i1-customer-closure-0f76`.
Review base: `codex/m13-secure-antigravity-integration` (PR #232).
Codex-owned R1 and Fortress recovery code was not modified.

Executable correction: `51ddfec39af6ece852bdc21b68795b2285dac720`.
Correction tree: `fa6c1508189eb7a7a4404fba9af42b750ea16532`.
The executable files are in that commit. This documentation commit names that
SHA and does not change `src/` or `tests/`. Hosted I1, Sovereign, and product
workflows run on the branch tip. This environment has Python 3.12.3 only.

## Before

`tests/js/m13-apex-customer.mjs` qualified `post_revocation_execution_attempt`
with:

```javascript
assert.notEqual(denied.value?.error, undefined);
assert.notEqual(denied.value?.approval_id, approvalId);
assert.ok(denied.status === 404 || denied.value?.error === "governance_denied" || denied.value?.proceed !== true);
```

That predicate passes an HTTP 500 body
`{error: "internal_server_error", message: "An unexpected error occurred."}`
because `error` is defined, `approval_id` is absent, and `proceed` is not
`true`. It also passes a 200 body whose `proceed` field is anything other
than exactly `true`, including a missing `proceed`. The stage was then marked
PASS.

`WebIdentityRepository.bind_sso_principal()` inserted a new directory user
with `web_users.verification_status = "IDENTITY_VERIFIED"`. Public SAML/OIDC
admission does not call that method. `admit_sso_principal()` only reads an
existing binding. No production caller of `bind_sso_principal()` was found.
Administrative and test provisioning did call it, and the inserted status is
the same status `CredentialIssuancePolicy` accepts for reusable API
credentials. Rebinding an existing row already left `verification_status`
unchanged. `VerificationService.apply_provider_event()` remains the provider
writer: a webhook that passes `HmacVerificationProvider.verify_webhook` and
carries `outcome: VERIFIED` plus `subject_id` maps to `IDENTITY_VERIFIED`.
That path was not used, and is not a substitute, for legal identity proofing
in this correction.

Hosted I1 on `7f5d07da322182a33acd0bd4ade6fd1ac4f53ac1` (run `40233292804`):

| Job | Result |
|---|---|
| `introduced-dco` `121289436475` | FAIL. Only `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` lacks `Signed-off-by`. Log time 2026-10-25 20:59:05 UTC (26 Oct 2026, 2:29 AM IST) |
| `real-customer-journey` `121289436499` | FAIL, exit 2. `POST /api/web/api-keys` returned 403 at 2026-10-25 21:01:18 UTC (26 Oct 2026, 2:31 AM IST) |
| `independent-security` 3.11 and 3.12 | PASS |
| `independent-mcp` 3.11 and 3.12 | PASS |
| Persona, virtual authenticator, native container, inherited policy | PASS |

Sovereign run `40233292814` passed on 3.11 and 3.12 and kept the default
journey at 17 PASS / 1 BLOCKED / 7 NOT_EXECUTED. Product run `40233292803`
passed console and contract jobs on 3.11 and 3.12.

## After

### Post-revocation refusal

`qualifyRevocationDenial` in `tests/js/revocation-denial.mjs` qualifies only:

- HTTP 404
- `error === "http_error"`
- `message === "Agent is not an active principal in this organization."`

That is the body `governance_call_tool` raises through `http_exception_handler`
when `admit_registered_agent` returns `LookupError` after `disable_agent`.
The qualifier also rejects any `approval_id`, `execution_authorization_id`,
`evidence_id`, or `outcome_id`, `proceed === true`, and
`execution_status === "SUCCEEDED"`. When evidence id lists are supplied they
must be identical, including length. The harness snapshots evidence after
revocation and before the denied call, then again after it.

`node --test tests/js/revocation-denial.test.mjs` fails qualification for
HTTP 500, malformed bodies, missing denial fields, ambiguous 200
`proceed: false` / `governance_denied` responses, a 403 that is not this
contract, effect fields, changed evidence ids, and `{timedOut: true}`.
The same file reconstructs the old predicate and shows that the HTTP 500
body still satisfies it and does not satisfy the new qualifier.
`tests/test_m13_apex_journey_evidence.py` runs that file. I1
`real-customer-journey` already invokes that pytest module, so the cases run
without editing workflow step scripts. These cases are component tests. They
are not default-customer acceptance.

The issued-key continuation in the harness is unchanged in intent and remains
unexecuted. The default ceremony never receives a 201 from
`POST /api/web/api-keys`, so it never reaches judgment success, approval,
execution, evidence, or this denial qualifier.

### Identity elevation

New directory users created by `bind_sso_principal()` are `BASIC_VERIFIED`.
Existing users keep their stored status, so a rebind cannot raise
`UNVERIFIED` or `BASIC_VERIFIED` to `IDENTITY_VERIFIED` and cannot strip a
status that a real provider event already wrote. `email_verified_at` on a
new directory row remains directory mailbox proof.

`tests/test_sso_identity_elevation.py` is the executable counterexample:

- A new ADMIN directory user reads back `BASIC_VERIFIED`.
- `identity_verifications` has no row and `get_human_status` reports
  `provider: null`.
- `CredentialIssuancePolicy.evaluate` on the development environment returns
  `allowed: false` and `IDENTITY_VERIFICATION_REQUIRED`.
- `admit_sso_principal` still admits that user as ADMIN. Enterprise SSO login
  is intact.
- Rebind of the same email does not change the status.
- An account created by `register()` stays `UNVERIFIED` after
  `bind_sso_principal`, and `get_human_status` is not `IDENTITY_VERIFIED`.

No HMAC `outcome: VERIFIED` event, Persona sandbox receipt, or direct
`IDENTITY_VERIFIED` fixture was used to simulate completed legal proofing.
`apply_provider_event()` was not weakened. Possession of the identity webhook
secret remains the provider authenticity control, with subject binding when
`expected_user_id` is set. Public SSO still cannot create that status.

Other `IDENTITY_VERIFIED` writers in `src/` are the provider outcome map in
`VerificationService._apply_human_outcome` and organization verification that
reads an already verified owner. `register()` does not set the column.
Persona sandbox still cannot write it.

### Default journey

Local command:

```text
PYTHONPATH=src:. .venv/bin/python scripts/engineering/m13_apex_customer_journey.py --authorized-disposable-bootstrap --report /opt/cursor/artifacts/m13-apex-default-journey.json
```

Exit 2. Acceptance `BLOCKED`. Stop `judgment`. 17 PASS, 1 BLOCKED,
7 NOT_EXECUTED, 0 FAIL. Judgment HTTP 403,
`error_code: IDENTITY_VERIFICATION_REQUIRED`,
`reason: QUALIFIED_IDENTITY_REQUIRED_FOR_CANONICAL_API_CREDENTIAL`.
`development_prototype` was not set. B1 was not enabled.

Approval, execution authorization, evidence, and revocation on the issued-key
path stay behind that 403. Component coverage of the denial contract and of
registered-agent admission (`tests/test_governed_agent_admission.py`, included
in the security run below) is not a 25/25 acceptance claim.

### DCO

No historical object was rewritten. No sign-off was fabricated. No exception
was added to `.github/workflows/dco.yml` or to I1 `introduced-dco`.

Unsigned object:

| Field | Value |
|---|---|
| SHA | `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` |
| Author and committer | Techezz Infos `<Techezzinfos@gmail.com>` |
| Author time | 2026-10-15 18:41:16 IST |
| Parent | `57c69344961196fd89b40e8ffec65c06a1898fce` |
| Tree | `06f9add5d47fe5af1a7a6c45f8955da5d9b57e9a` |
| Subject | `docs(security): publish WhitePact M13-S4 enterprise security qualification and Codex handoff suite` |
| Paths | 14 files under `docs/security/m13s4/` only |
| Trailers | no `Signed-off-by`, no `Co-authored-by` |

Required action: Techezz Infos, or the repository owner acting with that
author's authority, adds a real `Signed-off-by` for that author without
impersonation. Rewriting the published object is not authorized. An
owner-published exception would have to name this exact SHA, state that it is
not a sign-off, and be added to both the `.github/workflows/dco.yml` case list
and the I1 `introduced-dco` scan. That exception was not created.

Current CI behavior: I1 `introduced-dco` runs `git rev-list --no-merges
5291cc6d4e750c6ec5ec0688f8bfc9e3b72a8558..HEAD` and requires
`^Signed-off-by: .+ <.+@.+>$` on every commit. It does not read the historical
allowlist in `dco.yml`. On `7f5d07da` the job failed only on `39619c4b`.
New commits in this remediation use `git commit -s`. They do not clear that
failure. `dco.yml` itself runs on pull requests to `main` and
`cursor/whitepact-rc-remediation-b6a9`, and its allowlist still does not
include `39619c4b`.

## Exact code diff

`bind_sso_principal` new-user insert:

```diff
-                        verification_status="IDENTITY_VERIFIED",
+                        verification_status="BASIC_VERIFIED",
```

The docstring now states that a new directory user is `BASIC_VERIFIED` and
that rebinding does not change `verification_status`.

`post_revocation_execution_attempt` now calls `qualifyRevocationDenial` and
marks FAIL, setting `stop`, when qualification fails. Evidence ids are taken
after disable and compared after the denied call and again after the 409
approval replay.

New files:

- `tests/js/revocation-denial.mjs`
- `tests/js/revocation-denial.test.mjs`
- `tests/test_sso_identity_elevation.py`

`tests/test_m13_apex_journey_evidence.py` shells out to
`node --test tests/js/revocation-denial.test.mjs`.

## Local verification

Python 3.12.3, Node v22.23.4, PostgreSQL 16 on `127.0.0.1:5432`.

| Command | Result |
|---|---|
| `node --test tests/js/revocation-denial.test.mjs` | 8 passed |
| `pytest tests/test_sso_identity_elevation.py tests/test_m13_apex_journey_evidence.py` | 9 passed |
| Default journey above | exit 2, 17 / 1 / 7 |
| I1 security file set plus agent admission, SSO elevation, and journey evidence | 307 passed, 1 deprecation warning, exit 0, 315.42s. Completed 26 Oct 2026, 12:23 PM IST |
| `ruff check` on the edited Python files | passed |
| `manage_license_headers.py --check` | passed |

The security file set was the I1 `independent-security` pytest modules:
`test_m13s_security_regression.py`, `test_revocation_kernel.py`,
`test_delegation_revocation_verification.py`, `test_in_flight_revocation.py`,
`test_dns_egress_security.py`, `test_isolation_egress_boundary.py`,
`test_runtime_resilience_adversarial.py`, `test_inflight_liveness_adversarial.py`,
`test_m13_apex_migration_guard.py`, `test_m13_apex_origin.py`,
`test_enterprise_layer2_identity_security.py`,
`test_enterprise_security_branch_campaign.py`,
`test_enterprise_security_branch_campaign_batch2.py`.
Python 3.11 was not installed here. Hosted 3.11 and 3.12 jobs are the
cross-version record and are not claimed from this machine.

`tests/test_p0_tenant_admission.py` still cannot create organizations in this
environment because `create_org` requires a verified session and CSRF. Those
failures happen before `bind_sso_principal` and are not caused by the status
change. The new counterexample inserts the organization row directly and
checks admission itself.

## Security implications

A server error or an ambiguous tool response can no longer be recorded as a
revoked-agent denial. The recognized refusal is the 404 admission failure,
with no new approval, no execution authorization, and no new evidence id.
SSO directory provisioning can still log a bound principal in and can no
longer mint the assurance reusable API credentials require. The default
customer path still stops until an authorized identity provider writes
`IDENTITY_VERIFIED` through the provider event path.

## Remaining external dependencies

- Authorized identity-provider evidence that can produce canonical
  `IDENTITY_VERIFIED` for the default customer. Until that exists the
  25-stage journey stays BLOCKED at 17 / 1 / 7.
- A real sign-off by Techezz Infos `<Techezzinfos@gmail.com>` for
  `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`, or an owner-published exact-SHA
  exception in both DCO checks. Neither is in this branch.
- Hosted confirmation of the I1, Sovereign, and product workflows on the tip
  of this branch. `introduced-dco` and `real-customer-journey` are expected
  to remain red for the two reasons above. That expected red is not a
  qualification.
- Python 3.11 execution remains a hosted CI property.

## Hosted CI

Not yet terminal for `51ddfec39af6ece852bdc21b68795b2285dac720` or the
documentation tip that names it. `introduced-dco` and `real-customer-journey`
are expected to stay red. A green security or Sovereign job does not make
this verdict PASS. The terminal workflow names are appended when CI finishes.
