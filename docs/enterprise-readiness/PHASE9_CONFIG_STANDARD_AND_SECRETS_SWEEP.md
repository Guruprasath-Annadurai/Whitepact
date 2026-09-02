# Phase 9 — Production Configuration Standard + Secrets-Never-Logged Sweep

**Directive**: WHITEPACT — FULL ENTERPRISE PRODUCTION + PUBLIC LAUNCH
CLOSURE MASTER DIRECTIVE, Phase 9.

## What this phase delivered

1. **`docs/security/PRODUCTION_CONFIGURATION_STANDARD.md`** —
   consolidates the production-recommended value for every
   security-relevant `Settings` field (grounded directly in
   `dashboard/config.py`, not invented), the fail-closed startup
   checks that already enforce some of them
   (`verify_heart_production_enforcement()`, `activate_production_crypto()`),
   and where every category of secret in `Settings` lives.

2. **Extended the secrets-never-logged test pattern** beyond crypto
   activation (`tests/test_crypto_activation.py`'s existing, narrower
   coverage) to every other credential-handling module —
   `tests/test_secrets_never_logged_sweep.py`: API key creation, TOTP
   MFA enrollment (secret + all 10 backup codes), webhook signing
   secrets. Real requests through the real REST API, `caplog`
   capturing everything logged at `DEBUG`.

## A real bug found and fixed while writing the sweep, not hypothetical

At `DEBUG` log level, `aiosqlite`'s own internal logging emits the
**complete SQL statement including bound parameter values** for every
query. Confirmed directly: the webhook-secret sweep test failed before
the fix, with the raw 40-character secret visible in a captured
`aiosqlite` `INSERT INTO webhook_configs` debug log line — meaning any
secret ever written to an unencrypted column (field-level encryption
is opt-in via `RAI_FIELD_ENCRYPTION_KEY`, not default) would appear in
plaintext in the log stream the moment an operator set
`RAI_LOG_LEVEL=DEBUG` for troubleshooting.

**Fixed** in `logging_config.py`'s `configure_logging()`: `aiosqlite`
and `asyncpg` (the Postgres driver, same class of risk) are now
explicitly capped at `INFO` regardless of the app's own configured log
level — raw SQL/parameter logging is never granted "for free" by
turning up app-level verbosity.

## Verification

`tests/test_secrets_never_logged_sweep.py`: 3 passed (API key
material, TOTP secret + backup codes, webhook signing secret — none
appear in captured logs). `tests/test_crypto_activation.py`: unchanged,
still passing (the pre-existing, narrower crypto-activation coverage
this phase extended, not replaced). `ruff check` / `mypy
src/responsibleai`: clean.

## Phase 9 verdict

**READY TO ADVANCE.** The configuration standard consolidates
previously-scattered guidance into one place; the secrets sweep found
and closed a real, previously-unknown information-disclosure gap, not
just added coverage of already-safe code.
