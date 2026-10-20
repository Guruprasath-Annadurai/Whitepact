# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""CLI resource ownership; no authority or production identity fixtures."""

import asyncio
from unittest.mock import AsyncMock

import pytest

from responsibleai.db.engine import create_engine
from responsibleai.sovereign import cli_core
from responsibleai.sovereign.errors import SovereignTenantIsolationError


@pytest.mark.asyncio
@pytest.mark.parametrize("path", ["success", "invalid", "denied", "initialization", "cancelled"])
async def test_cli_closes_its_engine_before_return_or_error(monkeypatch, path):
    engine = create_engine(":memory:")
    original_close = engine.close
    close = AsyncMock(wraps=original_close)
    monkeypatch.setattr(engine, "close", close)
    monkeypatch.setattr(cli_core, "create_engine", lambda _: engine)
    try:
        if path == "success":
            assert await cli_core.cmd_xray("local-label", json_mode=True) == cli_core.EXIT_OK
        elif path == "invalid":
            assert await cli_core.cmd_capsule_validate(None, None, True) == cli_core.EXIT_INVALID
        elif path == "denied":
            with pytest.raises(SovereignTenantIsolationError):
                await cli_core.cmd_trace("local-label", "missing", True)
        elif path == "initialization":
            monkeypatch.setattr(engine, "init", AsyncMock(side_effect=RuntimeError("init failed")))
            with pytest.raises(RuntimeError, match="init failed"):
                await cli_core.cmd_xray("local-label", True)
        else:
            monkeypatch.setattr(
                cli_core.SovereignService,
                "build_xray_async",
                AsyncMock(side_effect=asyncio.CancelledError),
            )
            with pytest.raises(asyncio.CancelledError):
                await cli_core.cmd_xray("local-label", True)
        close.assert_awaited_once()
    finally:
        # Retire a genuinely opened SQLite worker even on the pre-fix RED run.
        await original_close()
