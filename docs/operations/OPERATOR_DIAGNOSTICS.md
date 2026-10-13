# Operator Diagnostics

## Safe endpoints

| Endpoint | Purpose |
|----------|---------|
| `GET /api/health` | Version, module list, DB backend (may be 503 if DB down) |
| `GET /readyz` | Traffic admission |
| `GET /api/restore/status` | Restore gate |
| `python -m responsibleai.operations.config_validate` | Config contract |

## Diagnostic bundle (support-safe)

Include:

- `version`, `environment`, schema/migration head
- Health summary JSON
- Recent error **codes** (not payloads)

Exclude:

- API keys, cookies, tokens, encryption keys, customer payloads

## Multi-replica check

If `WHITEPACT_WORKERS` or replica count > 1, verify Postgres + Redis per `multi_replica_problems()`.
