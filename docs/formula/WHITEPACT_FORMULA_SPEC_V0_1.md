# WhitePact Formula — Formal Specification v0.1

**Program:** WhitePact Formula  
**Research notation:** Ω∞  
**Spec version:** `FormulaVersion = 0.1.0`  
**Status:** Gate 1 — documentation only; no runtime enforcement  
**Release baseline:** Git tag `v1.3.1` @ `894efe30514553f7e0d047a1569a80d36c53a236`

---

## Formula constitution (normative doctrine)

These statements are **design principles** and **policy anchors**, not theorems. They constrain what any implementation may claim.

1. **INTELLIGENCE DOES NOT CREATE AUTHORITY.**  
   Inference, planning, or model confidence never mints permission.

2. **CAPABILITY DOES NOT CREATE PERMISSION.**  
   Reachable power is evidence for judgment; it is not authorization.

3. **UNCERTAINTY DOES NOT CREATE AUTHORIZATION.**  
   Missing proof, stale evidence, or `UNKNOWN` trust cannot yield `ALLOW` for side-effecting execution.

4. **DELEGATED AUTHORITY MUST REMAIN WITHIN LEGITIMATE SOVEREIGN AUTHORITY.**  
   Delegation is a transform on grants, not a source of new sovereign power unless an explicit authority-creation event occurs outside the autonomous actor.

5. **AN AI SYSTEM MUST BE JUDGED NOT ONLY BY THE ACTION IT REQUESTS, BUT BY THE MATERIAL CAPABILITIES AND CONSEQUENCES THAT ACTION CAN REACH.**  
   Requested act `α` is insufficient; bounded reachability under `τ` is in scope.

6. **EXECUTION REQUIRES SATISFACTION OF ALL APPLICABLE HARD PROOF OBLIGATIONS.**  
   No scalar score substitutes for a failed hard obligation.

7. **EVERY MATERIAL JUDGMENT MUST BE EXPLAINABLE, VERSIONED AND EVIDENCE-BACKED.**  
   Reproducibility requires pinned `FormulaVersion`, graph/policy/evidence versions, and hashed inputs.

**WhitePact canonical doctrine (operational):**  
*The agent may think freely. It may plan freely. But it cannot act outside independently enforced authority.*

---

## Purpose of this document

This specification defines the **mathematical objects**, **state spaces**, **judgment shape**, and **versioning** of WhitePact Formula v0.1. It is written so that a skeptical engineer can answer: what does each symbol mean, under what assumptions, and what fails when assumptions break?

Companion documents (same directory, v0.1):

| Document | Role |
|----------|------|
| `WHITEPACT_FORMULA_AXIOMS_V0_1.md` | Axioms, law classification, invariants |
| `WHITEPACT_FORMULA_SEMANTICS_V0_1.md` | Authority, capability, causality, trust, uncertainty, intent |
| `WHITEPACT_FORMULA_PROOF_OBLIGATIONS_V0_1.md` | Hard obligations PO-* |
| `WHITEPACT_FORMULA_COMPUTATIONAL_MODEL_V0_1.md` | Complexity, bounds, INCOMPLETE |
| `WHITEPACT_FORMULA_THREAT_MODEL_V0_1.md` | Adversarial and operational threats |
| `WHITEPACT_FORMULA_FALSIFICATION_CRITERIA_V0_1.md` | Hypotheses H1–H10 |
| `WHITEPACT_FORMULA_VALIDATION_PROTOCOL_V0_1.md` | Later test classes |
| `WHITEPACT_FORMULA_CLAIM_BOUNDARIES_V0_1.md` | Permitted and forbidden claims |
| `WHITEPACT_FORMULA_GATE1_REVIEW.md` | Consistency review and red-team |

---

## Notation table (canonical v0.1)

Symbols are **unique** across the Formula corpus. **Agent** entities use `Ag` or `σ` (subject); **authority** uses `𝔄` or `Grant`; never bare `A` for both.

| Symbol | Meaning | Type / domain | Determinism | Normative? |
|--------|---------|---------------|-------------|------------|
| `t`, `t₀` | Discrete evaluation time index | `ℕ` or `ℝ⁺` clock | Deterministic index | Informative |
| `𝒲` | World-state space | Structured product (below) | Model-dependent | Normative |
| `W_t` | World state at `t` | `𝒲` | Observational snapshot | Normative |
| `X_t` | Observable environment/system state | `𝒳` | Partial, sensor-bounded | Informative |
| `M_t` | Memory/context for action determination | `ℳ` | May be lossy | Informative |
| `I_t` | Intent bundle (human + agent views) | `ℐ` | Mixed epistemic | Advisory |
| `𝔄_t` | Authority state (grants, denials, lifecycle) | `𝔄` | Deterministic given DB | Normative |
| `C_t` | Capability state (known/reachable) | `𝒞` | Bounded search | Informative |
| `G_t` | Unified graph (policy, capability, causal views) | `𝒢` | Versioned, incomplete | Informative |
| `P_t` | Policy / constitutional constraints | `𝒫` | Versioned rules | Normative |
| `T_t` | Trust state | `𝒯` | Three-valued + evidence | Normative for ALLOW |
| `R_t` | Risk state | `ℛ` | Vector / class | Advisory |
| `E_t` | Evidence state | `ℰ` | Hashes, freshness | Normative input |
| `U_t` | Epistemic uncertainty state | `𝒰` | Multi-dimensional | Informative |
| `α`, `act` | Action under judgment | `𝒜ct` | Requested or simulated | Normative input |
| `σ` | Subject (agent or principal) | `Σ` | Identity-bound | Normative |
| `τ` | Transition kernel | `𝒲 × 𝒜ct → 𝒫(𝒲)` | See §Transition | Model |
| `𝒲_poss` | Possible world states | Subset of `𝒲` | Over-approximation | Informative |
| `𝒲_auth` | Authorized world states | Subset of `𝒲_poss` | Proof-derived | Normative |
| `𝒲_adm` | Admissible world states | Subset of `𝒲_auth` | Policy + safety | Normative |
| `F_H(W,α)` | Bounded future reachable set | `𝒫(𝒲)` | Conservative approx. | Informative |
| `SFE_H(W)` | Safe Future Envelope | `𝒫(𝒲)` | Constraint aggregate | Normative target |
| `J_Ω` | Judgment function | See §Judgment | Deterministic given inputs | Normative output |
| `H` | Horizon (steps) | `ℕ`, `H ≤ H_max` | Configurable | Normative bound |
| `Ψ(α)` | Causal power vector | `ℝ^k` (fixed k) | Graph-bounded | Advisory |
| `Φ(α)` | Action potential | Partial order / vector | Not authority | Advisory |
| `H_A` | Authority entropy (optional) | `ℝ⁺` | Only if distribution defined | Experimental |

**Units:** Unless stated, scores are **dimensionless** in `[0,1]` after explicit normalization. Graph distances are **hop counts**. Time is **UTC timestamps** or logical clocks as declared per tenant.

---

## World state

At time index `t`, the **WhitePact world-state** is:

```text
W_t = ( X_t, M_t, I_t, 𝔄_t, C_t, G_t, P_t, T_t, R_t, E_t, U_t )
```

### Component definitions

| Component | Definition | Domain | Codomain / carrier | Failure when missing |
|-----------|------------|--------|--------------------|----------------------|
| `X_t` | Observable system and environment state: APIs up, resource locks, external workflow status, configuration surface | Tenant-scoped sensors, APIs, logs | `𝒳` | Treat observables as `UNKNOWN`; do not infer |
| `M_t` | Memory and context used to choose `α`: conversation, plan, tool outputs in retention window | Bounded buffers, RAG, session store | `ℳ` | Shorter horizon; higher `U_t.model` |
| `I_t` | Pair `(I_H, I_A)` — organizational intent vs agent operational interpretation | Declarations, tickets, prompts, classified model outputs | `ℐ = ℐ_H × ℐ_A` | Intent evidence absent → advisory only |
| `𝔄_t` | Legitimate authority: grants, denials, delegation edges, lifecycle (active/expired/consumed/revoked) | Authority store | `𝔄` | No `EXECUTE`; hard PO-AUTHORITY fails |
| `C_t` | Capability state: direct tools, credentials, network reach, composition closures **as known to the model** | Discovery + graph | `𝒞` | Closure marked incomplete |
| `G_t` | Versioned graphs: capability `G_C`, causal `G_ψ`, policy dependency views | `GraphVersion` | `𝒢` | Incomplete graph → conservative reach |
| `P_t` | Applicable policy and constitutional rules at `PolicyVersion` | Policy engine | `𝒫` | Ambiguity → `UNKNOWN` / `APPROVAL` |
| `T_t` | Trust labels per principal, tool, channel, evidence source | `𝒯 = {TRUSTED, UNTRUSTED, UNKNOWN}` | Product of finite sets | `UNKNOWN` blocks ALLOW |
| `R_t` | Risk posture: classes, ceilings, residual estimates | `ℛ` | Vector | Exceeding ceiling → `DENY` or `APPROVAL` |
| `E_t` | Evidence artifacts: hashes, lineage, freshness, verification status | `ℰ` | Structured records | Stale/missing → obligation failure |
| `U_t` | Epistemic uncertainty (not aleatoric noise alone) | `𝒰` (see Semantics doc) | Multi-field | Propagates to `INCOMPLETE` judgments |

**State space:** `𝒲 = 𝒳 × ℳ × ℐ × 𝔄 × 𝒞 × 𝒢 × 𝒫 × 𝒯 × ℛ × ℰ × 𝒰`.

Assumptions: (A1) tenant boundary is enforced outside Formula; (A2) clock source is agreed per evaluation; (A3) `W_t` is a **snapshot** — concurrent mutations are handled via versioning and reconciliation doctrine, not by pretending a single global truth without events.

---

## Transition kernel τ

**Signature:**

```text
τ : 𝒲 × 𝒜ct → 𝒫(𝒲)
```

`𝒫(𝒲)` denotes a **set**, **distribution**, or **symbolic over-approximation** of successor states. v0.1 **does not** mandate a single semantics; each analysis module declares its fragment:

| Fragment | τ semantics | Use |
|----------|-------------|-----|
| Authority lifecycle | **Deterministic** on grant events | PO-GRANT, expire, revoke |
| Side-effecting tool apply | **Nondeterministic** set (environment) | External systems |
| Stochastic environments | **Probabilistic** (optional) | Risk advisory only |
| Abstract interpretation | **Symbolic over-approximation** | `F_H`, SFE |
| Capability expansion | **Monotone set union** until bound | `C*` / `C*_H` |

**Normative rule:** τ **never** increases legitimate authority without an **authority-creation event** in `𝔄` attributable to an authorized principal (see Axioms — conservation). τ **may** increase **reachable capability** via information gain (information hazard) without increasing `𝔄`.

---

## Possible, authorized, admissible

Three nested state sets at time `t`:

```text
𝒲_adm(t) ⊆ 𝒲_auth(t) ⊆ 𝒲_poss(t) ⊆ 𝒲
```

| Set | Meaning |
|-----|---------|
| `𝒲_poss(t)` | States **reachable** from `W_t` under physical/tool/environment dynamics, ignoring permission |
| `𝒲_auth(t)` | States reachable **without violating authority** in `𝔄_t` along any path in the modeled horizon |
| `𝒲_adm(t)` | States satisfying **policy, trust, risk, temporal, and evidence** constraints (SFE ingredients) |

**Invariant (structural):** nesting above is a **CORE** invariant of the theory. Violations indicate model bug, not agent freedom.

Capability sets mirror this:

```text
𝒞_adm(t) ⊆ 𝒞_auth(t) ⊆ 𝒞_poss(t)
```

| Set | Meaning |
|-----|---------|
| `𝒞_poss` | Tools, credentials, compositions reachable in `G_C` (possibly bounded) |
| `𝒞_auth` | Capabilities **covered** by valid grants for σ at `t` |
| `𝒞_adm` | Capabilities allowed after policy + trust + risk envelopes |

**CORE:** `Capable(σ, α) ⇏ Authorized(σ, α)` — capability membership in `𝒞_poss` does not imply authorization.

---

## Judgment function J_Ω (overview)

```text
J_Ω(W_t, α_t, H, FormulaVersion) → JudgmentOutcome
```

**Outputs (v0.1):** `EXECUTE`, `EXECUTE_SCOPED`, `APPROVAL`, `REAUTHORIZE`, `SANDBOX`, `SIMULATE`, `QUARANTINE`, `DENY`, `UNKNOWN`, `RECONCILE`.

Each output: preconditions, proof obligations, whether it **grants authority** (only external grant events do), human requirements, side-effect allowance, terminality — detailed in **Semantics** and **Proof Obligations** documents.

**Formal target shape (qualified):**

```text
EXECUTE(α_t) only if:
  ∀ p ∈ HardObligations(α_t): Satisfied(p)     [deterministic where applicable]
  AND FutureCondition(α_t)                       [qualified bounded model]
  AND ResidualRiskWithinPolicy(α_t)
  AND NoKnownAuthorityViolation(α_t)
```

**Honest semantics:** `FutureCondition` means **no violation discovered within the qualified bounded model**, not global safety.

---

## Versioning and reproducibility

| Field | Role |
|-------|------|
| `FormulaVersion` | Semantics bundle (e.g. `0.1.0`) |
| `FormulaSpecHash` | Hash of normative doc set |
| `EvaluationVersion` | Implementation-independent eval profile |
| `GraphVersion` | `G_t` snapshot id |
| `PolicyVersion` | `P_t` id |
| `EvidenceVersion` | `E_t` bundle id |

A stored judgment must replay with identical inputs and versions. **v0.2 must not retroactively redefine v0.1** judgments.

---

## Proof object (specification only)

Canonical **Formula proof object** fields (no serialization mandated in Gate 1):

`evaluation_id`, `formula_version`, `formula_spec_hash`, `tenant_id`, `actor`, `action`, `graph_version`, `policy_version`, `input_hash`, `proof_obligations`, `satisfied_obligations`, `failed_obligations`, `unknown_obligations`, `capability_paths`, `causal_paths`, `future_search_summary`, `uncertainty`, `judgment`, `reason_codes`, `timestamp`, `evidence_hash`.

Normative vs informative fields: see **Proof Obligations** document.

---

## Concept classification (Ω∞ “God Mode” review)

| Concept | Gate 1 class | Notes |
|---------|--------------|-------|
| World state `W_t` | **CORE** | |
| Safe Future Envelope `SFE_H` | **CORE** | Qualified bounded |
| Authority tensor | **REMOVE** | Replaced by grant relation + `𝔄_t` |
| Authority conservation | **CORE** invariant (conditional proof) | |
| Capability gravity | **REMOVE** | No physics metaphor |
| Causal power `Ψ` | **ADVISORY** vector | |
| Action potential `Φ` | **ADVISORY** partial order | Never overrides authority |
| Intent divergence `D` | **ADVISORY** vector | |
| Intent curvature | **EXPERIMENTAL** | Discrete derivative optional |
| Autonomy pressure | **ADVISORY** observations | |
| Information hazard | **CORE** | Capability delta via read paths |
| Authority entropy `H_A` | **DEFER** | Only if distribution defined |
| Sovereignty impact | **ADVISORY** operational recoverability | |
| Multi-agent emergence | **CORE** (coalition semantics) | |
| Adversarial future search | **CORE** (bounded) | |
| Counterfactual governance | **ADVISORY** | Recommends, does not substitute |
| Minimum sufficient authority | **HEURISTIC** optimization | Pareto, not unique law |

---

## Benchmark families (schema only)

`B1`–`B12` defined in **Validation Protocol** — Gate 1 provides schemas and example fields only; no harness.

---

## Gate 1 scope boundary

This specification introduces **no** runtime code, migrations, APIs, CLI, UI, MCP changes, or V1.3.1 behavior changes. WhitePact V1 enforcement (Gate B closed, 30 MCP tools, Phase7A off) remains untouched on the release baseline.
