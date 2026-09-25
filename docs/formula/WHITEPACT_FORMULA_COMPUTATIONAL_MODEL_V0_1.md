# WhitePact Formula — Computational Model v0.1

Analysis of tractability, bounds, and honesty labels for incomplete computation.

---

## Symbolic bounds (configurable, not production constants)

| Parameter | Role |
|-----------|------|
| `H_max` | Maximum future horizon |
| `N_nodes_max` | Graph nodes expanded per evaluation |
| `N_edges_max` | Edges traversed |
| `coalition_size_max` | Agents in coalition analysis |
| `search_branch_max` | Branching factor cap |
| `evaluation_deadline` | Wall-clock budget |
| `memory_budget` | Bytes for frontier |

**Rule:** If any bound exhausted → obligation or judgment includes **`INCOMPLETE`** or **`UNKNOWN`** — never silent completeness.

---

## Problem complexity sketch

| Problem | Typical complexity | v0.1 stance |
|---------|-------------------|-------------|
| Grant validity check (single grant) | O(1) DB | Deterministic correct |
| `Authorized(σ,α,ρ,ctx,t)` with k grants | O(k · match) | Polynomial |
| Grant intersection / difference | O(k²) tuples worst case | Polynomial in k |
| Delegation chain walk | O(depth) | Polynomial with depth cap |
| Capability one-hop expand | O(deg(v)) | Polynomial |
| Capability closure exact | O(|V|+|E|) | Polynomial if graph finite |
| Capability closure bounded | O(min(budget, |V|)) | May be incomplete |
| Graph reachability | O(|V|+|E|) | Polynomial |
| Multi-agent coalition closure | O(n · closure) | Exponential in n without cap |
| Future search `F_H` | O(branch^H) worst case | **Exponential** — must bound |
| Adversarial violation search | NP-hard in general graphs | Heuristic + bound |
| Min sufficient authority | Multi-objective optimization | Pareto; NP-hard reductions possible |
| Counterfactual compare | 2× single eval | 2× base cost |

**NP-hard candidates:** Finding worst-case violation path with minimal hops is graph homomorphism / reachability variant under rich labels — treat as **exponential in H** with explicit budget.

---

## Soundness / completeness language

| Analysis | Target property |
|----------|-----------------|
| Authority PO checks | **Soundness** (no false SATISFIED if store corrupt — requires trusted store) |
| Capability over-approx | **Conservative over-approximation** — may over-deny |
| Capability under-approx | **Best effort** — unsafe for sole deny |
| Future `F_H` default | **Conservative over-approx** for safety |
| Intent interpretation | **Advisory**, probabilistic |
| Trust UNKNOWN | **Sound** block on EXECUTE |

---

## DoS / complexity threats

Adversarial graphs maximizing branch factor → mitigated by `search_branch_max`, `evaluation_deadline`, tenant quotas (later implementation). Gate 1 **documents** risk; mitigation in Gate 2+.

---

## Parallelism

Independent PO checks parallelize. Future search is frontier-parallel with shared budget — implementation choice.

---

## Gate 1

No engines implemented: no `CapabilityClosureEngine`, `SafeFutureEnvelope`, `OmegaJudgmentEngine`.
