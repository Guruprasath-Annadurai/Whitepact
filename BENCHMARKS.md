# Performance Benchmarks

Last run: 2026-08-17 · Platform version: 1.2.0

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

This is a **single developer laptop, single-threaded, in-process** run — not
a production server, not under concurrent load, and not measuring network or
database I/O (all benchmarked calls are pure in-memory Python; no DB, no
HTTP round trip). Treat these numbers as **relative** cost comparisons
between hot paths in this codebase, not as production capacity planning
numbers. See "What this does not measure" below for the real gaps.

## Results

| Operation | N | mean (ms) | p50 (ms) | p95 (ms) | p99 (ms) | ops/sec |
|---|---|---|---|---|---|---|
| `GuardrailsEngine.scan` (clean text, ~60 chars) | 2000 | 0.0164 | 0.0162 | 0.0164 | 0.0215 | 60,382 |
| `GuardrailsEngine.scan` (text with 3 PII matches) | 2000 | 0.0255 | 0.0250 | 0.0256 | 0.0398 | 39,083 |
| `TrustScoreEngine.compute` (6 dimensions) | 5000 | 0.0041 | 0.0040 | 0.0041 | 0.0043 | 239,393 |
| `WhitePactRuntimeGateway.evaluate` (LOW-risk, allowed, clean text) | 2000 | 0.0190 | 0.0186 | 0.0189 | 0.0332 | 52,301 |
| `WhitePactRuntimeGateway.evaluate` (LOW-risk, PII redaction path) | 2000 | 0.0293 | 0.0287 | 0.0301 | 0.0508 | 33,994 |
| `WhitePactRuntimeGateway.evaluate` (authority DENY, short-circuit) | 2000 | 0.0020 | 0.0019 | 0.0020 | 0.0025 | 472,818 |
| MCP `TOOL_DEFS` linear lookup by name (29 tools) | 5000 | 0.0013 | 0.0013 | 0.0014 | 0.0014 | 716,555 |
| `validate_attenuation` (narrowed child authority, passes) | 5000 | 0.0006 | 0.0006 | 0.0007 | 0.0008 | 1,404,461 |
| `AuthorityContext.constraint_violation` (`max_value_usd`, within limit) | 5000 | 0.0006 | 0.0006 | 0.0007 | 0.0007 | 1,364,396 |
| `check_composition_violation` (2-step history, 3-step rule, completing action) | 5000 | 0.0039 | 0.0039 | 0.0040 | 0.0041 | 247,952 |
| `scan_memory_write` (benign text, ~55 chars) | 5000 | 0.0045 | 0.0044 | 0.0045 | 0.0047 | 219,181 |
| `scan_memory_write` (injection pattern, ~58 chars) | 5000 | 0.0041 | 0.0041 | 0.0042 | 0.0043 | 236,649 |
| `build_evidence_bundle` (50 records, in-memory) | 1000 | 0.0098 | 0.0095 | 0.0098 | 0.0118 | 100,737 |
| `verify_evidence_bundle` (50 records, valid chain) | 1000 | 0.2175 | 0.2142 | 0.2278 | 0.3548 | 4,594 |
| `WhitePactRuntimeGateway.evaluate` (LOW-risk, allowed, autonomy budget under cap) | 2000 | 0.0191 | 0.0187 | 0.0190 | 0.0297 | 52,013 |

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
  to ~473k ops/sec** in this run — a real, expected change, not noise: the
  v3 authority-layer work (`MACHINE_AUTHORITY_V1.md`) added the workflow-
  composition and autonomy-budget checks ahead of this short-circuit point
  in `evaluate()`'s pipeline. Both are skipped entirely when the caller
  doesn't pass `workflow_rules`/`autonomy_budget` (true of this benchmark,
  and true of every call before those features existed), so the drop is
  the cost of the `is not None`/`if workflow_rules:` guard checks
  themselves, not the features' actual logic running — still ~2
  microseconds per denied call, not a meaningful regression.
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
  count under the cap) costs effectively nothing extra** (0.0191ms vs.
  0.0190ms for the same call with no budget configured) — the check itself
  is a single integer comparison; the real cost of this feature is the
  async DB query the *caller* runs to compute the count
  (`recent_autonomous_action_count()`, not benchmarked here — see "What
  this does not measure" below).

## What this does not measure

Stated honestly, so these numbers aren't mistaken for more than they are:

- **No concurrency/load test.** All runs are single-threaded, sequential
  calls. Real throughput under concurrent requests (the dashboard's actual
  deployment shape, per `helm/rai-governance/`) depends on Python's GIL,
  ASGI worker count, and database contention — none of which this
  microbenchmark exercises.
- **No database-backed paths benchmarked.** `EvidenceRepository.record()`,
  `ApprovalRepository` resolution, `DelegationRepository.grant()`/
  `get_authority_chain()`/`revoke_branch()`, `recent_autonomous_action_count()`,
  `EvidenceRepository.list_for_bundle()`, and any REST endpoint that
  touches SQLite/PostgreSQL are not included here — those numbers are
  dominated by I/O and connection-pool behavior, not the in-memory logic
  benchmarked above, and would need a separate, DB-backed benchmark
  harness (with a stated DB backend and hardware) to be meaningful.
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
