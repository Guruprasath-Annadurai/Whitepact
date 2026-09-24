# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch coverage for dashboard rate-limit key selection."""

from __future__ import annotations

from starlette.requests import Request

from responsibleai.dashboard.app import _get_rate_limit_key


def _request(headers: list[tuple[bytes, bytes]]) -> Request:
    scope = {
        "type": "http",
        "method": "GET",
        "path": "/",
        "headers": headers,
        "client": ("203.0.113.9", 12345),
        "server": ("test", 80),
        "scheme": "http",
    }
    return Request(scope)


def test_rate_limit_key_hashes_bearer_token() -> None:
    req = _request([(b"authorization", b"Bearer org-secret-token")])
    key = _get_rate_limit_key(req)
    assert key.startswith("key:")
    assert len(key) == len("key:") + 24


def test_rate_limit_key_empty_bearer_falls_back_to_ip() -> None:
    req = _request([(b"authorization", b"Bearer    ")])
    key = _get_rate_limit_key(req)
    assert key == "203.0.113.9"


def test_rate_limit_key_no_auth_uses_client_ip() -> None:
    req = _request([])
    assert _get_rate_limit_key(req) == "203.0.113.9"
