# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from fastapi import HTTPException

import responsibleai.dashboard.app as dashboard_app
from responsibleai.global_directory.repository import GlobalDirectoryRepository
from responsibleai.global_directory.service import GlobalDirectoryService


async def get_global_directory_service() -> GlobalDirectoryService:
    engine = dashboard_app._db_engine
    if engine is None:
        raise HTTPException(status_code=503, detail="Database not initialized")
    return GlobalDirectoryService(GlobalDirectoryRepository(engine))
