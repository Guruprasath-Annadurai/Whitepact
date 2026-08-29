# Security Remediation Gap 7 — ExecutionAuthorization Trust-Boundary: Report

STATUS: **VERIFIED, then hardened with a regression guard.** The
hypothesis ("`ExecutionAuthorization` never crosses a process
boundary") was treated as a hypothesis, not a given, and searched
exhaustively — re-confirmed on this remediation branch, independent of
`CODEX_REVIEW_HANDOFF.md`'s earlier finding.

## Search performed

Exhaustive search across `src/responsibleai/` for any of: HTTP client
calls, queues, background workers, Celery, serialization (`json.dumps`,
`pickle`), IPC, subprocess, message buses, Redis, caches, or event
systems, in any file that references `ExecutionAuthorization`.

**Files referencing `ExecutionAuthorization`** (10 total):
`mcp/server.py`, `mcp/governance_integration.py`,
`governance/jit_credential.py`, `governance/execution.py`,
`governance/reconciliation.py`, `governance/upstream_executor.py`,
`governance/attestation.py`, `governance/__init__.py`,
`governance/legitimacy_envelope.py`, `governance/authority_grant.py`.

**Result**: `ExecutionAuthorization` (the class definition,
`governance/execution.py`) has no `to_dict`/`asdict`/`__reduce__`
method, and no serialization call (`json.dumps`, `pickle.dumps`) or
boundary-crossing primitive (queue, Celery task, Redis, message bus)
appears in any of the 10 files above. The three real call sites of
`authorize_execution()` — `mcp/upstream_dispatch.py` and two in
`mcp/governance_integration.py` — each construct the object and pass
it directly to `executor.execute(authorization, action)` within the
same `async def`, same call stack.

**Conclusion**: the hypothesis holds by exhaustive search, not
assumption. This is executable evidence, not a promise.

## The regression guard added

The directive's own conditional logic applies precisely: *"If it
truly remains process-local, add a regression/invariant check
preventing future accidental serialization or boundary crossing."*
`ExecutionAuthorization` is a plain dataclass — Python's standard
`pickle` protocol can serialize *any* object with picklable fields by
default, dataclass or not, whether or not anyone has written code that
does so today. "No one currently serializes it" is a fact about
current call sites, not a structural guarantee — exactly the kind of
gap a regression test should close, since a future contributor adding
a queue/worker/cache call site involving this class would not
otherwise be flagged.

`tests/test_execution_authorization_boundary_invariant.py`:

1. **Call-site enumeration guard**: `authorize_execution()` has
   exactly the three known, audited call sites. A fourth call site
   appearing anywhere — including a queue/worker/Celery task file —
   fails the test, forcing deliberate review rather than silent
   expansion.
2. **No-serialization-primitive-nearby guard**: none of the (up to
   date, dynamically enumerated, not hardcoded) files that reference
   `ExecutionAuthorization` also contain a boundary-crossing primitive
   (`pickle.`, `json.dumps`, `redis.`, `celery`, `Queue(`,
   `multiprocessing`, `subprocess.`, an outbound HTTP call). A future
   PR that adds, say, `redis_client.set(key, authorization)` to
   `jit_credential.py` would fail this test immediately.
3. **Structural class-shape guard**: `ExecutionAuthorization` has no
   `to_dict`/`asdict`-style method and no custom `__reduce__` —
   proving nothing has *added* serialization support since this
   review, which would itself be a signal the process-local assumption
   is being reconsidered and needs fresh review.

No source code changed — this gap closes with verification and a
regression guard, not a fix, because nothing was found broken.
