# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Shared production configuration contract (CLI + startup)."""

from __future__ import annotations

from typing import TYPE_CHECKING

from responsibleai.operations.auth_contract import validate_dashboard_auth

if TYPE_CHECKING:
    from responsibleai.dashboard.config import Settings


def collect_production_configuration_errors(settings: Settings) -> list[str]:
    """Pure, secret-safe production configuration errors for the current Settings."""
    if not settings.is_production:
        return []

    errors: list[str] = []
    errors.extend(validate_dashboard_auth(settings))

    if settings.allow_all_origins:
        errors.append("production_allow_all_origins_forbidden")
    if settings.mcp_http_allow_unauthenticated_demo:
        errors.append("production_mcp_unauthenticated_demo_forbidden")

    from responsibleai.dashboard.config import multi_replica_problems

    db_backend = (
        "postgresql" if (settings.database_url or "").startswith("postgresql") else "sqlite"
    )
    rl_backend = "redis" if settings.redis_url else "memory"
    if settings.workers > 1:
        for problem in multi_replica_problems(db_backend, rl_backend):
            errors.append(f"multi_replica_unsafe: {problem}")

    return errors
