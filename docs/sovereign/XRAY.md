# Sovereign X-Ray

X-Ray builds an **authority topology graph** from canonical WhitePact persistence:

- `OrgRepository`, `PolicyRepository`, `OrgAuthorityCeilingRepository`
- `DelegationRepository.get_org_graph()`
- `EvidenceRepository.list_for_org()` (bounded sample)

## Guarantees

- Stable node and edge IDs (deterministic sort order)
- Mandatory edge provenance (`derivation`, `source`, `explanation`, optional `fact_refs`)
- Tenant isolation via org-scoped repository queries
- Bounded traversal (`GraphQueryBudget`: depth, nodes, edges)
- Cycle detection during delegation forest walk (marks graph `truncated`)

## Non-goals

- X-Ray does **not** mint authority or infer reachability without delegation facts
- Transitive `CAN_CALL` edges are derived only from persisted `granted_action_types`
