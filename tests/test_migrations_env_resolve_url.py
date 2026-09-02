"""Tests for `responsibleai.db.url_resolution.resolve_migration_db_url()`
(used by `migrations/env.py`, extracted so it's testable outside
alembic's own runtime context).

Security-freeze review finding (docs/security-review/
STAGE5_INDEPENDENT_REVIEW_GATE.md, item 3): a plausible-looking but
unrecognized DB-URL env var name (e.g. plain `DATABASE_URL`) previously
fell through silently to the local SQLite default, discovered directly
during this project's own PostgreSQL migration-verification pass.
Reproduces the gap, then verifies the fix refuses to guess.
"""

from __future__ import annotations

import pytest

from responsibleai.db import url_resolution as db_url_resolution


@pytest.fixture(autouse=True)
def _clean_db_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Every DB-URL-related env var this module reads or refuses,
    cleared before each test so ambient environment state (e.g. this
    developer machine's own shell) can't leak into the assertions."""
    for name in (
        "RAI_DB_URL",
        "RAI_DATABASE_URL",
        "RAI_DB_PATH",
        "DATABASE_URL",
        "DB_URL",
        "POSTGRES_URL",
        "POSTGRESQL_URL",
        "PG_URL",
        "SQLALCHEMY_DATABASE_URL",
        "SQLALCHEMY_URL",
    ):
        monkeypatch.delenv(name, raising=False)


class TestRecognizedEnvVarsStillWork:
    def test_rai_db_url_used_directly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAI_DB_URL", "sqlite+aiosqlite:///explicit.db")
        assert db_url_resolution.resolve_migration_db_url() == "sqlite+aiosqlite:///explicit.db"

    def test_rai_database_url_used_directly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAI_DATABASE_URL", "sqlite+aiosqlite:///explicit2.db")
        assert db_url_resolution.resolve_migration_db_url() == "sqlite+aiosqlite:///explicit2.db"

    def test_postgresql_scheme_rewritten_to_asyncpg(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAI_DB_URL", "postgresql://user@localhost/db")
        assert (
            db_url_resolution.resolve_migration_db_url() == "postgresql+asyncpg://user@localhost/db"
        )

    def test_rai_db_path_used_as_sqlite_file(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAI_DB_PATH", "custom.db")
        assert db_url_resolution.resolve_migration_db_url() == "sqlite+aiosqlite:///custom.db"

    def test_rai_db_path_memory_special_case(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAI_DB_PATH", ":memory:")
        assert db_url_resolution.resolve_migration_db_url() == "sqlite+aiosqlite:///:memory:"


class TestNoEnvVarsAtAllStillFallsBackSilently:
    """The documented, intentional default (local dev, nothing set) must
    remain unchanged -- only a plausible-but-wrong alias should raise,
    never the plain absence of any DB configuration at all."""

    def test_falls_back_to_governance_db(self) -> None:
        assert db_url_resolution.resolve_migration_db_url() == "sqlite+aiosqlite:///governance.db"


class TestUnrecognizedAliasRefusesToGuess:
    """Reproduces the exact mistake made during this project's own
    Stage 1 PostgreSQL round-trip verification: setting DATABASE_URL
    instead of RAI_DB_URL silently produced a SQLite migration."""

    def test_plain_database_url_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://user@localhost/prod")
        with pytest.raises(RuntimeError, match="DATABASE_URL"):
            db_url_resolution.resolve_migration_db_url()

    def test_error_names_the_correct_variable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("DATABASE_URL", "postgresql://user@localhost/prod")
        with pytest.raises(RuntimeError, match="RAI_DB_URL"):
            db_url_resolution.resolve_migration_db_url()

    @pytest.mark.parametrize(
        "alias",
        [
            "DB_URL",
            "POSTGRES_URL",
            "POSTGRESQL_URL",
            "PG_URL",
            "SQLALCHEMY_DATABASE_URL",
            "SQLALCHEMY_URL",
        ],
    )
    def test_other_common_aliases_also_raise(
        self, monkeypatch: pytest.MonkeyPatch, alias: str
    ) -> None:
        monkeypatch.setenv(alias, "postgresql://user@localhost/prod")
        with pytest.raises(RuntimeError, match=alias):
            db_url_resolution.resolve_migration_db_url()

    def test_rai_db_url_takes_priority_over_an_unrecognized_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A deployment that (correctly) sets RAI_DB_URL alongside an
        unrelated DATABASE_URL some other tool reads must not be broken
        by this check."""
        monkeypatch.setenv("RAI_DB_URL", "postgresql://user@localhost/correct")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user@localhost/unrelated")
        assert (
            db_url_resolution.resolve_migration_db_url()
            == "postgresql+asyncpg://user@localhost/correct"
        )

    def test_rai_db_path_takes_priority_over_an_unrecognized_alias(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A deployment that (correctly) sets RAI_DB_PATH for the local
        SQLite file must not be broken by this check either."""
        monkeypatch.setenv("RAI_DB_PATH", "custom.db")
        monkeypatch.setenv("DATABASE_URL", "postgresql://user@localhost/unrelated")
        assert db_url_resolution.resolve_migration_db_url() == "sqlite+aiosqlite:///custom.db"
