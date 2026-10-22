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
