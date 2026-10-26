# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Caller flags cannot disable mandatory production recovery authority."""

import pytest

from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    MissingLifecycleProviderError,
    RestoreReconciliationEngine,
)
from responsibleai.db.engine import create_engine


@pytest.mark.asyncio
async def test_production_cannot_opt_out_of_durable_store_b(monkeypatch):
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    engine = create_engine(":memory:")
    try:
        with pytest.raises(MissingLifecycleProviderError):
            RestoreReconciliationEngine(
                engine,
                lifecycle_provider=InMemoryLifecycleStateProvider(),
                require_durable=False,
            )
    finally:
        await engine.close()
