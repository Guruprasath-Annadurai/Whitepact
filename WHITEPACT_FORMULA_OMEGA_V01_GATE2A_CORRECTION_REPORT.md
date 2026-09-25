# WhitePact Formula Ω∞ — Gate 2A Independent Authority-Model Correction Report

**PR:** #117  
**Branch:** `feature/whitepact-formula-omega-v0.1-gate2`  
**Gate 2A base (pre-correction head):** `1fd2f513f8e5e13b74d28344f94bc5f0e8068d72`  
**Gate 2A final head:** `63260f07ffb118d05550b856d72ce8e89f687c6d` (tree `879347e79f0ecfe4b327f3907adb657319b0cb08`)  
**Formula unit tests:** 37 (`tests/formula/`)  
**Property matrix:** P1–P12 in `tests/formula/test_gate2_properties_p1_p12.py`

## Summary

Gate 2A closes independent-review P1 authority-model defects: fail-closed context matching, delegation and wildcard subset semantics, full issuer containment, explicit tenant-bound root principals, tenant isolation in effective evaluation, logical immutability of snapshots, content-addressed graph hashes, unified grant lifecycle, semantic grant intersection, org-ceiling DROP semantics, trace empty-path hardening, canonical serialization coverage, `ProbabilityMass` validation, and executable invariant checks for `INV_UNKNOWN_NOT_AUTHORITY` and `INV_ORG_CEILING`.

## Finding register

| # | Original defect | Reproduction | Fix | New invariant / test | Result |
|---|-----------------|--------------|-----|-------------------|--------|
| 1 | Missing grant context keys treated as match | `grant.context={"environment":"prod"}`, eval `{}` authorized | `grant_context_matches()`; evaluator skips non-matching grants | `test_gate2_authority_algebra.py` context tests; adversarial | Fail-closed |
| 2 | Child `{}` accepted under parent `environment=prod` | `authority_subset` direction wrong | `context_subset()` requires child retain parent equality constraints | P3 property; delegation tests | Rejected |
| 3 | Empty child purposes = wildcard broader than parent | `purposes=ops` parent, child `{}` passed subset | `WILDCARD` token; `dimension_subset`; empty sets invalid for grants | wildcard unit + P3 | Rejected |
| 4 | `issuer_can_grant` action/resource only | Issuer mints higher risk / delegation / time | `grant_contained_in_issuer_authority()` + full `authority_subset` | `test_gate2_authority_algebra.py` issuer tests | Contained |
| 5 | `tenant_root:` prefix trusted | Arbitrary issuer id with prefix | `TenantRootPrincipal` + evidence/policy refs | `test_root_requires_evidence_not_prefix` | Prefix untrusted |
| 6 | Cross-tenant grant/deny composition | Tenant A grant in tenant B eval | `tenant_id` on `effective()`; validation helpers in `tenant.py` | P10; adversarial cross-tenant | Isolated |
| 7 | Frozen dataclass + mutable dicts | Mutate attrs after `freeze()` | `GraphNode.build` / `AuthorityContext` frozen pairs; `immutability.py` | `test_snapshot_immutable_after_mutation` | Stable snapshot |
| 8 | `content_hash` included `version_number` | Two freezes same content differ hash | Hash canonical nodes/edges only; version in `GraphVersion` | `test_graph_snapshot_hash_stable_for_same_content` | Content-addressed |
| 9 | PENDING usable via inconsistent APIs | Mixed `valid_at` / `assert_grant_usable` | Only `ACTIVE` usable; all other lifecycle states rejected | lifecycle tests in algebra | Coherent |
| 10 | Creation event field drift | subject/issuer/tenant mismatch | `validate_creation_event()` before `apply_creation_event` | creation tests | Validated |
| 11 | `grant_id` in intersection equality | Two grants never intersect semantically | `PermissionAtom` vs provenance; semantic `grant_intersection` | algebra tests | Semantic ops |
| 12 | Ambiguous org ceiling | Silent clip vs drop | **DROP** tuple when grant risk exceeds org max (documented) | P8; `check_org_ceiling` | DROP |
| 13 | Empty trace path vacuous True | `all_paths_authorized(())` True | Empty path → False; docs on event-id predicate | `test_state_path_empty_not_authorized` | Hardened |
| 14 | Partial canonical serialization | Grants/traces/eval inconsistent | Extended `serialization.py` + P9 | `test_gate2_property.py` | Deterministic |
| 15 | `ProbabilityMass` accepted NaN/inf | Invalid distributions | Explicit range + sum validation | adversarial probability tests | Rejected |
| 16 | Declared invariants without checks | `INV_UNKNOWN`, `INV_ORG_CEILING` missing | Implemented on `FormulaInvariantChecker` | invariant + P1/P8 | Executable |
| 17 | Incomplete P1–P12 | Placeholders | Full matrix `test_gate2_properties_p1_p12.py` | 12 properties | Covered |
| 18 | Conservation after fixes | Prior partial verdict | Re-run; no known pure-algebra widening after fixes | property + adversarial suite | See §Conservation |
| 19 | CI | Red on authority defects | `ruff`, `mypy`, `pytest tests/formula` green locally | CI on PR head | Pending exact-head green |
| 20 | Reports | Gate 2 report stale | This file + updated `WHITEPACT_FORMULA_OMEGA_V01_GATE2_REPORT.md` | — | Updated |
| 21 | Verdict | — | — | — | See §Verdict |
| 22 | Hard stop | — | No Gate 3 / no merge | — | Observed |

## Authority conservation (reassessment)

**AUTHORITY CONSERVATION PARTIALLY ESTABLISHED — UNPROVEN CASES REMAIN**

Pure grant algebra and evaluator paths addressed in Gate 2A show no known authority-widening defect under the declared semantics (property tests P1–P12 and adversarial cases). Machine-checked proof of all composition paths and concurrent durable-store enforcement remain outside this gate.

## Verdict (Gate 2 post–2A)

**WHITEPACT FORMULA Ω∞ GATE 2 PASS — CANONICAL SYSTEM & AUTHORITY MODEL READY FOR CAPABILITY ENGINE**

*(Subject to exact-head CI green and independent review per program charter; PR #117 not auto-merged.)*

## Hard stop

Gate 3, capability closure, Safe Future Envelope, future search, and Omega judgment were not started.
