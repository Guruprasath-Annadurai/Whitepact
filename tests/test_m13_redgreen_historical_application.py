# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual historical source-process startup; not all historical release binaries."""

import asyncio
import io
import os
import subprocess
import sys
import tarfile
from contextlib import aclosing

import pytest

from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url


@pytest.mark.asyncio
async def test_historical_0065_application_refuses_0066_before_serving(tmp_path):
    historical = "bff5f143933d518e921592361f0171d7cf7ff6ef"
    # Exact ancestor source, not a reconstruction of its guard in the test.
    archive = subprocess.check_output(["git", "archive", historical, "src"])
    with tarfile.open(fileobj=io.BytesIO(archive)) as source:
        source.extractall(tmp_path, filter="data")
    program = """
import asyncio
from pathlib import Path
import responsibleai.dashboard.app as module
assert Path(module.__file__).resolve().is_relative_to(Path.cwd() / 'src')
async def main():
    try:
        async with module.app.router.lifespan_context(module.app):
            raise AssertionError('Historical application served incompatible schema')
    except RuntimeError as error:
        assert str(error) == 'Startup refused: incompatible PostgreSQL schema revision'
        print('HISTORICAL_APPLICATION_REFUSED')
asyncio.run(main())
"""
    async with aclosing(isolated_pg_url("wp_historical_application")) as databases:
        async for database in databases:
            await _run_alembic(_find_alembic_ini(), _migration_env(database), "upgrade", "0066")
            env = dict(
                os.environ,
                PYTHONPATH=str(tmp_path / "src"),
                WHITEPACT_DATABASE_URL=database,
                WHITEPACT_AUTO_MIGRATE="false",
                WHITEPACT_ENV="development",
            )
            child = await asyncio.create_subprocess_exec(
                sys.executable,
                "-c",
                program,
                cwd=tmp_path,
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            try:
                stdout, _ = await asyncio.wait_for(child.communicate(), 45)
            finally:
                if child.returncode is None:
                    child.kill()
                    await child.communicate()
            # Do not echo child stderr: dependency diagnostics can contain URLs.
            assert child.returncode == 0, "Historical startup failed outside the required guard"
            assert b"HISTORICAL_APPLICATION_REFUSED" in stdout
