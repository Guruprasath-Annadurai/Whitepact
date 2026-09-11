# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Strict environment builder and sanitizer for isolated execution.

Guarantees zero control-plane secrets or ambient process credentials
leak into the isolated execution plane.
"""

from __future__ import annotations

import os
import re
from collections.abc import Mapping

# Sensitive key patterns that must NEVER leak into an execution environment
_BLOCKED_ENV_PATTERNS = [
    re.compile(r"KEY", re.IGNORECASE),
    re.compile(r"SECRET", re.IGNORECASE),
    re.compile(r"TOKEN", re.IGNORECASE),
    re.compile(r"PASSW", re.IGNORECASE),
    re.compile(r"CRED", re.IGNORECASE),
    re.compile(r"DATABASE", re.IGNORECASE),
    re.compile(r"POSTGRES", re.IGNORECASE),
    re.compile(r"REDIS", re.IGNORECASE),
    re.compile(r"CONN", re.IGNORECASE),
    re.compile(r"AUTH", re.IGNORECASE),
    re.compile(r"SESSION", re.IGNORECASE),
    re.compile(r"PRIVATE", re.IGNORECASE),
    re.compile(r"CERT", re.IGNORECASE),
    re.compile(r"DSN", re.IGNORECASE),
    re.compile(r"URL", re.IGNORECASE),
    re.compile(r"JWT", re.IGNORECASE),
    re.compile(r"API", re.IGNORECASE),
    re.compile(r"BEARER", re.IGNORECASE),
]

# Minimal explicit safe allowlist from host environment
_SAFE_HOST_ALLOWLIST = {
    "PATH",
    "LANG",
    "LC_ALL",
    "LC_CTYPE",
    "TZ",
}


def build_isolated_environment(
    *,
    organization_id: str,
    action_id: str,
    extra_env: Mapping[str, str] | None = None,
    inherit_safe_host_vars: bool = True,
) -> dict[str, str]:
    """Construct an isolated environment dictionary for execution.

    1. Starts with an empty environment.
    2. Selectively copies safe POSIX variables if requested.
    3. Injects sandbox telemetry and identification markers.
    4. Validates any extra environment variables against the blocked pattern list.
    """
    clean_env: dict[str, str] = {}

    if inherit_safe_host_vars:
        for var in _SAFE_HOST_ALLOWLIST:
            if var in os.environ:
                clean_env[var] = os.environ[var]

    # Ensure basic fallback PATH
    if "PATH" not in clean_env:
        clean_env["PATH"] = "/usr/local/bin:/usr/bin:/bin"

    # Injected sandbox markers
    clean_env["WHITEPACT_SANDBOX"] = "1"
    clean_env["WHITEPACT_TENANT_ID"] = organization_id
    clean_env["WHITEPACT_ACTION_ID"] = action_id
    clean_env["PYTHONUNBUFFERED"] = "1"
    clean_env["PYTHONDONTWRITEBYTECODE"] = "1"

    if extra_env:
        for k, v in extra_env.items():
            # Validate that caller didn't pass sensitive variables
            if is_sensitive_env_key(k):
                continue
            clean_env[k] = str(v)

    return clean_env


def is_sensitive_env_key(key: str) -> bool:
    """Check if an environment variable key looks like a secret or credential."""
    return any(pat.search(key) for pat in _BLOCKED_ENV_PATTERNS)
