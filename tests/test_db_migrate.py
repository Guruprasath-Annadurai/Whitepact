"""Tests for automatic schema migration at startup (db/migrate.py).

Guarded with importorskip("alembic") — the subprocess this module shells
out to uses sys.executable, i.e. the exact interpreter running this test,
so if alembic isn't importable here it wouldn't be importable there either.
"""

from __future__ import annotations

import uuid
from pathlib import Path

import pytest

pytest.importorskip("alembic")

from sqlalchemy import text

from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import (
    MigrationError,
    _find_alembic_ini,
    _migration_env,
    _needs_baseline_stamp,
    _run_alembic,
    run_migrations_or_raise,
)


async def _build_baseline_only_schema(db_path: str) -> None:
    """Build a DB matching a real pre-Alembic install: only migration 0001's
    tables, no alembic_version tracking.

    `create_engine(...).init()` can't be used to simulate this — its
    metadata reflects *current* code, which already includes every later
    migration's columns baked into the Table() definitions. Running
    `alembic upgrade 0001` specifically, then dropping alembic_version,
    reproduces exactly what an old, never-migrated install actually has.
    """
    ini_path = _find_alembic_ini()
    assert ini_path is not None
    env = _migration_env(db_path)
    await _run_alembic(ini_path, env, "upgrade", "0001")

    engine = create_engine(db_path)
    try:
        async with engine.raw.begin() as conn:
            await conn.execute(text("DROP TABLE alembic_version"))
    finally:
        await engine.raw.dispose()


@pytest.fixture()
def tmp_sqlite_path(tmp_path: Path) -> str:
    return str(tmp_path / "test.db")


class TestMigrationEnv:
    def test_sqlite_path_sets_db_path(self):
        env = _migration_env("/tmp/foo.db")
        assert env["RAI_DB_PATH"] == "/tmp/foo.db"
        assert "RAI_DATABASE_URL" not in env

    def test_postgres_url_sets_database_url(self):
        env = _migration_env("postgresql://u:p@host/db")
        assert env["RAI_DATABASE_URL"] == "postgresql://u:p@host/db"
        assert "RAI_DB_PATH" not in env

    def test_postgres_scheme_variant_also_detected(self):
        env = _migration_env("postgres://u:p@host/db")
        assert env["RAI_DATABASE_URL"] == "postgres://u:p@host/db"

    def test_stale_db_url_is_removed(self, monkeypatch):
        monkeypatch.setenv("RAI_DB_URL", "sqlite+aiosqlite:///stale.db")
        env = _migration_env("/tmp/foo.db")
        assert "RAI_DB_URL" not in env


class TestFindAlembicIni:
    def test_finds_real_repo_ini(self):
        # This test file lives under <repo>/tests/, so alembic.ini should be
        # discoverable by walking up parents from wherever pytest's cwd is.
        result = _find_alembic_ini()
        assert result is not None
        assert result.name == "alembic.ini"


class TestNeedsBaselineStamp:
    async def test_fresh_empty_db_does_not_need_stamp(self, tmp_sqlite_path):
        # No tables at all yet — nothing to stamp; upgrade head runs 0001 normally.
        result = await _needs_baseline_stamp(tmp_sqlite_path)
        assert result is False

    async def test_preexisting_schema_without_version_needs_stamp(self, tmp_sqlite_path):
        engine = create_engine(tmp_sqlite_path)
        await engine.init()  # create_all() — simulates a pre-Alembic install
        await engine.close()

        result = await _needs_baseline_stamp(tmp_sqlite_path)
        assert result is True

    async def test_tracked_version_does_not_need_stamp(self, tmp_sqlite_path):
        engine = create_engine(tmp_sqlite_path)
        await engine.init()
        async with engine.raw.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
            ))
            await conn.execute(text(
                "INSERT INTO alembic_version (version_num) VALUES ('0004')"
            ))
        await engine.close()

        result = await _needs_baseline_stamp(tmp_sqlite_path)
        assert result is False

    async def test_empty_version_table_still_needs_stamp(self, tmp_sqlite_path):
        """The exact scenario a SQLite non-transactional-DDL partial failure
        leaves behind: alembic_version table exists but has no row."""
        engine = create_engine(tmp_sqlite_path)
        await engine.init()
        async with engine.raw.begin() as conn:
            await conn.execute(text(
                "CREATE TABLE alembic_version (version_num VARCHAR(32) NOT NULL)"
            ))
        await engine.close()

        result = await _needs_baseline_stamp(tmp_sqlite_path)
        assert result is True


class TestRunMigrationsOrRaise:
    async def test_fresh_database_reaches_head(self, tmp_sqlite_path):
        await run_migrations_or_raise(tmp_sqlite_path)

        engine = create_engine(tmp_sqlite_path)
        try:
            async with engine.raw.connect() as conn:
                rows = await conn.execute(text("SELECT version_num FROM alembic_version"))
                assert rows.scalar() == "0007"

                cols = await conn.execute(text("PRAGMA table_info(organizations)"))
                col_names = {r[1] for r in cols.fetchall()}
                assert "plan" in col_names
                assert "sso_required" in col_names
        finally:
            await engine.raw.dispose()

    async def test_preexisting_unstamped_database_reaches_head(self, tmp_sqlite_path):
        """The real-world case: an existing self-hosted install's DB, built
        by an older version of the app before this migration system
        existed, with no alembic_version tracking at all."""
        await _build_baseline_only_schema(tmp_sqlite_path)

        await run_migrations_or_raise(tmp_sqlite_path)

        engine2 = create_engine(tmp_sqlite_path)
        try:
            async with engine2.raw.connect() as conn:
                rows = await conn.execute(text("SELECT version_num FROM alembic_version"))
                assert rows.scalar() == "0007"
        finally:
            await engine2.raw.dispose()

    async def test_running_twice_is_idempotent(self, tmp_sqlite_path):
        await run_migrations_or_raise(tmp_sqlite_path)
        await run_migrations_or_raise(tmp_sqlite_path)  # should not raise — already at head

        engine = create_engine(tmp_sqlite_path)
        try:
            async with engine.raw.connect() as conn:
                rows = await conn.execute(text("SELECT version_num FROM alembic_version"))
                assert rows.scalar() == "0007"
        finally:
            await engine.raw.dispose()

    async def test_missing_alembic_ini_raises(self, tmp_sqlite_path, monkeypatch):
        monkeypatch.setattr(
            "responsibleai.db.migrate._find_alembic_ini", lambda: None
        )
        with pytest.raises(MigrationError, match="Could not locate alembic.ini"):
            await run_migrations_or_raise(tmp_sqlite_path)

    async def test_unique_temp_dbs_do_not_interfere(self, tmp_path):
        """Sanity check that two independent DBs migrate independently."""
        db_a = str(tmp_path / f"{uuid.uuid4()}.db")
        db_b = str(tmp_path / f"{uuid.uuid4()}.db")

        await run_migrations_or_raise(db_a)
        assert Path(db_a).exists()
        assert not Path(db_b).exists()
