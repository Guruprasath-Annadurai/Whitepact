#!/usr/bin/env python3
# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline, non-mutating first-run preflight. Never emit environment values."""

from __future__ import annotations

import ipaddress
import json
import os
import shutil
import sys
from collections.abc import Mapping
from urllib.parse import urlsplit

DATABASE_KEYS = ("WHITEPACT_DATABASE_URL", "DATABASE_URL", "RAI_DATABASE_URL")
REDIS_KEYS = ("WHITEPACT_REDIS_URL", "RAI_REDIS_URL")
DISPATCHER_KEYS = (
    "PHASE7A_DISPATCHER_ENABLED",
    "WHITEPACT_PHASE7A_DISPATCHER_ENABLED",
    "RAI_PHASE7A_DISPATCHER_ENABLED",
)


def local_service_url(value: str, service: str) -> bool:
    """Validate only explicit loopback endpoints, without DNS or connecting.

    Forbid URL query overrides (including libpq host/service overrides), fragments,
    escaped hostnames and ambiguous whitespace. This is a preflight, not a server
    configuration replacement or a guarantee that loopback services are isolated.
    """
    if not value or len(value) > 8192 or any(c.isspace() or ord(c) < 32 for c in value):
        return False
    try:
        parsed = urlsplit(value)
        schemes = (
            {"postgresql", "postgresql+asyncpg", "postgresql+psycopg"}
            if service == "postgresql"
            else {"redis", "rediss"}
        )
        if parsed.scheme not in schemes or parsed.query or parsed.fragment:
            return False
        host = parsed.hostname
        if not host or "%" in host or parsed.port == 0:
            return False
        if host != "localhost" and not ipaddress.ip_address(host).is_loopback:
            return False
        if service == "postgresql":
            return bool(parsed.username and parsed.password and parsed.path.strip("/"))
        return parsed.path in ("", "/") or (
            parsed.path.startswith("/") and parsed.path[1:].isascii() and parsed.path[1:].isdigit()
        )
    except (ValueError, UnicodeError):
        return False


def inspect_environment(
    environ: Mapping[str, str],
    *,
    executables: Mapping[str, bool] | None = None,
    python_version: tuple[int, ...] | None = None,
) -> dict[str, object]:
    """Return fixed diagnostic vocabulary only; no values, URLs or paths."""
    # Pydantic settings are case-insensitive. Do not accidentally ignore a
    # lower-case alias that the server would consume.
    normalized: dict[str, str] = {}
    conflicting = False
    relevant = set(DATABASE_KEYS + REDIS_KEYS + DISPATCHER_KEYS) | {
        "WHITEPACT_AUTH_ENABLED",
        "RAI_AUTH_ENABLED",
        "WHITEPACT_API_KEYS",
        "RAI_API_KEYS",
        "WHITEPACT_ENV",
        "RAI_ENV",
    }
    for key, value in environ.items():
        canonical = key.upper()
        if canonical not in relevant:
            continue
        if canonical in normalized and normalized[canonical] != value:
            conflicting = True
        normalized[canonical] = value
    environ = normalized
    tools = (
        executables
        if executables is not None
        else {name: shutil.which(name) is not None for name in ("git", "docker", "node", "npm")}
    )
    version = python_version if python_version is not None else sys.version_info[:2]
    checks: dict[str, str] = {
        "case_insensitive_aliases_unambiguous": "FAIL" if conflicting else "PASS",
        "python_3_11_or_newer": "PASS" if version >= (3, 11) else "FAIL",
        **{
            f"{name}_on_path": "PASS" if tools.get(name) else "MISSING"
            for name in ("git", "docker", "node", "npm")
        },
    }
    for label, keys, service in (
        ("postgresql_loopback_config", DATABASE_KEYS, "postgresql"),
        ("redis_loopback_config", REDIS_KEYS, "redis"),
    ):
        values = [environ[key] for key in keys if key in environ]
        checks[label] = (
            "MISSING"
            if not values
            else "PASS"
            if all(local_service_url(value, service) for value in values)
            else "FAIL"
        )
    # Reject unsafe aliases even when a higher-precedence value would shadow them.
    checks["authentication_enabled"] = (
        "PASS"
        if all(
            environ.get(key, "true").lower() in ("true", "1", "yes", "on")
            for key in ("WHITEPACT_AUTH_ENABLED", "RAI_AUTH_ENABLED")
        )
        else "FAIL"
    )
    checks["dispatcher_disabled"] = (
        "PASS"
        if all(
            environ.get(key, "false").lower() in ("false", "0", "no", "off")
            for key in DISPATCHER_KEYS
        )
        else "FAIL"
    )
    # Match Settings._parse_keys: NoDecode comma-separated strings, not JSON.
    # The canonical source wins even if empty; legacy does not repair an
    # explicitly empty higher-priority configuration.
    raw_keys = environ.get("WHITEPACT_API_KEYS", environ.get("RAI_API_KEYS", ""))
    checks["api_key_configured"] = (
        "PASS" if any(part.strip() for part in raw_keys.split(",")) else "MISSING"
    )
    checks["non_production_environment"] = (
        "PASS"
        if all(
            environ.get(key, "development").lower() in ("development", "dev", "test", "staging")
            for key in ("WHITEPACT_ENV", "RAI_ENV")
        )
        else "FAIL"
    )
    return {
        "schema": "whitepact-first-run-preflight-v1",
        "checks": checks,
        "configuration_preflight": "PASS"
        if all(v == "PASS" for v in checks.values())
        else "BLOCKED",
        "connections_tested": False,
        "executable_versions_tested": False,
        "customer_root_consent": "NOT_VERIFIED_REQUIRES_REVIEWED_PROVISIONING",
        "customer_execution_ready": False,
        "production_ready": False,
        "mutations_performed": False,
    }


def main() -> int:
    report = inspect_environment(os.environ)
    print(json.dumps(report, sort_keys=True, indent=2))
    return 0 if report["configuration_preflight"] == "PASS" else 2


if __name__ == "__main__":
    raise SystemExit(main())
