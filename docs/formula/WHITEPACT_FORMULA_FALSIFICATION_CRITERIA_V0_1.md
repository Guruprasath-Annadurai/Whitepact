# WhitePact Formula — Falsification Criteria v0.1

For each hypothesis: what evidence would weaken or invalidate it. Gate 1 requires intellectual honesty — the theory must be disprovable.

---

## H1 — Capability closure utility

**Hypothesis:** Bounded capability closure detects materially reachable power not obvious from direct tools.

**Falsified / weakened if:**

- ≥ X% of post-incident reviews find reachable paths outside `C*_H` with complete graph assumption (X set by validation protocol, e.g. 5% in pilot).
- False deny rate > Y% without proportional safety gain.

**Measure:** Red-team paths vs closure output; post-mortem path coverage.

---

## H2 — Authority conservation detection

**Hypothesis:** Conservation rules detect unauthorized privilege creation in autonomous loops.

**Falsified if:**

- Simulated or real scenarios increase effective authority without grant event and Formula returns EXECUTE.
- Delegation bugs bypass `Delegate ⊆ parent` without UNKNOWN.

**Measure:** Property tests on grant algebra; adversarial delegation corpus.

---

## H3 — Safe Future Envelope

**Hypothesis:** `F_H ⊆ SFE_H` catches dangerous transitions in bounded model.

**Falsified if:**

- Benchmarks B10/B12 show violations reachable within H but envelope check SATISFIED (soundness failure).
- Or envelope always vacuous (too coarse) — no discriminative power.

**Measure:** B-family scenarios; differential testing vs brute force on small graphs.

---

## H4 — Minimum sufficient authority

**Hypothesis:** Optimization reduces privilege vs naive grants.

**Falsified if:**

- Cost function always recommends maximal grant (degenerate).
- Pareto frontier unstable under small policy edits.

**Measure:** Simulations on B5/B6.

---

## H5 — Causal reach meaning

**Hypothesis:** `Ψ` correlates with operational blast radius.

**Falsified if:**

- High `Ψ` actions routinely harmless; low `Ψ` actions cause major incidents (miscalibration).

**Measure:** Incident tagging vs Ψ deciles.

---

## H6 — Intent divergence value

**Hypothesis:** `D` adds detection beyond PO-POLICY + PO-AUTHORITY.

**Falsified if:**

- A/B: removing intent layer changes catch rate < ε on adversarial corpus.

**Measure:** B6 copilot scenarios.

---

## H7 — Coalition emergence

**Hypothesis:** Coalition analysis finds emergent capability union misses.

**Falsified if:**

- B7 coalitions: emergent paths only found by naive union anyway, or analysis always INCOMPLETE.

**Measure:** B7 with ground-truth composition semantics.

---

## H8 — Reproducibility

**Hypothesis:** Same inputs + versions ⇒ identical judgment hash.

**Falsified if:**

- Non-deterministic judgments without documented source on replay.

**Measure:** Differential replay tests (Validation Protocol).

---

## H9 — Safety vs false deny

**Hypothesis:** Formula improves safety without unacceptable false deny.

**Falsified if:**

- Safety incidents unchanged but deny rate ↑ beyond agreed SLO.
- Or safety ↓ with deny rate ↓ (useless).

**Measure:** Pilot KPIs; B1–B12 aggregate.

---

## H10 — Computational viability

**Hypothesis:** Evaluations complete within `evaluation_deadline` on production-shaped graphs.

**Falsified if:**

- > Z% evaluations INCOMPLETE at P50 graph size (Z e.g. 50%).

**Measure:** Performance benchmarks on anonymized graphs.

---

## Meta-falsification

If **AX-2** (capability ≠ authority) is routinely bypassed in operator practice, the **system** is falsified even if docs are consistent — implementation gate failure.
