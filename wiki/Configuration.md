# Configuration

All configuration is via environment variables. Copy `.env.example` to `.env` and edit.

---

## Database

| Variable | Default | Description |
|---|---|---|
| `RAI_DB_URL` | *(unset)* | Full SQLAlchemy URL. Takes priority over `RAI_DB_PATH`. Examples: `postgresql://user:pass@host:5432/db`, `sqlite+aiosqlite:///governance.db` |
| `RAI_DATABASE_URL` | *(unset)* | Alias for `RAI_DB_URL` (Heroku-style) |
| `RAI_DB_PATH` | `governance.db` | SQLite file path. Use `:memory:` for ephemeral. Ignored when `RAI_DB_URL` is set |

---

## Authentication

| Variable | Default | Description |
|---|---|---|
| `RAI_AUTH_ENABLED` | `true` | Set `false` to disable auth (development only) |
| `RAI_API_KEYS` | *(empty)* | Comma-separated Bearer tokens. When empty and auth is enabled, all requests return 403 |
| `RAI_OIDC_ISSUER` | *(unset)* | OIDC provider issuer URL (e.g., `https://company.okta.com`) |
| `RAI_OIDC_JWKS_URI` | *(unset)* | JWKS endpoint for JWT validation |
| `RAI_OIDC_AUDIENCE` | *(unset)* | Expected `aud` claim in JWT |

---

## Rate limiting

| Variable | Default | Description |
|---|---|---|
| `RAI_RATE_LIMIT_DEFAULT` | `100/minute` | Rate limit per API key (not global). Format: `{count}/{period}` where period is `second`, `minute`, `hour` |
| `RAI_REDIS_URL` | *(unset)* | Redis URL for distributed rate limiting. When unset, limits are in-memory and reset on restart |

---

## Governance thresholds

| Variable | Default | Description |
|---|---|---|
| `RAI_ALERT_THRESHOLD` | `5.0` | Trust score drop (points) that triggers a `drift_alert` webhook event |
| `RAI_MONTHLY_BUDGET_USD` | `10000.0` | Monthly AI spend limit. Triggers `budget_exceeded` event when crossed |

---

## Server

| Variable | Default | Description |
|---|---|---|
| `RAI_HOST` | `127.0.0.1` | Bind address |
| `RAI_PORT` | `8765` | Port |
| `RAI_ALLOWED_ORIGINS` | `*` | CORS allowed origins, comma-separated |

---

## Logging

| Variable | Default | Description |
|---|---|---|
| `RAI_LOG_LEVEL` | `INFO` | Log level: `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `RAI_LOG_JSON` | `true` | Structured JSON logs via structlog. Set `false` for human-readable console output |

---

## OpenTelemetry

| Variable | Default | Description |
|---|---|---|
| `RAI_OTEL_ENDPOINT` | *(unset)* | OTLP HTTP endpoint (e.g., `http://otel-collector:4318`). When unset, telemetry is disabled |
| `RAI_OTEL_SERVICE_NAME` | `responsibleai` | Service name reported in traces and metrics |

---

## Example `.env`

```bash
# Database
RAI_DB_URL=postgresql://rai_user:secret@postgres:5432/responsibleai

# Auth
RAI_AUTH_ENABLED=true
RAI_API_KEYS=sk-rai-prod-aaaa,sk-rai-svc-bbbb

# Rate limiting (distributed)
RAI_REDIS_URL=redis://redis:6379/0
RAI_RATE_LIMIT_DEFAULT=200/minute

# Governance
RAI_ALERT_THRESHOLD=5.0
RAI_MONTHLY_BUDGET_USD=25000.0

# Logging
RAI_LOG_LEVEL=INFO
RAI_LOG_JSON=true

# Observability
RAI_OTEL_ENDPOINT=http://otel-collector:4318
RAI_OTEL_SERVICE_NAME=responsibleai-prod
```
