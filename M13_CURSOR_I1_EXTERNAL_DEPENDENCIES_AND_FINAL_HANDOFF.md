# M13 Cursor I1 external dependencies and final handoff

Verdict: **PARTIAL**. I1 is not qualified. M13 stays OPEN. Global production is NO-GO. M14 is not authorized.

Starting evidence commit: `12ad4da66f9a962c943108d346541f2b10ea6d90`, tree `a02bca77cb88a60066d787b4d38c8a403da6018a`.
Branch: `cursor/m13-i1-customer-closure-0f76`.
Pull request: #232.
Review base ref: `codex/m13-secure-antigravity-integration`.
That ref now resolves to `1a65dda2369a12e2c94dc35efa3b4ea0fd464fb6`. This branch forked from `b00e2a39aa47ae24e6a2a1de4d3f2d6b6ea81c15`.
No identity-provider secret is configured in this environment. No secret value is recorded here.

This document does not install a DCO exception, does not merge Codex recovery, and does not change the customer journey.

## 1. Implemented and tested engineering

These items are already on the starting evidence commit. This handoff does not repeat their patches.

| Area | Where it lives | What was verified |
|---|---|---|
| Registered-agent admission | `src/responsibleai/governance/agent_admission.py`, `src/responsibleai/dashboard/app.py` | An org-scoped credential may name one ACTIVE agent in that organization. Foreign and disabled agents are refused. The API key remains the caller. |
| Post-revocation refusal | `tests/js/revocation-denial.mjs`, `tests/js/m13-apex-customer.mjs` | The only qualifying denial is HTTP 404, `error` `http_error`, message `Agent is not an active principal in this organization.`, with no approval, execution authorization, evidence, or outcome id, and with unchanged evidence ids. HTTP 500, malformed bodies, missing fields, ambiguous responses, and timeouts fail. |
| Denial regression wiring | `tests/test_m13_apex_journey_evidence.py` | `node --test tests/js/revocation-denial.test.mjs` runs inside the I1 customer job. A pass there is a component result. |
| SSO directory assurance | `src/responsibleai/db/web_identity_repository.py`, `tests/test_sso_identity_elevation.py` | A new directory user is `BASIC_VERIFIED`. Rebind does not change `verification_status`. Issuance stays `IDENTITY_VERIFICATION_REQUIRED`. `admit_sso_principal` still admits the directory user. |
| Persona sandbox boundary | `src/responsibleai/enterprise/persona_sandbox.py`, `tests/test_stage3_persona_sandbox.py` | Sandbox decisions do not write `IDENTITY_VERIFIED` and do not mint reusable credentials. |
| Default ceremony shape | `scripts/engineering/m13_apex_customer_journey.py` | Hosted I1 on `bdf3ec6f05604436d4a84b4b0500927bc2dcde92` and again on `12ad4da66f9a962c943108d346541f2b10ea6d90` exited 2 at `judgment`. |

Hosted record for `12ad4da66f9a962c943108d346541f2b10ea6d90`, I1 run `40284538249`:

- `introduced-dco` failed only on `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`.
- `real-customer-journey` exited 2. `POST /api/web/api-keys` returned 403 at 26 Oct 2026, 12:46 PM IST.
- `independent-security` passed on Python 3.11 and 3.12.
- MCP, Persona, virtual authenticator, native container, and inherited policy passed.
- Sovereign run `40284538301` passed.
- Product run `40284538128` passed.

The executable receipt for the same tree, captured on `bdf3ec6f05604436d4a84b4b0500927bc2dcde92` (tree `c6a0cd38bf9de0e2b39d3e17351fd114ed202604`, clean), is acceptance `BLOCKED`, stop `judgment`, 17 PASS / 1 BLOCKED / 7 NOT_EXECUTED / 0 FAIL, `error_code` `IDENTITY_VERIFICATION_REQUIRED`, `development_prototype` false, `authority_seeded` false. `12ad4da6` adds only the CI record and keeps that executable tree's sources.

Local Python 3.12.3 coverage already recorded in `M13_CURSOR_PR232_ADVERSARIAL_CORRECTION_REPORT.md` remains the local security evidence: 307 passed in the I1 security file set, 8 revocation-denial cases, 9 elevation and receipt tests. Python 3.11 evidence is the hosted pair above.

## 2. Genuine external prerequisites

No authorized identity provider is enrolled. The process environment has no Persona, KYC, or identity-webhook variable set. The development fallback in `resolve_identity_webhook_secret` is a known weak sample. Production boot rejects a missing secret, that sample, and any secret shorter than 32 characters. Using the development fallback to POST a `VERIFIED` event would fabricate `IDENTITY_VERIFIED`. That action is not available as customer qualification.

### Canonical path that already exists

Issuance for `POST /api/web/api-keys` goes through `EnterpriseIAM.create_api_key` and `CredentialIssuancePolicy.evaluate`. Development, staging, and production all require `get_human_status()["status"] == "IDENTITY_VERIFIED"`. The journey sends `environment: "test"`, which maps to `DEVELOPMENT`. Organization verification is an additional gate only for a `PRODUCTION` environment on an `ORGANIZATION` workspace. `IDENTITY_VERIFIED` is account assurance. It is not an execution grant.

`GET /api/enterprise/identity/verification` returns the latest `identity_verifications` row when one exists, including `provider`, `assurance_level`, `verified_at`, and `expires_at`. Operators read that payload. The `web_users.verification_status` column alone is not the provenance record.

`POST /api/enterprise/identity/verification/start` calls `VerificationService.start_human_verification`. It stores `REVIEW_REQUIRED`, provider name `hmac-reference`, and a `session_id`. It does not set `IDENTITY_VERIFIED`.

`POST /api/enterprise/identity/verification/webhook` calls `apply_provider_event` with the raw body, `X-Identity-Signature`, and `X-Identity-Timestamp`. The route does not add `expected_user_id` or `expected_org_id`. Authenticity is HMAC-SHA256 over `payload_bytes + timestamp_utf8`, compared in constant time. The timestamp must parse as ISO-8601 and fall within 300 seconds. The JSON object must contain `event_id`. A human event must contain `subject_id`. `outcome` `VERIFIED` maps to `IDENTITY_VERIFIED` for 365 days from the server clock. `assurance_level`, `country`, `reference_id`, and `review_status` are stored when present. The current policy does not compare `assurance_level` to an allowlist. Replay of the same provider name plus `event_id` hits `uq_identity_provider_event` and returns `PROVIDER_REPLAY`. The adapter name stored today is `hmac-reference`. A commercial vendor needs its own `IdentityVerificationProvider`. None is registered.

### Human-controlled onboarding

The repository owner, or a delegate with authority to contract for WhitePact, does every step below. Engineering cannot complete them from this environment.

1. Choose the legal-identity provider and the assurance level that the owner accepts for reusable API credentials. Record that decision outside this repository. Persona sandbox approval is not that decision.
2. Place the webhook secret only in the deployment secret store as `WHITEPACT_IDENTITY_WEBHOOK_SECRET` or `RAI_IDENTITY_WEBHOOK_SECRET`. Production requires a non-sample value of at least 32 characters. Do not commit it, print it, or paste it into a report.
3. Give that secret only to the chosen provider. Possession of the secret is what makes a webhook authentic, because the public route trusts `subject_id` inside a valid signature.
4. Run the canonical journey through `policy_assignment`. Those stages do not require `IDENTITY_VERIFIED`.
5. As the signed-in customer, call `POST /api/enterprise/identity/verification/start`. Keep `subject_id` and `verification_id`. Confirm `GET /api/enterprise/identity/verification` still reports a status other than `IDENTITY_VERIFIED`.
6. Complete proofing on the provider's own site. The provider's event must use `subject_id` equal to that WhitePact user id, a new `event_id`, `outcome` `VERIFIED`, and the owner-approved `assurance_level`.
7. The provider POSTs the raw JSON to `/api/enterprise/identity/verification/webhook` with `X-Identity-Timestamp` and `X-Identity-Signature` equal to the hex HMAC-SHA256 of the raw body concatenated with the timestamp string.
8. Read `GET /api/enterprise/identity/verification` again. Qualification requires `status` `IDENTITY_VERIFIED`, `provider` naming the authorized adapter, a `verified_at` timestamp, and the approved `assurance_level`. Then rerun `scripts/engineering/m13_apex_customer_journey.py --authorized-disposable-bootstrap` on the same commit the provider served.
9. For a later production key (`environment: "live"`), repeat organization proofing with `kind` `organization` until `get_org_status` is `ORGANIZATION_VERIFIED`. The current default journey does not reach that gate.

Until step 8 has happened against a real provider, canonical acceptance stays BLOCKED.

## 3. Human governance decisions

### Identity

The owner decides which provider and which `assurance_level` may write `IDENTITY_VERIFIED`. No such decision is recorded in this branch. A signed HMAC from the development sample is not that decision.

### DCO

Unsigned object, unchanged:

| Field | Value |
|---|---|
| SHA | `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc` |
| Author and committer | Techezz Infos `<Techezzinfos@gmail.com>` |
| Author time | 15 Oct 2026, 6:41 PM IST |
| Parent | `57c69344961196fd89b40e8ffec65c06a1898fce` |
| Tree | `06f9add5d47fe5af1a7a6c45f8955da5d9b57e9a` |
| Subject | `docs(security): publish WhitePact M13-S4 enterprise security qualification and Codex handoff suite` |
| Paths | 14 files under `docs/security/m13s4/` |
| Trailers | none |

Two checks exist, and they are not the same:

- `.github/workflows/dco.yml` runs on pull requests to `main` and `cursor/whitepact-rc-remediation-b6a9`. It scans `base..head` and already has exact-SHA exceptions for the 9 Oct 2026 pair and the 11 Oct 2026 four. `39619c4b` is absent. Pull request #232 does not target those bases, so this workflow is not the I1 failure.
- `.github/workflows/m13i1-integration.yml` job `introduced-dco` scans `5291cc6d4e750c6ec5ec0688f8bfc9e3b72a8558..HEAD` and has no exception list. It is the check that failed on `12ad4da6`.

A later commit that says the author attests `39619c4b` does not change the body of `39619c4b`. Both checks read that historical body for `^Signed-off-by: .+ <.+@.+>$`. A side letter does not clear either job.

The human decision is one of these two, and neither is taken here:

1. Techezz Infos, with the repository owner's agreement, signs that exact object. Rewriting published history to do so is not authorized by this handoff.
2. The repository owner publishes an exception that names only `39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`, states that the exception is not a `Signed-off-by`, and installs that exact SHA in both `dco.yml` and `introduced-dco`. Installing it in only one file leaves the other red.

Proposed exception text for owner review. It is not in `compliance/`, and it is not in either workflow.

```text
Owner-approved historical DCO exception for 39619c4b46dac5d6e69c9e00ce887c2ed9641cfc.
This exception is not a Signed-off-by trailer.
Record: compliance/DCO_HISTORICAL_EXCEPTION_2026-10-15.md
```

Proposed `dco.yml` case arm, not inserted:

```text
39619c4b46dac5d6e69c9e00ce887c2ed9641cfc)
  echo "Owner-approved historical DCO exception for ${sha}."
  echo "This exception is not a Signed-off-by trailer."
  echo "Record: compliance/DCO_HISTORICAL_EXCEPTION_2026-10-15.md"
  continue
  ;;
```

Proposed `introduced-dco` arm, not inserted, placed before the `Signed-off-by` test and limited to that one SHA:

```text
39619c4b46dac5d6e69c9e00ce887c2ed9641cfc)
  echo "Owner-approved historical DCO exception for ${sha}."
  echo "This exception is not a Signed-off-by trailer."
  missing stays 0
  continue
  ;;
```

The owner record, if they approve it, must say the exception does not authorize production, merge to `main`, deployment, or any other SHA.

### Recovery scope

Codex owns the four commits on `codex/m13-secure-antigravity-integration` after `b00e2a39aa47ae24e6a2a1de4d3f2d6b6ea81c15`. They are not merged into this branch. Their qualification is a Codex and owner decision. This handoff does not grant the limited nonproduction recovery authorization.

## 4. Unexecuted canonical customer stages

Hosted and local default ceremonies stop at `judgment`. Logout still runs and passes. These seven stages stay `NOT_EXECUTED`:

| Stage | Acceptance objective still waiting |
|---|---|
| `human_approval` | The signed-in human approves the registered agent's pending approval. |
| `execution_grant` | `POST /api/web/approvals/{id}/execute` returns a short-lived authorization and evidence id. |
| `controlled_execution` | The harmless `rai_policy_check` execution is the one tied to that evidence. |
| `evidence_verification` | Local chain verification reports the evidence intact and records that it is not independent witnessing. |
| `revocation` | The registered agent becomes `DISABLED` and its delegation is revoked. |
| `post_revocation_execution_attempt` | The same tool call meets the 404 admission contract above, with unchanged evidence ids. |
| `post_revocation_denial` | Replaying the approval execution returns HTTP 409 and the evidence id list stays unchanged. |

The harness contains that continuation for a real HTTP 201 API key. The live journey receives HTTP 403, so the continuation does not run. B1 development-agent credentials and `bind_sso_principal` are not used to pass the gate. Component denial tests remain in force for the refusal contract. They do not mark these seven stages passed.

## 5. Remaining independent qualification

- A provider-backed rerun of the 25-stage ceremony on one named commit, with `acceptance` `PASS` only if all 25 stages pass their own objectives.
- Python 3.11 and 3.12 I1, Sovereign, and product workflows on that same commit.
- `introduced-dco` green only after the owner decision in section 3 is actually installed, or after a real sign-off exists on `39619c4b`.
- Codex qualification of the recovery commits below, on their own heads, before any integration SHA is cut.
- No production deployment, protected merge, M14 authorization, or spending.

## 6. File-level integration plan

`git merge-tree` of `12ad4da66f9a962c943108d346541f2b10ea6d90` with `1a65dda2369a12e2c94dc35efa3b4ea0fd464fb6` reports no overlap. The same check against `codex/whitepact-m13-combined-recovery` at `d8875619c41ac96ef3cac2653390ebf4fb7ce416` also reports no overlap. That is a snapshot. It is not a merge, and it is not qualification.

Cursor files to keep from pull request #232, the diff `b00e2a39..12ad4da6`:

- `src/responsibleai/dashboard/app.py`
- `src/responsibleai/db/web_identity_repository.py`
- `src/responsibleai/enterprise/persona_sandbox.py`
- `src/responsibleai/governance/agent_admission.py`
- `tests/js/m13-apex-customer.mjs`
- `tests/js/revocation-denial.mjs`
- `tests/js/revocation-denial.test.mjs`
- `tests/test_governed_agent_admission.py`
- `tests/test_m13_apex_journey_evidence.py`
- `tests/test_sso_identity_elevation.py`
- `tests/test_stage3_persona_sandbox.py`
- `M13_CURSOR_CANONICAL_CUSTOMER_FINAL_EVIDENCE.md`
- `M13_CURSOR_PR232_ADVERSARIAL_CORRECTION_REPORT.md`
- this handoff, once it is committed

Codex recovery files to take from the qualified recovery head, currently the four commits after `b00e2a39`:

| Commit | Files |
|---|---|
| `ee392aaae1b9d7c065eaaee627f17babcc73b242` | `.github/workflows/m13-absolute-runtime-review.yml`, `.github/workflows/m13-r1-operator-recovery.yml`, `scripts/engineering/m13_docker_qualification_probe.py`, `tests/test_stage3_docker_qualification_probe.py` |
| `6cbbea226c36ba053f26fc2f25c8d120a68b74ea` | `tests/test_stage3_floor_installation_binding.py` |
| `fe3a4b58137db62e387322de3105befc11b690d8` | `scripts/engineering/m13_floor_repair_poc.py` |
| `1a65dda2369a12e2c94dc35efa3b4ea0fd464fb6` | `tests/test_stage3_floor_installation_binding.py` |

Do not edit those recovery files on this branch. Do not retarget pull request #232 onto them in this handoff.

When, and only when, the owner has recorded the identity decision or has accepted that identity remains blocked, has recorded the DCO decision, and Codex has named one qualified recovery SHA:

1. Fetch both heads. Confirm the recovery SHA contains the four commits above, or replace this table with the files actually changed since `b00e2a39`.
2. Diff the two heads with `git diff --name-only <cursor-sha>...<recovery-sha>` and the reverse. If any path appears on both sides, stop. Resolve that path in a new review. Do not take one side silently.
3. From the Cursor SHA, merge the recovery SHA with `--no-ff`. The expected message is a merge of two qualified heads, not a rewrite.
4. Run the default journey and expect exit 2 and 17 / 1 / 7 until a real provider event exists. Run the Codex recovery tests the recovery head already requires. Run I1 on the merge commit.
5. The merge commit is the candidate SHA. It is still not production, and it is still not M14, until the 25 stages and both DCO checks pass on that exact SHA.

No candidate SHA exists. `1a65dda2369a12e2c94dc35efa3b4ea0fd464fb6` is the current Codex base tip, not a qualified integration head.
