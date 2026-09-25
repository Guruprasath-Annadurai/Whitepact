# WhitePact Formula — Gate 2 System Model

**FormulaVersion:** 0.1.0  
**Package:** `responsibleai.formula`

Gate 2 implements the canonical in-memory domain library: graph snapshots, grant algebra, traces, fences, and invariant checking. No API, MCP, DB, or judgment engines.

## Typed transitions (Gate 1 P1 resolved)

Separate protocols in `transitions.py` — no unified `τ : 𝒲 × Act → 𝒫(𝒲)` implementation:

| Type | Signature role |
|------|----------------|
| `DeterministicTransition` | `W × Act → W` |
| `NondeterministicTransition` | `W × Act → frozenset[W]` |
| `ProbabilisticTransition` | `W × Act → ProbabilityMass[W]` |
| `AbstractTransition` | abstract domains |
| `CapabilityTransition` | capability evolution |
| `AuthorityTransition` | grant-store evolution |

## Canonical graph

`CanonicalAISystemGraph` → immutable `GraphSnapshot` with `content_hash`.

## Authority

`EffectiveAuthorityEvaluator`: **union** of applicable grants → **ceiling restriction** → **explicit deny subtraction**.

## Trace vs state

- `TraceAuthorized(π)` — every event has witness id  
- `StatePathSemantics.exists_authorized_path` vs `all_paths_authorized` — **not equivalent** (see tests)

## Commit fence

`EvaluationPin` + `CommitFence` — authority/graph version must match at commit.
