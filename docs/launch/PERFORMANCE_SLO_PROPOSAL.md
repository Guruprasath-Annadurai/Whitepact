# Performance SLO proposal

These targets are not approved and are not release gates. The owner
must accept the workload assumptions before they become gates.

No security check, log, or evidence write may be disabled to meet them.

## Proposed workloads

| Workload | Proposed p50 | Proposed p95 | Proposed p99 | Notes |
| --- | --- | --- | --- | --- |
| Authorization kernel, one tenant, no database | 1 ms | 5 ms | 10 ms | In-process `WhitePactRuntimeGateway.evaluate` only |
| Database-backed governed decision | 25 ms | 80 ms | 150 ms | PostgreSQL, one replica, warm pool |
| HTTP API evaluate | 40 ms | 120 ms | 250 ms | Authenticated request, evidence write included |
| MCP governed tool call | 50 ms | 150 ms | 300 ms | Authorization plus metering, no model inference |
| Controlled container execution | 500 ms | 2 s | 5 s | Image already local, `--network=none` |

Capacity assumption, also unapproved: 50 concurrent agents, 10 tenants,
2 application replicas, PostgreSQL 16, Redis 7, error rate under 0.1%
for 30 minutes. This is not a promise of infinite scale.

## What was measured on this candidate

`scripts/bench_authorization_layers.py` ran 2000 allow and 2000 deny
decisions in one process. Guardrails and authority checks stayed on.
Both decision classes were correct for every iteration.

The run recorded about 0.006 ms allow p50, 0.007 ms allow p95, and
0.008 ms allow p99, near 150,000 calls per second, one tenant, no
database, no HTTP, and no MCP. RSS was about 32 MB. That number is an
in-process microbenchmark. It does not meet or replace an HTTP, MCP, or
container SLO.

The earlier HTTP figures (about 37.6 ms p50, 103.4 ms p95, 126.1 ms
p99, 400 requests/second) remain local ASGI results from a previous
tree. They were not reproduced here and are not production capacity.

Database-backed latency, MCP overhead, approval issuance, multi-replica
HTTP, soak, and recovery-under-load were not measured on this tree.

## Reproduction

```bash
python scripts/bench_authorization_layers.py \
  --output /tmp/authorization-kernel-bench.json
```

`docs/launch/evidence/authorization-kernel-bench.json` records
`source_commit` `3dc209352032fc48110645935717ab7bff673f8b`. The commit
that adds the JSON is a later documentation commit. Re-run the command
on the exact tree under review. The numbers are not an approved SLO.
