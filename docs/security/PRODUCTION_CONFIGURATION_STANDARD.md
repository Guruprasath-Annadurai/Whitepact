# Production Configuration Standard

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 9. `00_MASTER_READINESS_AUDIT.md`'s
Configuration row named the gap: a real, typed `Settings` class with
documented defaults already exists (`dashboard/config.py`), but the
specific *production* recommendation for each security-relevant field
was scattered across per-feature docstrings rather than living in one
place. This document consolidates it — every field named below is
real, taken directly from `Settings`, not invented.

This is a **recommendation and reference document**, not new
enforcement code. Where a setting is already fail-closed-enforced at
startup (`heart_production_gate.py`'s `verify_heart_production_enforcement()`,
`db/crypto_activation.py`), that's noted; where it's operator
discipline this document can only recommend, that's stated plainly
too.

## Required for any real production deployment

| Setting | Production value | Why |
|---|---|---|
| `auth_enabled` | `true` | Default is already `true` — confirmed directly (`Settings().auth_enabled == True` with no env override). Never set `false` outside local development. |
| `api_keys` (`RAI_API_KEYS`) | unset, or bootstrap-only | A flat legacy key is a cross-org super-admin credential (see `CREDENTIAL_SCOPING_AND_ROTATION.md`) — issue real org-scoped keys via `POST /api/orgs/{org_id}/keys` and stop relying on this once an org exists. |
| `enterprise_mode` | `true` for any deployment governing real agent/tool traffic | Gates Heart legitimacy enforcement (`heart_production_gate.py`) — fail-closed at startup if turned on incompatibly (see below), fail-open (Heart never consulted) if left off. This is the single highest-leverage flag in the whole config surface. |
| `mcp_governance_enabled` | `true` | **Required** alongside `enterprise_mode=true` — `verify_heart_production_enforcement()` raises `HeartEnforcementError` and refuses to start otherwise, specifically to prevent believing "enterprise_mode=true" means governance is active when the actual dispatch path was never wired to consult it. |
| `mcp_http_allow_unauthenticated_demo` | `false` | Same fail-closed startup check — incompatible with `enterprise_mode=true`. |
| `crypto_root_key` | a real 32-byte key, set once, backed up outside the app's own database | Required for field-level encryption to activate at all (`db/crypto_activation.py`). Losing this key makes every encrypted column permanently unreadable — back it up somewhere the database backup itself doesn't cover. |
| `database_url` | a real `postgresql://...` URL | SQLite (the default) is explicitly the self-hosted single-instance option — `SLA.md`'s own hosted tiers require Postgres + Redis (`docker-compose.prod.yml`). |
| `redis_url` | set for any multi-replica deployment | Required for `multi_replica` mode and for rate-limiting/plan-quota state to be shared across replicas rather than per-process (see `AuthFailureLimiter`'s and `PlanRateLimiter`'s own documented in-memory-per-replica limitation). |
| `allow_all_origins` | `false` | Set real `allowed_origins` instead — a wildcard CORS origin on an authenticated API is a real cross-origin credential-theft surface. |
| `log_json` | `true` | Structured logs are what every downstream log aggregator (and this codebase's own audit trail correlation via `request_id`) actually expects. |
| `log_level` | `INFO` (never `DEBUG` in production) | **Security-relevant, not just verbosity**: `logging_config.py`'s `configure_logging()` now explicitly caps `aiosqlite`/`asyncpg` at `INFO` regardless of the configured app level (Phase 9 fix, see below) — but the app's *own* structlog calls still honor whatever level is configured, and `DEBUG` is more verbose than any request-correlation need justifies in production. |

## Fail-closed startup checks that already exist (confirmed, not assumed)

- `verify_heart_production_enforcement()` (`governance/heart_production_gate.py`):
  refuses to start if `enterprise_mode=true` with `mcp_governance_enabled=false`,
  or with `mcp_http_allow_unauthenticated_demo=true` — both are exactly
  the "believes it's in production mode but the actual enforcement
  path was never wired" trap this function exists to prevent.
- `activate_production_crypto()` (`db/crypto_activation.py`): gates
  field-level encryption activation on `enterprise_mode` +
  `crypto_root_key`, fails closed if the key is malformed.
- `MaxBodySizeMiddleware` (Phase 18/19): rejects any request body over
  10 MB regardless of configuration — not a setting, always on.

## Secrets — where they live in `Settings`, and how each is scoped

Every `str | None` field in `Settings` ending in `_secret`, `_key`, or
`_token` is a real, distinct secret this platform may hold:
`crypto_root_key`, `oidc_client_secret`, `saml_session_secret`,
`stripe_secret_key`, `stripe_webhook_secret`, `alerts_webhook_token`,
`openai_apps_challenge_token`, and the four
`leaderboard_*_api_key` fields (third-party model-provider keys used
only for the public cross-model leaderboard feature, not this
platform's own auth). None of these should ever be committed to
version control, logged, or shared across environments (a staging
`crypto_root_key` must never be the same value as production's — see
`CREDENTIAL_SCOPING_AND_ROTATION.md` for the full credential-by-
credential breakdown of what each secret actually gates).

## Secrets-never-logged: verified coverage (Phase 9 extension)

`tests/test_crypto_activation.py::TestSecretsNeverAppearInLogs`
previously covered only the crypto root key / derived DEK. Extended
this phase to a real, executed sweep
(`tests/test_secrets_never_logged_sweep.py`) covering:

- **API key material** — a freshly-created key's raw value never
  appears in captured logs across the create-org → create-key flow.
- **TOTP MFA secrets and backup codes** — enroll → verify flow,
  neither the TOTP secret nor any of the 10 generated backup codes
  appear.
- **Webhook signing secrets** — a real webhook creation with a
  32+-character signing secret never appears.

**A real bug found and fixed while writing this sweep, not
hypothetical**: at `DEBUG` log level, `aiosqlite`'s own internal
logging emits the **complete SQL statement including bound parameter
values** for every query — meaning any secret ever written to an
unencrypted column (field-level encryption is opt-in, not default)
would appear in plaintext in the log stream the moment an operator set
`RAI_LOG_LEVEL=DEBUG` for troubleshooting. Confirmed directly: the
webhook-secret test failed before the fix, with the raw 40-character
secret visible in a captured `aiosqlite` `INSERT INTO webhook_configs`
debug log line. Fixed in `logging_config.py`'s `configure_logging()`:
`aiosqlite` and `asyncpg` (the Postgres driver) are now explicitly
capped at `INFO` regardless of the app's own configured log level —
raw SQL/parameter logging is never granted "for free" by turning up
app-level verbosity. If genuine query-level debugging is ever needed,
raise these two loggers back to `DEBUG` deliberately, in a disposable
environment, never as a byproduct of app-wide `DEBUG`.

## What this document does not cover

- Per-environment secret *values* — those belong in a secrets manager
  (Vault, AWS Secrets Manager, the deployment platform's own env-var
  encryption), never in this repository or its docs.
- Network-level configuration (reverse proxy TLS termination, firewall
  rules) — see `DEPLOYMENT.md`'s nginx section.
- Database connection pool tuning — see `db/engine.py`'s own
  documented `pool_size=10, max_overflow=20` defaults and reasoning.
