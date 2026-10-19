# M13 corrective checkpoint — 2026-10-19

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

- P0 qualification: new tenant-boundary correction needs exact-head Linux/PG
  evidence and independent Antigravity review. No claim of zero known P0.
- P1: complete failure-by-failure engineering/spec disposition; full and native
  matrices remain failed on predecessor source. Cold restart/all-metadata loss
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
