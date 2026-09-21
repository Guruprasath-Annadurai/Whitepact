# Sovereign Simulation (Phase C)

Sovereign simulators answer counterfactual questions using canonical WhitePact
authority and policy truth. They never mint grants, consume nonces, or dispatch
external effects.

## Blast Radius

**Question:** If a proposed capability or delegation change existed, what becomes reachable?

- Inputs: actor identity, hypothetical extra/removed capabilities, optional target, graph budget.
- Outputs: reachable capabilities, newly reachable, lost capabilities, delegation identities, bounded transitive paths, policy version boundary, truncation flags.
- Source: `DelegationRepository.get_org_graph`, `load_effective_authority`, `PolicyRepository`.
- Deterministic, tenant-scoped, cycle-safe traversal with `GraphQueryBudget`.

## Mission Simulator

**Question:** Would a multi-step mission be allowed step-by-step?

Each step is classified independently: `ALLOW`, `DENY`, `APPROVAL_REQUIRED`, `UNKNOWN`, `UNREACHABLE`.

Uses `Policy.evaluate` and effective capability sets. No MCP/network calls.

## Shadow Mode

**Question:** What would WhitePact have decided?

Shadow observations are labeled `non_authoritative` and `simulated`. Optional in-process
`PersistedShadowRecord` storage is distinct from execution evidence and cannot satisfy approvals.

## Policy Lab

- `validate_policy_rules` — lint structural issues.
- `run_policy_tests` — engine-backed expectations (PASS from evaluation, not hardcoded).
- `diff_policy_candidate` — added/removed/modified rules.
- `simulate_policy_candidate` — baseline vs candidate effects per action type.

## Zero-Effect Guarantee

Operations are wrapped with `@zero_effect_operation`. Consequential boundaries call
`record_consequential_invocation()` (authority kernel pre-effect CAS, synthetic counter).
Tests fail if simulators increment the consequential counter.

## UNKNOWN

Missing policy matches yield `UNKNOWN` mission steps. Graph budget exhaustion marks `unknown_paths`.

## Limits

Default graph budget: depth 8, 500 nodes, 2000 edges. Truncation is explicit in blast radius results.

## Tenant Isolation

All repository-backed simulators require matching `SovereignContext.organization_id`.
