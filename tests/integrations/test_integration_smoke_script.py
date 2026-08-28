# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Tests for scripts/integration_smoke.py -- the cross-platform onboarding
preflight script.

This does NOT re-test WhitePact's MCP protocol behavior itself (that's
already covered thoroughly, in-process, by test_mcp_http_transport.py and
test_mcp_transport_security.py). It tests that the smoke script's own
check functions correctly interpret server responses -- using
`httpx.MockTransport` to simulate exactly the response shapes the live
hosted endpoint returns, without a network call or a live DB-backed app.
That keeps this suite fast and deterministic while still catching
regressions in the smoke script's own pass/fail logic.
"""

from __future__ import annotations

import sys
from pathlib import Path

import httpx
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "scripts"))
import integration_smoke as smoke  # noqa: E402


def _client(handler) -> httpx.Client:
    return httpx.Client(transport=httpx.MockTransport(handler), base_url="http://testserver")


class TestHealthCheck:
    def test_passes_on_ok_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"status": "ok", "tools": 27})

        report = smoke.SmokeReport(base_url="http://testserver")
        with _client(handler) as client:
            smoke.check_health(report, client)
        assert report.results[0].passed

    def test_fails_on_non_ok_status(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(500, json={"status": "error"})

        report = smoke.SmokeReport(base_url="http://testserver")
        with _client(handler) as client:
            smoke.check_health(report, client)
        assert not report.results[0].passed


class TestAuthChecks:
    def test_unauthenticated_init_expects_401(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(401, json={"error": "unauthorized"})

        report = smoke.SmokeReport(base_url="http://testserver")
        with _client(handler) as client:
            smoke.check_initialize_requires_auth(report, client)
        assert report.results[0].passed

    def test_unauthenticated_init_flags_regression_if_200(self) -> None:
        """If a future change ever lets an unauthenticated request through,
        this must fail the smoke suite, not silently pass."""

        def handler(request: httpx.Request) -> httpx.Response:
            return httpx.Response(200, json={"result": "should not happen"})

        report = smoke.SmokeReport(base_url="http://testserver")
        with _client(handler) as client:
            smoke.check_initialize_requires_auth(report, client)
        assert not report.results[0].passed

    def test_invalid_token_rejected(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            assert request.headers["authorization"] == "Bearer not-a-real-key"
            return httpx.Response(401, json={"error": "unauthorized"})

        report = smoke.SmokeReport(base_url="http://testserver")
        with _client(handler) as client:
            smoke.check_invalid_token(report, client)
        assert report.results[0].passed


class TestAuthenticatedFlowSkipsWithoutKey:
    def test_skips_and_reports_real_provider_test_kind(self) -> None:
        def handler(request: httpx.Request) -> httpx.Response:
            raise AssertionError("should not make a request when no api_key is supplied")

        report = smoke.SmokeReport(base_url="http://testserver")
        with _client(handler) as client:
            smoke.check_authenticated_flow(report, client, api_key=None)

        assert len(report.results) == 2
        assert all(r.kind == "REAL_PROVIDER_TEST" for r in report.results)
        assert all(not r.passed for r in report.results)
        assert "FOUNDER_ACTIONS.md" in report.results[0].limitation


class TestReportExitCode:
    def test_local_protocol_failure_fails_the_run_even_if_provider_test_skipped(self) -> None:
        report = smoke.SmokeReport(base_url="http://testserver")
        report.add("some_local_check", "LOCAL_PROTOCOL_TEST", False, "boom")
        report.add("some_provider_check", "REAL_PROVIDER_TEST", False, "skipped: no key")
        local_failed = any(not r.passed for r in report.results if r.kind == "LOCAL_PROTOCOL_TEST")
        assert local_failed is True

    def test_only_provider_test_skip_does_not_fail_the_run(self) -> None:
        report = smoke.SmokeReport(base_url="http://testserver")
        report.add("some_local_check", "LOCAL_PROTOCOL_TEST", True, "ok")
        report.add("some_provider_check", "REAL_PROVIDER_TEST", False, "skipped: no key")
        local_failed = any(not r.passed for r in report.results if r.kind == "LOCAL_PROTOCOL_TEST")
        assert local_failed is False


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
