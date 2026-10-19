# IRONCLAD final qualification handoff

Final qualification update (2026-10-19): frozen implementation HEAD `ccf4e8cc80f1de52a0a9b445298055ac581f53e1`, tree `c7bef348b9dcea2e55a86d4b01f357fb1498ecd2`, parent `47fc55a1591890f18c06333b4f187d091535719d`. Draft PR #221 targets `codex/whitepact-m13-absolute-convergence`. Evidence-only branch adds tests/reports; implementation equivalence is checked independently. The current results below supersede historical pending statements retained later in this audit trail. M13 OPEN. GLOBAL PRODUCTION NO-GO.

## Final candidate verdict

**PARTIALLY READY — BLOCKERS REMAIN. M13 OPEN. GLOBAL PRODUCTION NO-GO. M14 NOT AUTHORIZED.**

Candidate source remains frozen and clean at the exact HEAD/tree/parent above. Reports are published separately on `codex/whitepact-m13-ironclad-evidence`; do not transfer candidate CI to a different source tree. Independent evidence test checkpoint `3e9d6b780672b568b3130649e0ec0e09975c91e1` (tree `2ed01463e28e7b5ed3ea537adcdd930460836a01`, parent `fd7472e09c9b200059db52132d13726e175ab83e`) changes only tests/workflow, with a CI-enforced empty implementation diff against sourcecc. No protected reproducer or H4 recovery source changed.

## Exact-head gate ledger

All run links use https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/ followed by the ID. All implementation runs below test sourcecc; evidence-contract run explicitly tests the evidence checkpoint with identical implementation.

| Gate / run | Independently observed result |
|---|---|
| Full 8-shard/16-job matrix39243226832 | FAIL; complete8029 unique cases per interpreter;7928 PASS/67 FAIL/0 ERROR/34 SKIP each |
| Full branch coverage | PASS:3.11 6949/8618=80.63355767%;3.12 6974/8618=80.92364818%; original80% threshold/source scopes |
| Targeted39243112392 | FAIL overall;98 authority PASS each;131 native PASS on3.12;129 PASS/2 FAIL on3.11 |
| Original CPU bound within targeted | PASS candidate10/10; RED baseline10/10; n=5 each interpreter/source |
| Route isolated + original instrumented cohort | 3×6 PASS each; no teardown ERROR; historical cause unresolved |
| Independent evidence contracts39246319117 | SUCCESS;4 PASS each, two actual Docker +two controlled callback checks, zero skips |
| Sovereign development39243120761 | SUCCESS; genuine freshPG prototype25 PASS each; strict default17 PASS/1 BLOCKED/7 NOT_EXECUTED |
| Product39243316986 | SUCCESS; frontend315, Python SDK94 each, agent bridge24 each, MCP363 each; actual browser4 PASS |
| SDK/package39243317495 | SUCCESS; configured TypeScript/Go/wheel/default-dashboard package gates; Go87.8% statement coverage |
| First Enrollment39243317358 | FAIL;95 PASS/12 FAIL each, protected pre-A2 root/authority fixtures |
| Independent Integration39243120600 | FAIL; DCO/Ruff, original migration/root/tracking and strict-default acceptance remain red |
| Runtime Review39243120593 | FAIL; runtime53 PASS/2 FAIL each; actualPG restore1 PASS/2 FAIL each |
| CodeQL39243317567 | SUCCESS |
| Configured Bandit/pip-audit39243317317 | SUCCESS; not a no-vulnerability certification |
| Historical Gitleaks39243318719 | SUCCESS |
| External OpenSSF publication / production | NOT_EXECUTED; not authorized |
| Separate optional framework consumers | Actual exactcc localhost22 PASS each;3.11 18.03s/3.12 18.74s; full-run22 optional skips remain skips |
| Fresh local PostgreSQL qualification | 6 PASS101.13s; four downgrade guards + schema + disposable-role retirement |

Full67 failures per interpreter:28 original pre-A2 root,24 historical migration-head assertions,5 immutable tracking contradictions,3 H4 recovery, and7 other gates (data classification,DCO,upstream absent-org precedence,restore503-vs500,source introspection,MFA positive-control400,mocked timeout revocation precedence). Every failure remains visible. First Enrollment's12 failures are9 TITAN-root and3 TITAN-authority cases listed individually in ROOT_A2_REPORT. Independent's three persisted-owner correction cases also lack the required A2 session; current genuine signed mutation counterparts pass. No copied owner report substitutes for execution.

Local diagnosis: original tenant-isolation file2 PASS on current local dependencies, while both Linux full runs fail its own-tenant MFA positive-control400 after all negative cross-tenant checks. Environment/order cause is unresolved, not labeled flaky. Original mocked timeout fails with retained tracking state (admission refusal reported as revocation, latest revoked epoch=-1), but **1 PASS in2.02s with a fresh TMPDIR**. No retained records were deleted; shared-registry/order interference remains a full-suite failure requiring fixture disposition. Initial optional-consumer-venv collection failed for missing FastAPI; retained as an unsuccessful attempt, not counted as a test result.

## Safety and integration decisions

### Five original counterexamples: independent acceptance status

| ID | Current evidence and original-gate verdict |
|---|---|
|ROOT-03|Unverified owner is denied; genuine signed A2 lifecycle/identity counterparts PASS in98-case Linux scope. Immutable email-binding reproducer attempts bootstrap without qualified A2 and therefore does not reach its old post-bootstrap assertion; original gate remains FAIL, not relabeled GREEN.|
|ROOT-04|Actual Unicode registration, email verification, WebAuthn and root-PoP IDNA/collision counterparts PASS both variants in Linux scope. Immutable canonical-IDNA reproducer lacks qualified A2 and remains FAIL before identifier assertion.|
|RUNTIME-03|Unchanged inspect/plugin negative test PASS both Linux interpreters. Actual shared-callback plugin/mixed-error counterparts2 PASS each. Separate immutable callback reproducer FAIL because its mocked shared cleanup bypasses inspection; unresolved gate explicitly retained.|
|RUNTIME-04|Unchanged directory-permission and scan-error fail-closed reproducers PASS both Linux interpreters. Unknown/corrupt legacy tracking remains unresolved; five conflicting original tracking tests remain FAIL.|
|PG-02|Four original PostgreSQL mandatory-refusal/rollback/concurrency guards PASS; no mandatory0064 schema served after an accepted downgrade. Immutable historical roundtrip test blob `f4d5731e9b2792b18a69e1fcfd475164ee4f0898` preserved and its historical head assertion remains FAIL.|

Original RED evidence is retained in the prior canonical reproducer history/reports. This successor does not fabricate a five-of-five immutable GREEN result: safe mandatory denial can prevent an older positive-setup assertion from running. Source integrity against793 is verified for every original reproducer, original root/migration suite and H4 source/test; no altered assertion replaces the originals. Admission/authority safety counterparts and original acceptance gates are reported separately.

Fresh exactcc local original-reproducer rerun: **10 PASS/2 FAIL in151.37s**, `/private/tmp/m13-ironclad-ccf4-original-counterexamples.xml`. Scope is unchanged apex TITAN acceptance + corrective authority + four migration guards. The two FAIL are the unverified/canonical-IDNA email-binding cases above; all other original scoped checks PASS. This is local PostgreSQL/component evidence, separate from actual Linux receipts.

- Root mutations lock current owner context before persisted principal state, then recheck verified email, active owner/session, recent server UV and PoP before write. Revoked principals cannot be promoted. New ownership transfer, genuine identity/capability and connection-pool counterparts pass without seeded authority.
- Workload-controlled CID removed as cleanup authority. Private0700 exact64-hex acknowledged receipts, bounded owned cancellation handoffs and PIPE drainage prevent foreign cleanup and untracked clients. Unknown creation remains unresolved even after a finite absence window.
- Same-organization native failures are retained, not solved by clearing uncertain records. Independent actual-Docker probes verify known-ACK cancellation/sibling success and lost-receipt affected-org denial/foreign-org success.
- Original callback/plugin reproducer still FAIL because it replaces the shared cleanup method now responsible for actual inspect handling. Two new tests exercise actual callback/shared cleanup and deny plugin or mixed absence/plugin errors. Counterparts do not automatically waive the immutable failure.
-0065 mandatory downgrade remains atomically refused under PostgreSQL locking; retention metadata is insufficient. Old pooled roles and deployed0064 binaries are not operationally qualified.
- Antigravity recovery-zero HEAD `8f1717c1bf1b5bbfe6fb0afc24f4bdc8ba73d9e1`, tree `3342e39c9cd809202123c7913680712d74ed8bf6`, parent `803c1ae665c175846efa5ffb588155291d555228` fetched only. No wholesale merge, H4 edit or independent recovery acceptance. Distributed-record pruning must prove containment rather than infer it from record absence. Public restore stays503.

## All25 actual customer stages on exact sourcecc

Both Python versions independently produce the same classifications in run39243120761. Receipts explicitly record clean implementationcc/treec7 and authority_seeded=false. Actual registration, HTTP APIs, fresh PostgreSQL, browser virtual WebAuthn, PoP, consent and controlled Docker execution are used; no synthetic applications/agents/grants/approvals/evidence.

| Stage | Phase | Development prototype | Strict default |
|---|---|---|---|
|1|signup|PASS|PASS|
|2|email_verification|PASS|PASS|
|3|password_login|PASS|PASS|
|4|organization_onboarding|PASS|PASS|
|5|passkey_enrollment|PASS|PASS|
|6|passkey_assertion_verification|PASS|PASS|
|7|secure_elevated_session|PASS|PASS|
|8|legitimate_identity_qualification|PASS|PASS|
|9|explicit_customer_consent|PASS|PASS|
|10|root_initiation|PASS|PASS|
|11|root_proof_of_possession|PASS|PASS|
|12|root_activation|PASS|PASS|
|13|application_registration|PASS|PASS|
|14|agent_registration|PASS|PASS|
|15|capability_delegation|PASS|PASS|
|16|policy_assignment|PASS|PASS|
|17|judgment|PASS|BLOCKED|
|18|human_approval|PASS|NOT_EXECUTED|
|19|execution_grant|PASS|NOT_EXECUTED|
|20|controlled_execution|PASS|NOT_EXECUTED|
|21|evidence_verification|PASS|NOT_EXECUTED|
|22|revocation|PASS|NOT_EXECUTED|
|23|post_revocation_execution_attempt|PASS|NOT_EXECUTED|
|24|post_revocation_denial|PASS|NOT_EXECUTED|
|25|logout_session_invalidation|PASS|PASS|

Stage8 is effective BASIC_VERIFIED account/authenticator control, not legal IDENTITY_VERIFIED. Strict judgment requires stronger identity and intentionally denies reusable credentials. Prototype is default-disabled and production-disabled. Stage19 proves real short-lived internal ExecutionAuthorization, not separate durable Phase7A grant certification. Stage21 is local-chain verification, not independent witnessing. Devmail/virtual hardware do not qualify production SMTP/physical authenticators. Actual receipts preserve agent revocation/epoch change, post-revocation PoP403 and approval replay409 without new evidence.

## Remaining priority issues and founder/owner decisions

- P0 acceptance: H4 canonical StoreB/reconciliation/FK/fencing independently unqualified; strict-default privileged customer journey BLOCKED. No public restore or production enablement.
- P1: historical Py3.11 teardown cause unresolved despite no recurrence; immutable native/callback security failures need formal policy-compatible disposition; full matrix67 failures each including unexplained Linux own-tenant MFA400 and original mocked timeout revocation outcome. Mandatory exact-head all-tests-green gate FAIL.
- P2/compliance:141 Ruff findings;15 milestone DCO author attestations; four unclassified authority tables; historical root/migration/tracking/source-introspection assertion dispositions; optional NLTK advisory risk and OpenSSF publication.
- Founder decisions: legal identity assurance/identifier reuse, authority-table retention/export/erasure/legal holds, authentic author attestations, and protected historical acceptance-policy changes. H4 operator recovery requires independent owner qualification; no silent uncertainty erasure authorized.

No merge/deployment/cloud provisioning/paid infrastructure/publication/M14 performed. Public free GitHub runners used; no framework rerun was denied by CI quota. Sub-agent model quota was exhausted earlier and is distinct from the actual completed framework/CI results.

## Historical audit trail (superseded by current evidence above)


**PARTIALLY READY — BLOCKERS REMAIN. M13 OPEN. GLOBAL PRODUCTION NO-GO. M14 NOT AUTHORIZED.**

## Published checkpoint

Draft https://github.com/Guruprasath-Annadurai/Whitepact/pull/221 is fetch-verified, targeting existing absolute-convergence source branch. PR #220 remains draft at `7939341f`9341f; H4 changes are absent. Source safety checkpoint ca135073b7bddce5b274c13983121eae02cbc347; exact reference cohort checkpointd9ddf44afa64fade5eb5805b03696b92533e0924. Both signed-off, not cryptographically signed.

## Evidence

- Ownership baseline2 FAIL/2 PASS50.70 s; corrected PostgreSQL11 PASS135.69 s.
- Pending-principal root race original4 FAIL69.43 s across all revoked lifecycle states; corrected genuine signed A2/B1 run pending.
- Teardown observation2 PASS3.52 s; actual Linux root cause and repeated success pending.
- Exact-head targeted workflow 39206376358, Sovereign39206402160, Independent39206402102 pending. Supersededca135073 workflow 39206348965 canceled to conserve resources; not a pass.
- No new full-suite or aggregate coverage acceptance yet. Prior793 results explicitly historical.

## Remaining engineering and human gates

P0/P1: independent corrected-root verification; H4 canonical recovery/PGFK/fencing owner qualification; unresolved complete root/identity/quorum counterpart coverage; Python 3.11 pending-task diagnosis; CPU bound; branch 80% both Python; exact-head broad security/product/Linux/PG matrices.

P2/compliance:28root and24migration immutable test dispositions;5tracking specification contradictions; upstream org-state/error precedence; source-introspection behavioral replacement decision; public restore500→503 protected assertion disposition only; four-table classification approval;141Ruff findings;15DCO genuine author attestations; optionalNLTK risk/OpenSSF publication. Prior skipped environments retain distinct NOT_EXECUTED/SKIP status.

Founder decisions: legal identity assurance and identifier reuse semantics; retention/export/erasure/legal holds; author attestations and protected historical acceptance changes. These decisions do not block unrelated safe engineering. No live role retirement, public restore enablement, production resources, publication, deployment, merge or M14 performed.

The25-stage customer journey is historical793 evidence (prototype25 PASS, strict default17 PASS/1 BLOCKED/7 NOT_EXECUTED); it has not yet been requalified on this candidate. A virtual authenticator, devmail and internal short authorization do not certify physical authenticators, SMTP, legal identity or a separately durablePhase7AGrant. Every stage needs exact-head receipt before final acceptance.

## Subsequent published-checkpoint CI evidence

At exact d9ddf44a, Sovereign workflow 39206402160 **SUCCESS** on both interpreters; actual fresh PostgreSQL/HTTP/Chromium development prototype25 PASS each, strict default17 PASS/1 BLOCKED/7 NOT_EXECUTED each. Independent39206402102 **FAIL** (DCO, protected original suites and strict-default journey gates). Targeted39206376358 **FAIL** overall: authority63 PASS each, isolated route18 PASS each, reference cohort988 PASS4 FAIL2 SKIP each, zero teardownERROR. One cohort failure is a diagnostic browser-cache omission corrected in the working changes; three are preserved tracking-policy contradictions.

These outcomes apply only to the published d9ddf44a tree. Further connection-reuse, root denial-precedence, capability/identity tests and profiling instrumentation require successor qualification. Local tests on those changes are identified separately; no exact-head CI status is transferred forward.

## All 25 stages at published d9ddf44a

Same classifications independently recorded on Python 3.11 and 3.12, workflow39206402160. Receipts are sovereign-prototype.json and sovereign-default.json in the per-interpreter sovereign-development artifacts. Both use actual fresh PostgreSQL, customer HTTP APIs, browser virtual-authenticator enrollment and signed assertions; authority_seeded is false. Development prototype is default-disabled and production-disabled.

| Stage | Actual phase | Development prototype | Strict default |
|---|---|---|---|
+| 1 | signup | PASS | PASS |
| 2 | email_verification | PASS | PASS |
| 3 | password_login | PASS | PASS |
| 4 | organization_onboarding | PASS | PASS |
| 5 | passkey_enrollment | PASS | PASS |
| 6 | passkey_assertion_verification | PASS | PASS |
| 7 | secure_elevated_session | PASS | PASS |
| 8 | legitimate_identity_qualification | PASS | PASS |
| 9 | explicit_customer_consent | PASS | PASS |
| 10 | root_initiation | PASS | PASS |
| 11 | root_proof_of_possession | PASS | PASS |
| 12 | root_activation | PASS | PASS |
| 13 | application_registration | PASS | PASS |
| 14 | agent_registration | PASS | PASS |
| 15 | capability_delegation | PASS | PASS |
| 16 | policy_assignment | PASS | PASS |
| 17 | judgment | PASS | BLOCKED |
| 18 | human_approval | PASS | NOT_EXECUTED |
| 19 | execution_grant | PASS | NOT_EXECUTED |
| 20 | controlled_execution | PASS | NOT_EXECUTED |
| 21 | evidence_verification | PASS | NOT_EXECUTED |
| 22 | revocation | PASS | NOT_EXECUTED |
| 23 | post_revocation_execution_attempt | PASS | NOT_EXECUTED |
| 24 | post_revocation_denial | PASS | NOT_EXECUTED |
| 25 | logout_session_invalidation | PASS | PASS |

Stage8 proves verified account/authenticator control, not legal identity or IDENTITY_VERIFIED. Stage17 strict default denies reusable credentials with IDENTITY_VERIFICATION_REQUIRED; no later privileged step is executed. Stage19 is an actual short-lived internal ExecutionAuthorization, not independent certification of a separately durable Phase7A grant. Stage20 executes the harmless rai_policy_check in controlled Docker. Stage21 verifies the local evidence chain and explicitly does not claim independent witnessing. Revocation disables the real agent, changes its epoch/delegation state, denies post-revocation agent PoP intent403, and denies approval replay409 without new evidence. Virtual hardware and devmail are not production physical-authenticator/SMTP qualification.

## Successor source checkpoint and current limits

Committed source47fc55a1591890f18c06333b4f187d091535719d additionally addresses forged cleanup identity, unknown late creation, client drainage and early cancellation ownership. Local final containment scope48PASS/8nativeSKIP; actual Linux and performance qualification pending. Connection/status and genuine authority/identity counterparts are committed in parentd480e8c87882a7fc5d353961a6fe22048380ab9f.

The source sub-agents hit their model usage limit after delivering their findings and files. No paid upgrade was purchased. Parent verification continued; this is not a GitHub CI quota rejection and is not used to invent a framework or Linux result. Untested environments remain explicitly unqualified.
