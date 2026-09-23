# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Centralized redaction for Sovereign outputs."""

from __future__ import annotations

import re
from typing import Any

_REDACTED = "[REDACTED]"
_SENSITIVE_KEYS = frozenset(
    {
        "password",
        "secret",
        "token",
        "api_key",
        "api-key",
        "authorization",
        "private_key",
        "private-key",
        "credential",
        "credentials",
    }
)
_BEARER = re.compile(r"Bearer\s+[A-Za-z0-9._~+/=-]+", re.IGNORECASE)
# Bounded segments avoid polynomial backtracking on attacker-controlled log payloads.
_JWT = re.compile(r"eyJ[A-Za-z0-9_-]{10,512}\.[A-Za-z0-9_-]{10,512}\.[A-Za-z0-9_-]{10,512}")


def _key_is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS or any(
        s in normalized for s in ("secret", "password", "token", "credential", "private_key")
    )


def redact_string(value: str) -> str:
    out = _BEARER.sub(f"Bearer {_REDACTED}", value)
    out = _JWT.sub(_REDACTED, out)
    return out


def redact_value(value: Any, *, depth: int = 0, max_depth: int = 12) -> Any:
    if depth > max_depth:
        return _REDACTED
    if isinstance(value, str):
        return redact_string(value)
    if isinstance(value, dict):
        out: dict[str, Any] = {}
        for k, v in value.items():
            if _key_is_sensitive(str(k)):
                out[str(k)] = _REDACTED
            else:
                out[str(k)] = redact_value(v, depth=depth + 1, max_depth=max_depth)
        return out
    if isinstance(value, list):
        return [redact_value(v, depth=depth + 1, max_depth=max_depth) for v in value]
    return value


def redact_for_debugger(payload: dict[str, Any]) -> dict[str, Any]:
    """Prefer keys, types, counts, fingerprints — never raw secrets."""
    return redact_value(payload)
