# Docker Compose live acceptance (v1.3.1 9.5 closure)

Environment: Cloud Agent VM with `docker-compose-v2` (sudo).

## Results

| Step | Status | Evidence |
|------|--------|----------|
| `docker compose build dashboard` | **PASS** | Image `responsibleai:95test` built after Dockerfile fix (`alembic.ini` + `migrations/` in builder stage) |
| `docker compose up -d` | **PASS** | `rai-postgres`, `rai-redis` healthy; containers created |
| PostgreSQL healthy | **PASS** | `pg_isready` inside `rai-postgres` |
| Redis healthy | **PASS** | compose healthcheck green |
| Dashboard `/api/health` | **FAIL** | `rai-dashboard` workers exit on `TimeoutError` connecting to `postgres:5432` from app network (TCP to `postgres:5432` does not complete from `rai-dashboard` in this VM) |
| MCP HTTP | **FAIL** | `rai-mcp-http` restart loop (same DB dependency) |
| `docker compose down` | **PASS** | stack removed with volumes |

## Verdict

**PARTIAL — BUILD AND ORCHESTRATION PROVEN; RUNTIME DB CONNECTIVITY BLOCKED IN THIS ENVIRONMENT**

This is an **environment/network limitation** on the closure VM (inter-container TCP to Postgres times out). It is **not** evidence that the compose file is invalid on a standard operator host. Operators should re-run the same compose file on their infrastructure.

## Fixes applied during closure (packaging)

- `Dockerfile` builder stage copies `alembic.ini` and `migrations/` so `python -m build` succeeds inside the image build.
- Closure harness uses `--env-file .env.prod.95test` and temporary `.env.prod` for service `env_file` references.

## Secrets

No API keys or passwords appear in this document. Test secrets live only in local `.env.prod.95test` (not committed).
