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
