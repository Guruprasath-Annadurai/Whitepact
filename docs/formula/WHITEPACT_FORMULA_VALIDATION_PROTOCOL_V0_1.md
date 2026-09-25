# WhitePact Formula — Validation Protocol v0.1

How later gates will test the formal model. **No harness in Gate 1.**

---

## Validation classes

| Class | Purpose | Applies to |
|-------|---------|------------|
| V1 Formal invariant tests | Grant algebra, nesting sets | Axioms, INV-* |
| V2 Property-based tests | Random grants/delegations | PO-*, conservation |
| V3 Simulation scenarios | τ and F_H on small worlds | SFE, futures |
| V4 Adversarial corpus | T1–T18 inspired inputs | Threat model |
| V5 Differential tests | Replay judgment hash | H8 |
| V6 Fuzzing | Graph + action fuzz | Capability closure |
| V7 Concurrency | Revoke during eval (scenario N) | Semantics |
| V8 Performance | Deadline, budgets | H10 |
| V9 Real integration | Shadow mode vs V1 | Non-regression |
| V10 External peer review | Math + security | Gate 1 docs |

---

## Concept → test mapping

| Concept | Primary classes |
|---------|-----------------|
| Authority lifecycle | V1, V2, V7 |
| Capability closure | V2, V6, V3 |
| Future envelope | V3, V5 |
| Trust UNKNOWN | V1, V4 |
| Lost ack | V3, B10 |
| Coalition | V3, B7 |
| Intent advisory | V4, B6 |
| Min sufficient authority | V3, B5 |

---

## Benchmark families B1–B12 (schema)

Each benchmark record:

```yaml
benchmark_id: B#
name: string
initial_state: W_0 reference (tenant, graph_version, grants, capabilities)
authority: grant set summary
capabilities: direct + known closure seed
action: α_requested
expected:
  reachable_paths: list (informative)
  violations: list (authority, policy, latent)
  judgment: J_Ω expected (may be set)
horizon: H
notes: assumptions
```

### Family descriptions

| ID | Family |
|----|--------|
| B1 | Simple tool agent |
| B2 | MCP agent |
| B3 | Coding agent |
| B4 | Cloud operator |
| B5 | Financial workflow |
| B6 | Enterprise copilot |
| B7 | Multi-agent coalition |
| B8 | Secret-discovery chain |
| B9 | Stale authorization |
| B10 | Lost-ack external mutation |
| B11 | Cross-tenant attack |
| B12 | Irreversible publication |

### Example stub (B9)

```yaml
benchmark_id: B9
name: stale_authorization
initial_state:
  tenant_id: T-example
  graph_version: gv-001
  grants:
    - grant_id: g1
      valid_until: "2026-01-01T00:00:00Z"
  clock: "2026-06-01T12:00:00Z"
action:
  type: external_transfer
expected:
  violations: [PO-TEMPORAL, PO-GRANT]
  judgment: DENY
```

---

## Exit criteria for future implementation gates

Implementation may proceed only when V1–V5 pass on agreed corpus for the implemented subset; V8 meets SLO; V9 shows no V1.3.1 regression in shadow mode.

---

## Gate 1

Defines protocol only — no test code added to repository.
