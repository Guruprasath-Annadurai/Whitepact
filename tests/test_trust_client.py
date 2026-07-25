"""Tests for TrustClient — the framework-agnostic HTTP client every
agent-framework integration in src/responsibleai/integrations/ builds on."""

from __future__ import annotations

import httpx
import pytest
import respx

from responsibleai.integrations.client import (
    DEFAULT_BASE_URL,
    TrustCheckResult,
    TrustClient,
)


class TestBaseUrlResolution:
    def test_defaults_to_hosted_instance(self) -> None:
        assert TrustClient().base_url == DEFAULT_BASE_URL

    def test_explicit_base_url_wins(self) -> None:
        assert TrustClient("https://example.com/").base_url == "https://example.com"

    def test_env_var_overrides_default(self, monkeypatch) -> None:
        monkeypatch.setenv("RAI_TRUST_API_BASE", "https://custom.example.com")
        assert TrustClient().base_url == "https://custom.example.com"


class TestCheckSync:
    @respx.mock
    def test_known_model_parses_full_result(self) -> None:
        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "gpt-4o", "provider": "openai", "known": True,
                "trust_score": {"overall": 88.0}, "certified": True,
                "has_reported_incidents": False, "passport_id": "p1",
                "verify_url": "/api/trust-index/verify/p1", "recent_incidents": [],
            })
        )
        result = TrustClient("https://api.test").check("gpt-4o", "openai")
        assert result == TrustCheckResult(
            model="gpt-4o", provider="openai", known=True,
            trust_score={"overall": 88.0}, certified=True,
            has_reported_incidents=False, passport_id="p1",
            verify_url="/api/trust-index/verify/p1", recent_incidents=[],
        )
        assert result.overall_score == 88.0

    @respx.mock
    def test_http_error_produces_error_result(self) -> None:
        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(500)
        )
        result = TrustClient("https://api.test").check("x", "y")
        assert result.error is not None
        assert result.known is False

    @respx.mock
    def test_connect_error_produces_error_result(self) -> None:
        respx.get("https://api.test/api/trust-index/check").mock(
            side_effect=httpx.ConnectError("nope")
        )
        result = TrustClient("https://api.test").check("x", "y")
        assert result.error is not None


class TestCheckAsync:
    @respx.mock
    async def test_known_model_parses(self) -> None:
        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "x", "provider": "y", "known": True,
                "trust_score": {"overall": 50.0}, "certified": False,
                "has_reported_incidents": False,
            })
        )
        result = await TrustClient("https://api.test").check_async("x", "y")
        assert result.known is True
        assert result.overall_score == 50.0


class TestPasses:
    def test_error_always_fails_open(self) -> None:
        r = TrustCheckResult("x", "y", known=True, trust_score={"overall": 0},
                              certified=False, has_reported_incidents=False, error="boom")
        assert r.passes(min_score=99, require_known=True) is True

    def test_unknown_fails_open_by_default(self) -> None:
        r = TrustCheckResult("x", "y", known=False, trust_score=None,
                              certified=False, has_reported_incidents=False)
        assert r.passes(min_score=99) is True

    def test_unknown_fails_closed_when_required(self) -> None:
        r = TrustCheckResult("x", "y", known=False, trust_score=None,
                              certified=False, has_reported_incidents=False)
        assert r.passes(require_known=True) is False

    @pytest.mark.parametrize(
        ("score", "min_score", "expected"),
        [(80, 70, True), (60, 70, False), (70, 70, True)],
    )
    def test_known_compares_against_threshold(self, score, min_score, expected) -> None:
        r = TrustCheckResult("x", "y", known=True, trust_score={"overall": score},
                              certified=False, has_reported_incidents=False)
        assert r.passes(min_score=min_score) is expected

    def test_reported_incidents_alone_do_not_fail_the_check(self) -> None:
        r = TrustCheckResult("x", "y", known=True, trust_score={"overall": 90},
                              certified=False, has_reported_incidents=True)
        assert r.passes(min_score=70) is True
