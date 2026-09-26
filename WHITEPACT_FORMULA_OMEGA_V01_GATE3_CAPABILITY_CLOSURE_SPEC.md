# WhitePact Formula Ω∞ — Gate 3 Capability Closure Specification

**Formula version:** 0.1.0  
**Scope:** Bounded capability closure only (not authority, not future envelope, not judgment).

## 1. Mathematical closure

Given immutable `GraphSnapshot` \(G\), seed facts \(C_0\), typed rules \(R\), and budget \(B\):

\[
F(C) = C \cup \text{DirectExtract}(G) \cup \bigcup_{r \in R} r(G, C)
\]

\[
C^\* = \mu C.\, F(C) \text{ truncated by } B
\]

Closure status:

- **COMPLETE** — fixed point reached within modeled universe and budget.
- **INCOMPLETE** — iteration/fact/rule budget exhausted before fixed point.
- **UNKNOWN** — unresolved epistemic/model notes remain.

## 2. Capability facts

`CapabilityFact` is immutable reachability: tenant, canonical `CapabilityActor` (sorted coalition), action (`call|read|write|execute`), target node, `CapabilityKind`, epistemic status, `is_direct`.

Semantic identity: `(tenant_id, actor.member_ids, action, target_node_id)` — independent of derivation path.

## 3. Direct vs composed

- **Direct:** extracted from `CAN_CALL|CAN_READ|CAN_WRITE|CAN_EXECUTE` from actor/component sources.
- **Composed:** derived only via explicit rules (e.g. `COMPOSE_VIA_CALL`, `MULTI_AGENT_RELAY`) with `route_node_ids` provenance.

## 4. Rule system

Typed rules in `capability/rules.py` — no arbitrary callbacks.

| Rule | Meaning |
|------|---------|
| `COMPOSE_VIA_CALL` | Actor calls intermediary; intermediary capability forwards to actor (composed). |
| `MULTI_AGENT_RELAY` | Same with `AGENT` intermediary. |
| `CREDENTIAL_UNLOCK` | `CAN_READ` credential + `REQUIRES` with `grants=call`. |
| `INFORMATION_REVEALS` | `CAN_READ` + `REVEALS`. |

**Not** derived: `HAS_AUTHORITY`, `APPROVED_BY`, `DEPENDS_ON`, `TRUSTS`, generic transitivity.

## 5–8. Credential, information, multi-agent

See rule table; all require explicit edges — no name-based inference.

## 9. Epistemic propagation

`compose_epistemic()` — weakest-link over `_ORDER`; derivations cannot exceed weakest premise.

## 10. Budgets

`CapabilityClosureBudget`: `max_iterations`, `max_facts`, `max_derivations`, `max_rule_applications`, `max_path_depth`.

## 11–13. Tenant isolation, snapshot pinning, determinism

Evaluation uses frozen `GraphSnapshot` (`content_hash`, `GraphVersion`). Cross-tenant seeds rejected. Canonical sorting for facts/derivations/serialization.

## 14. Non-goals

No Gate 4–10 surfaces (future envelope, judgment, persistence, runtime enforcement, production qualification).

## 15. Claim boundaries

Closure describes **modeled** reachability under declared rules — not universal AI capability, not safety, not permission.
