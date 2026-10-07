# Observability and alerting (staging plan)

## Logging

- Enable `WHITEPACT_LOG_JSON=true` / `RAI_LOG_JSON=true` in staging `.env.prod`.
- Ship logs: journald + optional Vector/Fluent Bit → (future) Loki or Cloudflare Logpush — **document chosen path at deploy**.
- Correlation: request ID middleware (`dashboard/middleware.py`); tie to OTEL trace ID when enabled.

## OpenTelemetry

- Configure existing OTEL env vars (see deployment docs) to staging collector.
- **Invariant:** exporter outage must not bypass authorization (qualified in M4/M6 tests; re-verify on staging).

## Metrics

- Do not expose unauthenticated `/metrics` on public LB.
- If Prometheus scrape is required, bind to private network + mTLS or SSH tunnel.

## Signal hooks

`scripts/cloud/gate2/health_signals.sh` prints JSON for backup age, backup failure, restore-drill failure, origin TLS failure, disk threshold, database connectivity, application health, and execution-service health. `condition_met` is an engineering result. The script sets `alerts_dispatched` to false. It does not claim a pager, webhook, or paid monitor is active.

## Alerts (minimum)

| Signal | Tool (low-cost) | Action |
|--------|-----------------|--------|
| `/livez` down | External uptime (Gate 2+) | Page operator |
| Backup script exit ≠ 0 | Cron email / webhook | Run backup runbook |
| Disk > 85% | node exporter or `df` cron | Expand volume |
| 5xx rate | LB metrics / app logs | Incident runbook |
| TLS expiry | CF dashboard | Renew origin cert |

## Health endpoints (canonical)

| Path | Meaning |
|------|---------|
| `/livez`, `/healthz` | Process alive |
| `/readyz` | Dependencies ready |
| `/api/health` | API health (may include dependency detail — restrict at edge) |
