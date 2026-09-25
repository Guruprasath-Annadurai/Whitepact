# WhitePact Formula — Trace Semantics v0.1

## Execution trace

`π = (W₀, e₁, W₁, …, eₙ, Wₙ)` implemented as `FormulaTrace` + `FormulaTraceEvent`.

## Predicates

| Predicate | Meaning |
|-----------|---------|
| `TraceAuthorized(π)` | Every event id ∈ authorized witness set |
| `TraceAdmissible(π)` | Every event id ∈ admissible witness set |
| `TraceCapabilityReach(π)` | Resources touched along π |

## State vs path

| Construction | Meaning |
|--------------|---------|
| `exists_authorized_path` | ∃ trace to state with all events authorized |
| `all_paths_authorized` | ∀ modeled traces to state, all authorized |

**These differ** — see `tests/formula/test_gate2_graph_trace.py`.

Nested `𝒲_auth` in Gate 1 maps to **exists-authorized-path projection** for state labels, not all-paths, unless explicitly qualified.
