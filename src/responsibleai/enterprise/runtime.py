# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise IAM runtime wiring. Redis is never RBAC authority."""

from __future__ import annotations

from dataclasses import dataclass

from responsibleai.db.engine import DatabaseEngine
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository

_engine: DatabaseEngine | None = None


@dataclass(frozen=True)
class EnterpriseRepos:
    engine: DatabaseEngine
    orgs: OrgRepository
    web: WebIdentityRepository


def configure_enterprise(engine: DatabaseEngine) -> None:
    global _engine
    _engine = engine


def get_enterprise_engine() -> DatabaseEngine:
    if _engine is None:
        raise RuntimeError("enterprise IAM is not configured")
    return _engine


def get_repos() -> EnterpriseRepos:
    engine = get_enterprise_engine()
    return EnterpriseRepos(
        engine=engine, orgs=OrgRepository(engine), web=WebIdentityRepository(engine)
    )
