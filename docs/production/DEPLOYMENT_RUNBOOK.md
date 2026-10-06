# Deployment Runbook (summary)

Full detail: `DEPLOY_RUNBOOK.md`, `DEPLOYMENT.md`.

## Release lifecycle

1. Merge to `main` only after CI + review (not performed by Launch Cell B).
2. Build immutable image: `docker build` → record digest.
3. Run migrations: Helm `job-migration` or `alembic upgrade head`.
4. Deploy dashboard + MCP with pinned digest.
5. Post-deploy: `/readyz`, `/api/health`, synthetic auth + evaluate.

## Compose (small hosted)

```bash
cp .env.prod.example .env.prod
docker compose -f docker-compose.prod.yml --env-file .env.prod up -d
```

Place TLS-terminating reverse proxy in front; do not expose Postgres/Redis ports publicly.

## Kubernetes

```bash
helm upgrade --install rai ./helm/rai-governance -f values.prod.yaml
```

Verify probes: `/livez`, `/readyz`.

## Immutable artifacts

Pin **container digest**, **git SHA**, **SBOM** from CI reproducible-build job when available.
