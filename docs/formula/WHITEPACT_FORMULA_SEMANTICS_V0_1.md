# WhitePact Formula — Semantics v0.1

Detailed semantics for authority, capability, causality, futures, trust, uncertainty, intent, execution state, and judgment outputs.

---

## Authority formalism

### Grant tuple

**DEFINITION (Grant).**  
`g = (σ, α_pattern, ρ, purpose, ctx, [t_start, t_end], delegator, cond, risk_ceil, grant_id)`

| Field | Domain | Notes |
|-------|--------|-------|
| `σ` | Subject id | Agent or service principal |
| `α_pattern` | Action pattern | May be parameterized |
| `ρ` | Resource id / pattern | Tenant-scoped |
| `purpose` | Purpose string / enum | Policy-matched |
| `ctx` | Context constraints | IP, session, MFA, etc. |
| `[t_start, t_end]` | Time interval | Half-open `[t_start, t_end)` |
| `delegator` | Principal or ∅ | ∅ for root grants |
| `cond` | Predicate list | All must hold |
| `risk_ceil` | Risk class cap | Advisory binding |
| `grant_id` | UUID | Stable reference |

### Predicates

**DEFINITION.**  
`Authorized(σ, α, ρ, ctx, t) ≡ ∃ valid g: Matches(g, σ, α, ρ, ctx, t) ∧ ¬Denied(σ, α, ρ, t)`.

**DEFINITION.**  
`EffectiveAuthority(σ, t) = { (α, ρ, ctx) : Authorized(σ, α, ρ, ctx, t) }`.

### Grant algebra

| Operator | Meaning |
|----------|---------|
| `𝔄₁ ⊆ 𝔄₂` | Every authorization in 𝔄₁ is authorized in 𝔄₂ |
| `𝔄₁ ∩ 𝔄₂` | Pointwise intersection on actions/resources satisfied by both |
| `𝔄₁ \ 𝔄₂` | Authorizations in 𝔄₁ not in 𝔄₂ |

Boolean authority is **insufficient** when grants carry orthogonal constraints; use **set of constrained tuples**, not one bit.

### Lifecycle operators

| Op | Effect on `Valid(g, t)` |
|----|-------------------------|
| `Delegate(parent, c)` | Creates child grant; child ⊆ constrained parent |
| `Renew(g, t')` | Extends `t_end` if authorized |
| `Revoke(g)` | `Valid → false`; may cascade |
| `Consume(g)` | One-shot: valid for one execution then `Consumed` |
| `Expire(g, t)` | Automatic when `t ≥ t_end` |
| `Supersede(g, g')` | `g` invalid when `g'` active |

---

## Capability formalism

**DEFINITION.** Capability graph `G_C = (V, E)` with typed edges:

- `tool_edge`, `credential_edge`, `compose_edge`, `info_edge` (see information hazard)

**DirectCapability(σ)** = nodes reachable in one hop from σ’s attachment set.

**Expand(C)** = one step of composition, credential unlock, API pairing per graph rules.

**ReachableCapability(σ, h)** = `C_h` where `C_0 = DirectCapability(σ)`, `C_{n+1} = C_n ∪ Expand(C_n)`.

**CapabilityClosure(σ)** = `C*` if iteration to fixed point with **unbounded** exploration (theoretical).

**Bounded closure `C*_H`:** Stop at hop bound `H` or node budget `N_nodes_max`.  
**INCOMPLETE** if bound hit — **never** present as global `C*`.

| Mode | Meaning |
|------|---------|
| Exact closure | Complete finite graph, exact semantics |
| Bounded closure | Stops early; may miss nodes |
| Over-approximation | Superset of true reachability (safe for deny) |
| Under-approximation | Subset (unsafe for safety-only deny) |
| Unknown closure | Graph incomplete |

v0.1 production theory **prefers conservative over-approximation** for safety-relevant deny; may increase false denials.

### Latent capability escalation

**DEFINITION.**  
`LatentEscalation(σ, t) ≡ (ReachableCap(σ,t) \ AuthCap(σ,t)) ≠ ∅` where `AuthCap` maps grants to capabilities.

**Theory does not hard-code response.** Response function `R_escalate` is policy + judgment:

| Condition | Typical response (policy) |
|-----------|----------------------------|
| High certainty path + current α uses latent | `REAUTHORIZE` / `DENY` |
| Low certainty / missing edge | `SIMULATE` / `UNKNOWN` |
| Exploratory only | Warning in proof object |

Depends on: reachability certainty, prerequisites, horizon, action class.

---

## Future state model

**DEFINITION.**  
`F_H(W_t, α_t) ⊆ 𝒲` — bounded reachable worlds after executing `α_t` for `H` steps.

Layers:

- `F_1(W,α)` — one-step successors under τ  
- `F_{k+1} = ⋃_{w ∈ F_k} F_1(w, α_k)` with branching bound `search_branch_max`

**Semantics (v0.1 default):** **conservative over-approximation** of true reachability for safety checks.

**Core condition (qualified):**  
`F_H(W,α) ⊆ SFE_H(W)` ⇒ no **modeled** violation in envelope.

| Situation | Status |
|-----------|--------|
| Mandatory | High-risk, irreversible, regulated actions |
| Advisory | Low-risk read paths |
| Unprovable | Incomplete τ |
| Infeasible | Budget exhausted → `INCOMPLETE` / `UNKNOWN` |

### Safe Future Envelope

**DEFINITION.**  
`SFE_H(W_t) = { w ∈ 𝒲 : AuthzOK(w) ∧ PolicyOK(w) ∧ TrustOK(w) ∧ RiskOK(w) ∧ TimeOK(w) ∧ EvidenceOK(w) }`  
each predicate evaluated on **abstract state** in the reachability abstraction.

**Tradeoff (documented):**

- Over-approx `F_H` → safe actions may be rejected (false deny)  
- Under-approx `F_H` → dangerous states may be missed (false allow in model)

---

## Causal model

**DEFINITION.** Causal influence graph `G_ψ = (V, E, ℓ)` with label `ℓ(e) ∈ {dependency, capability, observed, assumed, potential}`.

**Epistemic rule:** Edge label determines proof strength; **dependency ≠ observed causation**.

| Construct | Meaning |
|-----------|---------|
| `Descendants(α)` | Nodes downstream of action node |
| `CausalReach(α)` | Union of paths respecting observed+assumed edges per policy |
| `CriticalCausalReach(α)` | Subgraph touching critical resource class |

### Causal power Ψ

**DEFINITION (vector).**  
`Ψ(α) = (d_direct, d_trans, d_crit, d_ext, d_irrev)` — non-negative integers or normalized counts.

**Why vector:** Scalar collapses irreversibility vs breadth; **METRIC**, advisory only.

---

## Action potential Φ

**DEFINITION.**  
`Φ(α)` is a **partial order** on actions induced by component-wise comparison of:

`(privilege_level, blast_radius, irreversibility, uncertainty_penalty, trans_reach, amp_factor, external_effect)`.

**HEURISTIC:** May map to risk class for UI.  
**Hard rule:** `Φ` **never** implies `Authorized`.

---

## Trust semantics

**DEFINITION.** `TrustVal ∈ {TRUSTED, UNTRUSTED, UNKNOWN}` per (principal, channel, source).

Three-valued logic for obligations:

| TrustRequired | TRUSTED | UNTRUSTED | UNKNOWN |
|---------------|---------|-----------|---------|
| Allow EXECUTE | OK | Fail | **Fail** |

`TrustUnknown(α) ≡ ∃ source: TrustRequired(α, source) = UNKNOWN`.

---

## Uncertainty U_t

**DEFINITION.**  
`U_t = (u_source, u_model, u_graph, u_fresh, u_search)` each in `[0,1]` or enumerated `INCOMPLETE`.

| Component | Captures |
|-----------|----------|
| `u_source` | Epistemic: untrusted/stale sources |
| `u_model` | Model disagreement |
| `u_graph` | Missing/false edges |
| `u_fresh` | Evidence age |
| `u_search` | Timeout / branch limit |

Aleatoric uncertainty (environment randomness) lives in **risk** advisory, not authorization.

---

## Execution outcomes (lost ack)

**DEFINITION.**  
`ExecState ∈ {NOT_STARTED, IN_PROGRESS, SUCCEEDED, FAILED, UNKNOWN, RECONCILING}`.

**INVARIANT:** `UNKNOWN` **does not imply retry** for side-effecting actions.

**Safe transition:** `UNKNOWN → RECONCILING` before duplicate external effects (aligns with WhitePact reconciliation doctrine).

---

## Intent

`I_t = (I_H, I_A)` — organizational vs agent interpretation.

Model outputs are **advisory evidence** only.

**DEFINITION.**  
`D = (D_semantic, D_capability, D_consequence)` — divergence vector.

Combined `D_Ω` **DEFER** unless empirical justification in later gates.

### Intent curvature (experimental)

Discrete: `κ_intent(t) = ||I_A(t) - I_A(t-1)||` or second difference for change-point.  
**Class:** EXPERIMENTAL metric — not a law.

---

## Autonomy pressure (advisory)

**DEFINITION.** `AutonomyPressureObservation` = multiset of observable signals:

- repeated privilege expansion requests  
- repeated denials then retries  
- alternate-path search after deny  
- tool-surface expansion attempts  
- goal persistence after boundary rejection  

No inference of malice or consciousness.

---

## Information hazard

**DEFINITION.** For information object `i`:

`Read(i)` may yield `ΔC = C_{t+1} \ C_t` only if `G_C` has `info_edge(i, capability)`.

Authority unchanged unless separate grant. Secrets/credentials/IAM topology are canonical examples.

---

## Authority entropy

**Status:** **DEFER** from core. If used:

`H_A = -Σ p_i log p_i` requires **DEFINITION** of sample space (distribution over effective grant tuples).  
High entropy = diffuse authority footprint — **interpretation**, not permission.

---

## Recoverability / sovereignty impact

**DEFINITION.**  
`Recoverability(α) ∈ {reversible, compensable, irreversible}` × `{credential, data, financial, external_finality}` matrix.

No philosophical “sovereignty” scalar.

---

## Multi-agent coalition

Agents `Ag_1…Ag_n` with `𝒞_i`, `𝔄_i`.

`𝒞_coalition` = closure under **composition semantics** (not naive union if tools require role pairing).

**EmergentCapability** = `𝒞_coalition \ ⋃_i 𝒞_i`.

**Emergent authority** requires explicit grant — **AXIOM G**.

---

## Minimum sufficient authority

**HEURISTIC.** Minimize `cost(𝔄)` = vector `(breadth, time, irreversibility, privilege, trans_reach)` subject to `GoalReachable(𝔄)`. Pareto set, not unique.

---

## Adversarial future search

Bounded search for trajectories in τ that **maximize violation severity** within `H`, `search_branch_max`, timeout.  
Objective: find policy/authority violations, not “predict AI behavior.”

---

## Counterfactual governance

Compare `α` vs safer `α'` on: authority, reach, Ψ, irreversibility, risk.  
**Advisory** recommendation — no silent substitution.

---

## Judgment outputs J_Ω

| Output | Grants authority? | Side effects | Human | Terminal |
|--------|-------------------|--------------|-------|----------|
| EXECUTE | No (uses existing) | Allowed if PO ok | Optional policy | No |
| EXECUTE_SCOPED | No | Scoped | Often | No |
| APPROVAL | No | Blocked until human | Required | No |
| REAUTHORIZE | No | Blocked | Required | No |
| SANDBOX | No | Sandboxed only | Optional | No |
| SIMULATE | No | None | Optional | Yes |
| QUARANTINE | No | Blocked | Required | No |
| DENY | No | None | Optional | Yes |
| UNKNOWN | No | None | Reconcile | No |
| RECONCILE | No | Hold | Required | No |

**Grants authority** only via external grant workflow — never via `J_Ω` alone.
