# WhitePact Production Architecture (Launch Cell B)

## Topology

```
                         INTERNET
                            |
                       TLS / EDGE
                     (operator-owned)
                            |
                     LOAD BALANCER
                            |
            +---------------+---------------+
            |                               |
      DASHBOARD / API                   MCP SERVICE
      (uvicorn :8765)                  (:8766 HTTP)
            |                               |
            +---------------+---------------+
                            |
                 GOVERNANCE RUNTIME
         (policy, authority kernel, execution grants)
                            |
            +---------------+---------------+
            |               |               |
       PostgreSQL         Redis         Object store
     (authoritative)   (rate limits,    (future evidence
                       optional cache)   blobs if used)
                            |
                   EVIDENCE / AUDIT TABLES
                            |
              BACKUP (pg_dump scripts) / DR site
```

## Planes

| Plane | Components | Exposure |
|-------|------------|----------|
| **Control** | Migrations, Helm releases, config maps, feature flags | Operator/K8s only |
| **Data** | Postgres, encrypted columns, audit/evidence tables | Internal network |
| **Execution** | MCP tool dispatch, isolation broker, upstream gateway | Authenticated clients |
| **Observability** | structlog JSON, OTEL export, Prometheus hooks | Internal collectors |
| **Admin/operator** | `/api/restore/*`, diagnostics, support exports | Authenticated + auditable; never public anonymous |

## Authority doctrine in production

- No path may skip governance for consequential MCP tools in hosted mode.
- Restore admission gate blocks traffic until post-restore reconciliation (`backup_defense`).
- Caching and failover must not resurrect revoked grants (enforced in application layer; multi-replica requires Postgres + Redis).

## Multi-replica requirements

`multi_replica_problems()` in `dashboard/config.py` documents:

- **PostgreSQL** required (not SQLite).
- **Redis** required for shared rate limits.

## Formula Ω∞ (future)

Infrastructure must expose version, health, metrics, and rollback without bypassing Formula semantics. Rollout modes are defined in `responsibleai.operations.production_contract.FormulaRolloutMode` (not active on Gate 3 main).
