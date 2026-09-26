# WhitePact Formula — Authority Algebra v0.1 (Gate 2 implementation)

## Multiple grants

Independent grants **union** into `AuthorityTuple` atoms (action × resource × purpose × risk_ceiling × grant_id).

**Not intersection** — RoleA READ X + RoleB WRITE Y yields both permissions.

## Constraints applied after union

1. `OrgAuthorityCeilingModel` — filters actions/resources/risk  
2. `ExplicitDeny` — removes matching tuples (**deny wins**)  
3. Per-grant context matching at evaluation time  

## Delegation

`validate_delegation(parent, child)` requires `authority_subset(child, parent)` on all dimensions.

## Authority creation

Only via `AuthorityCreationEvent` with `issuer_can_grant` — not capability, inference, or coalition.

## Conservation (Gate 2 result)

**AUTHORITY CONSERVATION PARTIALLY ESTABLISHED — UNPROVEN CASES REMAIN**

- **Established:** delegation-only transitions cannot widen any grant dimension (`authority_subset` + tests).  
- **Established:** self-issued grants rejected; weak issuer cannot mint.  
- **Unproven:** full store mutation under concurrent revoke, break-glass, policy composition edge cases.
