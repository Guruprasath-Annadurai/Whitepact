# Launch Cell B — Supported Production Topology (B2)

Vendor-neutral reference architecture for operating WhitePact in production.

## Components

| Tier | Component | Role |
|------|-----------|------|
| Edge | TLS ingress / load balancer | Terminates TLS; routes to dashboard (8765) and MCP HTTP (8766) |
| App | Dashboard Deployment | FastAPI + static UI; `WHITEPACT_WORKERS` ≥ 1 |
| App | MCP HTTP Deployment | Governed MCP transport; separate HPA/PDB from dashboard |
| Data | PostgreSQL | System of record; **no SQLite** in production |
| Cache | Redis | Distributed rate limits + multi-replica safety |
| Ops | Helm pre-upgrade migration Job | Single-writer Alembic upgrades (`config.autoMigrate=false` when replicas > 1) |
| Ops | Logical backup target | Operator object store / volume (see `scripts/backup-postgres.sh`) |
| Identity | External OIDC/SAML | Dashboard transport auth (see B1 auth contract) |
| Observability | OTLP collector (optional) | Traces/metrics export |

## Network boundaries

- Postgres and Redis are **cluster-internal** (compose internal network or K8s NetworkPolicy).
- MCP ingress is a separate Service from dashboard HTTP.
- No `hostNetwork`, no `hostPath`, no privileged pods (enforced in Helm `securityContext`).

## Replica safety

- `replicaCount` / HPA min ≥ 2: requires `config.redisUrl` and `migration.enabled` with `autoMigrate=false`.
- PodDisruptionBudget `minAvailable: 1` on dashboard and MCP.

## Validation

```bash
python -m responsibleai.operations.helm_validate helm/rai-governance/values-production.yaml
helm lint helm/rai-governance/ -f helm/rai-governance/values-production.yaml
```

Evidence: `tests/production/test_helm_production_contract.py` (CI_VERIFIED + CONTAINER_TESTED static review).
