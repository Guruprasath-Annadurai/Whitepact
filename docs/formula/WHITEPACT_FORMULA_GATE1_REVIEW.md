# WhitePact Formula — Gate 1 Formal Consistency Review v0.1

Independent internal review after drafting the v0.1 corpus.

---

## Consistency checks

| Check | Result | Notes |
|-------|--------|-------|
| Circular definitions | **PASS** | `Authorized` defined from grants; `Valid` from lifecycle — no cycle |
| Contradictory axioms | **PASS** | AX-2 and capability checks align with nested sets |
| Undefined terms | **ACCEPTABLE** | `GoalReachable` deferred to policy — flagged for Gate 2 |
| Impossible proof obligations | **ACCEPTABLE** | PO-FUTURE-BOUND qualified; not absolute safety |
| Unbounded computation | **DOCUMENTED** | Exponential future search; bounds required |
| Scalar hiding multidimensionality | **MITIGATED** | Ψ vector, Φ partial order, U vector; H_A deferred |
| Heuristics as laws | **PASS** | H, I, min authority labeled HEURISTIC |
| Probabilistic as deterministic | **PASS** | Intent advisory; trust UNKNOWN blocks |
| Capability vs authority | **PASS** | AX-2 core |
| Trust vs authorization | **PASS** | Separate predicates |
| Prediction vs reachability | **PASS** | Adversarial search wording |
| Policy vs safety | **PASS** | SFE includes both; future check qualified |

---

## Findings (P0–P3)

| ID | Sev | Finding | Action |
|----|-----|---------|--------|
| F-P1 | P1 | Authority conservation not proven as theorem | Proof obligation Gate 2; state honestly in Axioms |
| F-P1b | P1 | `τ` semantics multi-fragment — integration risk | Gate 2 system model unifies fragments |
| F-P2 | P2 | `GoalReachable` for min authority undefined | Define in policy algebra Gate 2 |
| F-P2b | P2 | Grant tuple matching complexity at scale | Indexing — implementation |
| F-P3 | P3 | Intent curvature marginal value | EXPERIMENTAL only |
| F-P3b | P3 | Authority entropy deferred | OK for v0.1 |

No **P0 blocking** mathematical contradictions identified.

---

## Red-team scenarios (theory handling)

| Scenario | Handling |
|----------|----------|
| **A.** Shell access, no authority | `Capable` true, `Authorized` false → DENY; PO-AUTHORITY fails |
| **B.** Grant expires mid-plan | PO-TEMPORAL fails at execution time → DENY / REAUTHORIZE |
| **C.** Two safe agents combine credentials | Emergent capability in `𝒞_coalition`; authority needs coalition grant → REAUTHORIZE |
| **D.** Missing hidden edge | Under-approx risk; default over-approx for safety → may false deny; mark `u_graph` high |
| **E.** False edge in graph | False latent path → false REAUTHORIZE/deny; graph provenance threat T2 |
| **F.** Trust UNKNOWN | PO-TRUST blocks EXECUTE |
| **G.** Lost ack external success | ExecState UNKNOWN → RECONCILE; no auto retry (INV-4) |
| **H.** Future search depth bound | INCOMPLETE future; PO-FUTURE-BOUND UNKNOWN or DENY per policy |
| **I.** Intent “safe”, no authority | Advisory intent ignored for EXECUTE; PO-AUTHORITY fails |
| **J.** High Φ, valid authority | EXECUTE allowed if all PO satisfied; Φ advisory only |
| **K.** Low risk, unauthorized | DENY via PO-AUTHORITY |
| **L.** Safer alt needs less privilege, more time | Counterfactual governance recommends; no auto substitute |
| **M.** Delegator lacks authority | Delegate invalid → child grant invalid |
| **N.** Revocation during eval | Race: re-check PO-GRANT at commit fence (implementation Gate 2) |
| **O.** Spec change between eval and exec | Version pin mismatch → reject replay; new evaluation required |

---

## Gate 1 scoring (qualitative)

| Category | Rating |
|----------|--------|
| Formal consistency | **STRONG** |
| Clarity | **ACCEPTABLE** (large corpus; notation table helps) |
| Falsifiability | **STRONG** |
| Implementability | **ACCEPTABLE** (bounded pieces clear; integration P1) |
| Security relevance | **STRONG** |
| Computational realism | **STRONG** |
| Deterministic vs probabilistic separation | **STRONG** |
| Enterprise applicability | **ACCEPTABLE** |
| Backward compatibility (V1.3.1) | **STRONG** (docs only) |
| Claim discipline | **STRONG** |

---

## Verdict input

No **BLOCKING** category. Gate 1 documentation set is internally coherent enough to proceed to **system-model implementation (Gate 2)** pending explicit product/research approval per program charter.
