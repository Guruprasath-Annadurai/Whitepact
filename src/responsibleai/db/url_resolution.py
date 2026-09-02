"""Migration DB-URL resolution -- extracted from `migrations/env.py` so it
can be unit-tested without alembic's own runtime context (`alembic.context`
is only usable inside an active alembic invocation, which made this logic
untestable in its original location).

Security-freeze review finding (docs/security-review/
STAGE5_INDEPENDENT_REVIEW_GATE.md, item 3): a plausible-looking but
unrecognized DB-URL env var name (e.g. plain ``DATABASE_URL``) previously
fell through silently to the local SQLite default -- confirmed directly
during this project's own PostgreSQL migration-verification pass. A
misconfigured deployment could believe it just migrated production
PostgreSQL while it actually migrated an ephemeral or wrong SQLite file.
These names are now refused explicitly rather than guessed at.
"""

from __future__ import annotations

import os

UNRECOGNIZED_DB_URL_ENV_ALIASES = (
    "DATABASE_URL",
    "DB_URL",
    "POSTGRES_URL",
    "POSTGRESQL_URL",
    "PG_URL",
    "SQLALCHEMY_DATABASE_URL",
    "SQLALCHEMY_URL",
)


def resolve_migration_db_url() -> str:
    """Resolve the DB URL from environment variables.

    Priority:
    1. RAI_DB_URL — full SQLAlchemy-style URL
    2. RAI_DATABASE_URL — same, alternate name
    3. RAI_DB_PATH — file path (converted to sqlite+aiosqlite://)
    4. Falls back to ./governance.db

    Raises `RuntimeError` if none of the three recognized names above
    are set but a plausible-looking, unrecognized alias (e.g. plain
    ``DATABASE_URL``) is -- refusing to silently fall back to SQLite in
    that case rather than guessing the operator meant something this
    module doesn't actually read.
    """
    raw = os.environ.get("RAI_DB_URL") or os.environ.get("RAI_DATABASE_URL") or ""
    if raw:
        if raw.startswith("postgresql"):
            raw = raw.replace("postgresql://", "postgresql+asyncpg://", 1)
            raw = raw.replace("postgres://", "postgresql+asyncpg://", 1)
        return raw

    if "RAI_DB_PATH" not in os.environ:
        set_aliases = [name for name in UNRECOGNIZED_DB_URL_ENV_ALIASES if os.environ.get(name)]
        if set_aliases:
            raise RuntimeError(
                f"{', '.join(set_aliases)} is set, but this project only reads "
                "RAI_DB_URL or RAI_DATABASE_URL for a full database URL "
                "(or RAI_DB_PATH for a local SQLite file path). Rename to "
                f"RAI_DB_URL, or unset {', '.join(set_aliases)} if the local "
                "SQLite default (./governance.db) is actually intended."
            )

    path = os.environ.get("RAI_DB_PATH", "governance.db")
    if path == ":memory:":
        return "sqlite+aiosqlite:///:memory:"
    return f"sqlite+aiosqlite:///{path}"
