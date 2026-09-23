# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from fastapi import FastAPI
from fastapi.testclient import TestClient

from responsibleai.dashboard.middleware import SecurityHeadersMiddleware
from responsibleai.dashboard.paddle_csp import (
    _WHITEPACT_CONTENT_SECURITY_POLICY_BASE,
    PADDLE_CONNECT_ORIGINS,
    PADDLE_SCRIPT_ORIGINS,
    contains_broad_csp_wildcards,
    whitepact_csp_with_paddle,
)


def _directive_tokens(policy: str, directive: str) -> set[str]:
    part = next(p.strip() for p in policy.split(";") if p.strip().startswith(f"{directive} "))
    return set(part.split()[1:])


def test_paddle_script_origin_permitted_on_whitepact_spa() -> None:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/dashboard")
    def _handler():
        return {"ok": True}

    csp = TestClient(app).get("/dashboard").headers["Content-Security-Policy"]
    assert set(PADDLE_SCRIPT_ORIGINS) <= _directive_tokens(csp, "script-src")
    assert "'self'" in _directive_tokens(csp, "script-src")


def test_paddle_checkout_origins_without_wildcards() -> None:
    policy = whitepact_csp_with_paddle(_WHITEPACT_CONTENT_SECURITY_POLICY_BASE)
    assert set(PADDLE_CONNECT_ORIGINS) <= _directive_tokens(policy, "connect-src")
    assert set(("https://buy.paddle.com", "https://sandbox-buy.paddle.com")) <= _directive_tokens(
        policy, "frame-src"
    )
    assert not contains_broad_csp_wildcards(policy)
    assert "*" not in policy.split("script-src")[1].split(";")[0]


def test_unrelated_external_script_blocked() -> None:
    policy = whitepact_csp_with_paddle(_WHITEPACT_CONTENT_SECURITY_POLICY_BASE)
    script_part = next(p for p in policy.split(";") if p.strip().startswith("script-src"))
    assert "https://evil.example" not in script_part
    assert "https://cdn.tailwindcss.com" not in script_part


def test_legacy_route_does_not_include_paddle_cdn() -> None:
    app = FastAPI()
    app.add_middleware(SecurityHeadersMiddleware)

    @app.get("/evaluate")
    def _handler():
        return {"ok": True}

    csp = TestClient(app).get("/evaluate").headers["Content-Security-Policy"]
    assert "cdn.paddle.com" not in csp


def test_csp_does_not_embed_server_api_key() -> None:
    policy = whitepact_csp_with_paddle(_WHITEPACT_CONTENT_SECURITY_POLICY_BASE)
    assert "pdl_" not in policy
    assert "test_" not in policy


def test_existing_security_directives_preserved() -> None:
    policy = whitepact_csp_with_paddle(_WHITEPACT_CONTENT_SECURITY_POLICY_BASE)
    assert "object-src 'none'" in policy
    assert "frame-ancestors 'none'" in policy
    assert "default-src 'self'" in policy


def test_paddle_script_origins_constant() -> None:
    assert PADDLE_SCRIPT_ORIGINS == ("https://cdn.paddle.com",)
