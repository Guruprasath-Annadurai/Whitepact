# Gate 2 — Proof Notes (Authority Conservation)

## Target

Delegation-only: `Effective(child) ⊆ Effective(parent)` on grant tuples.

Creation: `A_out ⊆ A_in ∪ {g}` where `g` from valid `AuthorityCreationEvent`.

## Assumptions

- Pure grant algebra; no concurrent mutation in proof  
- `tenant_root:*` issuers bounded by org ceiling  
- Deny set static during evaluation  

## Machine-checkable properties

- P3 delegation widen → `AuthorityExpansion`  
- P11 delegation chain `root_effective_subset`  
- Property tests P1–P12 in `tests/formula/test_gate2_property.py`

## Verdict

**AUTHORITY CONSERVATION PARTIALLY ESTABLISHED — UNPROVEN CASES REMAIN**
