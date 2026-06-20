# Deployment Guide — ResponsibleAI v0.5.0

## Quick start (Docker Compose)

```bash
git clone https://github.com/Guruprasath-Annadurai/ResponsibleAi.git
cd ResponsibleAi

# Generate an API key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"

# Configure environment
cp .env.example .env
# Edit .env — set RAI_API_KEYS to your generated key

docker compose up -d
```

Dashboard will be available at `http://localhost:8765`.
API docs at `http://localhost:8765/api/docs`.

---

## Environment variables

All settings are prefixed with `RAI_`. See [.env.example](.env.example) for the full list.

| Variable | Default | Description |
|---|---|---|
| `RAI_DB_PATH` | `~/.responsibleai/data.db` | SQLite file path |
| `RAI_API_KEYS` | _(empty = auth off)_ | Comma-separated API keys |
| `RAI_AUTH_ENABLED` | `true` | Toggle auth enforcement |
| `RAI_RATE_LIMIT_DEFAULT` | `100/minute` | Global rate limit |
| `RAI_RATE_LIMIT_EVALUATE` | `30/minute` | Evaluation endpoint limit |
| `RAI_ALLOWED_ORIGINS` | localhost only | CORS allowed origins |
| `RAI_ALLOW_ALL_ORIGINS` | `false` | CORS wildcard (dev only) |
| `RAI_ALERT_THRESHOLD` | `5.0` | Drift alert threshold (points) |
| `RAI_MONTHLY_BUDGET_USD` | `10000.0` | Budget limit (USD/month) |
| `RAI_LOG_LEVEL` | `INFO` | `DEBUG`/`INFO`/`WARNING`/`ERROR` |
| `RAI_LOG_JSON` | `true` | Structured JSON logs |
| `RAI_HOST` | `127.0.0.1` | Bind address (`0.0.0.0` in Docker) |
| `RAI_PORT` | `8765` | Listen port |
| `RAI_WORKERS` | `1` | Uvicorn worker count |

---

## Bare-metal install

```bash
python3 -m venv .venv
source .venv/bin/activate

pip install "biasbuster[dashboard]"
# or from source:
pip install -e ".[dashboard]"

# Configure
cp .env.example .env && nano .env

# Run
uvicorn responsibleai.dashboard.app:app \
    --host 0.0.0.0 --port 8765 --workers 2
```

---

## Authentication

The API uses Bearer token authentication. Set `RAI_API_KEYS` to one or more keys:

```bash
# Generate a key
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# → abc123def456...

# Set in .env
RAI_API_KEYS=abc123def456...

# Use in requests
curl -H "Authorization: Bearer abc123def456..." \
     http://localhost:8765/api/health
```

The root `/` and `/api/health` endpoints are publicly accessible (no auth required).

---

## Reverse proxy (nginx)

```nginx
server {
    listen 443 ssl;
    server_name ai-governance.example.com;

    ssl_certificate     /etc/ssl/certs/your.crt;
    ssl_certificate_key /etc/ssl/private/your.key;

    location / {
        proxy_pass http://127.0.0.1:8765;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        client_max_body_size 10m;
    }
}
```

---

## Persistent storage

The SQLite database is stored at `RAI_DB_PATH` (default: `~/.responsibleai/data.db`).
In Docker, this maps to the `rai-data` volume.

Enable WAL mode for better concurrent read performance (already set by CostTracker and TrustDriftMonitor):

```sql
PRAGMA journal_mode=WAL;
PRAGMA synchronous=NORMAL;
```

To export a backup:

```bash
sqlite3 /data/responsibleai.db ".backup /tmp/backup.db"
```

---

## Health checks

```bash
# Simple health
curl http://localhost:8765/api/health

# Metrics (requires auth)
curl -H "Authorization: Bearer <key>" http://localhost:8765/api/metrics
```

Response fields: `status`, `uptime_seconds`, `checks.database`, `checks.auth`, `modules`.

---

## PyPI install

```bash
pip install biasbuster                      # core only
pip install "biasbuster[dashboard]"         # + governance API
pip install "biasbuster[all]"               # + all provider integrations
```

---

## Upgrading

```bash
# Docker
docker compose pull && docker compose up -d

# Bare metal
pip install --upgrade "biasbuster[dashboard]"
```

Database schema migrations run automatically on startup via `CREATE TABLE IF NOT EXISTS`.
