# Performance Benchmarks

Last run: 2026-08-11 · Platform version: 1.2.0

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
| `GuardrailsEngine.scan` (clean text, ~60 chars) | 2000 | 0.0164 | 0.0162 | 0.0165 | 0.0231 | 60,204 |
| `GuardrailsEngine.scan` (text with 3 PII matches) | 2000 | 0.0257 | 0.0252 | 0.0260 | 0.0344 | 38,770 |
| `TrustScoreEngine.compute` (6 dimensions) | 5000 | 0.0040 | 0.0040 | 0.0041 | 0.0044 | 241,563 |
| `WhitePactRuntimeGateway.evaluate` (LOW-risk, allowed, clean text) | 2000 | 0.0184 | 0.0182 | 0.0185 | 0.0252 | 54,054 |
| `WhitePactRuntimeGateway.evaluate` (LOW-risk, PII redaction path) | 2000 | 0.0279 | 0.0275 | 0.0282 | 0.0360 | 35,664 |
| `WhitePactRuntimeGateway.evaluate` (authority DENY, short-circuit) | 2000 | 0.0009 | 0.0009 | 0.0010 | 0.0010 | 990,549 |
| MCP `TOOL_DEFS` linear lookup by name (27 tools) | 5000 | 0.0013 | 0.0013 | 0.0013 | 0.0015 | 701,107 |

## Reading these numbers

- **The gateway itself adds very little overhead over the guardrails scan it
  wraps** — `evaluate()` on the clean-text path (0.0184ms) is close to
  `GuardrailsEngine.scan` alone (0.0164ms); the risk classification and
  authority checks are effectively free by comparison (confirmed separately
  by the DENY short-circuit row, which returns before ever touching
  guardrails and is ~20x faster).
- **PII redaction roughly doubles the guardrails cost** for the specific
  3-match test string used here (regex matching cost scales with the number
  of pattern matches, not a fixed overhead) — expect this to vary with input
  length and match density, not to be a fixed multiplier.
- **The authority-DENY short-circuit is ~1M ops/sec** because it returns
  before running any content scan — this is the deliberately cheap path
  `SPEC.md` Section 9 requires: a denied action should never pay the cost of
  a full evaluation.
- **`TrustScoreEngine.compute` is pure arithmetic** (weighted sum over 6
  caller-supplied floats) — its cost is negligible relative to anything that
  does string scanning, which is expected and not a target for optimization.

## What this does not measure

Stated honestly, so these numbers aren't mistaken for more than they are:

- **No concurrency/load test.** All runs are single-threaded, sequential
  calls. Real throughput under concurrent requests (the dashboard's actual
  deployment shape, per `helm/rai-governance/`) depends on Python's GIL,
  ASGI worker count, and database contention — none of which this
  microbenchmark exercises.
- **No database-backed paths benchmarked.** `EvidenceRepository.append()`,
  `ApprovalRepository` resolution, and any REST endpoint that touches
  SQLite/PostgreSQL are not included here — those numbers are dominated by
  I/O and connection-pool behavior, not the in-memory logic benchmarked
  above, and would need a separate, DB-backed benchmark harness (with a
  stated DB backend and hardware) to be meaningful.
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
