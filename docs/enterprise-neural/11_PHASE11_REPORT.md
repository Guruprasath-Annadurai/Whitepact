# Phase 11 — Citadel Execution Containment: Report

STATUS: **PASS**. Audit-driven, not a rebuild. `00_PHASE0_AUDIT.md`
§4 flagged execution-permit binding as "partially implemented for
MCP-mediated tool calls... not yet a general Citadel-style containment
boundary" — that finding is now stale. Since that audit, Execution
Permit v2 and the JIT Credential Broker generalized the containment
boundary well beyond MCP-mediated internal tool calls.

## Objective

Per `docs/enterprise-neural/11_PHASE11_DESIGN.md`: verify the master
directive's Phase 11 ("Citadel Execution Containment") against the
real, existing codebase — per Phase 0's own §6 instruction ("§18
[Citadel containment] describe[s] layers that partially exist
[`WhitePactRuntimeGateway`, `InternalToolExecutor`] under different
names — reuse them, do not rename or reimplement") and directive rule
63. Audit first.

## Current state before phase

`governance/execution.py`'s `ExecutionAuthorization` (digest-bound,
org-bound, expiry, single-use), `Executor` Protocol, and
`_validate_authorization()` shared checks already existed. Since Phase
0's audit, `governance/upstream_executor.py`'s `UpstreamMCPExecutor`
became a second, real `Executor` implementation, adding
target-fingerprint drift detection
(`check_target_fingerprint`/`AuthorizationTargetDriftError`), a JIT
Credential Broker (`governance/jit_credential.py`, single-use
time-boxed credentials), and DNS re-validation immediately before
dispatch. Both executors were already extensively tested
(`test_executor_bypass_invariant.py`, `test_upstream_gateway.py`,
`test_tool_trust.py`'s `TestExecutionPermitV2FingerprintDrift`,
`test_jit_credential.py`) — but nothing had regression-tested the one
property that ties both together: that every concrete executor
actually runs the shared validation function, rather than
reimplementing it (correctly or, someday, incorrectly).

## Architecture implemented

No new architecture — this phase adds **evidence**:

- `tests/test_citadel_execution_containment.py` — structural
  regression guards (source-text scan confirming
  `_validate_authorization()` has exactly the two known executor call
  sites, and `check_target_fingerprint()` has exactly one) plus
  runtime tests (a no-fingerprint authorization never drift-errors
  through the real `InternalToolExecutor`; replay and action-mismatch
  protections hold identically on both `InternalToolExecutor` and
  `UpstreamMCPExecutor`, proven independently rather than assumed to
  transfer from one executor's tests to the other's).

## Files created

- `tests/test_citadel_execution_containment.py`
- `docs/enterprise-neural/11_PHASE11_DESIGN.md`
- `docs/enterprise-neural/11_PHASE11_REPORT.md` (this file)

## Files modified

`CHANGELOG.md`, `docs/enterprise-neural/PROGRESS_LEDGER.md` — no
source file required a change.

## Database migrations

None.

## Security properties added

None newly *created* — this phase adds regression tests that make two
already-true properties (every executor validates through the shared
function; target-fingerprint checking stays scoped to the executor
that actually needs it) fail loudly if a future change silently breaks
them — most concretely, if a future `MCPExecutor`/`HTTPExecutor`
(named as not-yet-built in `execution.py`'s own docstring) is added
without calling `_validate_authorization()`.

## Privacy properties added

None new.

## Trust boundaries changed

None.

## Threats mitigated

Regression of "every concrete Executor runs the shared authorization
validation, not a hand-rolled reimplementation" is now caught by CI.
The shared replay-protection and action-mismatch properties are now
proven on both executor surfaces this platform has, independently.

## Threats not yet mitigated — named explicitly, not glossed over

1. **The self-hosted stdio transport's `dispatch_tool()` call
   (`mcp/server.py:244`) remains ungoverned** — same underlying gap
   named in Phase 8 (Gap 1) and Phase 10 (Gap 2). This phase confirmed
   again, by reading it in context, that this is not a new bypass: it
   only executes when `governance is None` (no hosted governance
   context for this call), with an explicit comment and `assert`
   guarding the governed path so `dispatch_tool()` is never
   double-called when governance is active. Architectural, not an
   oversight — the stdio transport has no organizational identity to
   build a decision against.
2. **`ExecutionAuthorization` remains deliberately unsigned** — a real,
   already-documented design decision (`execution.py`'s own module
   docstring), correct as long as the object never crosses a process
   boundary. Signing becomes load-bearing only if a future
   `MCPExecutor`/`HTTPExecutor` proxies to a separate process/service —
   not built yet, not this phase's scope.

## Known limitations

The structural regression guards are text-based source scans, not a
full AST/import-graph analysis — same heuristic, same documented
limitation, as Phase 8's and Phase 10's own guards.

## Unit test results

7 tests in `tests/test_citadel_execution_containment.py`:
`TestEveryExecutorValidatesTheSharedAuthorization` (1),
`TestCheckTargetFingerprintSingleCallSite` (1),
`TestInternalToolExecutorNeverFingerprintChecks` (1),
`TestSharedValidationHoldsIdenticallyOnBothExecutors` (4: replay and
action-mismatch, each proven on both executors independently). All
passing.

## Integration test results

The structural guards scan the actual shipped source tree. The
runtime tests call the real `InternalToolExecutor.execute()` and
`UpstreamMCPExecutor.execute()` — the same call shape
`governance/execution.py` and `governance/upstream_executor.py`'s own
production callers use, not a mock of either executor.

## Property test results

None new this phase — same judgment as Phase 8/10: these are
architectural invariants better suited to example-based/structural
tests than property-based generation.

## Fuzz results

Not run.

## Adversarial test results

`test_replay_is_refused_on_upstream_executor` is the most notable: it
proves replay protection holds even *after* a downstream failure (the
fake HTTP factory raises mid-execution, after the authorization is
already marked consumed) — a second call still hits
`AuthorizationAlreadyConsumedError`, not the same downstream failure
again, confirming the `consumed` flag is set before the network
attempt, not after a successful one.

## Regression results

Full suite: **3121 passed, 1 skipped, 0 failed**, 129.79s
(`/tmp/full_run_phase11.log`).

## Static analysis

`ruff check`/`ruff format --check`: clean. `mypy src/responsibleai`
(CI's actual scope): clean — unaffected, no source file changed.
`mypy` run manually against the new test file surfaces two
`arg-type` findings on the fake registry fixture; confirmed this is a
pre-existing, accepted pattern already present in
`tests/test_upstream_gateway.py` and `tests/test_tool_trust.py` (both
already-passing, established test files) — CI's mypy step scopes only
`src/responsibleai`, never `tests/`, so this is consistent with
existing convention, not a new gap introduced here.

## Dependency audit

No new dependency.

## Secret scan

No secrets introduced.

## Supply-chain results

Not re-run this phase.

## Performance results

Not applicable.

## Backward-compatibility result

Fully backward compatible — test-only addition, zero source file
changed.

## Migration result

Not applicable.

## Rollback procedure

Delete `tests/test_citadel_execution_containment.py`. Nothing else to
revert.

## Documentation updated

`docs/enterprise-neural/11_PHASE11_DESIGN.md`, this report,
`PROGRESS_LEDGER.md`, `CHANGELOG.md`.

## Claims now supported by evidence

"Every concrete `Executor` implementation in this codebase validates
an `ExecutionAuthorization` through the same shared, audited
`_validate_authorization()` function — with target-fingerprint drift
detection scoped to exactly the executor that resolves external
targets — and both known executors refuse a stale, forged, or replayed
authorization identically" — true, evidenced by the tests above, run
against the real executor implementations, not fixtures.

## Claims still unsupported

"The self-hosted stdio transport is governed" — false, pre-existing,
same gap as Phase 8/10, named here again for completeness.
"`ExecutionAuthorization` is cryptographically signed" — false, by
deliberate design, documented in `execution.py`'s own module
docstring; correct as long as it never crosses a process boundary.

## Errors found and fixed this phase

None — the audit confirmed the properties already held; no bug found
in shipped code.

## Residual risks

The two named gaps (stdio transport ungoverned, unsigned
authorization) remain open, correctly out of this phase's scope but
not silently forgotten — tracked here and in the ledger.

## Next-phase dependencies

Phase 12 (Platform + Network + Service Isolation) is next. Given the
pattern across Phases 8, 10, and 11, an audit-first pass is again
warranted before assuming net-new scope — `THREAT_MODEL.md`'s stated
gaps (application-layer message signing for the MCP transport,
per-connection SSE DoS protection) and `00_PHASE0_AUDIT.md`'s KMS/HSM
finding are plausible existing starting points for what "Platform +
Network + Service Isolation" already partially covers versus what's
genuinely unbuilt.
