# Stranger integration (documentation-only path)

Engineer used: `docs/PACKAGE_IDENTITY.md`, `README.md`, `docker-compose.prod.yml` headers.

| Step | Result |
|------|--------|
| Identify package name | **PASS** — `rai-governance-platform` |
| Install command | **PASS** — `pip install "rai-governance-platform[dashboard,postgres]"` |
| Import | **PASS** — `import responsibleai` |
| Migrate without checkout | **PARTIAL** — wheel now ships `alembic.ini` + `migrations/` (9.5 closure packaging) |
| Boot dashboard | **NOT PROVEN** without reading compose/env examples |
| Full pilot without founder | **NOT PROVEN** |

Hidden assumptions noted: `.env.prod` secrets, Postgres/Redis for prod compose, Paddle for billing.
