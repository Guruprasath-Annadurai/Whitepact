# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Validate current process environment against production contracts.

Usage:
    python -m responsibleai.operations.config_validate [--expect-production]

Exits 0 when Settings load successfully and optional production checks pass.
Does not print secret values.
"""

from __future__ import annotations

import argparse
import sys

from responsibleai.dashboard.config import (
    Settings,
    is_production_environment,
    multi_replica_problems,
)


def _load_settings() -> Settings:
    return Settings()


def validate(expect_production: bool = False) -> list[str]:
    errors: list[str] = []
    try:
        settings = _load_settings()
    except Exception as exc:
        return [f"settings_load_failed: {exc}"]

    if expect_production and not settings.is_production:
        errors.append("expected_production_environment_but_got_other")

    if settings.is_production:
        if not settings.database_url:
            errors.append("production_missing_database_url")
        elif not settings.database_url.startswith(("postgresql://", "postgresql+asyncpg://")):
            errors.append("production_database_not_postgresql")
        if settings.auth_enabled and not settings.api_keys and not settings.oidc_enabled:
            errors.append("production_auth_enabled_without_credentials")
        if settings.allow_all_origins:
            errors.append("production_allow_all_origins_forbidden")

    db_backend = (
        "postgresql" if (settings.database_url or "").startswith("postgresql") else "sqlite"
    )
    rl_backend = "redis" if settings.redis_url else "memory"
    if settings.workers > 1:
        for problem in multi_replica_problems(db_backend, rl_backend):
            errors.append(f"multi_replica_unsafe: {problem}")

    return errors


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WhitePact production configuration validator")
    parser.add_argument(
        "--expect-production",
        action="store_true",
        help="Require WHITEPACT_ENV/RAI_ENV to be production|prod",
    )
    args = parser.parse_args(argv)

    if args.expect_production:
        import os

        env = os.environ.get("WHITEPACT_ENV") or os.environ.get("RAI_ENV") or "development"
        if not is_production_environment(env):
            print(f"CONFIG_INVALID: environment={env!r} is not production", file=sys.stderr)
            return 1

    errors = validate(expect_production=args.expect_production)
    if errors:
        for err in errors:
            print(f"CONFIG_INVALID: {err}", file=sys.stderr)
        return 1
    print("CONFIG_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
