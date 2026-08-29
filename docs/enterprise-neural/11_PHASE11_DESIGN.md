# Phase 11 — Citadel Execution Containment: Design

## Objective

Per the master directive's Phase 11 ("Citadel Execution Containment")
and `00_PHASE0_AUDIT.md` §4's finding: "Execution-permit binding
(short-lived, single-use, action-hash-bound) — **Partially
implemented** for MCP-mediated tool calls via `ExecutionAuthorization`
(digest, expiry, single-consumption) — not yet a general Citadel-style
containment boundary." Per directive rule 63 ("inspect before
implementing... do not rebuild systems merely to satisfy this
prompt") and §6's own instruction: "§18 (Citadel containment)
describe[s] layers that partially exist (`WhitePactRuntimeGateway`,
`InternalToolExecutor`) under different names — reuse them, do not
rename or reimplement." Audit first.

## Audit: the Phase 0 finding is now stale — the gap has substantially closed

Since Phase 0's audit was written, "Authority Everywhere" work
(Execution Permit v2, JIT Credential Broker) generalized
`ExecutionAuthorization` well beyond MCP-mediated internal tool calls:

- **`governance/execution.py`** — `ExecutionAuthorization`
  (action-digest-bound, org-bound, expiry, single-use `consumed`
  flag), `authorize_execution()` (the only construction site, proven
  by Phase 8's regression guard), the `Executor` Protocol, and
  `_validate_authorization()` — the four shared checks (consumed,
  expired, org mismatch, action mismatch) every concrete executor must
  run first.
- **`governance/upstream_executor.py`** — `UpstreamMCPExecutor`, a
  second, real `Executor` implementation for calls proxied to
  third-party upstream MCP servers (not internal tools). Adds, beyond
  `InternalToolExecutor`:
  - **Target-fingerprint drift detection**
    (`check_target_fingerprint`/`AuthorizationTargetDriftError`) — an
    authorization granted against one resolved server config (URL,
    enabled state, credential presence) is refused if that
    configuration drifted before execution, even though the
    `server_id::tool_name` target string itself is unchanged.
  - **JIT Credential Broker** (`governance/jit_credential.py`) — a
    single-use, time-boxed credential minted per-authorization, issued
    only against a still-valid authorization, consumed exactly once.
  - **DNS re-validation immediately before dispatch**, not only at
    registration time.
- Both executors are extensively tested: `tests/test_executor_bypass_invariant.py`
  (9 tests, `InternalToolExecutor`), `tests/test_upstream_gateway.py`
  (mismatched/expired/wrong-org/forged/unregistered/disabled/replay —
  `UpstreamMCPExecutor`), `tests/test_tool_trust.py`'s
  `TestExecutionPermitV2FingerprintDrift` (URL swap, credential swap,
  and the negative/unchanged case — proven through the real
  `UpstreamMCPExecutor.execute()`, not the standalone function),
  `tests/test_jit_credential.py` (17 tests).

**This is, in substance, already a general Citadel-style containment
boundary** — permit binding, single-use replay protection,
org-scoping, target-drift detection, and narrowly-scoped just-in-time
credentials, covering both execution surfaces this platform actually
has (internal tools, upstream MCP proxying).

## Verified via source-text scan (same heuristic as Phase 8/10's guards)

- `_validate_authorization(` has exactly two call sites:
  `execution.py:270` (inside `InternalToolExecutor.execute()`) and
  `upstream_executor.py:180` (inside `UpstreamMCPExecutor.execute()`)
  — the two, and only two, concrete `Executor` implementations in the
  codebase. No executor skips the shared four-check validation.
- `check_target_fingerprint(` has exactly one call site
  (`upstream_executor.py`) — `InternalToolExecutor` correctly never
  calls it, since internal tools have no external target to resolve
  (`target_fingerprint=None` by construction).
- `dispatch_tool(` has **two** real call sites, not one:
  `governance/execution.py:277` (inside the gated
  `InternalToolExecutor.execute()`) and `mcp/server.py:244`. The
  second is **not a bypass** — read in context, it only executes when
  `governance is None` (no hosted governance context populated for
  this call, e.g. the self-hosted stdio transport, or
  `mcp_governance_enabled=False`); when governance *is* active, the
  function returns via `apply_governance()`'s result before ever
  reaching that line, with an explicit comment and `assert` guarding
  exactly this. This is the same, already-documented gap named in
  Phase 8 (Gap 1) and Phase 10 (Gap 2): the stdio transport has no
  organizational identity to build a governance decision against in
  the first place. Confirmed again here, not silently missed.

## Genuine, narrowly-scoped gap this phase closes

Neither of the two structural properties above (single validator
call-set across all executors; single fingerprint-check call site) was
previously a regression-tested guarantee — only true by inspection.
Phase 8's own guard covered `ExecutionAuthorization`'s single
*construction* site, not that every executor consuming one actually
*validates* it through the shared function. A future executor
(`MCPExecutor`/`HTTPExecutor`, named as not-yet-built in
`execution.py`'s own docstring) could be added without calling
`_validate_authorization()` — reimplementing the four checks by hand,
incorrectly, exactly the risk `Executor`'s own docstring warns about —
and nothing today would catch that in CI.

## Scope for this phase

New file: `tests/test_citadel_execution_containment.py`:

1. Structural guard: every concrete `Executor` implementation
   (`InternalToolExecutor`, `UpstreamMCPExecutor` — the known set,
   updated deliberately if a third is ever added) calls
   `_validate_authorization()` in its own defining file.
2. Structural guard: `_validate_authorization()` has no call site
   outside those two files.
3. Structural guard: `check_target_fingerprint()` has exactly one call
   site (`upstream_executor.py`).
4. Runtime: a fresh `ExecutionAuthorization` with no
   `target_fingerprint` never raises `AuthorizationTargetDriftError`
   through `InternalToolExecutor` (the "internal tools have nothing to
   resolve" property, exercised end-to-end rather than only unit-level
   as `test_tool_trust.py`'s existing test does for `authorize_execution()`
   alone).
5. Runtime adversarial: a stale/forged authorization presented to
   *either* executor is refused before any side effect — parametrized
   across both `InternalToolExecutor` and `UpstreamMCPExecutor` for
   the shared `_validate_authorization` properties, proving the same
   guarantee holds identically on both surfaces rather than assuming
   it transfers from one executor's tests to the other's.

No source file changes. No new architecture. No database migration.
