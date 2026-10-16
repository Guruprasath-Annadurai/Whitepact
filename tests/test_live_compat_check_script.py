# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The live-endpoint conformance checker, exercised against the in-process hosted app (and an unfit one)."""

from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

import httpx
import pytest

from tests import test_mcp_oauth_authorization_server as _base

oauth_app = _base.oauth_app

_spec = importlib.util.spec_from_file_location(
    "live_mcp_compat_check",
    Path(__file__).resolve().parents[1] / "scripts" / "live_mcp_compat_check.py",
)
checker = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
sys.modules["live_mcp_compat_check"] = checker
_spec.loader.exec_module(checker)  # type: ignore[union-attr]


def _client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="https://testserver")


async def test_a_conformant_endpoint_passes_every_check_without_a_credential_for_discovery(
    oauth_app,
) -> None:
    app, *_ = oauth_app
    async with _client(app) as client:
        checks = await checker.run_checks(client, resource=_base.RESOURCE, token=None)
    by_status = {c.name: c.status for c in checks}
    assert "FAIL" not in by_status.values(), [c for c in checks if c.status == "FAIL"]
    assert any(
        c.status == "SKIP" for c in checks
    )  # credential-gated checks are skipped, never passed
    assert (
        by_status["unauthenticated request gets 401 (Claude ignores a challenge on 200)"] == "PASS"
    )
    assert by_status["PKCE S256 advertised"] == "PASS"


async def test_a_wrong_resource_url_fails_the_exact_match_check(oauth_app) -> None:
    app, *_ = oauth_app
    async with _client(app) as client:
        checks = await checker.run_checks(client, resource="https://testserver/other", token=None)
    failed = {c.name for c in checks if c.status == "FAIL"}
    assert "protected-resource `resource` equals the connector URL exactly" in failed


async def test_a_bad_credential_fails_instead_of_skipping(oauth_app) -> None:
    app, *_ = oauth_app
    async with _client(app) as client:
        checks = await checker.run_checks(client, resource=_base.RESOURCE, token="wp_live_invalid")
    assert any(c.status == "FAIL" and "initialize" in c.name for c in checks)


def test_the_script_never_prints_the_token(capsys: pytest.CaptureFixture[str], monkeypatch) -> None:
    monkeypatch.setenv("WHITEPACT_COMPAT_TOKEN", "super-secret-token-value")
    assert (
        checker.main(
            [
                "--base-url",
                "http://insecure.example.com",
                "--resource",
                "http://insecure.example.com/mcp",
            ]
        )
        == 2
    )
    out = capsys.readouterr()
    assert "super-secret-token-value" not in out.out + out.err
