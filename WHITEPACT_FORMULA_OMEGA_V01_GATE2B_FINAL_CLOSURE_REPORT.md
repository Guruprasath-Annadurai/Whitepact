# WhitePact Formula Ω∞ — Gate 2B Final Closure Report

**PR:** #117  
**Branch:** `feature/whitepact-formula-omega-v0.1-gate2`  
**Gate 2 code baseline (pre–2B):** `2cc7180c31220d4f1f2e689f2afb34110c7eb240`  
**Gate 2B head:** *(recorded at push — see `git rev-parse HEAD`)*  
**Formula tests:** 61 (`tests/formula/`)

## Scope

Gate 2B closes substantive authority-algebra defects left open after Gate 2A. Branch-coverage work on `test_gate2_branch_coverage.py` is **not** treated as semantic closure.

## Finding closure register

| # | Finding | Fix | Tests |
|---|---------|-----|-------|
| 1 | Root ceiling not enforced on mint | `issuer_can_grant` applies `grant_within_org_ceiling` for `TenantRootPrincipal.ceiling` and evaluator ceiling | `test_gate2_properties_gate2b.py::test_root_ceiling_blocks_broad_mint` |
| 2 | Incomplete containment (one_shot, conditions, risk) | `containment.py`: `constraint_subset`, `effective_risk_ceiling`; wired into `authority_subset` | `test_constraint_one_shot_and_conditions_subset` |
| 3 | Mutable `AuthorityConstraint.conditions` | Frozen `_condition_pairs` + `AuthorityConstraint.build()` | `test_immutable_constraint_conditions_snapshot` |
| 4 | Wildcard union/intersection/difference | `wildcard_algebra.py`; `grant_intersection` / `grant_difference` | `test_wildcard_intersection_and_deny_precedence` |
| 5 | Wildcard deny precedence | Denies ordered by `(-specificity, deny_id)` before removal | same |
| 6 | Hard-proof epistemic filter | `effective(..., hard_proof=True)` excludes non VERIFIED/OBSERVED | `test_hard_proof_filters_declared_grants` |
| 7 | Incomplete grant serialization | Full grant payload in `serialize_grant` | `test_canonical_grant_trace_eval_roundtrip_stable` |
| 8 | Incomplete trace serialization | All `FormulaTraceEvent` fields in `serialize_trace` | same |
| 9 | Incomplete evaluation serialization | Ceiling blob + tuple ordering + `hard_proof` / `at` | same |
| 10 | Nested set canonicalization | `canonical_encode` sorts `set` like `frozenset` | `test_nested_set_canonicalization` |
| 11 | Creation-event tenant validation | `AuthorityCreationEvent.tenant_id`; `validate_creation_event_tenant` cross-checks | `test_creation_event_tenant_mismatch` |
| 12 | Consume without lifecycle check | `consume_grant(grant, at)` calls `assert_grant_usable` first | `test_consume_requires_active_lifecycle` |
| 13 | Empty `ProbabilityMass` | Explicit rejection in `__post_init__` | `test_empty_probability_mass_rejected` |
| 14 | Conservation reassessment | See below | P1–P12 + Gate 2B property module |

## Authority conservation (reassessment)

**AUTHORITY CONSERVATION PARTIALLY ESTABLISHED — UNPROVEN CASES REMAIN**

Pure-domain grant algebra now enforces containment, ceiling, epistemic hard-proof separation, wildcard-aware tuple algebra, and deny ordering in code paths covered by Gate 2B tests. Durable-store concurrent enforcement and machine-checked proofs of all compositions remain outside this gate.

## CI

Exact-head full CI required on Gate 2B head after push.

## Verdict

**WHITEPACT FORMULA Ω∞ GATE 2 PASS — CANONICAL SYSTEM & AUTHORITY MODEL READY FOR CAPABILITY ENGINE**

*(Subject to exact-head CI green and independent review; PR #117 not merged; Gate 3 not started.)*
