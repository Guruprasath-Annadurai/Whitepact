# WhitePact Initial SLO Policy (B6)

**Status:** TARGET values for launch qualification — not GUARANTEED until measured in production.

| SLI | TARGET (launch) | MEASURED | Notes |
|-----|-----------------|----------|-------|
| Dashboard availability | 99.5% monthly | NOT_TESTED in prod | Based on `/livez` + `/readyz` semantics |
| API success rate (non-4xx) | 99.0% | NOT_TESTED in prod | Excludes client errors |
| p95 dashboard latency | < 800ms | See `artifacts/production/b9-load-smoke.json` | TestClient smoke only |
| p99 dashboard latency | < 1500ms | See B9 artifact | Environment-specific |
| Backup job success | 100% per schedule | NOT_TESTED | Operator cron |
| Restore rehearsal | PASS quarterly | See `artifacts/production/b4-restore-rehearsal.json` | Disposable PG only |

Alerts: `artifacts/production/alerts.catalog.json`
