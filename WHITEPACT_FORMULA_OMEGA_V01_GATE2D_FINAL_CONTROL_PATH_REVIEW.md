# WhitePact Formula Ω∞ — Gate 2D Final Control-Path Review

**PR:** #117 (open, not merged)  
**Branch:** `feature/whitepact-formula-omega-v0.1-gate2`  
**Gate 2C CI-green code tip:** `0f9bb3eebcde1615f7354edb6427236be8d5d23c`  
**Gate 2D baseline commit:** `3f921ddba731b324ac74ab0fd5591b5e4ab76430`  
**Gate 2D baseline tree:** `64fb289aaa9e04d4c8c742919a0ce897f413e43d`  
**v1.3.1 tag:** unchanged (`894efe30514553f7e0d047a1569a80d36c53a236`)  
**PR #98 / `cursor/whitepact-dev-environment-f7a9`:** not touched  

## Objective

Close three control-path gaps between formal authority semantics and runtime evaluation paths without redesigning Gate 2 or starting Gate 3.

## Changes (Gate 2D)

| Area | Fix |
|------|-----|
| **A. Delegation depth** | `validate_delegation(..., ceiling=...)` and `apply_delegation(..., ceiling=...)` enforce `grant_within_org_ceiling` on the child when an org ceiling governs the chain. `DelegationChain.validate(ceiling=...)` threads the same path. Depth semantics: depth 0 = root grant; each hop +1; grants with `delegation_depth > max_delegation_depth` rejected; at max depth `allow_delegation` cannot permit another hop. |
| **B. Conditions** | `grant_conditions_match()` fail-closed equality semantics; `EffectiveAuthorityEvaluator.effective(..., conditions=...)` filters grants before union. `AuthorityContext` (environment keys) remains separate from `AuthorityConstraint.conditions` (runtime state). |
| **C. Effective risk** | `grant_union()` emits `AuthorityTuple.risk_ceiling = effective_risk_ceiling(grant)` so org restriction, serialization, and subset checks agree. |

### Files touched

- `src/responsibleai/formula/authority/algebra.py`
- `src/responsibleai/formula/authority/containment.py`
- `src/responsibleai/formula/authority/creation.py`
- `src/responsibleai/formula/authority/delegation.py`
- `tests/formula/helpers.py`
- `tests/formula/test_gate2_properties_gate2c.py` (delegation path via `apply_delegation`)
- `tests/formula/test_gate2_properties_gate2d.py` (new)

## Evidence

### Delegation path

Gate 2D tests exercise `apply_delegation` and `DelegationChain.validate` with org ceilings for max_depth 0/1/2, wrong depth, depth reset, cross-tenant ceiling, and ceiling bypass prevention.

### Conditions fail-closed

Missing keys, wrong values, and partial multi-key state yield empty effective authority; exact match activates; child cannot drop parent conditions (`constraint_subset` / `authority_subset`); strengthening allowed.

### Effective risk

`risk_ceiling=10` with `max_risk_class=3` yields tuple risk 3; org ceiling 5 accepts; ceiling 2 drops; serialized evaluation records 3.

## Formula tests

| | Count |
|--|-------|
| Pre–Gate 2D | 70 |
| Post–Gate 2D | 91 (`pytest tests/formula`) |

## Authority conservation

**AUTHORITY CONSERVATION ESTABLISHED FOR PURE DECLARED GRANT ALGEBRA; DURABLE CONCURRENT ENFORCEMENT UNPROVEN**

No counterexample found in reviewed pure algebra for: delegation depth bypass (when ceiling supplied), condition bypass at `effective()`, risk widening via `grant_union`, or parent condition removal on delegate.

## Remaining issues

| Priority | Item |
|----------|------|
| P3 | Durable-store / concurrent enforcement |
| P3 | Tenant policy catalog binding for finite wildcard universe |

## CI (exact-head)

| Field | Value |
|-------|-------|
| Gate 2D code commit | `06f347cecb28a44b57bfe293c9b659d828cf0854` |
| Gate 2D code tree | `9d7abdd9956f5c1fdb8d5de730c5b036446e51b9` |
| Final commit (exact PR head) | `6b401b3` *(update if superseded)* |
| Final tree | *(see `git rev-parse HEAD^{tree}` on PR head)* |
| Workflow run | *(pending)* |
| Branch coverage | *(pending full CI)* |

## Gate 3

**Not started.**

## Verdict

**WHITEPACT FORMULA Ω∞ GATE 2 CONDITIONAL — CONTROL-PATH GAP REMAINS**

*(Conditional only until exact-head full CI green on final report commit; no unresolved P1 control-path defects in code review.)*
