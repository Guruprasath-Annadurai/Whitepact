# WhitePact Formula Ω∞ — Gate 2C Final Review

**PR:** #117  
**Branch:** `feature/whitepact-formula-omega-v0.1-gate2`  
**Prior Gate 2B commit:** `3007005102a5e83aca6ccd178af3b11879bc319a`  
**Gate 2C head:** `17e91d9ab2c64ea80854018087e355e6afa2ab64` (tree `fa2598b8fd5381833f50c4f3c9d21a73742fef9f`)  
**Formula tests:** 70 (`tests/formula/`)

## Blocker closure

### 1. Wildcard allow + specific deny (P1)

**Defect:** `ALLOW action="*"` with `DENY action="read"` left `read` authorized because `*` atoms did not match specific denies.

**Fix:** `materialize_wildcard_tuples()` expands wildcard allows into concrete atoms using the v0.1 finite universe (`FORMULA_V01_ACTIONS` / `FORMULA_V01_RESOURCES` / purposes) before deny subtraction. `apply_explicit_denies` is order-independent over applicable denies.

**Tests:** `tests/formula/test_gate2_properties_gate2c.py` (ALLOW */DENY read/write, resource/account-1, DENY *, order independence).

**Result:** PASS — read/write/account-specific denies remove concrete authority; full wildcard deny empties effective set.

### 2. Root delegation ceiling (P1/P2)

**Design:** **OPTION A — IMPLEMENT** (partial v0.1 depth model).

- `AuthorityGrant.delegation_depth` (default 0; auto 1 when `delegator` set in test helper).
- `grant_within_org_ceiling`: `allow_delegation` only if `delegation_depth < max_delegation_depth`.
- `validate_delegation`: child depth must equal `parent.delegation_depth + 1`.

**Tests:** `test_max_delegation_depth_zero_blocks_delegable_mint`, `test_max_delegation_depth_one_blocks_second_hop_delegation`.

**Result:** PASS — depth 0 blocks delegable mint; depth 1 blocks delegable grant at hop 1.

### 3. Canonical nested set freezing (P2)

**Defect:** `freeze_value` iterated sets in insertion order.

**Fix:** Sets/frozensets canonicalized via recursive freeze + `json.dumps` sort keys.

**Tests:** `test_nested_set_freezing_canonical` (context, graph node attributes, `canonical_sha256`).

**Result:** PASS — permuted sets yield identical frozen pairs and graph `content_hash`.

## Authority conservation

**AUTHORITY CONSERVATION ESTABLISHED FOR PURE DECLARED GRANT ALGEBRA; DURABLE CONCURRENT ENFORCEMENT UNPROVEN**

## CI

Exact-head full CI required on Gate 2C tip (Python 3.11/3.12, branch coverage ≥ 80%, security checks).

## Remaining issues

| Priority | Item |
|----------|------|
| P3 | Durable-store / concurrent enforcement integration (later gate) |
| P3 | Expand v0.1 action/resource universe binding to tenant policy catalog |

## Verdict

**WHITEPACT FORMULA Ω∞ GATE 2 PASS — AUTHORITY FOUNDATION APPROVED FOR CAPABILITY ENGINE**

*(Subject to exact-head CI green; PR #117 not merged; Gate 3 not started.)*
