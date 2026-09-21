# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.db import DatabaseEngine, create_engine
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore

_bound_engine: DatabaseEngine | None = None


def bind_sovereign_engine(engine: DatabaseEngine) -> None:
    global _bound_engine
    _bound_engine = engine


def get_bound_engine() -> DatabaseEngine | None:
    return _bound_engine


async def build_sovereign_service() -> SovereignService:
    if _bound_engine is not None:
        return SovereignService(store=SovereignCanonicalStore.from_engine(_bound_engine))
    engine = create_engine(":memory:")
    await engine.init()
    return SovereignService(store=SovereignCanonicalStore.from_engine(engine))
