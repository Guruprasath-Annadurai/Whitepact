# WhitePact Heart — Performance Baseline (Phase H16)

> First-ever latency/throughput measurements for the Heart's hot
> paths. These are **baseline measurements on one development
> machine**, not a tuned SLA and not representative of production
> load characteristics (no network I/O, no database, no concurrency
> modeling — the entire Heart, as of H0-H15, is pure, synchronous,
> in-memory Python). Treat every number below as "this is roughly
> what it costs today, on this machine" — a starting point for
> noticing regressions, not a guarantee.

## Methodology

All measurements: `time.perf_counter()` around a tight loop of N
repeated calls, wall-clock elapsed / N. Single-threaded, no warmup
period excluded (Python's CPython interpreter has no JIT to warm up).
Measured on the machine this phase was written on; `tests/test_heart_performance.py`
encodes generous (10-100x baseline) bounds around these numbers as
regression guards, not as reproductions of the exact baseline —
different hardware will show different absolute numbers, and that's
expected and fine.

## Baseline measurements

| Operation | Scenario | Latency | Throughput |
|---|---|---|---|
| `sovereignty_kernel.evaluate()` (H13) | Full legitimate chain (root + consent + purpose + delegation) | ~17.3us/call | ~57,900 calls/sec |
| `sovereignty_kernel.evaluate()` (H13) | Empty input (no root/consent/etc supplied) | ~12.4us/call | ~80,600 calls/sec |
| `root_authority.validate_root_chain()` (H3) | 32-hop chain walk (the maximum before `CHAIN_TOO_DEEP`) | ~16.6us/call | ~60,100 calls/sec |
| `non_delegable_authority.check_non_delegable_authority()` (H7) | 1000 action types, no match (worst case — full scan) | ~4,350us/call (4.35ms) | ~230 calls/sec |
| `non_delegable_authority.check_non_delegable_authority()` (H7) | 1000 action types, match found early in sorted order | sub-millisecond | N/A (single-call measurement) |

## What these numbers mean

**`evaluate()` and `validate_root_chain()` are fast and roughly
constant-cost** for realistic inputs — a full Heart decision (all four
of H3-H6's checks) costs about the same as an empty one, since the
dominant cost is Python function-call and object-construction
overhead, not any of the actual comparison logic (which is all simple
field comparisons, set operations, or short string comparisons). At
~58,000 calls/sec single-threaded, this layer would not be a
bottleneck for any plausible request rate a single governance-decision
service would see, if wired into a live path.

**`check_non_delegable_authority()` is the one operation with a real,
documented scaling characteristic worth knowing about** — it is
O(`action_types` × `registry size`) in the worst case (no match found,
every action type checked against every one of the fixed registry's 7
patterns). At the registry's current fixed size, this only becomes
noticeable with unusually large `action_types` sets (the 1000-entry
case above, ~230 calls/sec, is roughly 250x slower than `evaluate()`
itself). This is **not a bug** — the registry is deliberately small
and fixed (H7's own design), and no code path anywhere in this
codebase currently constructs `action_types` sets anywhere near 1000
entries; a realistic `DelegationRecord.granted_action_types` is a
handful of specific permissions, not hundreds. Flagged here so a
future caller passing an unusually large action-type set (e.g. "all
actions this org has ever defined," a plausible but not currently
implemented use case) knows what to expect, rather than discovering it
as a surprise.

## What Phase H16 explicitly does not measure

- **Concurrent/multi-threaded throughput.** Every measurement above is
  single-threaded. The Heart's pure functions have no shared mutable
  state (every H3-H12 record type is a frozen dataclass), so they are
  almost certainly safe to call concurrently from multiple threads
  without contention — but this phase does not measure or prove that
  claim under real concurrent load, since nothing currently calls the
  Heart from a multi-threaded context.
- **Any live-path latency.** No database, network call, or real
  `RootResolver` implementation exists yet — every measurement above
  exercises the Heart's pure orchestration logic only, given
  already-in-memory domain objects. A real deployment resolving a root
  chain from a database would have a completely different (and almost
  certainly dominant) latency profile driven by that I/O, not by
  anything measured in this phase.
- **Memory usage.** Not profiled in this phase; every Heart record
  type is a small, frozen dataclass, unlikely to be a meaningful
  memory concern at any plausible scale, but this is an assumption,
  not a measurement.
