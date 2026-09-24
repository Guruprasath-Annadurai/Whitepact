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
_MAX_JWT_SEGMENT = 512
_MAX_REDACT_INPUT = 65536


def _jwt_end(text: str, start: int) -> int | None:
    """Linear-time end index for a JWT-shaped substring starting at start (or None)."""
    if not text.startswith("eyJ", start):
        return None
    i = start + 3
    n = len(text)
    for _part in range(3):
        seg = 0
        while i < n and (text[i].isalnum() or text[i] in "_-"):
            seg += 1
            if seg > _MAX_JWT_SEGMENT:
                return None
            i += 1
        if seg < 1:
            return None
        if _part < 2:
            if i >= n or text[i] != ".":
                return None
            i += 1
    return i


def _key_is_sensitive(key: str) -> bool:
    normalized = key.lower().replace("-", "_")
    return normalized in _SENSITIVE_KEYS or any(
        s in normalized for s in ("secret", "password", "token", "credential", "private_key")
    )


def _redact_jwt_like(text: str) -> str:
    out: list[str] = []
    i = 0
    n = len(text)
    while i < n:
        end = _jwt_end(text, i)
        if end is not None:
            out.append(_REDACTED)
            i = end
            continue
        out.append(text[i])
        i += 1
    return "".join(out)


def redact_string(value: str) -> str:
    if len(value) > _MAX_REDACT_INPUT:
        value = value[:_MAX_REDACT_INPUT]
    out = _BEARER.sub(f"Bearer {_REDACTED}", value)
    return _redact_jwt_like(out)


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
