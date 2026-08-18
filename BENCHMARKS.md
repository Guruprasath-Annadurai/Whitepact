# Performance Benchmarks

Last run: 2026-08-18 · Platform version: 1.2.3

Every number below came from an actual execution of
[`scripts/run_benchmarks.py`](scripts/run_benchmarks.py) in this repository
— not an estimate, not a theoretical calculation. Re-run the script and
paste its output here if you change any of the benchmarked code paths; a
stale number is worse than no number.

## Environment

```
Python: 3.14.6
Platform: macOS-26.5.2-arm64-arm-64bit-Mach-O
```

This is a **single developer laptop, single-threaded, in-process** run.
Every row except the last is pure in-memory Python (no DB, no HTTP round
trip) and not under concurrent load. The last row is the one exception —
a real SQLite-in-memory DB write — added this pass specifically to start
filling the gap the rest of this document is honest about below. Treat
all of these numbers as **relative** cost comparisons between hot paths
in this codebase, not as production capacity planning numbers. See "What
this does not measure" below for the real gaps that remain.

## Results

| Operation | N | mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | ops/sec |
|---|---|---|---|---|---|---|
| `GuardrailsEngine.scan` (clean text, ~60 chars) | 2000 | 0.0164 | 0.0160 | 0.0166 | 0.0268 | 60,252 |
| `GuardrailsEngine.scan` (text with 3 PII matches) | 2000 | 0.0257 | 0.0252 | 0.0260 | 0.0404 | 38,653 |
| `TrustScoreEngine.compute` (6 dimensions) | 5000 | 0.0041 | 0.0041 | 0.0042 | 0.0044 | 235,567 |
| `WhitePactRuntimeGateway.evaluate` (LOW-risk, allowed, clean text) | 2000 | 0.0195 | 0.0191 | 0.0199 | 0.0283 | 50,987 |
| `WhitePactRuntimeGateway.evaluate` (LOW-risk, PII redaction path) | 2000 | 0.0296 | 0.0292 | 0.0308 | 0.0395 | 33,686 |
| `WhitePactRuntimeGateway.evaluate` (authority DENY, short-circuit) | 2000 | 0.0019 | 0.0018 | 0.0020 | 0.0021 | 493,893 |
| MCP `TOOL_DEFS` linear lookup by name (29 tools) | 5000 | 0.0013 | 0.0013 | 0.0013 | 0.0014 | 716,191 |
| `validate_attenuation` (narrowed child authority, passes) | 5000 | 0.0006 | 0.0006 | 0.0006 | 0.0007 | 1,459,393 |
| `AuthorityContext.constraint_violation` (`max_value_usd`, within limit) | 5000 | 0.0006 | 0.0006 | 0.0007 | 0.0007 | 1,375,942 |
| `check_composition_violation` (2-step history, 3-step rule, completing action) | 5000 | 0.0038 | 0.0038 | 0.0040 | 0.0042 | 253,020 |
| `scan_memory_write` (benign text, ~55 chars) | 5000 | 0.0043 | 0.0043 | 0.0044 | 0.0045 | 226,461 |
| `scan_memory_write` (injection pattern, ~58 chars) | 5000 | 0.0040 | 0.0040 | 0.0041 | 0.0043 | 242,588 |
| `build_evidence_bundle` (50 records, in-memory) | 1000 | 0.0095 | 0.0093 | 0.0096 | 0.0132 | 103,900 |
| `verify_evidence_bundle` (50 records, valid chain) | 1000 | 0.2136 | 0.2118 | 0.2255 | 0.2550 | 4,677 |
| `WhitePactRuntimeGateway.evaluate` (LOW-risk, allowed, autonomy budget under cap) | 2000 | 0.0190 | 0.0187 | 0.0191 | 0.0215 | 52,348 |
| `AuditRepository.write` (SQLite in-memory, hash-chained insert) | 500 | 0.5286 | 0.5210 | 0.5866 | 0.6359 | 1,891 |

## Reading these numbers

- **The gateway itself adds very little overhead over the guardrails scan it
  wraps** — `evaluate()` on the clean-text path (0.0190ms) is close to
  `GuardrailsEngine.scan` alone (0.0164ms); the risk classification and
  authority checks are effectively free by comparison (confirmed separately
  by the DENY short-circuit row, which returns before ever touching
  guardrails and is still ~10x faster than the full evaluate path).
- **PII redaction roughly doubles the guardrails cost** for the specific
  3-match test string used here (regex matching cost scales with the number
  of pattern matches, not a fixed overhead) — expect this to vary with input
  length and match density, not to be a fixed multiplier.
- **The authority-DENY short-circuit dropped from ~990k ops/sec (2026-08-11)
  to ~494k ops/sec** in this run — a real, expected change, not noise: the
  v3 authority-layer work (`MACHINE_AUTHORITY_V1.md`) added the workflow-
  composition and autonomy-budget checks ahead of this short-circuit point
  in `evaluate()`'s pipeline. Both are skipped entirely when the caller
  doesn't pass `workflow_rules`/`autonomy_budget` (true of this benchmark,
  and true of every call before those features existed), so the drop is
  the cost of the `is not None`/`if workflow_rules:` guard checks
  themselves, not the features' actual logic running — still ~2
  microseconds per denied call, not a meaningful regression.
- **`MCP TOOL_DEFS` lookup by name benchmarks a hypothetical linear scan,
  not how the server actually dispatches a call** — worth clarifying,
  since the row's name could be misread as a real bottleneck.
  `mcp/tools.py`'s `dispatch_tool()` already resolves a tool name via a
  dict (`_TOOL_HANDLERS`), O(1), not a scan over `TOOL_DEFS`. That dict
  used to be rebuilt fresh on every single call (~29 entries allocated
  per tool invocation for no reason, since the mapping never changes at
  runtime); this pass hoisted it to a module-level constant built once at
  import time instead — a small, real, zero-risk fix found while
  auditing this benchmark suite for anything actually worth optimizing.
- **`TrustScoreEngine.compute` is pure arithmetic** (weighted sum over 6
  caller-supplied floats) — its cost is negligible relative to anything that
  does string scanning, which is expected and not a target for optimization.
- **The v3 authority-layer primitives are all sub-microsecond-to-low-
  microsecond, pure-Python operations** — `validate_attenuation()` and
  `constraint_violation()` are simple dict/set comparisons (~0.0006ms,
  1.3-1.4M ops/sec); `check_composition_violation()` and
  `scan_memory_write()` (~0.004-0.005ms) cost roughly the same as one
  `GuardrailsEngine.scan()` call, expected since both are doing comparable
  work (subsequence matching over a short list; regex matching over a short
  string). None of these are a meaningful addition to the gateway's overall
  per-call cost.
- **`build_evidence_bundle()` is cheap (~0.01ms for 50 records) —
  `verify_evidence_bundle()` is not (~0.22ms for the same 50 records, ~22x
  slower).** This is expected and correctly attributable: building a bundle
  just packages already-computed hashes; verifying one recomputes every
  record's sha256 from scratch plus the bundle-level digest — real
  cryptographic work, not overhead to optimize away. At ~4,600 verifications/
  sec for 50-record bundles, this is not a hot path (an auditor verifying a
  downloaded export, not a per-request operation) and no optimization is
  planned.
- **Wiring the Autonomy Budget into `evaluate()` (with a real policy and a
  count under the cap) costs effectively nothing extra** (0.0190ms vs.
  0.0195ms for the same call with no budget configured, within this run's
  noise floor) — the check itself is a single integer comparison; the
  real cost of this feature is the async DB query the *caller* runs to
  compute the count (`recent_autonomous_action_count()`, still not
  benchmarked directly — see "What this does not measure" below).
- **`AuditRepository.write()` (~0.53ms, ~1,900 ops/sec on SQLite
  in-memory) is roughly 20-30x the cost of the in-memory logic it sits
  alongside** — every one of the pure-Python operations above completes
  in well under 0.03ms; the single DB insert this method performs (a
  hash-chain compute plus one row write, serialized behind an
  `asyncio.Lock` for chain-ordering correctness) dominates. This is the
  first real, if partial, confirmation of what "What this does not
  measure" already said honestly: request latency in production is
  governed by I/O, not by the guardrails/authority/trust logic this
  document mostly benchmarks. SQLite-in-memory is also the *cheapest*
  possible case — no disk I/O, no network, no connection pool contention
  — so treat this number as a floor, not a representative production
  figure; the live deployment's actual Postgres-over-network latency for
  the same write is not measured here.

## What this does not measure

Stated honestly, so these numbers aren't mistaken for more than they are:

- **No concurrency/load test.** All runs are single-threaded, sequential
  calls. Real throughput under concurrent requests (the dashboard's actual
  deployment shape, per `helm/rai-governance/`) depends on Python's GIL,
  ASGI worker count, and database contention — none of which this
  microbenchmark exercises.
- **Only one database-backed path is benchmarked so far**
  (`AuditRepository.write()`, above, added this pass), and only against
  SQLite-in-memory, the cheapest case — no disk I/O, no network, no
  connection-pool contention. `EvidenceRepository.record()`,
  `ApprovalRepository` resolution, `DelegationRepository.grant()`/
  `get_authority_chain()`/`revoke_branch()`, `recent_autonomous_action_count()`,
  `EvidenceRepository.list_for_bundle()`, and any REST endpoint that
  touches a real (non-in-memory) SQLite file or PostgreSQL are still not
  included — those numbers are dominated by I/O and connection-pool
  behavior in a way this single addition doesn't capture, and would need
  a broader benchmark harness against a stated real DB backend and
  hardware to be meaningful for production capacity planning.
- **No network-backed paths benchmarked.** `TrustClient.check()`/
  `check_async()` (Continuous MCP Trust's live re-fetch on a cache miss)
  and `A2ATrustGate.check()`/`check_async()` (which calls the same client
  for the remote agent's trust score) both make a real HTTP call in the
  uncached case — their latency is dominated by that round trip, not local
  computation, and is out of scope for this in-process harness the same
  way the hallucination/bias-probe LLM calls below already are.
- **No MCP transport-level benchmark.** The `TOOL_DEFS` lookup above is a
  Python-level micro-benchmark of the dispatch table, not an end-to-end
  measurement of a tool call over stdio, Streamable HTTP, or SSE — those
  numbers would include serialization, transport, and (for HTTP) auth
  overhead not present here.
- **No hallucination/bias-probe benchmarks.** `HallucinationDetector` and
  BiasBuster's probes typically call out to an LLM provider in real usage;
  their latency is dominated by that network call, not local computation —
  benchmarking them meaningfully requires a fixed provider/model choice and
  is out of scope for a "local, in-process" benchmark run.
- **Single machine, single run.** No statistical comparison across hardware,
  no CI-integrated regression tracking yet. If perf regression detection
  becomes a real need, that's a follow-up, not something claimed here.

## Re-running

```bash
source .venv/bin/activate
python3 scripts/run_benchmarks.py
```
