# Installation

Supported paths in this repository (do not mix undocumented flags):

| Path | When to use |
|------|-------------|
| **pip / editable install** | Development, quickstart scripts, unit tests |
| **PyPI** | Consumers who do not clone the repo |
| **Docker Compose** | Single-node demo/staging with persistent SQLite volume |
| **Helm** | Kubernetes deployment of dashboard + MCP workloads |

## Python (from source)

**Prerequisites:** Python 3.11+, `venv`, build tools for native wheels if needed.

```bash
git clone https://github.com/Guruprasath-Annadurai/Whitepact.git
cd Whitepact
python3 -m venv .venv && source .venv/bin/activate
pip install -U pip
pip install -e ".[dashboard]"          # API + dashboard
pip install -e ".[dashboard,mcp]"      # + MCP server entrypoints
pip install -e ".[dashboard,postgres]" # + PostgreSQL driver
```

**Health / first request (dashboard):**

```bash
uvicorn responsibleai.dashboard.app:app --host 127.0.0.1 --port 8765
curl -fsS http://127.0.0.1:8765/api/health
```

**Configuration:** copy `.env.example` → `.env`. Key variables are documented there
and summarized in [Troubleshooting — configuration](troubleshooting.md#configuration).

**First governed action (no HTTP):**

```bash
python examples/quickstart_stranger_authority.py
```

**Cleanup:** deactivate venv; remove `.venv` if desired.

## Python (PyPI)

```bash
pip install "rai-governance-platform[dashboard]"
```

Import name remains `responsibleai`. See [`docs/PACKAGE_IDENTITY.md`](PACKAGE_IDENTITY.md).

## Docker

**Prerequisites:** Docker Engine, Compose v2, free port **8765**.

```bash
cp .env.example .env
docker compose up --build -d
```

| Check | Command |
|-------|---------|
| Health | `curl -fsS http://127.0.0.1:8765/api/health` |
| Logs | `docker compose logs -f dashboard` |

**Configuration:** `env_file: .env` in `docker-compose.yml`; `RAI_DB_PATH=/data/responsibleai.db`.

**Common failures:** port in use, missing `.env`, auth enabled without `RAI_API_KEYS` on protected routes.

**Cleanup:**

```bash
docker compose down        # keep data volume
docker compose down -v     # delete rai-data volume
```

## Helm

Chart: `helm/rai-governance/` (app version **1.3.1**).

**Prerequisites:** `kubectl` context (for real deploy), `helm` 3.x.

**Lint / render (no cluster required):**

```bash
helm lint helm/rai-governance
helm template demo helm/rai-governance \
  --set dashboard.replicaCount=1 \
  --set secrets.apiKeys="replace-me"
```

**Install (only when you operate a cluster):**

```bash
helm upgrade --install whitepact helm/rai-governance -n whitepact --create-namespace \
  -f your-values.yaml
```

Set secrets via Kubernetes secrets or external secret managers — never commit real keys.
See chart `values.yaml` for service ports, MCP deployment toggles, and migration job.

**Health:** hit the dashboard Service ingress/host on `/api/health` after deploy.

**First governed request:** org-scoped API key from the dashboard, then
`POST /api/governance/tools/call` (see [HTTP examples](examples/http_governance.md)).
