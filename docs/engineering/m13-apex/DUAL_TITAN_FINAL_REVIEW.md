# Dual-TITAN independent review — 17 October 2026

M13 OPEN. GLOBAL PRODUCTION NO-GO. This is a partial qualification checkpoint,
not milestone acceptance. No merge, deployment, spend, publication or M14.

## Source provenance and selection

Started from clean APEX `1bd70571f417226f2e247903817988c4c5410f16`, tree
`bf6a310698f4e608ba268c88fd0bba09c08e2568`, parent
`ba94652842e511de3dbc30169789e7e17e428d14` on
`codex/whitepact-m13-apex-integration`. Canonical remote is
`https://github.com/Guruprasath-Annadurai/Whitepact.git`.

Fetched actual remote heads, then created separate detached review worktrees:

| Owner | Actual remote branch | HEAD | Tree | Parent |
|---|---|---|---|---|
| TITAN-1 | antigravity/whitepact-m13-titan | 2819be0938ac88c57dc9a7d0d1215c96d87b35ab | 781c18cc192a291786df7ea0565038698b9645cb | 9fbfc122c4b2b9f58b9ab3cb813293b2a7a6219b |
| TITAN-2 | antigravity/whitepact-m13-titan2 | 622b02d6d52b6467204f0464bda9252a65606e33 | a44c5bca1238923c32fbce25585a80b4b2bbafdb | d64992f1a6709a06247fa939a28576481371245d |

No wholesale merge. Selected only mandatory persisted email-denial checks at
APEX root initiation and completion. These deny unverified/disabled accounts;
they do not create canonical principals, elevate sessions, or enable root
activation. Existing assurance status must also qualify. Other owner root,
first-passkey, session, application and agent changes remain under review.

Selection preserves the owner's compatibility rule: a persisted confirmed
mailbox with legacy UNVERIFIED status qualifies as BASIC_VERIFIED for this
check only. It does not update the user's status or create a verified external
identity. An initial stricter selection omitted that rule and caused seven
existing bootstrap setup failures; corrected before checkpointing. A historical
9fc source comparison passed those nine bootstrap tests, but is not the immediate
1bd predecessor and therefore is not used as proof of its behavior.

Both owners now carry the same migration guard already integrated in APEX.
TITAN-1 and APEX in-flight scanners match. TITAN-2's scanner matches APEX too;
its remaining isolation diff is the container backend. Preserve APEX's scanner,
inspect-error handling, tenant prefixes, MCP/SSE binding and nonce semantics.
Container cancellation/lifetime changes are withheld pending the findings below.

## Independent counterexamples

Original reproducers were not edited. Logs are local independent executions,
not copied owner results. All listed completed scopes have zero skips.

| Boundary | Predecessor | Corrected owner | Interpretation |
|---|---|---|---|
| Unverified root authority, default flags | 9fb: FAIL, BOOTSTRAPPED, 22.55s | 2819: PASS, 19.81s | Original stronger authority reproducer now rejects before authority writes |
| Explicit assurance false / true | Integrated predecessor: 1 FAIL / 1 PASS, 26.07s | 2819: 2 PASS, 30.95s | False predecessor flag reaches missing canonical-principal FK; not a legitimate denial contract |
| Cleanup error loses cancellation | d649: FAIL, 4.30s | 622: PASS, 3.85s | Unchanged original helper reproducer RED → GREEN |
| ROOT-03/04 and RUNTIME-03/04 original four-case file | Historical RED preserved in unified report | 2819: 3 PASS / 1 FAIL, 49.07s | Unverified original case now raises the correct early EnterpriseError before its label assertion; report failure unchanged, never call four-case suite green |
| Mandatory downgrade, optional roundtrip, concurrent writer, incompatible 0064 interval | Unsafe retention predecessor RED preserved | 622: 5 PASS, 96.89s | Actual PostgreSQL; no mandatory 0064 interval permitted |

The original four-case unverified test assumes bootstrap succeeds before
checking EMAIL metadata. The new denial contradicts that setup assumption.
Its immutable failure remains visible; the separate unchanged stronger authority
test establishes the relevant denial. Verified IDNA and both runtime cases pass.
Full collision, lifecycle, session, owner, quorum, proof-of-possession and tenant
qualification are not established merely by those four narrow cases.

### New cancellation findings

New independent file `scripts/engineering/reproducers/test_m13_dual_titan_cancellation.py`
against 622: **2 FAIL in 0.47s**, no skips. It does not change the originals.

1. Two `cancel()` calls become four pending cancellation requests after cleanup.
   The helper counts caught cancellations without consuming their existing
   task count, then calls `cancel()` again. The test waits on thread events and
   checks the exact final count; no timing-only sleep determines completion.
2. Actual production `execute()` exhibits the same 4-versus-2 count after cleanup
   raises. Active tracking is retained during cleanup and becomes unresolved
   afterwards in this test; those tracking assertions pass before the count fails.

These are deterministic Python tests with mocked Docker transport and cleanup.
They are **not native Linux/Docker containment proof**. No container escape or
unauthorized execution was demonstrated by these findings.

Additionally, corrected owner's unchanged runtime suite plus in-flight suite:
**10 PASS / 1 FAIL in 3.64s**. Its next-admission test expects an ExecutionOutcome
but receives CancelledError. That is an interface/regression failure, not evidence
that admission succeeds. The initial mixed-worktree invocation failed conftest
import collection; its results are excluded and the corrected invocation above
uses one owner test tree. Owner must fix cancellation accounting and qualify the
denial return contract without swallowing caller cancellation.

## PostgreSQL verdict

APEX and both corrected owners refuse mandatory downgrade at revision 0065
under an ACCESS EXCLUSIVE table lock. This is stronger than retaining metadata
while allowing revision 0064 to serve. Integrated scope: **4 PASS in 77.07s**,
covering mandatory refusal, optional repeated roundtrip, concurrent mandatory
writer, and new real-PostgreSQL failed-DDL transaction rollback.

The new failed-DDL case creates a dependent view, observes downgrade failure,
checks revision 0065 and original data, removes only that test dependency, and
proves supported downgrade/re-upgrade retains the optional row and value.

The immutable original migration blob remains
`f4d5731e9b2792b18a69e1fcfd475164ee4f0898`. TITAN-2 still carries altered blob
`071cbecd44d8e965c694f9c857bf8d96fdc79fc3`; rejected. Its head==0064 assertion
is still a known historical CI failure at 0065. No replacement assertion or
policy bypass is used. Startup of arbitrary older binaries against a manually
changed database is not qualified by a migration refusal alone.

## Genuine customer journey

Fresh PostgreSQL, actual HTTP APIs, real Chromium WebAuthn, genuine password,
mailbox verification, scoped consent and Ed25519 root proof. No authority seeds.
New owner source 2819: **17 PASS / 1 BLOCKED / 7 NOT_EXECUTED**. BASIC_VERIFIED
here means mailbox verification, not independent external identity assurance.
Harness source was the uncommitted integration workspace; it has not changed
journey logic from the preceding checkpoint. Exact implementation identity is
recorded in `/private/tmp/apex-dual-2819-customer.json`.

| # | Stage | Owner 2819 | Integrated last clean 1bd70571 |
|---|---|---|---|
| 1 | Signup | PASS | PASS |
| 2 | Email verification | PASS | PASS |
| 3 | Password login | PASS | PASS |
| 4 | Organization onboarding | PASS | PASS |
| 5 | First passkey enrollment | PASS | BLOCKED |
| 6 | Passkey assertion | PASS | NOT_EXECUTED |
| 7 | Elevated session | PASS | NOT_EXECUTED |
| 8 | Basic identity qualification | PASS | NOT_EXECUTED |
| 9 | Explicit customer consent | PASS | NOT_EXECUTED |
| 10 | Root initiation | PASS | NOT_EXECUTED |
| 11 | Root proof of possession | PASS | NOT_EXECUTED |
| 12 | Root activation | PASS | NOT_EXECUTED |
| 13 | Application registration | PASS | NOT_EXECUTED |
| 14 | Agent registration | PASS | NOT_EXECUTED |
| 15 | Capability delegation | PASS | NOT_EXECUTED |
| 16 | Restrictive policy assignment | PASS | NOT_EXECUTED |
| 17 | Judgment | BLOCKED | NOT_EXECUTED |
| 18 | Human approval | NOT_EXECUTED | NOT_EXECUTED |
| 19 | Short-lived execution grant | NOT_EXECUTED | NOT_EXECUTED |
| 20 | Controlled execution | NOT_EXECUTED | NOT_EXECUTED |
| 21 | Evidence verification | NOT_EXECUTED | NOT_EXECUTED |
| 22 | Revocation | NOT_EXECUTED | NOT_EXECUTED |
| 23 | Execution attempt after revocation | NOT_EXECUTED | NOT_EXECUTED |
| 24 | Denial after revocation | NOT_EXECUTED | NOT_EXECUTED |
| 25 | Logout invalidation | PASS | PASS |

Stage17 still receives403 IDENTITY_VERIFICATION_REQUIRED from hosted API-key
issuance. A reusable organization key must not substitute for an agent execution
grant. Existing `/api/governance/approvals/{approval_id}/execute` calls the real
`resume_approval()` pipeline with nonce, epoch and authority resolver. Existing
tool-call API explicitly does not mint ExecutionGrant state. Product bridge work
must authenticate the canonical agent and preserve that kernel boundary before
any receipt for stages17–24 can be claimed. No fake grant or provider proof used.

## Release gates and remaining work

New candidate exact-head CI is pending, not copied from 1bd70571. That preceding
checkpoint passed product, CodeQL, MCP519, extended209, identity/origin83 and
native15; failed original migration assertion, DCO, historical Gitleaks, Ruff
and genuine customer acceptance. See the unified report and PR216 receipts.

P0: authenticated integrated customer journey and stages17–24; independent root
lifecycle qualification; first-passkey bootstrap review; unresolved founder
identity assurance record. P1: cancellation count and next-admission interface;
full actual execute/native matrix for owner lifetime changes; complete current
head regression matrix. P2/inherited release gates: Ruff cleanup, precise
historical scanner dispositions, genuine missing DCO signature. Their mandatory
policy gates remain failing regardless of priority labels.

Founder/maintainer actions: ratify unresolved identity assurance policy; obtain
the actual historical contributor's DCO attestation; obtain credential-owner
classification/rotation where needed and precise scanner-policy disposition;
formally disposition the immutable historical migration expectation. Never
forge signatures, rewrite protected history, alter the immutable test, or add a
blanket scanner bypass. M13 cannot be accepted on present evidence.
