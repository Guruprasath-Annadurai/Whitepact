# M13 unified independent acceptance report

**M13 OPEN. GLOBAL PRODUCTION NO-GO.** New TITAN changes are not accepted.

## Customer authority product continuation — 17 October 2026

Starting checkpoint: `4b6d43d4168d20c6489b1462b8940966e402c239`, tree
`4c2bb755dd37d81453047a6567ec9324aa51c41d`, parent
`fb73369513217bc5c10979c025f504c5e16d7e3c`; clean at resumption. Remote owner
heads remain `9fbfc122` / `d64992f1`. No corrected root/cancellation handoff exists.

**Origin binding defect:** the integrated passkey routes constructed
IdentitySecurityService with hardcoded `http://localhost`, omitting the browser's
ephemeral port. The prior exact-head customer artifact stopped before registration
with RP_OR_ORIGIN_CONTRACT_MISMATCH. New direct route/storage tests independently
reproduced nine failures before routing changed. Two earlier test setup attempts
errored because this Settings model has no WebAuthn fields; those attempts are
not assertion RED evidence. Corrected tests use actual supported environment
configuration and real SQLite challenge rows, not identity/trust fixtures.

**Product correction:** selectively reuse the reviewed owner's origin validation
helpers, but invoke them through a dedicated WebAuthn service factory at the four
passkey issuance/finish routes only. The existing service, root authority,
enrollment policy, session rotation, replay and containment implementations remain
unchanged. Nonproduction inference permits loopback origins only. Production
ignores client/proxy origins and requires explicit HTTPS origin plus a matching
RP ID. Configure `WHITEPACT_WEBAUTHN_ORIGIN` and `WHITEPACT_WEBAUTHN_RP_ID` on the
server; browser-supplied RP IDs are not authority. Forwarded headers do not replace
browser origin. Unrelated OAuth/TOTP/service construction is not retargeted.

Initial nine origin cases plus unchanged three identity-security suites: **82
PASS in 111.49s**, zero skips. An additional forwarded-header case is included
in final qualification. Exact committed-head CI adds this whole scope on both
supported Python versions with mandatory zero-skip receipts.

**Genuine integrated browser result:** origin comparison now passes, Chromium
creates its actual credential and reaches register/finish. The backend responds
403 AUTHENTICATION_ASSURANCE_TOO_LOW after the legitimate password session obtains
an ADD_PASSKEY grant. The 25-stage result remains 5 PASS / 1 BLOCKED /
19 NOT_EXECUTED, but the reason changes from origin mismatch to the independently
owned first-passkey enrollment policy. Do not mark enrollment or authentication
PASS, weaken that policy, or import the entire owner's service to bypass it.

**Downstream actual product workflow:** preserved 25 names/order; owner-source
genuine signup, WebAuthn, root, consent, application, agent, delegation and policy
still yield 17 PASS / 1 BLOCKED / 7 NOT_EXECUTED. Stage 17 now attempts actual
existing operations instead of stopping at an unexplored placeholder. Direct
customer-session intent admission returns 401; the documented org-key workflow
uses POST /api/web/api-keys, which instead returns 403 at canonical identity
eligibility. BASIC_VERIFIED email is not a substitute for IDENTITY_VERIFIED
qualification. No provider attestation, identity state, key, grant or approval is
seeded. Returned credentials, if legitimately issued in a future qualified flow,
stay private in browser memory and are revoked before logout; no token is logged.

Intent contracts narrow existing authority and do not mint Judgment or
ExecutionGrant. The current tools/call path likewise explicitly does not mint
ExecutionGrant state. A general org key cannot be assumed to be an authenticated
canonical agent grant. TITAN-1 must qualify the subject/tenant/delegation/policy
contract and existing-kernel approval-resume/grant API before stages 17–24 can
be accepted. Founder identity policy and actual verification prerequisites remain
separate decisions. The 401 and 403 receipts are product workflow boundaries,
not evidence that credential authentication should be bypassed.

The previous completed candidate results (MCP 519 and extended 209 per Python,
PG safety 3 per Python, native 15, frontend 315, SDK 3, frameworks 24/22) remain
historical until rerun at this checkpoint. Mandatory original revision assertion,
Ruff 101, unsigned ancestor DCO and six Gitleaks findings remain failed. No
protected test/hash, root enforcement or containment code changed here. Owner
handoff and final exact HEAD/tree/parent, clean browser receipts and CI results
are published separately on PR216 to avoid a self-referential report hash.

NEXT: independently qualify this committed origin correction; obtain enrollment,
root and cancellation owner corrections; qualify the canonical customer-agent
intent/judgment/approval/grant bridge with real identity and consent. **M13 NO-GO.**

## Corrective integration review — 17 October 2026 (client timezone)

This continuation starts from cleanfb73369513217bc5c10979c025f504c5e16d7e3c,
treeea3419dca53096350151d1ab7a496742958c7599, parentf89708a2. Both remote
branches fetched: TITAN-1 advanceseb4093->9fbfc122c4b2b9f58b9ab3cb813293b2a7a6219b;
TITAN-2 advances9de2->d64992f1a6709a06247fa939a28576481371245d. Separate detached
owner worktrees preserve both branches. The following section supersedes prior
status summaries; older sections remain historical evidence.

| Counterexample | Original RED | Corrected owner | Integrated disposition |
| --- | --- | --- | --- |
| ROOT-03 identifier label | eb4093 FAIL | 9fb narrow PASS | Full authority closure FAIL: unverified owner still BOOTSTRAPPED; root source withheld |
| ROOT-04 IDNA normalization | eb4093 FAIL | 9fb narrow PASS | Root file withheld with ROOT-03; full collision/lifecycle acceptance pending |
| RUNTIME-03 plugin false absence | 9de2 FAIL | d649 PASS | Selected only synchronous removal/inspection method; integrated2-case runtime scope PASS |
| RUNTIME-04 directory permission | 9de2 FAIL | d649 PASS | Selected d649 tracking reader; integrated original/revocation/migration scope35PASS |
| PG-02 mandatory passkey retention | 9de2 drops1->0 | d649 original roundtrip PASS, intermediate schema safety FAIL | New fail-closed guard rejects downgrade with mandatory rows; local guard/default/race tests PASS |

Original four-case reproducer blob7e3500ca714701553e69afb2de12174a72d08a22
matches APEX and both owners unchanged. Narrow owner root2PASS/29.33s and
runtime2PASS/3.95s do not close stronger security conditions. The unchanged PG
probe passes retention/re-upgrade on d649, but a new intermediate-revision test
FAIL20.37s: mandatory data remains only in a side table at revision0064.
An additional actual application test on d649 FAIL16.70s: after that downgrade,
the development application completes lifespan startup with auto_migrate=False
and serves GET/login HTTP200 while the mandatory flag exists only in retention
metadata. This proves no global runtime refusal, not an authenticated execution
bypass or production-mode qualification. The failure is preserved separately.

### Integration decisions and runtime conflicts

- Select d649 `_check_remote_worker_active`: one actual scandir traversal,
  tenant-prefix isolation, unreadable/corrupt records unresolved and scan failure
  unresolved. TITAN-1's pre-probe followed by glob still discards unreadable files;
  do not combine that weaker reader with the selected implementation.
- Select only d649 `_remove_containers`, including plugin/daemon distinction and
  deadline failure. Keep the rest of container_backend out of wholesale imports.
  Five selected owner helper/failure tests PASS; one cancellation test explicitly
  deselected in that subset, not counted as passing or skipped. Entire owner
  runtime/nonce scope independently14PASS/28.15s.
- Withhold new async cancellation/registry lifetime architecture from either
  branch. New cancellation-plus-cleanup-error counterexample on d649 FAIL3.71s:
  an exception exits the shield loop before its cancellation-restoring finally;
  a caller catches it and resumes despite the prior cancellation request. Existing
  APEX cancellation/lifetime limitations remain P0; no complete containment
  acceptance is claimed by integrating the synchronous inspection improvement.
- Withhold TITAN-1 root implementation: genuine repository/workspace operations,
  unverified user, supported default flags and real Ed25519 signature still grant
  BOOTSTRAPPED authority (new test FAIL18.83s). Changing an identifier label to
  UNVERIFIED does not prevent ACTIVE principal/root/consent/delegation issuance.
  Actor constructed at service boundary; public HTTP exploitability is unverified.
  No competing root implementation or founder policy decision made here.

### Fail-closed migration strategy

Retention-only rollback is rejected. The selected forward0065 upgrade can restore
previous retained data, but downgrade now locks bootstrap records ACCESS EXCLUSIVE
on PostgreSQL, checks every stored mandatory flag and raises before DDL if any
nonzero flag exists. Revision0065, the actual enforced column and flag remain
atomically intact. Nonmandatory historical rows may roundtrip0064/0065. No
expired-record exception silently drops a prior authentication requirement.

New real PostgreSQL tests: mandatory downgrade refusal and nonmandatory repeated
roundtrip included in35PASS scope; concurrent writer test separately1PASS/13.48s.
The latter observes an ungranted AccessExclusiveLock, commits a concurrent0->1
writer, and proves downgrade then refuses without losing schema or value.
The first guard attempt exposed a new-test exception-type error (MigrationError
is not RuntimeError); corrected only the new test, then reran successfully.

The unchanged original preservation probe now returns FAIL/MigrationError at the
deliberately unsupported mandatory downgrade. This is retained, not edited into
PASS. Policy-specific denial tests establish the intended secure result. The
original immutable migration test f4d5731e9b2792b18a69e1fcfd475164ee4f0898 remains
unchanged; its historical0064 head expectation will fail at the new0065 head.
TITAN-2 still has altered071c; it is not imported. Formal historical disposition
and independent owner review remain required for full migration acceptance.

### Genuine customer continuation and exact-head qualification

Historical25 phase names/order and receipt schema retained. The harness now uses
real authenticated application registration/readback, agent registration,
two-minute attenuated delegation, restrictive REQUIRE_APPROVAL policy and policy
readback. No trusted database rows, grants, approvals or execution evidence seeded.
First owner-source9fb run:17PASS /1BLOCKED /7NOT_EXECUTED; final clean committed
harness repeat and exact-head CI receipt are published on PR216 separately.

| Stages | Actual owner-source result |
| --- | --- |
| 1–12 signup through root/consent | PASS as before, actual HTTP/WebAuthn/PoP |
| 13 application_registration | PASS, actual registration/readback, no execution authority |
| 14 agent_registration | PASS, actual application linkage, no delegation at registration |
| 15 capability_delegation | PASS, actual server-issued scope/target-attenuated delegation and consent |
| 16 policy_assignment | PASS, actual restrictive policy API |
| 17 judgment | BLOCKED: customer-agent judgment/grant/execution contract unqualified |
| 18 human_approval | NOT_EXECUTED |
| 19 execution_grant | NOT_EXECUTED |
| 20 controlled_execution | NOT_EXECUTED |
| 21 evidence_verification | NOT_EXECUTED |
| 22 revocation | NOT_EXECUTED |
| 23 post_revocation_execution_attempt | NOT_EXECUTED |
| 24 post_revocation_denial | NOT_EXECUTED |
| 25 logout_session_invalidation | PASS |

The existing governed tools/call route requires an org API key and explicitly
does not mint ExecutionGrant state; it is not evidence that this customer's
agent has a complete judgment/approval/grant path. Do not substitute fixture or
direct-service grants. Root source remains rejected despite the positive journey.
Owner handoff: PR215 comment6222818444.

Framework reruns now execute with the corrected `sdk/python` path:24PASS/23.82s
and22PASS/25.19s, zero skips. Prior missing-module failures remain recorded.
Startup/receipt tests20PASS; local runtime negatives2PASS; integrated regression
35PASS. New committed-head Python/MCP/frontend/native/migration CI still required.
CI now executes extended/MCP/migration scopes even after original-suite failure,
while retaining that failure and strict skip gates. No check is disabled or made
nonblocking. DCO, Ruff101 and six historical Gitleaks findings remain unresolved.

Remaining P0: unverified authority, cancellation/containment lifetime, complete
customer execution journey, historical mandatory gates. P1: full lifecycle,
collision and tenant authority qualification. Founder RecordA and PathB decisions
stay unratified. NEXT: owner authority/cancellation corrections; exact-head
native/security/PG qualification of selected changes; authenticated customer
judgment/approval/grant bridge. **M13 NO-GO.**

## 1. Candidate provenance

Preserved implementation checkpoint: `08551472503fb7d0422a99bebcb926a4e496ece3`.
Tree: `23ba90aeeff2e868f0dbe5fded122a9598374014`.
Parent: `09f6e4cc132285717d4f3000aac3dd9c7a7ce6df`.
Branch: `codex/whitepact-m13-apex-integration`; draft PR216 targets Forge.
Canonical origin: https://github.com/Guruprasath-Annadurai/Whitepact.
Worktree clean before this continuation. This checkpoint adds independent
reproducers, this report, ledger evidence and APEX customer CI coverage; it does
not import either new security implementation. The containing checkpoint's exact
HEAD/tree/parent and subsequent CI receipt are published on PR216 separately.

Freshly fetched security candidates, reviewed in separate clean detached worktrees:

| Owner | Commit | Tree | Verified parent |
| --- | --- | --- | --- |
| TITAN-1 | eb4093e58ec4f068baa2ad706a86d7998d9de15d | d9fb06c416fed6794f0bf84c172b91f30367f577 | e1a9f1235d6b46b7423c21815ff27ebebf6887c6 |
| TITAN-2 | 9de2d5cc17671b2731aab8eaa1b388d9b4fa67cb | 3ea1c180680340e6556e84e65623650db50c11e4 | 6b604bf12ac07508c5b584b85ed48df8a983e5af |

Earlier selectively integrated SSE credential binding, tenant nonce admission,
EPERM tracking, directory, organization and skip-accounting changes are preserved.
No wholesale security merge, main merge, deployment, cloud provisioning or M14.

## 2. TITAN-1 security integration review

The new completion transaction creates a HUMAN principal, promotes a pending
principal to ACTIVE and creates a VERIFIED EMAIL identifier before root insertion.
It rechecks organization, owner membership, user lifecycle, existing roots and
pending quorum recovery under the tenant epoch transaction. Email and canonical
principal type/verification prerequisites are not all independently established
by those checks. Founder identity policy cannot be inferred from this bridge.

**Positive evidence:** independently executed unchanged owner root suite:
11 PASS in 219.44s, zero skips. The unchanged real customer harness removes the
old FK failure under mandatory passkey/identity flags; see section 4.

**Counterexample ROOT-03:** register an unverified user and create its workspace
using actual repositories/services on migrated PostgreSQL; initiate with supported
default flags and complete with a genuine Ed25519 root signature. The new bridge
stores EMAIL verification_state=VERIFIED while web_users.email_verified_at stays
NULL. No principal/identifier/root fixtures inserted. This is a service-boundary
finding: the actor is constructed for the service test, and ordinary web password
login separately rejects unverified users. Public HTTP exploitability is not
established. Root key possession cannot establish mailbox ownership.

**Counterexample ROOT-04:** the same supported flow with genuinely verified
`@bücher.example` email stores that Unicode domain as normalized_value, while
PrincipalDirectory canonical EMAIL normalization uses `@xn--bcher-kva.example`.
The bridge's lower/strip comparison bypasses the directory normalization contract;
canonical resolution/collision safety is not qualified. Both independent email
tests FAIL against exact eb4093 in 51.44s. Do not silently change the directory
contract or ratify external identity assurance to accept the bridge.

Disposition: **PENDING / RETURNED TO TITAN-1**, not selectively integrated.

## 3. TITAN-2 containment integration review

Owner container/liveness tests: independently 10 PASS in 4.45s, zero skips.
These are injected/mock contract tests, not native Linux acceptance. In particular,
some manually move registry entries as the implementation is expected to do;
that does not prove the actual execute/finally path performs those transitions.

Independent counterexamples against exact 9de2: **2 FAIL in 7.03s**.

- RUNTIME-03: failed Docker inspect with stderr `authorization plugin not found`
  matches the generic `not found` substring. `_remove_containers` returns success
  despite failed removal and no authoritative container-absence result.
- RUNTIME-04: `os.scandir` PermissionError on an existing tracking directory is
  suppressed inside Path.glob; the outer handler never runs and remote-worker
  scanning returns an empty list. Patching Path.glob itself misses this path.

The cancellation loop shields an executor future and delays cancellation until
cleanup finishes. Repeated cancellation, thread hangs, actual execute-path
cleanup failures, successful cleanup, concurrent cleanup and native Linux behavior
still need complete independent qualification. Do not equate its unit successes
with the invariant that live/unconfirmed execution never disappears from tracking.
Disposition: **PENDING / RETURNED TO TITAN-2**, not selectively integrated.

## 4. Canonical principal and genuine customer qualification

Same preserved APEX Python/Node harness, actual HTTP, email delivery, fresh
PostgreSQL, Chromium virtual WebAuthn and generated signed root PoP:

- Previous e1a9: **10 PASS / 1 FAIL / 14 NOT_EXECUTED**; canonical-principal FK
  failure reproduced again with this exact harness.
- New eb4093: **13 PASS / 1 BLOCKED / 11 NOT_EXECUTED**. Read-only diagnostic:
  canonical principal=1, root=1, consent=1. No trust records seeded. Rotated prior
  session returns401; logout invalidates the resulting session. BASIC_VERIFIED
  email is not external real-world identity proofing. CDP is not hardware evidence.

| Historical stage | Phase | eb4093 result |
| --- | --- | --- |
| 1 | signup | PASS |
| 2 | email_verification | PASS |
| 3 | password_login | PASS |
| 4 | organization_onboarding | PASS |
| 5 | passkey_enrollment | PASS |
| 6 | passkey_assertion_verification | PASS |
| 7 | secure_elevated_session | PASS |
| 8 | legitimate_identity_qualification | PASS, BASIC_VERIFIED only |
| 9 | explicit_customer_consent | PASS |
| 10 | root_initiation | PASS |
| 11 | root_proof_of_possession | PASS |
| 12 | root_activation | PASS |
| 13 | application_registration | BLOCKED |
| 14 | agent_registration | NOT_EXECUTED |
| 15 | capability_delegation | NOT_EXECUTED |
| 16 | policy_assignment | NOT_EXECUTED |
| 17 | judgment | NOT_EXECUTED |
| 18 | human_approval | NOT_EXECUTED |
| 19 | execution_grant | NOT_EXECUTED |
| 20 | controlled_execution | NOT_EXECUTED |
| 21 | evidence_verification | NOT_EXECUTED |
| 22 | revocation | NOT_EXECUTED |
| 23 | post_revocation_execution_attempt | NOT_EXECUTED |
| 24 | post_revocation_denial | NOT_EXECUTED |
| 25 | logout_session_invalidation | PASS |

Stage13 is the existing harness boundary
`DOWNSTREAM_AUTHORITY_CONTRACTS_NOT_QUALIFIED`, not a failed attempted application
endpoint. No application success is claimed. TITAN-1 must correct the negative
binding cases and qualify the downstream authority contracts before product
integration extends these stages. This is an owner-source receipt, not acceptance
of the APEX integrated candidate or all root security conditions.

## 5. PostgreSQL migration security disposition

Independent fresh PostgreSQL16.15 test against exact 9de2:
0063->0064->0065 preserves existing rows across two tenants and non-null defaults.
Nonempty downgrade/reupgrade preserves ordinary rows but changes stored required
passkey flag1->0. **PG-02 P0 BLOCKED**. No fail-closed downgrade restriction was
supplied in the new runtime commit. A schema roundtrip is not preservation of
authorization semantics. TITAN must implement an approved fail-closed restriction
or preservation policy; no migration source was changed here.

## 6. Native Linux results

At committed APEX08551472, exact-head independent run38938820891 native scope:
15 PASS in114.47s, zero skips. It does not qualify the rejected 9de2 cleanup
implementation, actual cross-user EPERM, or all its new failure paths. New owner
mock tests on macOS are not relabeled native Linux tests. Integrated 9de2 native
qualification is NOT_EXECUTED because its counterexamples fail.

## 7. MCP, SDK and product matrix

At APEX08551472, independent run38938820891: original36, extended205 and full
MCP519 PASS on EACH Python3.11/3.12, strict skip receipts zero. Prior nonce/EPERM
selection independently reproduced3 failures then local31 PASS/zero skips.
Product run38938824938: frontend315 tests/35 files, each Python79 focused,
24 Forge/display and363 inventory/SDK/schema PASS; browser wrappers4 PASS.
CodeQL38938829084 PASS workflow. None proves the new rejected security sources.

Earlier separately installed external consumers: Python wheel, TypeScript
ESM/CommonJS and Go3 PASS; LangChain/LangGraph/OpenAI Agents/ADK24 PASS; separate
CrewAI/LlamaIndex22 PASS, all zero skips. Those are historical receipts described
in SDK_INSTALLATION_COMPATIBILITY.md, not new exact-head acceptance in this
continuation. Combined framework installation is BLOCKED by incompatible OpenAI
major requirements. External providers remain NOT_TESTED/BLOCKED. No publishing.

## 8. Immutable evidence

Required migration reproducer original blob:
`f4d5731e9b2792b18a69e1fcfd475164ee4f0898`.
Verified unchanged in APEX and eb4093. TITAN-2 9de2 still contains altered blob
`071cbecd44d8e965c694f9c857bf8d96fdc79fc3`; it cannot replace original evidence.
No original APEX reproducer or integrity manifest changed.

Unchanged original independent_m13r2 scope on eb4093: **18 PASS / 1 FAIL /
0 SKIP in127.93s**. Failure is original migration test's0064 expectation after
upgrade head now0065. Preserve that failure and test identity; this is not a
runtime FK regression and must not be fixed by editing the historical assertion.

## 9. Mandatory CI and compliance

The exact APEX08551472 results above are historical relative to this packaging
checkpoint. Its independent workflow remains FAIL: customer,101 inherited Ruff
findings, unsigned39619c4b ancestor. The old customer job ran M13-I3. This change
adds the unchanged APEX25-stage harness as an independent subsequent step even
after legacy failure and uploads both receipts. New exact-head runs are required.

DCO: author/maintainer authentic remediation accepted under existing policy is
required for39619c4b46dac5d6e69c9e00ce887c2ed9641cfc. No forged signoff, history
rewrite, narrowed base or disabled check. Ruff:101 inherited findings include
security-owned implementation and immutable tests; owner-reviewed source fixes
and founder disposition of immutable-test conflict remain required. Gitleaks:
prior full-history six fingerprints remain unresolved; owner must classify each,
rotate any real credential and obtain approval for historical remediation.
No secret values, blanket allowlist or history deletion are used. See earlier
exact findings in FINAL_ENGINEERING_REPORT.md and PR216 receipt6217965662.

## 10. Defects, decisions and independent verdict

| Priority | Issue | Owner / disposition |
| --- | --- | --- |
| P0 | Unconfirmed container removal accepted; scan failure clears tracking | TITAN-2, returned |
| P0 | Passkey requirement lost on nonempty downgrade | TITAN migration owner, BLOCKED |
| P0 | Genuine full customer chain incomplete; root policy unratified | TITAN-1 / founder, BLOCKED |
| P0 | Mandatory CI/compliance failures | Security maintainers / authentic author / founder |
| P1 | Unverified email promotion at service boundary | TITAN-1; HTTP reachability unverified |
| P1 | Noncanonical IDNA email binding | TITAN-1, returned |
| P1 | New containment success/failure/native coverage incomplete | TITAN-2, pending |
| P2 | Supported framework combined install conflict and provider qualification | SDK/platform owners, BLOCKED |

Founder Decision Record A remains unratified. Preserve stricter requirements;
do not choose identity policy or PathB emergency-ticket lifetime by assumption.
No mandatory gate is waived by a local pass or an owner report.

**Independent verdict: M13 NO-GO.** New security changes failed independent
acceptance and are withheld. Owner handoff:
https://github.com/Guruprasath-Annadurai/Whitepact/pull/215#issuecomment-6221687719.
Independent negative tests are preserved separately under
`scripts/engineering/reproducers/test_m13_apex_titan_acceptance.py`; they are
explicit owner-source qualification reproducers, not ordinary candidate successes.

## 11. Remaining work and reproducibility

Next three actions: obtain owner corrections for four counterexamples and rollback
policy; independently rerun corrected root/containment and unchanged genuine
journey before selective import; qualify the final integrated committed source,
native Linux, all25 stages and required CI/compliance gates. No existing grant,
approval or fixture can substitute for the missing customer authority journey.

Local raw evidence:
`/private/tmp/apex-eb4093-customer.json`, `apex-e1a9-original-red.json`,
`apex-eb4093-email-binding.log`, `apex-9de2-independent-counterexamples.log`,
`apex-eb4093-owner-root-tests.log`, `apex-9de2-owner-tests.log`,
`apex-eb4093-original-security.log`, `apex-9de2-postgres-rollback.json`.

From APEX root, run new negative tests explicitly with candidate source precedence:

```sh
PYTHONPATH=/private/tmp/whitepact-apex-titan-eb4093/src:. /Users/ag/Whitepact/.venv/bin/python -m pytest scripts/engineering/reproducers/test_m13_apex_titan_acceptance.py -k root_email -q -o addopts=''
PYTHONPATH=/private/tmp/whitepact-apex-titan2-9de2d5/src:. /Users/ag/Whitepact/.venv/bin/python -m pytest scripts/engineering/reproducers/test_m13_apex_titan_acceptance.py -k 'inspect_plugin or directory_permission' -q -o addopts=''
```

Expected current results are failures. Do not load an owner's pytest pythonpath
configuration when claiming predecessor or integrated APEX test provenance.
