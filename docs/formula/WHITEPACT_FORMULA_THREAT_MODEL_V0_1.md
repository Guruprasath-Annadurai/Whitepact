# WhitePact Formula — Threat Model v0.1

Assets, attackers, failure modes, mitigations, and what Gate 1 vs later gates address.

---

## Assets

| Asset | Description |
|-------|-------------|
| A1 | Authority store integrity |
| A2 | Graph snapshots (`G_C`, `G_ψ`) |
| A3 | Policy bundles `P_t` |
| A4 | Evidence artifacts `E_t` |
| A5 | Judgment / proof objects |
| A6 | Formula spec versions |
| A7 | Tenant isolation boundary |

---

## Threat catalog

| ID | Threat | Attacker capability | Failure mode | Mitigation (target) | Gate 1 | Later gates |
|----|--------|---------------------|--------------|---------------------|--------|-------------|
| T1 | Incomplete graph | Passive / env | Missed latent capability | Over-approx + INCOMPLETE flag | Model | Graph ingestion tests |
| T2 | Graph poisoning | Insider / compromised pipeline | False edges → false deny/allow | Signed graph versions, provenance | Threat doc | Integrity CI |
| T3 | False capability edge | Same as T2 | Wrong `F_H` | Edge epistemic labels | Semantics | Validation |
| T4 | Hidden capability edge | Attacker hides path | False allow in under-approx | Conservative over-approx | Semantics | Red team |
| T5 | Authority data poison | DB attacker | Unauthorized EXECUTE | Trusted store, audit | PO-AUTHORITY | Integration |
| T6 | Stale authority | Ops lag | Expired grant used | PO-TEMPORAL | Semantics | Clock tests |
| T7 | Semantic intent poison | Prompt injection | “Looks safe” advisory | Intent advisory only | Axioms | Corpus |
| T8 | Policy ambiguity | Author error | UNKNOWN flood | Policy lint | — | Gate 2 |
| T9 | Trust provider outage | Infra | UNKNOWN | Block EXECUTE | Trust table | DR tests |
| T10 | Proof tampering | MITM / storage | False SATISFIED | Signed proofs, hash chain | Spec | Crypto |
| T11 | Formula version swap | Deployment | Wrong semantics | Pin versions | Versioning | Release |
| T12 | Cache poisoning | Cache attacker | Stale judgment | TTL + hash inputs | — | Impl |
| T13 | Complexity DoS | Adversarial graph | Timeout → fail-open? | **Must fail closed** on EXECUTE | Computational | Perf tests |
| T14 | Future-search explosion | Branch bomb | INCOMPLETE treated complete | Budget flags | Bounds | Fuzz |
| T15 | Multi-agent collusion | Coalition | Emergent capability | Reauthorization axiom | Axioms | B7 benchmark |
| T16 | Cross-tenant | Confused deputy | Data leak | PO-TENANT | Semantics | B11 |
| T17 | Maximize UNKNOWN | Adversarial input | Operational paralysis | Explicit UNKNOWN semantics | Axioms | Metrics |
| T18 | Timeout exploit | Force fail-open | Unsafe EXECUTE | UNKNOWN/DENY default | Proof doc | Concurrency tests |

---

## Fail-open prohibition

**DESIGN PRINCIPLE:** Timeout, INCOMPLETE, or UNKNOWN on **hard** obligations must **not** default to EXECUTE. Gate 2+ must test this explicitly (T13, T18).

---

## Gate 1 coverage

Gate 1 proves **nothing operationally** — it defines threats and required mitigations so later gates can test them.
