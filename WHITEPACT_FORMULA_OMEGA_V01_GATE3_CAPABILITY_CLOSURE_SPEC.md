# WhitePact Formula Ω∞ — Gate 3 Capability Closure Specification

**Formula version:** 0.1.0  
**Scope:** Bounded capability closure only (not authority, not future envelope, not judgment).

## 1. Mathematical closure

Given immutable `GraphSnapshot` \(G\), seed facts \(C_0\), typed rules \(R\), optional joint rules \(J\), and budget \(B\):

\[
F(C) = C \cup \text{DirectExtract}(G) \cup \bigcup_{r \in R} r(G, C) \cup \bigcup_{j \in J} j(C)
\]

\[
C^\* = \mu C.\, F(C) \text{ truncated by } B
\]

## 2. Semantic identity vs support

- **CapabilityFact** — semantic reachability only: `(tenant_id, actor.member_ids, action, target_node_id)`. Epistemic status on the fact is the **deterministic aggregate** across all witnesses (weakest-link merge of witness epistemics; order-independent).
- **CapabilityDerivation** — witness/support: rule id, prerequisites, graph node/edge ids, route, cumulative `derivation_depth`, per-witness epistemic status. Multiple distinct witnesses may support one semantic fact; duplicate fingerprints are deduplicated.

## 3. Cumulative derivation depth

Depth is derived from merged `route_node_ids` across prerequisite witnesses: `derivation_depth = len(route) - 1` (minimum 0). Composition merges routes at the junction node; depth never collapses to a shallow local tuple when the prerequisite chain is deep.

## 4. Direct extraction

Graph `CAN_*` edges emit `DIRECT_EXTRACTION` witnesses with edge id, source/target nodes, route, and epistemic weakest-link over **source node, edge, target node**. Seeds use rule `SEED` (distinct provenance).

## 5. Composition rules

| Rule | Premises (epistemic) |
|------|----------------------|
| `COMPOSE_VIA_CALL` | Outer call capability, inner capability, intermediary node |
| `MULTI_AGENT_RELAY` | Same with `AGENT` intermediary |
| `CREDENTIAL_UNLOCK` | Read capability, credential node, `REQUIRES` edge, target |
| `INFORMATION_REVEALS` | Read capability, source node, `REVEALS` edge, target |
| `JOINT_COALITION` | Explicit `JointCapabilityRule` prerequisites (no inference from coexistence) |

**Not** derived: `HAS_AUTHORITY`, `APPROVED_BY`, `DEPENDS_ON`, `TRUSTS`, generic transitivity.

## 6. Relay vs coalition

- **Relay:** single actor causes an intermediary’s capability (composition rules).
- **Coalition:** `JointCapabilityRule` requires all listed semantic prerequisites for listed members; canonical sorted `CapabilityActor` coalition.

## 7. Budgets and fail-honest status

`CapabilityClosureBudget.validate()` rejects non-positive limits. If any budget dimension or `max_path_depth` blocks a remaining valid frontier, status is **INCOMPLETE** with deterministic `unresolved_notes` — never **COMPLETE**.

- **COMPLETE** — fixed point inside modeled universe; no truncated frontier; no budget exhaustion.
- **INCOMPLETE** — computation bound stopped exploration.
- **UNKNOWN** — reserved for unresolved modeled conclusion (not used merely because facts have low epistemic confidence).

## 8. Seeds

Seeds must match snapshot tenant; actor and target node ids must exist in the snapshot (fail-closed). Duplicate semantic seeds merge support deterministically (not last-write-wins).

## 9. Tenant isolation

Cross-tenant seeds, actors, targets, rules, or witnesses raise typed Formula errors.

## 10. Determinism

Canonical sorting for facts, witnesses, routes, and serialization. Equivalent semantic input yields identical canonical hash.

## 11. Non-goals

No Gate 4–10 surfaces. **CAPABILITY ≠ AUTHORITY.**

## 12. Claim boundaries

Closure describes **modeled** reachability under declared rules — not universal AI capability, not safety, not permission.
