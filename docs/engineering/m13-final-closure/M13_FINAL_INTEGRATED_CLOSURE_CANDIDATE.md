# M13 final integrated closure candidate — in progress

**C. BLOCKED — ENGINEERING OR SECURITY FAILURES REMAIN.**

M13 OPEN. GLOBAL PRODUCTION NO-GO. M14 NOT AUTHORIZED. This is an engineering
record, not independent acceptance or permission to release.

## Source and publication

The recovered published baseline is
`e4f3f12862712762f0d16d561afbd195067606e3`, tree
`1244eb605ccd9590437a7ac6483ff8a3f245ba42`, parent
`4acf2143a2b48c4bcdb434c4fb6c140d31cd39b2`.
Normal push succeeded after approved network access. PR223 was verified OPEN
DRAFT at that head. No force push or remote reconciliation was necessary.
Subsequent corrections described here require their own exact commit receipt
and fresh CI; baseline success cannot qualify them automatically.

## Database outage disposition

The unchanged real SDK/TCP/PostgreSQL test reproduced the reported post-outage
503 in 49.05 seconds. Reconnection is not authorization to leave FAILED.
The public reconcile route deliberately returns
`RESTORE_SECURITY_QUALIFICATION_REQUIRED`; it is not an operator authority path.

Founder-approved correction changes only the final historical recovery
expectation to continued 503 restore_quarantine, preserves original outage,
credential and effect assertions, and additionally checks persisted execution
authorization counts do not increase. Original source is recoverable at the
published baseline; original module blob:
`a8b5ecb2fff7e7e70ef5789b1a9d883fde0bff21`.

An additive authenticated customer test attempts both public reconcile aliases
concurrently with claimed operator/READY input and verifies denial, retained
FAILED state and no counter effect. Its initial FAILED state is explicitly a
synthetic test precondition, not proof of an actual restore or operator identity.

Both revised outage and negative customer tests pass on real PostgreSQL 16.15:
Python3.12 2 passed; Python3.11 2 passed. Local receipts are
`/private/tmp/m13-convergence-recovery-py312.xml` and corresponding py311.xml.

**Positive authorized operator recovery remains BLOCKED/UNQUALIFIED.** No fake
operator, public restore activation, direct FAILED-to-READY workaround, clearing
of uncertainty or weakening of Store B/journal/revocation was introduced.
Missing/corrupt evidence, replay/stale operator authority and concurrent authorized
recovery cannot be called qualified merely because public routes deny requests.

## Root and WebAuthn fixtures

Historical module blob `68d9933b8b4a12dc9f1655f96259d710470763d0`
at the published baseline remains recoverable. Valid owner-session enrollment,
server verification and exact operation-bound assertions replace missing
prerequisites, not production assurance rules. Every original root assertion
is preserved and checked by an additive AST integrity test. Neighboring customer
test functions are likewise checked unchanged, except the specifically approved
outage disposition.

The pending quorum and genuine unseeded enrollment cases reproduced two failures
before correction; both now pass on Python3.11 and3.12 against real PostgreSQL.
Expired/mismatched WebAuthn and rollback controls pass on3.12 (2 tests).
The full root module executed on both interpreters: **15 passed/1 failed** each.
That initial run exposed the recycled-identifier fixture's ownership mismatch.
Following the explicit founder disposition, the newly registered user now creates
the target workspace through IAM. The old revoked principal/identifier remains
historical data, and a separate old-owner workspace remains owned by the old user.
Added negatives require preserved revocation and deny cross-workspace bootstrap
and old-principal authority. This corrected case passes on both interpreters.
No SQL ownership transfer or production authorization change was made. A fresh
complete enrollment run is still required; the earlier15/1 result is not relabeled.

Subsequent complete local enrollment review:112 passed/0 failed/0 skipped on each
interpreter (3.12:408.90 seconds;3.11:348.04 seconds). One later additive startup-assertion
integrity meta-test was exercised separately; fresh exact-head CI must include it
and cannot inherit a113-test full-run claim from the112-test receipt.

The historical “concurrent race” test is sequential. An additive actual
concurrent-completion test uses two valid signed assertions for one ceremony,
requires one successful completion and one specific canonical denial, and checks
exactly one persisted root. Python3.12 and Python3.11 each pass (1 test).
Its earlier test mistakes (wrong column and superseded ceremony) were diagnosed
and corrected; those failed attempts are not qualification evidence.

The full authority-closure module passes all3 tests on each interpreter after valid owner,
proof-of-possession and exact-operation WebAuthn prerequisites are supplied.
The full consequential chain separately passes on both interpreters. All
original assertions in both historical modules are AST-checked unchanged.
These controlled authenticator fixtures are not hardware-authenticator or
external identity-provider qualification.

## SDK, identity and frontend

- Complete TypeScript SDK build/tests with approved loopback access: 56 passed,
  0 failed/skipped. Earlier restricted-sandbox20 socket failures were environmental.
- Python SDK seven-file unit/contract/negative scope: 92 passed on each interpreter
  (3.12 prior checkpoint,3.11 fresh here); no full-platform inference.
- Two local identity campaigns:30 and43 passed on3.12. The second initially
  could not collect without lxml; repository-declared SSO dependencies were
  installed into the isolated environment, not omitted or skipped.
- Frontend at published baseline:316 passed, lint/TypeScript/build passed.
  No frontend changes in this corrective slice. Hosted results remain separate.
- Strict-default customer journey remains historically17 PASS/1 BLOCKED/7 NOT
  EXECUTED; the development25-PASS prototype does not establish strict acceptance.
  External identity assurance has not been fabricated.

## Static quality and CI

Full source Ruff lint passes. Mypy reports no issues in429 source files.
Actual configured formatter command `ruff format --check src/ tests/ sdk/python/`
initially reported14 files. The founder-approved fixed allowlist, original and
revised blobs, original diagnostic digest and AST/directive verification are in
`M13_APPROVED_14_FILE_FORMATTING.md`. All14 formatting relationships now verify;
the configured full-matrix formatter check passes. Ten additive provenance
tests include deliberate semantic/directive/hash tampering and missing evidence.
Combined provenance/fixture checks:29 passed on each interpreter. No blanket
exception or hash bypass was added. The full-matrix workflow now pins Ruff0.17.0,
fetches historical evidence and executes the exact formatting guard. Existing
independent-original and cancellation provenance gates remain intact.

Published baseline workflows include runtime and native containment successes,
but enrollment and SDK/recovery-dependent lanes remain red. Fresh full dual-Python
and coverage evidence must run against the final committed candidate. The80%
branch threshold is unchanged. No old matrix totals are relabeled as current.

Neighbor restore/admission run:14 passed/1 failed/3 warnings on3.12. The failing
startup fixture supplied no durable Store B while expecting RESTORE_PENDING.
Following the explicit founder disposition, that fixture now supplies a real
isolated durable provider, preserves the original pending-state assertion and
checks restrictive-state persistence/restart. Original source blob:
`1e7cf4cec7370c0520da4b67d68d337bc0bf407c` at the published baseline.
Additive missing/unavailable-location/corrupt-provider cases require FAILED,
MCP denial, unchanged authorization counts and continued denial after database
reconnection and gate reconstruction. Startup scope:7 passed on each interpreter,
including real PostgreSQL16 and SQLite; one Starlette deprecation warning each.
Their preserved test-owned file marker is explicitly not a native containment
receipt; real unresolved-execution/journal verification remains a separate gate.

## Compliance, independent review and blockers

- Historical DCO commit39619c4b46dac5d6e69c9e00ce887c2ed9641cfc still needs
  genuine contributor/maintainer disposition; no signoff was forged.
- Conservative authority/journal classifications remain; engineering does not
  substitute for owner approval of retention/export/erasure/legal holds.
- Actual operator recovery qualification, remaining root/authority failures,
  full matrix/coverage, exact-head security/static CI, optional-dependency coverage,
  historical provenance and independent acceptance remain mandatory.
- Antigravity must independently verify the eventual exact SHA/tree, migration0066,
  native Docker/PG, recovery, WebAuthn, SDK and customer evidence. No older verdict
  transfers to this candidate. No final independent verdict has been obtained.
- Old-binary and obsolete-role fencing require their separate operational proof.

No merge, deployment, package publication, DNS/cloud mutation, paid resource,
public restore activation, release tag, history rewrite or M14 execution.

## Exact-head CI follow-on: historical checkout availability

Published9c980bac7381b7f9fd1dfbd04badb90be09462bd (tree
4549b1ce67aaf01a495a83fab0da2f799f9cc98f) received fresh hosted successes for
First Enrollment113 tests on each interpreter, SDK Integration, SDK/package,
security scan, native containment, Enterprise Completion, M11, M12-P, M12 Product
and Sovereign lanes. Full matrix and other lanes remain pending; no overall
qualification is claimed.

M13-I1 run39828489715 fails its historical-evidence preflight because that job's
checkout has default shallow history. The completed job reports Read-only Git
inspection failed. Local clean full-history preflight passes with original eight
independent blobs and the original-to-revised cancellation guard intact.
A new workflow regression reproduced1 failed/2 passed before correction.
The narrow correction adds only fetch-depth0 to that checkout, preserving exact
ref and disabled credential persistence. Provenance/workflow scope then passes
32 tests on each interpreter. No original hash, security assertion, cleanliness
check or acceptance requirement was removed. Fresh successor CI is mandatory.

The same hosted run separately reports the known historical DCO requirement and
failed/BLOCKED customer-journey gates; these are not converted into successes by
the checkout correction. Current customer artifacts require independent reading
before any old stage-count result can be attributed to the new head.
