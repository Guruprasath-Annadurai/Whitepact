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
        # dataclasses.replace, not ==, since `checked_at` is stamped at
        # construction time (Continuous MCP Trust) and would never
        # equal a second `datetime.now(UTC)` call made here.
        from dataclasses import replace

        assert replace(result, checked_at=result.checked_at) == TrustCheckResult(
            model="gpt-4o", provider="openai", known=True,
            trust_score={"overall": 88.0}, certified=True,
            has_reported_incidents=False, passport_id="p1",
            verify_url="/api/trust-index/verify/p1", recent_incidents=[],
            checked_at=result.checked_at,
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


class TestIsStale:
    def test_fresh_result_is_not_stale(self) -> None:
        r = TrustCheckResult("x", "y", known=True, trust_score=None,
                              certified=False, has_reported_incidents=False)
        assert r.is_stale(ttl_minutes=10) is False

    def test_old_result_is_stale(self) -> None:
        from datetime import UTC, datetime, timedelta

        old = datetime.now(UTC) - timedelta(minutes=20)
        r = TrustCheckResult("x", "y", known=True, trust_score=None,
                              certified=False, has_reported_incidents=False, checked_at=old)
        assert r.is_stale(ttl_minutes=10) is True


class TestCachingDisabledByDefault:
    """cache_ttl_minutes=0 (the default) -- every call() is a live
    fetch, identical to TrustClient's behavior before caching existed."""

    @respx.mock
    def test_two_calls_both_hit_the_network(self) -> None:
        route = respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "x", "provider": "y", "known": True,
                "trust_score": {"overall": 90}, "certified": False,
                "has_reported_incidents": False,
            })
        )
        client = TrustClient("https://api.test")
        client.check("x", "y")
        client.check("x", "y")
        assert route.call_count == 2


class TestCachingEnabled:
    @respx.mock
    def test_second_call_within_ttl_served_from_cache(self) -> None:
        route = respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "x", "provider": "y", "known": True,
                "trust_score": {"overall": 90}, "certified": False,
                "has_reported_incidents": False,
            })
        )
        client = TrustClient("https://api.test", cache_ttl_minutes=10)
        first = client.check("x", "y")
        second = client.check("x", "y")
        assert route.call_count == 1
        assert second is first
        assert second.stale is False

    @respx.mock
    def test_different_model_provider_pairs_cached_separately(self) -> None:
        route = respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "x", "provider": "y", "known": True,
                "trust_score": {"overall": 90}, "certified": False,
                "has_reported_incidents": False,
            })
        )
        client = TrustClient("https://api.test", cache_ttl_minutes=10)
        client.check("x", "y")
        client.check("a", "b")
        assert route.call_count == 2

    @respx.mock
    def test_expired_cache_entry_triggers_live_refetch(self) -> None:
        from datetime import UTC, datetime, timedelta

        route = respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "x", "provider": "y", "known": True,
                "trust_score": {"overall": 95}, "certified": False,
                "has_reported_incidents": False,
            })
        )
        client = TrustClient("https://api.test", cache_ttl_minutes=10)
        client._cache[("x", "y")] = TrustCheckResult(
            "x", "y", known=True, trust_score={"overall": 10},
            certified=False, has_reported_incidents=False,
            checked_at=datetime.now(UTC) - timedelta(minutes=20),
        )
        result = client.check("x", "y")
        assert route.call_count == 1
        assert result.overall_score == 95
        assert result.stale is False

    @respx.mock
    def test_failed_refetch_falls_back_to_stale_cached_entry(self) -> None:
        from datetime import UTC, datetime, timedelta

        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(500)
        )
        client = TrustClient("https://api.test", cache_ttl_minutes=10)
        client._cache[("x", "y")] = TrustCheckResult(
            "x", "y", known=True, trust_score={"overall": 42},
            certified=False, has_reported_incidents=False,
            checked_at=datetime.now(UTC) - timedelta(minutes=20),
        )
        result = client.check("x", "y")
        assert result.stale is True
        assert result.overall_score == 42  # the old data, not discarded
        assert result.error is None  # real data exists -- not the no-data error path

    @respx.mock
    def test_failed_refetch_with_no_prior_cache_produces_error_result(self) -> None:
        respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(500)
        )
        client = TrustClient("https://api.test", cache_ttl_minutes=10)
        result = client.check("x", "y")
        assert result.error is not None
        assert result.stale is False

    @respx.mock
    async def test_async_caching_and_stale_fallback_mirror_sync(self) -> None:
        from datetime import UTC, datetime, timedelta

        route = respx.get("https://api.test/api/trust-index/check").mock(
            return_value=httpx.Response(200, json={
                "model": "x", "provider": "y", "known": True,
                "trust_score": {"overall": 90}, "certified": False,
                "has_reported_incidents": False,
            })
        )
        client = TrustClient("https://api.test", cache_ttl_minutes=10)
        await client.check_async("x", "y")
        await client.check_async("x", "y")
        assert route.call_count == 1

        route.mock(return_value=httpx.Response(500))
        client._cache[("x", "y")] = TrustCheckResult(
            "x", "y", known=True, trust_score={"overall": 90},
            certified=False, has_reported_incidents=False,
            checked_at=datetime.now(UTC) - timedelta(minutes=20),
        )
        stale_result = await client.check_async("x", "y")
        assert stale_result.stale is True
