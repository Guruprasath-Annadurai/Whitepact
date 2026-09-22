# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from responsibleai.db import DatabaseEngine, create_engine
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.sovereign.service import SovereignService
from responsibleai.sovereign.sources import SovereignCanonicalStore

_bound_engine: DatabaseEngine | None = None
_web_identity_repo: WebIdentityRepository | None = None


def bind_sovereign_engine(engine: DatabaseEngine) -> None:
    global _bound_engine
    _bound_engine = engine


def get_bound_engine() -> DatabaseEngine | None:
    return _bound_engine


def bind_web_identity_repository(repo: WebIdentityRepository) -> None:
    global _web_identity_repo
    _web_identity_repo = repo


def get_web_identity_repository() -> WebIdentityRepository:
    if _web_identity_repo is None:
        raise RuntimeError(
            "Web identity repository is not bound; mount Sovereign web routes via the dashboard app."
        )
    return _web_identity_repo


async def build_sovereign_service() -> SovereignService:
    if _bound_engine is not None:
        return SovereignService(store=SovereignCanonicalStore.from_engine(_bound_engine))
    engine = create_engine(":memory:")
    await engine.init()
    return SovereignService(store=SovereignCanonicalStore.from_engine(engine))
