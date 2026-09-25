# Production-shaped performance (LOCAL-CONTAINER)

Environment label: **LOCAL-CONTAINER** (PostgreSQL + single uvicorn worker)

Target: `http://127.0.0.1:19595/api/health`

| concurrency | samples | errors | p50 | p95 | p99 | max | est rps |
|---:|---:|---:|---:|---:|---:|---:|---:|
| 1 | 50 | 0 | 17.93 | 23.54 | 27.12 | 27.12 | 1843.83 |
| 10 | 50 | 0 | 183.23 | 475.21 | 484.35 | 484.35 | 103.23 |
| 25 | 50 | 0 | 409.86 | 487.78 | 507.17 | 507.17 | 98.59 |
| 50 | 30 | 0 | 463.19 | 527.03 | 565.99 | 565.99 | 53.0 |
| 100 | 30 | 0 | 697.37 | 792.26 | 792.52 | 792.52 | 37.85 |

Not production-scale. Governance/evidence/MCP paths not fully swept in this harness.
