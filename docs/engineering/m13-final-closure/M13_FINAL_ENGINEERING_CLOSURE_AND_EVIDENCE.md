# M13 Final Red-to-Green — engineering evidence

**C. BLOCKED — ENGINEERING OR SECURITY GATES REMAIN.**

## A. Source

Branch `codex/whitepact-m13-final-convergence`, PR223 draft. Starting candidate
55fcb8015abca2bb8ac94826a30c270bb1c73a49, tree
abb1f1249b81edd7e94171b615a57b144a17c490, parentf556bb7a.
Alembic0066. All earlier approved dispositions remain ancestors.
This record accompanies actual fixture corrections; its future commit identity
must be read from Git and exact-head manifests, not a self-referential claim.

## B. Immediate runtime/restore corrections

Original runtime reproducer blob4d7d39934f7f3a87c3e833e9176f5e8cf29aad00;
original restore reproducer blob61259878ff820168aa3eb49f75a4841fb416ce3c.
Unchanged two-case reproduction on Python3.12:2FAIL in9.11s, receipt
`/private/tmp/m13-redgreen-runtime-before.xml`.

A1 plugin callback: original fixture never acknowledges inert CREATE and mocks
the actual inspection helper away. Existing production inspection is not
diagnosed as missing. Narrow fixture disposition requested; pending approval.
No original assertion was deleted, no extra production check added.

A2 contention: supply a synthetic full private CID for inert CREATE, not a
successful cleanup result. Resolve the existing explicit development component
configuration before the bounded scheduling probe. Original contended lock,
two cancellation requests, pending-task, CancelledError, unresolved evidence
and cancellation-count assertions remain unchanged. No timeout increases.
Python3.12:1PASS4.42s; Python3.11:1PASS3.56s. Receipts
`/private/tmp/m13-redgreen-contention-after-py312.xml`, correspondingpy311.
Initial incomplete fixture attempts failed and are not reported as successful.
When this scripts-only test is invoked alone, its documented nonproduction
component environment requires `WHITEPACT_ALLOW_UNISOLATED_EXECUTION=1`;
the normal runtime CI scope loads the existing tests/conftest.py opt-in.
No production flag or new bypass was introduced.

A3 restore: each disposable database now has a test-private tracking directory
and singleton, restored with monkeypatch after the fixture. No pre-existing
tracking file is deleted. The old fixture reused `restored-tenant` across
independent registries and left uncertainty visible to later reconciliation.
Prior PG16 CI39733087713 records the original third-test failure with the
earlier synthetic execution. Original three assertions/cases are preserved.
Added a fourth negative case: uncertain termination must still reject tombstone
reconciliation and retain both unresolved state and its local evidence file.
Real PG16 dual-Python after-results are PENDING at report creation.

Commands use `PYTHONPATH=src:. <python> -m pytest <exact test IDs> -q
-o addopts='' --tb=short --junitxml=<receipt>`. Scoped Ruff and diff checks PASS.

## C. Complete regression accounting

The latest complete downloaded matrix is f556bb7a, not this successor:
run39480793805,8123 cases per interpreter;7998PASS/91FAIL/0ERROR/34SKIP.
Branch coverage80.47%(3.11),80.74%(3.12). All16 shard plans/source IDs checked.
Machine-readable ledger: `/private/tmp/M13_CONVERGENCE_III_EXACT_HEAD_FAILURE_LEDGER.json`.
The older bff5f14372-failure count is not current qualification. Successor full
matrix is required; no tests skipped/xfail-marked or thresholds lowered here.

## D. Runtime and database evidence

Exact55fcb801 native run39733082625 passed per interpreter35unit/PG,
5migration/compatibility,2cold restart and19native cases, no skips/failures/errors.
Downloaded manifests match HEAD/tree/parent, at
`/private/tmp/m13-runtime-approval-native-55fcb801`.
This proves the dedicated single-host cases, not multi-host or every crash point.
Full-suite cold tests still failed under broader context; root cause remains OPEN.
The current runtime accepts exactly0066. Historical old-binary execution and
database-role retirement/fencing remain mandatory separate requirements.

## E. Customer and identity

Strict-default17PASS/1BLOCKED/7NOT_EXECUTED remains historical and separate
from prototype25PASS. No WebAuthn, quorum or identity assurance relaxed.
No legal identity assertion substituted for real provider qualification.

## F. CI, compliance and independent review

Run links use https://github.com/Guruprasath-Annadurai/Whitepact/actions/runs/ID.
55fcb801 runtime review39733087713:FAIL on retained other counterexamples and
restore; native jobs PASS. Product/Sovereign and successor complete checks must
be inspected separately; no old result is assigned to new source.
Prior mypy387 source files PASS. Broader Ruff, authentic historical DCO,
dependency/NLTK assessment, seven individually triaged broad Gitleaks findings,
and human classification of five authority tables remain OPEN as applicable.
No forged attestation or invented retention/erasure/legal-hold policy.
Antigravity exact-head independent qualification remains PENDING. A CI workflow
named independent review is not a substitute for Antigravity execution.

## G. Remaining actions and authority

Obtain plugin fixture disposition; prove corrected restore positive/negative
on PG16; rerun integrated original runtime scope; finish complete failure ledger
and actual old-binary/role fencing; qualify root/customer, SDK/MCP/framework and
frontend gates; resolve security/static/compliance requirements; obtain exact-head
Antigravity review. Mandatory failures remain, not just human acceptance.
No main merge, force push, release/package publication, deployment, cloud/DNS
mutation, paid provisioning, public restore activation or M14.
M13 OPEN — GLOBAL PRODUCTION NO-GO.

## Red-to-Green execution update (2026-10-22)

- Corrected fixture source890ad7a0e89fb436955aac325fdee302748da456 was
  actually checked out in runtime run39735534564 (verified checkout/source logs).
  Artifact labels contain synthetic PR merge SHA f0749756 and must not be used
  as the tested source. Parsed restore JUnit:4PASS on each interpreter, including
  uncertainty denial. Contended-registry original passes. Runtime3.12 is
  54PASS/1FAIL(plugin);3.11 is53PASS/2FAIL(plugin plus a different original
  cleanup-after-cancellation case). No blanket runtime PASS is claimed.
- Added exact historical source-process test atd1f6f748b3f296e94505330d1f30a243bf159680.
  It archives the actualbff5f143 source, starts its real ASGI lifespan in a
  separate interpreter against migrated0066 and requires incompatible startup
  refusal before serving. Dedicated run39735880980 passed both interpreters;
  exact-source manifests and historical JUnit downloaded to
  `/private/tmp/m13-redgreen-historical-d1f6f748`. This covers that ancestor,
  not every historical release or production credential retirement.
- Root-hardening original baseline:9FAIL/4PASS on3.12; missing recent ownerUV.
  Fixtures now enroll and authenticate actual test signing keys through
  IdentitySecurityService, retain the server session binding, sign root PoP,
  request exact-operation challenges and advance authenticator counters.
  No PASSKEY_UV facts or generic verification flags are written directly.
  The original39 assert ASTs remain identical. Current complete module:
  **13PASS/0FAIL/0SKIP on3.12 (40.22s) and3.11 (30.60s)**. Earlier incremental
  attempts6FAIL/7PASS are preserved; they exposed missing operation assertions
  and a nonadvancing test counter, not missing production authentication checks.
  Receipts `/private/tmp/m13-redgreen-root-qualified-counters-py312.xml` andpy311.
- Static cleanup uses explicit unused bindings rather than removing effectful
  calls, removes unused imports (preserving imported pytest fixture via explicit
  re-export), and normalizes nonprotected import order and literal encodings.
  No original security assertion removed or weakened. Broader Ruff fell from188
  to11 remaining findings:4immutable independent import-order issues and7blind
  exception assertions. These are OPEN, not excluded from final qualification.
  One SDK timeout test calls nonexistent `get_compliance_report()` and accepts
  AttributeError as success under broad Exception. A narrow correction was
  requested; it is not accepted as actual timeout proof.
- Added native pre-START crash probes at before-CREATE, after-CREATE/before
  acknowledgement and acknowledged/before-START. Pause hooks exist only in
  the disposable test-worker script; actual backend CREATE, PostgreSQL journal,
  Docker identity and labels are exercised. Cleanup targets only a fullCID
  independently checked against exact tenant/execution/generation labels.
  Execution of these additional cases is PENDING; no native PASS transferred.

Founder decisions still pending include the plugin fixture seam correction;
further protected-test disposition, authentic historical DCO and legal policy
must remain explicit. Remaining actionable engineering/full matrix and
independent qualification are not complete. No production or M14 authority.

## Red-to-green CA-bundle remediation and native receipts

- Exact prior head `30d0be53550fc95a595f567788cec90feea82ede`, tree
  `674646ffc77f4b35adbeee40f1936a7a2ad112ff`, native run39738289826:
  both Python3.11/3.12 artifacts independently record that head/tree/parent.
  Each has35unit,19native,5cold,5migration,1historical tests:65PASS,
  0FAIL/ERROR/SKIP. Five cold cases include the three new pre-START windows.
  This supersedes only their PENDING execution note, not the full crash matrix.
- Security run39738408701 failed on certifi2026.7.22/PYSEC-2026-4320.
  The root package, independently distributed Python SDK and security-tool input
  now require certifi>=2026.10.19. Both locks target2026.10.19; no unrelated
  dependency version changed. TLS/hostname validation and transport code remain
  unchanged. Upstream advisory GHSA-6q48-6c7w-9gw2 and OSV identify the compromised
  CA trust issue; official PyPI artifact hashes match both generated locks.
- New floor/lock regression tests first failed2/2 against the prior manifests.
  Corrected Python3.12 tests pass3/3, including actual HTTPcore default context
  loading the installed corrected bundle with CERT_REQUIRED/hostname checking.
  `uv lock --check --offline`, hash-enforced tooling installation, `pip check`,
  scoped Ruff/format/diff checks pass. Tooling-lock pip-audit reports no known
  vulnerabilities (nonfatal advisory/cache warnings retained, not suppressed).
- Broader local egress scope:109PASS/7FAIL; socket binding/DNS unavailable in
  this execution environment. These are NOT waived or claimed green. Fresh
  exact-head Linux CI remains required. Independent read-only patch review
  found no concrete surviving bypass or legitimate regression.
- Prior-head CodeQL/Gitleaks/SDK-package/product/Sovereign workflows succeeded;
  runtime and independent integration failed, full matrix remained queued.
  Those results do not qualify the next commit. DCO, customer journey, original
  independent security and full lint failures remain OPEN pending exact receipts
  and scoped dispositions. GLOBAL PRODUCTION NO-GO; M13 OPEN; M14 unauthorized.

### Successor receipts and persisted-owner fixture

- CA-bundle successor752d68ace0efd7d1d9e5404c01feff2cb3309b65/tree
  e002863cdd9caae0e25b3000a7a8ddb0bb8c2611: security scan39740194707 SUCCESS.
  Floor/default-TLS regressions3PASS on both local Python3.11/3.12;42SDK
  transport/credential/package checks PASS on3.12. Full matrix39740255590
  queued at inspection; no complete-suite success claimed.
- Current independent root reproducer failed before its mutation because it
  lacked verified owner WebAuthn. Its fixture now enrolls/authenticates through
  IdentitySecurityService, retains the resulting server session, and obtains
  an exact-operation assertion before revoking email/membership/organization.
  No assurance flag or production repository state is seeded. All original
  assertion ASTs remain identical. New positive control PASS on3.12; original
  thirteen root-hardening tests13PASS. Real PostgreSQL reproduction of the
  three persisted-revocation cases remains PENDING exact-head Linux CI.

### Audit/backup assertion specificity

- Original H3 blob882b5e7ad0965485867f337e8d86fba65f6024af and H4
  e56029775e6746dd94a15bffa2a3508cd4deb296 remain available in parent history.
  Three blind Exception assertions now require duplicate/unique IntegrityError
  or SQLite's invalid-database DatabaseError. Focused tests3PASS on3.12.
  Corrupt-file connections close explicitly. No acceptance of AttributeError,
  unrelated setup failure or nonintegrity exception as a security success.
- H4 tracking uses a temporary per-test directory, preserving every outer
  unresolved record. This reproduced a distinct original fixture contract gap:
  test07's callback returnsNone but expects confirmed termination. Full H3/H4
  run39PASS/1FAIL on3.12. Production correctly retains uncertainty. Formal
  disposition requested for explicit True success fixture plus additive None
  negative test; original assertion not weakened or silently replaced.

### Data inventory completeness (Codex integration ownership)

- Reproduced original inventory gate1FAIL/2PASS: five authority/journal tables
  lacked classification. Added explicit CRITICAL security classifications;
  exportable=False, erasable=False and SECURITY_EVIDENCE_DEFAULT preserve the
  previous fail-closed fallback. No root/WebAuthn/journal enforcement, schema,
  migration or production operation changed. All original inventory assertions
  retained; five additional cases protect the non-export/non-erasure posture.
- Inventory/export10PASS on Python3.11 and3.12. Erasure/retention/tenant-export
  scope5PASS on3.12 with one existing legacy-static-key deprecation warning.
- Outage tests now require OSError/SQLAlchemy OperationalError rather than any
  Exception; unrelated logic/attribute failures no longer count as proof of a
  database outage. Collection10cases PASS; realPG execution remains pending.
- Actual customer artifact39738299380 confirms17PASS/1BLOCKED/7NOT_EXECUTED:
  judgment403 IDENTITY_VERIFICATION_REQUIRED, BASIC_VERIFIED/no provider.
  Passkey success is not external identity qualification. No assurance flags,
  provider credentials or authority are fabricated to bypass this blocker.
  Legacy browser probe separately reports downstream contracts unqualified.

## Founder-approved fixture/provenance dispositions (2026-10-22)

Approval received for the callback CREATE/no-op seams, SDK false-positive tests,
four import-order corrections, awaited restore-check patch, historical0064
fixture and explicit backup termination acknowledgement. No production security
checks, timeout guarantees, migrations or SDK retry behavior changed.

### Recoverable original evidence

Independent source commit57c69344961196fd89b40e8ffec65c06a1898fce remains pinned.

| File under tests/independent_m13r2 | Original blob | Approved revised blob |
| --- | --- | --- |
| test_m13p_postgres_schema.py | a0b0953ab261079b28e516760921b5892aa71c63 | 3d46e3616990f3c364e244ae277b74149ceb992c |
| test_m13p_security_contract_acceptance.py | 99cd279b17c53f01a1f876480a4435b0504ca2e1 | cda15e380ecd36b845561644ca8cb8a2fd2a292a |
| test_m13r_migration_roundtrip.py | f4d5731e9b2792b18a69e1fcfd475164ee4f0898 | 661b08b9150e93babf282294199639592b3384b4 |
| test_m13r_verified_containment.py | 4d0d984d2a84e53cd503696e2e3b9d3a19ef2ede | 137c337e4a33305f1168e1babf53f44dee0ce362 |

All26 original assertion ASTs match. Three files change import order only;
migration-roundtrip additionally changes exactly two upgrade targets from head
to0064, under its separate approval. Its second runtime-ID test still uses
current head. All constraint/downgrade assertions remain intact.

Immediate pre-change parent59e9ac62197e05f10dbf3fe3dc916cd037fd04af blobs:
callback module60e0b8005279020f4a094e96fc0b089e410e292d;
backup065f54ea88c2bf75de7fb6d228b1958317810f4b;
egress0918f4c1811da2d1e661a22323a6cb52d84953ee;
SDK08fe3a00b315b7ad3688a1b9be3b8224f14c44db.
Original callback55fcb blob4d7d39934f7f3a87c3e833e9176f5e8cf29aad00 remains
recoverable independently of subsequent contention-fixture correction.

### Verification and limits

- Provenance guard keeps all eight original hashes, verifies their original
  Git-reference availability, requires the exact approved revised blobs, and
  compares complete import/non-import ASTs with only the two authorized0064
  substitutions. Unknown hashes, changed imports/assertions, missing originals
  and unauthorized logic fail closed. Three workflow single-hash checks now
  call this stronger full-manifest preflight; no unconditional hash waiver.
- Guard/preflight16PASS on3.12. Combined approved guard/SDK/backup/egress scope
  45PASS on3.11. Both corrected SQLite independent modules12PASS on3.12 and
  those modules plus three real-helper ambiguity probes15PASS on3.11; one
  existing static-key deprecation warning each. No assertions skipped.
- SDK's original test was executed and PASSED despite its method being absent:
  confirmed AttributeError false-positive. Corrected existing IDs require
  ReadTimeout with configured timeout propagation and HTTPStatusError502 with
  exactly one mutation. AttributeError/TypeError/authentication cannot satisfy
  the timeout proof (three additive controls). Five focused cases PASS on3.12.
  Added real delayed-socket deadline test; local bind is platform-denied, not
  skipped. Linux dual-Python execution is mandatory, not inferred from injection.
- H3/H4/SDK/egress local cohort56PASS/1FAIL on3.12 before the three additional
  wrong-error controls: sole failure is forbidden local socket bind; one existing
  Starlette deprecation warning. Backup success now explicitly returnsTrue;
  None/False/exception retain tracking, produce no confirmed IDs and deny new
  admission. Actual containment evidence is NOT manufactured from these doubles.
- The original callback now reaches real cleanup, but its unchanged matcher
  requires 'inspect' while production raises 'containment unconfirmed after
  12.0s'. One FAIL remains; requested a separate message-only disposition.
  Production remains fail-closed. Three additive actual-helper plugin/daemon
  ambiguity tests PASS and preserve unresolved tracking/subsequent denial.
- Full Ruff src/tests/scripts PASS; actionlint and immutable-action checks PASS.
  Added missing copyright/SPDX headers to three new Codex test helpers without
  changing their logic. RealPG16 roundtrip, fresh CI and independent Antigravity
  verification remain PENDING. No qualification or M13 closure is claimed.

### Fresh full-matrix receipts and safe cold-worker diagnosis

Run39741800960 at exact59e9ac62197e05f10dbf3fe3dc916cd037fd04af/tree
7f5e95f7bcf7b637462fac5c225093920c3d7294 completed all16 shard plans.
Each interpreter:8018PASS/84FAIL/0ERROR/34SKIP (8136 cases). Every plan records
matching head/tree and clean source; execution inventories match. The separate
External /Users/ag/WHITEPACT_M13_RED_TO_GREEN_59E9AC62_FAILURE_LEDGER.json retains all failure/skip IDs and
diagnostic/JUnit hashes. No skip waived, no result transferred to later heads.

Five cold-worker tests fail before reaching their real boundary in the broad
matrix despite dedicated native success. Their stderr was intentionally discarded
to protect credentials; the cause is not yet proven. Test-only worker diagnostics
now emit only a bounded ASCII exception class into a private0600 create-once file.
Tests display that sanitized category, never exception text, traces or connection
strings. Corrupt/oversized/non-ASCII diagnostics are not reprinted. Focused
diagnostic tests4PASS per interpreter before the create-once error-handling
refinement; subsequent verification remains recorded by the next exact-head run.
Native behavior, readiness and admission predicates are unchanged.

SDK/package CI39741808004 and product CI39741808010 at59e9ac62 also identify
the same single remaining actual customer test: expected automatic recovery
after PostgreSQL outage, but the server retains503 FAILED quarantine. This is
not silently relabeled an outage or bypassed. A narrow historical expectation
disposition was requested; public restore activation remains CLOSED.

SDK read-deadline successor8c27c764 adds an actual delayed successful response
control:50ms deadline must time out;2s deadline must receive success after500ms.
This verifies read timeout behavior, not a total mutation/execution deadline.
Real socket execution remains blocked locally and mandatory in Linux CI.

## Approved callback/cancellation completion checkpoint

Founder explicitly approved the callback matcher 'containment unconfirmed' and
the cancellation CREATE acknowledgement/pre-resolved development configuration.
No outage-expectation disposition was included in that reply; that unrelated
historical assertion remains unchanged and OPEN.

- Corrected callback records actual mocked Docker inspect targets and requires
  RuntimeError from the real cleanup helper. Its final ExecutionOutcome is
  unsuccessful, uncertainty remains registered, tracking remains present and
  subsequent admission is denied. The natural5s execution wall timeout is not
  used as proof of plugin handling; the separate real-helper RuntimeError and
  inspected exact CID establish that path. No timeout bound was extended.
- Original cancellation source at969c97ae975c6dc271b8d139318a9a91bb2a6f08,
  blob `bc00c78e9cafa461b58cde388610b43c5866acfe`,
  remains pinned. Revised blob08e36bbf2c6ac0a412d397ae1c248d816190852a adds
  only the approved fixture setup. All9 original assertions remain intact;
  one additional check requires the existing explicit development journal mode.
- Provenance checks both original Git availability and the exact revised blob,
  then constructs the only permitted AST transformation. Altered cancellation
  counts, timeouts, CID, logic or missing original evidence are rejected. The
  workflow's old single-hash assertion is replaced by this relationship check,
  not by an unconditional new hash or a blanket either-hash exception.
- Callback/cancellation/provenance/CREATE scope29PASS on each Python3.11/3.12.
  Exact two corrected tests plus provenance16PASS each with no skips/errors:
  /private/tmp/m13-approved-exact-callback-cancellation-py311.xml andpy312.xml.
  Invalid/partial/mismatched CREATE acknowledgement never sends START.
- Broader initial3.12 scope79PASS/3FAIL: two neighboring supposed-unit probes
  contacted actual Docker CREATE, one PostgreSQL case could not connect under
  local restrictions.3.11 initially lacked Hypothesis, now installed. Nothing
  is waived or described as a successful complete neighborhood run.
- Separate ordinary unit-fixture repair: cleanup-race probes mocked START and
  failure of removal but left CREATE real, potentially leaking stopped daemon
  objects into later native tests. Their CREATE is now inert and tracking paths
  are per-test, with every original assertion preserved. Sentinel test proves
  the controlled probe makes zero subprocess/daemon calls. Native tests remain
  untouched by this module fixture. Neighbor containment/revocation scope43PASS
  per interpreter; sentinel separately1PASS on3.12. Fresh Linux verification of
  the broad-suite cold-worker failure cause remains PENDING, not presumed fixed.
- Full Ruff, actionlint, pinned-action checks PASS. Source/readiness rules remain
  unchanged. Independent Antigravity review and exact-head Linux/PG16 CI are
  mandatory before qualification. M13 OPEN; GLOBAL PRODUCTION NO-GO.

### Follow-on inventory reconciliation and SDK checks

- Reproduced duplicate sibling React keys in AgentInventoryPage: both authority
  panels used the organization ID. The new regression failed (1 failed, 5 passed)
  before correction. Distinct panel-prefixed keys retain organization-change
  remounts without changing requests, authorization or authority state.
- After correction: frontend ESLint PASS, Vitest 316 passed / 0 failed / 0 skipped,
  TypeScript and production build PASS. No duplicate-key warning remains. Generated
  bundled assets are rebuilt with the source; no browser/visual qualification is
  inferred from these unit/build results.
- Python SDK unit/contract/negative scope: 92 passed. Actual SDK wheel built and
  installed offline into a separate clean virtual environment outside the checkout;
  installed-package import, remote HTTP credential rejection and certifi floor pass.
- TypeScript SDK compilation passes; complete unit run reports 36 passed, 20 failed,
  0 skipped. Every failure encounters local `listen EPERM` on loopback. Those tests
  remain unchanged and require real Linux execution; this is not a green SDK suite.
- Go is absent from the local PATH; local race/package qualification remains blocked.
  GitHub API status queries currently fail to connect. Exact-head CI and independent
  Antigravity acceptance are pending, not inherited from earlier commits.
- The historical outage-recovery assertion is unchanged: the latest approval
  authorizes only the two specified runtime corrections, not an outage disposition.
