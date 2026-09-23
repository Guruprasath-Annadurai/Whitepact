# Production configuration baseline

Production is identified by `WHITEPACT_ENV=production` or `RAI_ENV=production` (see `dashboard/config.py`).

## Fail-closed rules (SOURCE-CODE VERIFIED)

| Requirement | Enforcement |
|-------------|-------------|
| PostgreSQL URL only | `Settings._enforce_production_database` |
| Field encryption key | `WHITEPACT_FIELD_ENCRYPTION_KEY` or `RAI_FIELD_ENCRYPTION_KEY` required |
| No Phase7A dispatcher in prod | `refuse_production_phase7a` |
| No conflicting DB URL env vars | Raises in production |
| Paddle env consistency | Paddle validator on settings |
| Hosted MCP preflight | `mcp/server.py` `hosted_production_preflight` |
| OIDC/WebAuthn placeholders rejected | `enterprise/security/preflight.py` |
| Legacy plaintext ciphertext | Disallowed in production (`db/encryption.py`) |

## Prohibited insecure combinations (non-exhaustive)

- `WHITEPACT_OIDC_SKIP_VERIFICATION=1` in production  
- `WHITEPACT_OIDC_ALLOW_RAW_ID_TOKEN=1` in production  
- SQLite `database_url` in production  
- Missing field encryption key in production  
- Placeholder session secrets when WebAuthn/OIDC enabled  

## Customer / deployer responsibilities

- Inject secrets via platform secret store (not git)  
- Configure TLS termination and HSTS at edge  
- Operate Postgres backups and test restores (see DR report)  
- Set `WHITEPACT_FIELD_ENCRYPTION_KEY` before storing tenant secrets  

See `DEPLOY_RUNBOOK.md` for operational steps.
