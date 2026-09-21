# Release validation environment (PREPARATION)

This document supports **future** combined WhitePact V1 RC validation. It is not a
final release verdict.

## RELEASE_ENVIRONMENT_DEPENDENCY_MAP

| Capability | Install path | Notes |
|------------|--------------|-------|
| Core + Alembic | `pip install -e .` | Base `pyproject.toml` |
| Dashboard / FastAPI / SQLAlchemy | `[dashboard]` | Includes **`cbor2>=5.6.0`** for WebAuthn CBOR (`enterprise/security/webauthn.py`) |
| PostgreSQL async driver | `[postgres]` | `asyncpg` |
| Dev / CI test stack | `[dev]` | pytest, mypy, ruff, **cbor2**, asyncpg, MCP, etc. |
| SSO / SAML | `[sso]` | JWT, signxml, lxml |
| MCP server | `[mcp]` | MCP SDK pin `<2.0.0` |
| VADER sentiment (legacy) | `[sentiment]` | opt-in `nltk>=3.10.0` |
| Redis rate limits | `[redis]` | optional |

### `cbor2` / `ModuleNotFoundError`

**Root cause:** Enterprise WebAuthn and dashboard paths import `cbor2`. It is declared in:

- `[project.optional-dependencies] dashboard` → `cbor2>=5.6.0`
- `[project.optional-dependencies] dev` → `cbor2>=5.6.0`

**Fix:** Install a supported extra, e.g.:

```bash
pip install -e ".[dev,dashboard,postgres]"
```

Do not add undeclared `pip install cbor2` in production runbooks unless metadata is updated deliberately.

## PostgreSQL (disposable)

Default admin URL (test-only):

`postgresql://wp:wp@127.0.0.1:55432/postgres`

### Commands

```bash
chmod +x scripts/release/postgres_disposable.sh scripts/release/validate_backend.sh
./scripts/release/postgres_disposable.sh start
./scripts/release/postgres_disposable.sh wait
./scripts/release/postgres_disposable.sh reset   # destroy volume + recreate
./scripts/release/postgres_disposable.sh down
```

Docker Compose file: `docker-compose.release-test.yml`

Override admin URL:

`export WHITEPACT_TEST_PG_ADMIN_URL=postgresql://...`

## Alembic

On RC lineage @ P0 integration (`8df07ff`):

- **Single head:** `0060` (`0060_test_consequential_counters.py`)
- **0061:** not present on this lineage; expect on future **combined** RC after Sovereign integration

```bash
export WHITEPACT_TEST_PG_ADMIN_URL=postgresql://wp:wp@127.0.0.1:55432/postgres
# per-database URL is created by tests via tests/pg_test_url.py
alembic heads
alembic upgrade head   # requires RAI_DB_URL / migration env — prefer pytest migration proofs
```

## Environment variables (test)

| Variable | Purpose |
|----------|---------|
| `WHITEPACT_TEST_PG_ADMIN_URL` | Disposable Postgres admin |
| `RAI_AUTO_MIGRATE` | `false` for explicit migration tests |
| `RAI_AUTH_ENABLED` | `true` for realistic auth paths |
| `RAI_MCP_ALLOW_TEST_TOOLS` | Server-only; never set from client input |

No production secrets in this harness.

## Canonical validation command

```bash
./scripts/release/validate_backend.sh
```

Logs under `artifacts/release-validation/<timestamp>/`.

## CI preparation

See `.github/workflows/release-validation-preparation.yml` (workflow_dispatch draft).
Does not replace existing `ci.yml`. Frontend integration CI remains **Codex-owned** —
document adjustments on combined RC, do not edit `codex/*` branches.

## Teardown

```bash
./scripts/release/postgres_disposable.sh down
```
