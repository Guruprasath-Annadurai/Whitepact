# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Operator diagnostics CLI (Launch Cell B — B11). Secret-safe."""

from __future__ import annotations

import argparse
import os
import sys

from responsibleai.dashboard.config import Settings
from responsibleai.db.encryption import field_encryption_is_configured
from responsibleai.operations.config_validate import validate
from responsibleai.operations.production_config import collect_production_configuration_errors


def _print_kv(key: str, value: str) -> None:
    print(f"{key}={value}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="WhitePact operator diagnostics (no secrets)")
    parser.add_argument("--expect-production", action="store_true")
    args = parser.parse_args(argv)

    settings = Settings()
    _print_kv("environment", settings.environment)
    _print_kv("is_production", str(settings.is_production).lower())
    _print_kv("auth_enabled", str(settings.auth_enabled).lower())
    _print_kv("workers", str(settings.workers))
    _print_kv(
        "database_backend",
        "postgresql" if (settings.database_url or "").startswith("postgresql") else "sqlite",
    )
    _print_kv("redis_configured", str(bool(settings.redis_url)).lower())
    _print_kv("field_encryption_configured", str(field_encryption_is_configured()).lower())
    _print_kv("formula_rollout_mode", os.environ.get("WHITEPACT_FORMULA_ROLLOUT_MODE", "OFF"))

    errors = validate(expect_production=args.expect_production)
    if settings.is_production:
        errors = list({*errors, *collect_production_configuration_errors(settings)})
    _print_kv("config_validation", "ok" if not errors else "invalid")
    for err in errors:
        print(f"config_error={err}", file=sys.stderr)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
