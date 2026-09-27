# SLI / SLO Policy (initial)

## SLIs (measurable)

| SLI | Definition |
|-----|------------|
| API availability | Ratio of successful `/readyz` checks |
| MCP availability | Successful MCP health + handshake |
| Decision latency | p95 `/api/evaluate` (staging) |
| Evidence persistence | Successful audit write / attempt |

## SLO targets (staging-first)

| SLO | Target | Evidence |
|-----|--------|----------|
| API monthly availability | 99.5% | **NOT_TESTED** |
| p95 evaluate latency | < 2s @ nominal load | **NOT_TESTED** |

## Error budget

When error budget exhausted for a release window: freeze feature deploys; prioritize rollback or hotfix; incident commander reviews.

Do not advertise five-nines.
