# WhitePact Production Configuration Contract

**Source of truth:** `src/responsibleai/dashboard/config.py` (`Settings`)  
**Validator CLI:** `python -m responsibleai.operations.config_validate [--expect-production]`  
**Auth contract:** `responsibleai.operations.auth_contract` (`validate_dashboard_auth`, OIDC/SAML completeness; VC issuers are **MCP transport only**, not dashboard HTTP auth)  
**Startup gate:** `assert_hosted_enterprise_boot_safe()` → `operations.preflight.assert_production_configuration_safe()` shares `collect_production_configuration_errors()` with the CLI validator

## Environment model

| Environment | `WHITEPACT_ENV` / `RAI_ENV` | Notes |
|-------------|----------------------------|--------|
| LOCAL | `development`, `local` | SQLite default allowed |
| TEST | `test` | Pytest fixtures |
| CI | `ci` / `development` | Matrix in `.github/workflows/ci.yml` |
| STAGING | `staging` | Should mirror production **shape** |
| PRODUCTION | `production` or `prod` | **Explicit only** — never inferred |
| DISASTER_RECOVERY | `disaster_recovery` (recommended) | Same validators as production |

## Variable classes

| Class | Examples |
|-------|----------|
| **REQUIRED (production)** | `DATABASE_URL` (PostgreSQL), `WHITEPACT_FIELD_ENCRYPTION_KEY`, dashboard auth (complete OIDC or SAML — not static API keys; not VC-only) |
| **OPTIONAL_WITH_SAFE_DEFAULT** | `WHITEPACT_LOG_JSON=true`, rate limit strings |
| **DEVELOPMENT_ONLY** | SQLite `db_path`, `auth_enabled=false`, `allow_all_origins=true` |
| **PRODUCTION_FORBIDDEN** | See `PRODUCTION_FORBIDDEN_FLAGS` in `operations/production_contract.py` |
| **SECRET** | API keys, Redis password, encryption key, webhook HMAC, OIDC client secret |
| **NON_SECRET** | `WHITEPACT_ENV`, `PUBLIC_BASE_URL`, OTEL endpoint URL |

## Production fail-closed rules (implemented)

- No SQLite in `production`/`prod`.
- Conflicting `DATABASE_URL` variants forbidden in production.
- Field encryption key required in production.
- Paddle env must match API key prefix.
- MCP hosted production preflight (`mcp/server.py`).

## Executable tests

- `tests/test_config.py` — production database and encryption
- `tests/production/test_launch_cell_b_contract.py` — contract smoke
- `tests/production/test_production_auth_contract.py` — OIDC/SAML/VC-MCP auth matrix
- `tests/production/test_production_startup_preflight.py` — CLI vs startup equivalence
- `tests/test_enterprise_layer2_identity_security.py` — preflight placeholders

## Reference files

- `.env.prod.example` / `DEPLOYMENT.md` / `DEPLOY_RUNBOOK.md`
