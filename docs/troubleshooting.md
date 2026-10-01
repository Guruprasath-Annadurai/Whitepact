# Troubleshooting

Canonical guide for real failure modes in this repository. Messages vary slightly
by version; search logs for the `reason` / `detail` field from FastAPI responses.

## Startup failure

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `ModuleNotFoundError: responsibleai` | Package not installed | `pip install -e ".[dashboard]"` from repo root |
| Uvicorn exits on import | Missing optional extra | Install matching extra from `pyproject.toml` |
| `WHITEPACT_ENV=production` boot error | Missing field encryption key | Set `WHITEPACT_FIELD_ENCRYPTION_KEY` / `RAI_FIELD_ENCRYPTION_KEY` per `.env.example` |
| Port bind error | `8765` in use | Change `RAI_PORT` or stop conflicting process |

## Database connectivity

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| SQLite permission denied | `RAI_DB_PATH` not writable | Fix path permissions or use Docker volume |
| Postgres connection refused | `RAI_DATABASE_URL` wrong | Verify host, TLS, credentials; install `[postgres]` extra |
| Migration errors on start | Schema drift | Run Alembic migrations (`alembic upgrade head`) or Helm migration job |

## Configuration failure

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Settings validation error at import | Invalid env type | Cross-check `.env` against `.env.example` |
| CORS errors in browser | Origin not allowed | Set `RAI_ALLOWED_ORIGINS` or dev-only `RAI_ALLOW_ALL_ORIGINS=true` |
| Rate limit 429 | `slowapi` limits | Adjust `RAI_RATE_LIMIT_*` or backoff |

## Invalid credentials

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| HTTP 401 | Missing/invalid `Authorization: Bearer` | Add key from dashboard; check `RAI_API_KEYS` |
| MCP initialize auth failure | Wrong bearer on HTTP transport | Regenerate org-scoped key |

## Invalid authority

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `AuthorityDenied` in Python resolver | No delegation / consent / root | Grant via `DelegationRepository` or HTTP delegations API |
| `DelegationEscalationError` | Grant exceeds parent | Narrow `granted_action_types` or constraints |
| HTTP 400 "org-scoped API key" | Legacy flat key on governance route | Use org-scoped key |

## Expired grant

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Previously allowed action denied | `expires_at` passed | Re-grant with new expiry |
| Consent/root expiry | Time-bound proof | Renew consent/root records (`test_phase1_authority.py` patterns) |

## Revoked grant

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| Denied after admin revoke | `revoke_branch` cascaded | Expected; re-delegate if still needed |
| Stale ALLOW with old `AuthorityContext` | Caller cached context | Reload via `get_effective_authority()` / MCP dispatch |

## Policy denial

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `DENY` with policy reason codes | Org policy rule match | Inspect `GET /api/governance/policy` |
| Composition violation | Workflow sequence rule | See `tests/test_workflow_authority.py` |

## Tenant mismatch

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| `ValueError` on `GovernanceContext` | Agent `org_id` ≠ key org | Align identity org with API key org |
| Empty evidence for agent | Wrong org filter | Query with correct `org_id` |

## MCP connection issue

| Symptom | Likely cause | What to do |
|---------|--------------|------------|
| stdio server not listed | Client config path | Verify `whitepact-mcp` on PATH |
| HTTP MCP 403/connection reset | Origin not in `RAI_MCP_HTTP_ALLOWED_ORIGINS` | Add client origin or use stdio locally |
| Tool count mismatch | Custom build | Expect **30** production tools |

## Port conflict

Docker Compose maps `8765:8765`. Change host port in `docker-compose.yml` or stop local uvicorn.

## Migration mismatch

Helm chart may run a migration Job; if dashboard version ≠ migration revision, check
`migrations/` and `alembic.ini` alignment with image tag.

## Health-check failure

```bash
curl -v http://127.0.0.1:8765/api/health
```

Docker: `docker compose ps` — unhealthy container often means app not listening or DB path missing.

## Getting more signal

- Structured logs: `RAI_LOG_JSON=true`, `RAI_LOG_LEVEL=DEBUG`
- Run focused tests: `pytest tests/test_workflow_authority.py -q`
- Integration smoke: `python scripts/integration_smoke.py` (MCP protocol)
