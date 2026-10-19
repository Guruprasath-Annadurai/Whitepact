# M13 corrective checkpoint — 2026-10-19

## Latest candidate: ed1eb770

HEAD `ed1eb7705b69bef30fbbacb3717219ea995f41a6`, tree
`a576376ddbc46843f7cd90cba6ac057cc7d1a823`, parent
`851f52888a57df35619b9d75ab3d6f61c4f53bc7`. The later sections preserve their
explicit predecessor source scopes. Candidate source is clean and pushed.

This final dependency correction raises MCP minimum and lock from1.29.1 to
patched1.30.0 for GHSA-84m7-p3x7-pcfv (stateful HTTP session accumulation).
No dependency requirements changed between those release metadata sets. PyPI
hashes were verified; `uv lock --check` and147-package installed compatibility
checks passed. See M13_FINAL_MCP_DEPENDENCY_REVIEW.md. Default-branch alerts now
include this fifth advisory, but candidate lock also already has fixed
source-map-js1.2.2, Mako1.4.3 and multidict6.9.1. NLTK remains unresolved.

Actual installed CrewAI/LlamaIndex consumer tests on this source:22PASS on
Python3.11 (24.07s) and22PASS on3.12 (24.76s), receipts
`/private/tmp/m13-final-ed1e-consumers-{311,312}.xml`. Local contract-server
interop is not a Core authority or customer journey proof. The separate563-case
MCP/SDK bounded regression scope completed **563PASS**,10warnings in927.83s,
with the actual patched MCP1.30.0 installed. Receipt:
`/private/tmp/m13-final-mcp130-green-v2.xml`. This is local Python3.11 evidence,
not Linux daemon qualification or an invented full-suite result.

Exact-head CI run register (all completed; no result transferred from predecessors):

| Scope | Run |
| --- | --- |
| Full matrix | [39297637229](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297637229) — FAIL; complete accounting on both interpreters |
| Targeted native/authority/PG | [39297605013](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297605013) — FAIL; actual scopes detailed below |
| Runtime | [39297610672](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297610672) — FAIL:53PASS/2FAIL and restore2PASS/1FAIL per interpreter |
| Integration/compliance | [39297610725](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297610725) — FAIL |
| Sovereign customer journey | [39297610803](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297610803) — SUCCESS, default journey remains BLOCKED |
| Product | [39297611098](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297611098) — SUCCESS |
| SDK | [39297637319](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297637319) — SUCCESS |
| CodeQL | [39297638898](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297638898) — SUCCESS |
| Security scan | [39297636709](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297636709) — SUCCESS |
| Gitleaks | [39297636735](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39297636735) — SUCCESS |

Superseded851 full run39296536950 is CANCELED, not PASS or a quota denial.
Completed851 receipts independently confirm default17PASS/1BLOCKED/7NOT_EXECUTED
and development prototype25PASS with production disabled; runtime53PASS/2FAIL
and restore2PASS/1FAIL per interpreter. They are not transferred to ed1eb770.
All141 Ruff errors are in16 preserved original security/reproducer files; no
unblocked product-source Ruff errors were found. The full gate remains failed.
Per-case predecessor83-failure/34-skip ledger is in
[M13_FINAL_3946_FAILURE_LEDGER.md](M13_FINAL_3946_FAILURE_LEDGER.md).

### Independent original-counterexample replay on ed1eb770

Receipt `/private/tmp/m13-final-ed1e-original-counterexamples.xml`:10PASS/5FAIL
in262.26s. All original scripts remain unchanged. Four separate Recovery Zero
owner-source counterexamples also pass4/4 in7.03s on the exact final candidate
(`/private/tmp/m13-final-ed1e-owner-counterexamples.xml`).

| Required original counterexample | Actual result / limit |
| --- | --- |
| ROOT-03 unverified email authority | Original identifier replay FAILS early with email verification required. Separate original default-flag denial and both explicit-assurance denial cases PASS. No unverified authority receipt is fabricated. |
| ROOT-04 canonical IDNA/collision | Original canonical-IDNA replay FAILS early with recent server WebAuthn UV required; its identifier assertion is NOT_REACHED. Signed-A2 counterparts require separate exact-head evidence. |
| RUNTIME-03 daemon/plugin errors | Unchanged plugin-error negative PASS; controlled Docker response, not a native daemon failure experiment. |
| RUNTIME-04 tracking permission errors | Unchanged directory PermissionError negative PASS; permission exception injected, not claimed as a native ACL test. |
| PG-02 mandatory passkey downgrade | Both unchanged intermediate0064 and retained-requirement tests PASS on real PostgreSQL. Protected migration reproducer remains blob f4d5731e9b2792b18a69e1fcfd475164ee4f0898. |

Three further original root-completion mutation cases (email, membership,
organization) FAIL before mutation at the new UV prerequisite. They are not
accepted mutation coverage. The separate cleanup-error, exact cancellation
count and retained-tracking negative cases PASS. These are neither an all-GREEN
original suite nor grounds to relax A2. Independent signed-A2 evidence and
formal original-test disposition remain required.

Final exact-head Sovereign artifacts independently record clean ed1eb770/tree
a576376d, default17PASS/1BLOCKED/7NOT_EXECUTED, prototype25PASS, no seeded authority
and production disabled. All25 stage statuses match the customer table below;
that table is now also independently supported on the final HEAD. Sovereign
component scope49PASS and native scope19PASS on each interpreter; this separate
native scope does not erase the failing runtime/native matrices.

Exact-head introduced DCO gate uses5291cc6d..HEAD and flags one unsigned commit:
`39619c4b46dac5d6e69c9e00ce887c2ed9641cfc`. This is a different scope from the
preserved15-commit milestone authorship ledger and227-entry all-history ledger;
do not conflate their counts. Actual author/owner disposition is still required.
Exact-head inherited Ruff remains141errors. Customer artifacts explicitly use
a CDP virtual authenticator: actual server signature/UV checks are exercised,
but physical hardware authenticator qualification is NOT_EXECUTED. HTTP/browser
account setup is not a full visual form usability audit.

### Completed exact-head targeted qualification

Each Python3.11/3.12 artifact independently records authority98PASS, final
contracts31PASS (including actual PostgreSQL cross-tenant rejection), native
133PASS/1FAIL, recovery39PASS/4FAIL, and each of three route repetitions6PASS.
Original reference cohort is982PASS/10FAIL/2SKIP on each interpreter, no ERROR.
The four recovery failures remain original H4test07, H4test11, the compound
Fortress FK replay with earlier unresolved execution, and the imported owner's
name-only orphan recovery expectation. Native failure is the production
host-side refusal test receiving restore denial first. None is silently waived.
Signed-A2 current ownership/identifier/mutation counterparts are among the
98PASS; the five original prerequisite failures remain failed separately.

Original CPU source baseline `d9ddf44afa64fade5eb5805b03696b92533e0924`, tree
`fccb81c969698c7a16d6815e4d1f8c745c243142`, is clean in the receipts. Five runs
on each interpreter are RED (outcome durations4.304867306–4.689138711s). Final
candidate receipts record clean exact ed1eb770/treea576376d; five runs on each
interpreter are GREEN (1.128450624–1.182625454s), below the unchanged3s bound.
These are actual native Linux Docker executions, not copied local measurements
or optional OS skips. Their GREEN result does not clear the native scope's
separate failed assertion.

Completed Python3.11 full interpreter has8shards,8,079uniquecases,
7,961PASS/84FAIL/34SKIP/0ERROR. Both new cross-tenant cases PASS. In addition to
the predecessor's83 failures, `test_repeated_sequential_timeout_soak` failed:
iteration17 reported an actual in-flight authorization revocation rather than
the expected timeout. Preserve that receipt as an additional failure; no
unsupported flakiness classification, exception suppression or relaxed bound.
Python3.12 full matrix is also complete:7,962PASS/83FAIL/34SKIP/0ERROR,
8,079unique cases with complete accounting. Its timeout-soak case passed; that
does not reclassify Python3.11's failure. Both interpreters'563 MCP/SDK cases
PASS in the full Linux matrix, independently of the local563PASS run.

Aggregate branch coverage: Python3.11 7,077/8,760=80.7876712329%; Python3.12
7,101/8,760=81.0616438356%. The unchanged80% branch threshold is satisfied;
the mandatory test gate is not. All18 artifacts (16shards,2aggregates) were
downloaded and independently parsed at `/private/tmp/m13-final-ed1e-full-final`.
Final per-case verdicts and skip reasons are recorded in
[M13_FINAL_ED1E_FAILURE_LEDGER.md](M13_FINAL_ED1E_FAILURE_LEDGER.md).

Migration verdict is limited to the supported Alembic downgrade path: mandatory
passkey requirements cause atomic refusal, rather than permitting0064 with
retention metadata. This does not independently prove that an out-of-band old
application binary cannot connect to a newer schema. Old-binary operation and
deployment compatibility remain BLOCKED pending explicit independent evidence;
no migration script result is substituted for that assurance.

**BLOCKED — ENGINEERING OR SECURITY GATES REMAIN. M13 OPEN. GLOBAL PRODUCTION NO-GO.**

This checkpoint supersedes earlier “current” and “pending extraction” labels in
the eight historical reports. It does not erase their rejected receipts.

## Candidate and independent correction

Draft PR: https://github.com/Guruprasath-Annadurai/Whitepact/pull/223

| Identity | Exact value |
| --- | --- |
| Branch | codex/whitepact-m13-final-convergence |
| HEAD | 851f52888a57df35619b9d75ab3d6f61c4f53bc7 |
| Tree | c66bed85ac9bbaff54af9c5a08e29f82f441ec99 |
| Parent | 39461fec883aeb18a14f486ba9d65a2c02b20d06 |
| Parent tree | c798eb7f40794bfff248be9f3d6c5deb16b85fee |

Source was committed with a DCO sign-off and pushed; this is not a cryptographic
signature. PR220/221/222 and protected history remain untouched. No merge to
main, deployment, publication, paid infrastructure, or M14 work occurred.

Independent negative fixtures on SQLite and real disposable PostgreSQL proved
that the predecessor reconciler followed a tenant-A request's approval ID into
tenant B and changed B's PENDING approval to REVOKED. Both assertions were RED:
`/private/tmp/m13-final-cross-tenant-red-v3.xml` (2 FAIL, 26.88s). These are
malformed database fixtures, not fabricated customer grants or journey receipts.
An initial environment import error and an earlier rejection-only two-case RED
remain distinct receipts.

The correction checks request/approval ownership and runtime child/request
ownership before any tenant mutation. A mismatch rolls back the transaction,
persists a FAILED restore record, and leaves the gate FAILED. Approval revocation
also requires its tenant explicitly. Public reconciliation remains disabled.

Local corrected evidence:

| Scope | Result | Receipt |
| --- | --- | --- |
| Cross-tenant plus live admission and production durable-provider contracts | 10 PASS, 99.61s | /private/tmp/m13-final-cross-tenant-green.xml |
| Unchanged original same-tenant PostgreSQL approval/request FK reproducer, isolated | 1 PASS, 26.21s | /private/tmp/m13-final-cross-tenant-original-fk.xml |
| Cross-tenant rollback plus persisted FAILED assertions, both actual databases | 2 PASS, 25.19s | /private/tmp/m13-final-cross-tenant-persistence-green.xml |
| Ruff check / format, two changed Python files | PASS | local command output |
| Mypy, changed implementation file | PASS | /private/tmp/m13-final-cross-tenant-mypy.log |

These checks do not qualify every newly added child-reference preflight branch.
Full exact-head CI is mandatory and pending. Cold process restart with every
registry/receipt association lost also remains independently unqualified.

## Completed predecessor matrix — not transferable to this HEAD

Exact source `39461fec883aeb18a14f486ba9d65a2c02b20d06`, clean tree
`c798eb7f40794bfff248be9f3d6c5deb16b85fee`:

| Gate | Actual result on each Python version | Run |
| --- | --- | --- |
| Eight full-suite shards, Ubuntu 24.04 / PostgreSQL 16 | 7,960 PASS / 83 FAIL / 0 ERROR / 34 SKIP; complete 8,077-case accounting | [39258774395](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258774395) |
| Branch coverage, Python 3.11 | 7,074 / 8,754 branches; unchanged 80% gate exceeded | same full run |
| Branch coverage, Python 3.12 | 7,097 / 8,754 branches; unchanged 80% gate exceeded | same full run |
| Authority scope | 98 PASS | [39258704190](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258704190) |
| New integration contracts | 29 PASS | same targeted run |
| Actual native containment scope | 133 PASS / 1 FAIL | same targeted run |
| Recovery originals and owner additions | 39 PASS / 4 FAIL | same targeted run |
| Runtime review | 53 PASS / 2 FAIL; restore scope 2 PASS / 1 FAIL | [39258713249](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258713249) |
| Sovereign development qualification | SUCCESS; prototype 25 PASS, default BLOCKED | [39258713269](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258713269) |
| Product review | SUCCESS | [39258713327](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258713327) |
| SDK/package | SUCCESS | [39258786256](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258786256) |
| CodeQL | SUCCESS | [39258793506](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258793506) |
| Configured security scan | SUCCESS | [39258803237](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258803237) |
| Gitleaks | SUCCESS | [39258815944](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258815944) |
| Independent integration / inherited policies | FAIL, including full Ruff: 141 errors | [39258713255](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39258713255) |

Native new late-ACK/missing-tracking ownership, acknowledged cancellation with a
same-tenant sibling, and lost-receipt/foreign-tenant isolation each actually
passed on Linux. The native scope still failed
`test_production_never_runs_it_host_side`: restore admission FAILED before the
expected isolation refusal. This is not a green native matrix or an OS skip.

Of the 67 original baseline failures, 65 still failed and two passed:
`test_03_restored_database_stale_revocation_epoch_advanced` and
`test_cross_tenant_isolation_on_org_endpoints`. There were 18 failures outside
that ledger, including the imported owner's name-only detached recovery
expectation. Original cases remain unchanged; passing safer counterparts is
not silent disposition of the historical assertions. The separately targeted
reference shard had 981 PASS / 10 FAIL / 1 ERROR / 2 SKIP on Python 3.11 and
982 PASS / 10 FAIL / 2 SKIP on 3.12; the ERROR is preserved, not called PASS.

Earlier bb6e full receipts had hundreds of failures and 33 errors per interpreter.
The hermetic gate fixture fixed shared singleton leakage without setting READY
or clearing runtime evidence. Failed callbacks now retain the same active and
unresolved owner entry. Those corrections do not erase the rejected matrices.

## All 25 genuine customer stages

Fresh PostgreSQL / actual HTTP / Chromium receipts in the predecessor Sovereign
run record clean exact implementation HEAD, `authority_seeded=false`, and
`production_enabled=false`. The default journey is the policy-relevant result.
The opt-in B1 development prototype is a separate experiment, never production
activation or legal identity assurance.

| Stage | Default | B1 development prototype |
| --- | --- | --- |
| 1 Signup | PASS | PASS |
| 2 Email verification | PASS | PASS |
| 3 Password login | PASS | PASS |
| 4 Organization onboarding | PASS | PASS |
| 5 Passkey enrollment | PASS | PASS |
| 6 Passkey assertion verification | PASS | PASS |
| 7 Secure elevated session | PASS | PASS |
| 8 Identity qualification (BASIC_VERIFIED only) | PASS | PASS |
| 9 Explicit customer consent | PASS | PASS |
| 10 Root initiation | PASS | PASS |
| 11 Root proof of possession | PASS | PASS |
| 12 Root activation | PASS | PASS |
| 13 Application registration | PASS | PASS |
| 14 Agent registration | PASS | PASS |
| 15 Capability delegation | PASS | PASS |
| 16 Policy assignment | PASS | PASS |
| 17 Judgment | BLOCKED | PASS |
| 18 Human approval | NOT_EXECUTED | PASS |
| 19 Short-lived execution grant | NOT_EXECUTED | PASS |
| 20 Controlled execution | NOT_EXECUTED | PASS |
| 21 Evidence verification | NOT_EXECUTED | PASS |
| 22 Revocation | NOT_EXECUTED | PASS |
| 23 Post-revocation execution attempt | NOT_EXECUTED | PASS |
| 24 Post-revocation denial | NOT_EXECUTED | PASS |
| 25 Logout/session invalidation | PASS | PASS |

Default: 17 PASS / 1 BLOCKED / 7 NOT_EXECUTED. Founder-ratified A2 and B1 remain
in force; do not request them again. Reusable human/service keys still require
IDENTITY_VERIFIED. BASIC_VERIFIED, WebAuthn UV and root PoP do not attest legal
identity. The unresolved decision is M13 acceptance scope under this policy,
not permission to bypass the default judgment requirement.

## Current exact-head run register

All entries below target `851f5288`; results must be extracted when complete.

| Scope | Run |
| --- | --- |
| Full 16-job matrix | [39296536950](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296536950) |
| Targeted native/authority/PG contracts | [39296477127](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296477127) |
| Runtime | [39296485782](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296485782) |
| Independent integration/compliance | [39296485463](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296485463) |
| Sovereign customer journey | [39296485490](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296485490) |
| Product | [39296485560](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296485560) |
| SDK | [39296535078](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296535078) |
| CodeQL | [39296539938](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296539938) |
| Security scan | [39296535531](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296535531) |
| Gitleaks | [39296538581](https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/39296538581) |

## Remaining engineering and founder-controlled gates

- P0 qualification: new tenant-boundary correction has exact-head Linux/PG
  regression evidence, but still requires independent Antigravity review.
  Cold restart/all-metadata-loss remains unverified. No claim of zero known P0.
- P1: complete failure-by-failure engineering/spec disposition; full and native
  matrices remain failed on the final candidate. Cold restart/all-metadata loss
  remains unverified. Independent root, migration, revocation and original
  counterexample gates cannot be inferred from product success.
- P1: historical DCO authorship debt, inherited Ruff/protected-test conflicts,
  four UNCLASSIFIED authority tables and legal retention classification remain
  unresolved. No forged author sign-offs or policy exclusions were introduced.
- P1: original migration downgrade reproducer blob
  `f4d5731e9b2792b18a69e1fcfd475164ee4f0898` remains immutable. Mandatory passkey
  downgrade refusal remains required; retained metadata is insufficient.
- P2 dependency risk: prior NLTK advisory disposition is not blanket acceptance;
  refreshed default-branch alert counts are not an exact candidate audit.
- Founder decisions: historical authors' actual DCO consent; legal table/data
  disposition; explicit treatment of incompatible original assertions; default
  customer acceptance scope; residual dependency risk. Existing A2/B1 ratification
  is preserved. No new production authority was requested or inferred.
- Independent Antigravity request:
  https://github.com/Guruprasath-Annadurai/Whitepact/pull/222#issuecomment-6267438304
  No response or acceptance existed when last checked. Codex is not its own
  independent reviewer. OpenSSF/main publication remains NOT_EXECUTED.

Updated owner H4/Fortress snapshots are separate review evidence, not modified
originals: `scripts/engineering/review_snapshots/test_m13_final_owner_*_updated.py`.
Their prior 23 PASS receipt does not waive three unchanged original failures.
