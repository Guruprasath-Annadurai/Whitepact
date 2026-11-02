# Database and Migrations

## Supported databases

| Database | Driver | Use case |
|---|---|---|
| SQLite | `aiosqlite` | Development, single-server deployments |
| PostgreSQL | `asyncpg` | Production, multi-server, horizontal scaling |

---

## Configuration

Priority order for database URL resolution:

1. `RAI_DB_URL` — full SQLAlchemy-style URL (takes priority)
2. `RAI_DATABASE_URL` — alias for `RAI_DB_URL`
3. `RAI_DB_PATH` — SQLite file path (converted to `sqlite+aiosqlite:///{path}`)
4. Default: `governance.db` in the current directory

### SQLite (default)

```bash
# Default (governance.db in cwd)
uvicorn responsibleai.dashboard.app:app --port 8765

# Custom path
RAI_DB_PATH=/var/lib/rai/governance.db uvicorn ...

# In-memory (tests / ephemeral)
RAI_DB_PATH=:memory: uvicorn ...
```

### PostgreSQL

```bash
RAI_DB_URL=postgresql://user:password@host:5432/responsibleai uvicorn ...

# Or with the standard Heroku-style URL
RAI_DATABASE_URL=postgresql://user:password@host:5432/responsibleai uvicorn ...
```

The async engine is configured with:
- `pool_size=10` — base connection pool
- `max_overflow=20` — burst capacity
- `pool_pre_ping=True` — detect stale connections
- `pool_recycle=3600` — recycle connections hourly

---

## Alembic migrations

ResponsibleAI uses Alembic for versioned schema management. The initial migration (`0001`) creates all 8 tables with their indexes.

### Run migrations

```bash
# SQLite
RAI_DB_PATH=/var/lib/rai/governance.db alembic upgrade head

# PostgreSQL
RAI_DB_URL=postgresql://user:pass@host:5432/db alembic upgrade head

# In-memory (for testing only — no permanent effect)
RAI_DB_PATH=:memory: alembic upgrade head
```

### Check migration status

```bash
alembic current    # currently applied revision
alembic history    # full revision chain
alembic heads      # latest available revisions
```

### Roll back

```bash
alembic downgrade -1       # one step back
alembic downgrade 0001     # back to specific revision
alembic downgrade base     # full rollback (drops all tables)
```

### Generate a new migration

After changing `src/responsibleai/db/engine.py`:

```bash
alembic revision --autogenerate -m "add_new_column"
```

Review the generated file in `migrations/versions/` before applying.

---

## Schema overview

### `token_usage`

Stores per-request token cost records.

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | autoincrement |
| request_id | VARCHAR(64) UNIQUE | idempotency key |
| provider | VARCHAR(50) | openai / anthropic / ... |
| model | VARCHAR(100) | model identifier |
| team | VARCHAR(100) | cost centre |
| application | VARCHAR(100) | service name |
| input_tokens | INTEGER | prompt tokens |
| output_tokens | INTEGER | completion tokens |
| cached_tokens | INTEGER | cached prompt tokens |
| input_cost | FLOAT | USD |
| output_cost | FLOAT | USD |
| total_cost | FLOAT | USD |
| recorded_at | VARCHAR(32) | ISO-8601 timestamp |

### `webhook_deliveries`

Persists webhook delivery attempts for retry recovery.

| Column | Type | Notes |
|---|---|---|
| id | VARCHAR(36) PK | UUID |
| webhook_id | VARCHAR(36) | references registered webhook |
| event | VARCHAR(64) | event name |
| payload | TEXT | JSON |
| status | VARCHAR(20) | pending / retrying / delivered / failed |
| attempts | INTEGER | attempt count |
| max_retries | INTEGER | configured maximum |
| status_code | INTEGER | last HTTP response code |
| last_error | TEXT | last error message |
| next_retry_at | VARCHAR(32) | ISO-8601, NULL when not retrying |
| delivered_at | VARCHAR(32) | ISO-8601, NULL until success |

---

## SQLite optimisations

When SQLite is detected, the engine runs:

```sql
PRAGMA journal_mode=WAL;       -- concurrent reads during writes
PRAGMA synchronous=NORMAL;     -- durable without fsync on every write
```

These run on every connection in `DatabaseEngine.init()`.

---

## Testing with in-memory SQLite

All tests use `:memory:` by default. The fixture pattern:

```python
@pytest.fixture()
async def db_engine():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(metadata.create_all)
    yield DatabaseEngine(engine)
    await engine.dispose()
```
