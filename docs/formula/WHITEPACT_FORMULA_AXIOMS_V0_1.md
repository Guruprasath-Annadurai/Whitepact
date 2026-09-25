# WhitePact Formula — Axioms, Laws, and Invariants v0.1

**FormulaVersion:** 0.1.0  
**Classification key:** AXIOM | DEFINITION | THEOREM | INVARIANT | HEURISTIC | METRIC | HYPOTHESIS | IMPLEMENTATION CHOICE

---

## Primitive axioms (normative)

**AX-1 (No intelligence authority).**  
No function of `M_t`, model logits, or plan quality implies `Authorized(σ, α, ρ, ctx, t)`.

**AX-2 (Capability ≠ permission).**  
∀σ, α, ρ, t: `ReachableCap(σ, α, t) → Authorized(σ, α, ρ, t)` is **false** as a universal implication.  
**DEFINITION:** `ReachableCap` means ∃ path in `𝒞_poss` under `G_C` and `C_t`.

**AX-3 (Unknown cannot authorize).**  
If any **required** hard proof obligation is `UNKNOWN`, judgment ∉ {`EXECUTE`, `EXECUTE_SCOPED`} unless policy explicitly allows scoped simulation without side effects.

**AX-4 (Nested worlds).**  
`𝒲_adm ⊆ 𝒲_auth ⊆ 𝒲_poss` and `𝒞_adm ⊆ 𝒞_auth ⊆ 𝒞_poss` at all well-formed snapshots.

**AX-5 (Reproducibility).**  
Judgments are functions of `(W_t, α, H, versions, bounds)`; undocumented nondeterminism is forbidden in normative paths.

**AX-6 (Non-omniscience).**  
Formula claims no complete knowledge of `𝒲_poss` or `𝒞_poss` unless explicitly proven under complete graph assumptions (rare).

---

## Candidate laws — classification

### Candidate A — Capability does not imply authority

| | |
|--|--|
| **Formal** | `Capable(σ, α) ⇏ Authorized(σ, α)` |
| **Class** | **AXIOM** (equivalent to AX-2) |
| **Status** | CORE invariant |

### Candidate B — Authority conservation

| | |
|--|--|
| **Formal** | For autonomous transition without external authority-creation event: `𝔄_out ⊆ 𝔄_in ∪ 𝔄_new_grant` where `𝔄_new_grant` must be signed by an authorized authority-creation principal |
| **Class** | **INVARIANT** (target); **THEOREM** only under explicit delegation calculus |
| **Proof status** | **Not fully proven** in v0.1 — see §Conservation proof obligations |

### Candidate C — Unknown cannot authorize

| | |
|--|--|
| **Formal** | `RequiredUnknownEvidence(p) → ¬AllowExecute` |
| **Class** | **AXIOM** (AX-3 operationalized) |

### Candidate D — Expired authority has no execution force

| | |
|--|--|
| **Formal** | `Expired(g, t) → ¬Valid(g, t)` for grant `g` |
| **Class** | **DEFINITION** + **INVARIANT** on grant lifecycle |
| **Deterministic** | Yes, given authoritative clock and grant store |

### Candidate E — Consumed one-shot authority

| | |
|--|--|
| **Formal** | `Consumed(g) → ¬Valid(g)` |
| **Class** | **DEFINITION** + **INVARIANT** |

### Candidate F — Delegation bounded by parent

| | |
|--|--|
| **Formal** | `Effective(Delegate(parent, c)) ⊆ Effective(parent) ∩ ApplyConstraints(c)` ∪ explicit new grants |
| **Class** | **INVARIANT** under delegation model |
| **Notes** | Deny rules subtract; intersection of multiple grants uses grant algebra in Semantics |

### Candidate G — Emergent multi-agent authority requires reauthorization

| | |
|--|--|
| **Formal** | Coalition capability `𝒞_coalition \ ⋃_i 𝒞_auth,i ≠ ∅` does **not** imply coalition authority; emergent **authority** requires explicit coalition grant |
| **Class** | **AXIOM** + **POLICY PRINCIPLE** |

### Candidate H — Irreversible actions require stronger proof

| | |
|--|--|
| **Formal** | `Irreversible(α) → StrongerProofSet(α) ⊃ BaseProofSet` |
| **Class** | **DESIGN PRINCIPLE** / policy tiering — **not** a mathematical law |
| **Reason** | “Stronger” is policy-defined (extra approvals, evidence), not a unique order theorem |

### Candidate I — Minimum sufficient authority

| | |
|--|--|
| **Formal** | `𝔄* ∈ argmin cost(𝔄) s.t. GoalReachable(𝔄)` |
| **Class** | **HEURISTIC** / optimization objective |
| **Notes** | May yield **Pareto frontier**; not unique; not invariant |

---

## Derived invariants (conditional)

**INV-1 (Execution ⊆ admissible capabilities).**  
If `J_Ω = EXECUTE(α)`, then effects of `α` lie within `𝒞_adm` as modeled — **only if** capability model is sound-complete for that action class; otherwise qualified.

**INV-2 (Future envelope).**  
When `FutureCondition` is marked **sound over-approximation**: `F_H(W,α) ⊆ SFE_H(W) ⇒` no modeled policy/trust/risk violation in envelope — **not** guarantee against model error.

**INV-3 (Trust gate).**  
`TrustRequired(α) = UNKNOWN` ⇒ ¬`EXECUTE`.

**INV-4 (Lost ack).**  
`ExecState = UNKNOWN` ⇒ ¬ automatic retry for side-effecting `α` with exactly-once semantics; must pass through `RECONCILE`.

---

## Authority conservation — honest status

**Claim (informal):** No legitimate **autonomous** transition increases authority without an authorized **authority-creation event** external to the acting autonomous agent.

**What counts as explicit new authority:**

- Grant record `g` with `created_by` ∈ principals authorized to mint that grant type
- Policy-approved break-glass workflow with auditable ticket id
- **Not:** tool output, inference, capability discovery, coalition composition

**Delegation chains:** Evaluated by walking delegator links; each hop applies `Delegate` constraints; effective grant = intersection of constraints along chain minus denies.

**Role aggregation:** `Effective(σ, t) = (⊗ role grants) ∩ org ceiling` — **DEFINITION** in Semantics; ⊗ is grant intersection operator.

**Deny wins:** If `Deny(σ, α, ρ)` active, subtract regardless of grants (implementation choice documented as **IMPLEMENTATION CHOICE** for tie-breaking only if policy says so).

**Transitive delegation:** Allowed only if each hop satisfies F; depth bounded by `delegation_depth_max` (symbolic).

**Revocation propagation:** Revoke on grant `g` invalidates derived grants with `derived_from = g` unless policy says otherwise (**DEFINITION**).

**Theorem status:** Full conservation **cannot be proven** in v0.1 without a complete formalization of `(𝔄, P, external events)`. Gate 1 states it as a **proof obligation** for Gate 2 system model, not a proven theorem.

---

## Hypotheses (falsifiable — see Falsification doc)

Examples: H1 capability closure utility, H2 conservation detection, H8 reproducibility. Listed as **HYPOTHESIS**, not axioms.

---

## Heuristics (must not be called laws)

- Weighted “risk scores” combining PO failures  
- Single scalar `Φ` dominating judgment  
- Shannon `H_A` without defined sample space  
- Intent curvature as safety gate  

---

## Relation to WhitePact V1

V1 runtime invariants (Gate B closed, 30 MCP tools, Phase7A off) are **outside** Formula v0.1 semantics. Formula v0.1 is a **parallel formal layer** for future gates; it does not alter V1.3.1 code on the release baseline.
