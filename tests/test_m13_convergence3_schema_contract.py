# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Current runtime revision policy; mocked transport is not PG migration proof."""

from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest

from responsibleai.db.runtime_compatibility import assert_runtime_schema_compatible


def engine_for(versions):
    result = MagicMock()
    result.scalars.return_value.all.return_value = versions
    connection = AsyncMock()
    connection.execute.return_value = result
    context = MagicMock()
    context.__aenter__ = AsyncMock(return_value=connection)
    context.__aexit__ = AsyncMock(return_value=False)
    return SimpleNamespace(
        raw=SimpleNamespace(
            dialect=SimpleNamespace(name="postgresql"),
            connect=MagicMock(return_value=context),
        )
    ), connection


@pytest.mark.asyncio
async def test_journal_runtime_accepts_exact_0066():
    engine, _ = engine_for(["0066"])
    await assert_runtime_schema_compatible(engine)


@pytest.mark.asyncio
@pytest.mark.parametrize("versions", [[], ["0064"], ["0065"], ["0067"], ["0065", "0066"]])
async def test_journal_runtime_rejects_missing_old_future_or_multiple_heads(versions):
    engine, _ = engine_for(versions)
    with pytest.raises(RuntimeError, match="incompatible"):
        await assert_runtime_schema_compatible(engine)


@pytest.mark.asyncio
async def test_unreadable_revision_never_becomes_compatible():
    engine, connection = engine_for(["0066"])
    connection.execute.side_effect = PermissionError("controlled denied read")
    with pytest.raises(RuntimeError, match="unverified"):
        await assert_runtime_schema_compatible(engine)
