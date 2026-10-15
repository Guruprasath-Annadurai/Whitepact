# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real TCP application + migrated PostgreSQL + Chromium. No identity/root seed."""

import asyncio
import json
import os
import secrets
import socket
from pathlib import Path

import pytest
import uvicorn

import responsibleai.dashboard.app as dashboard
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.runtime.gate import PRODUCTION_GATE_B_OPEN
from tests.pg_test_url import isolated_pg_url


@pytest.mark.asyncio
async def test_real_app_public_browser_and_unauthenticated_console(monkeypatch):
    assert not PRODUCTION_GATE_B_OPEN
    assert os.environ.get("PLAYWRIGHT_BROWSERS_PATH"), (
        "Set PLAYWRIGHT_BROWSERS_PATH to the explicitly installed test browser cache; "
        "pytest deliberately isolates HOME. No browser test is skipped."
    )
    async for url in isolated_pg_url("wp_m12p_browser"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        monkeypatch.setattr(dashboard.settings, "database_url", url)
        monkeypatch.setattr(dashboard.settings, "auto_migrate", False)
        monkeypatch.setattr(dashboard.settings, "auth_enabled", True)
        monkeypatch.setattr(dashboard.settings, "api_keys", [secrets.token_urlsafe(32)])
        monkeypatch.setattr(dashboard.settings, "environment", "development")
        sock = socket.socket()
        sock.bind(("127.0.0.1", 0))
        origin = f"http://127.0.0.1:{sock.getsockname()[1]}"
        server = uvicorn.Server(
            uvicorn.Config(dashboard.app, log_level="critical", access_log=False)
        )
        task = asyncio.create_task(server.serve(sockets=[sock]))
        process = None
        try:
            async with asyncio.timeout(30):
                while not server.started:
                    if task.done():
                        await task
                        raise AssertionError("Local application startup failed")
                    await asyncio.sleep(0.01)
            env = {
                key: os.environ[key]
                for key in ("PATH", "HOME", "TMPDIR", "PLAYWRIGHT_BROWSERS_PATH")
                if key in os.environ
            }
            env["WHITEPACT_TEST_BASE_URL"] = origin
            process = await asyncio.create_subprocess_exec(
                "node",
                "tests/js/m12p-live-public.e2e.mjs",
                cwd=Path(__file__).parents[1],
                env=env,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, _stderr = await asyncio.wait_for(process.communicate(), timeout=120)
            # The child uses a fresh unauthenticated DB and logs no response bodies.
            assert process.returncode == 0, _stderr.decode("utf-8", errors="replace")[:2000]
            result = json.loads(stdout)
            assert result["checks"] == 16 and result["mutations"] == 0
            assert (
                result["kind"]
                == "REAL_APP_PUBLIC_UNAUTHENTICATED_POSTGRESQL_NOT_CUSTOMER_AUTHORITY"
            )
        finally:
            if process is not None and process.returncode is None:
                process.kill()
                await process.wait()
            server.should_exit = True
            await asyncio.wait_for(task, timeout=20)
