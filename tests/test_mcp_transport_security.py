"""Tests for MCP hosted-transport security hardening:

- DNS rebinding protection (Host/Origin allowlisting), wired via
  `_build_transport_security` into both `/mcp` and `/sse`.
- `_AuthFailureLimiter`, the per-IP sliding-window brute-force guard on
  Bearer-auth attempts against both hosted transports.

See MIGRATION_WHITEPACT_V2.md's transport security section for the
rationale. The limiter uses Redis when configured and memory in development.
"""

from __future__ import annotations

import asyncio

import httpx
import pytest
from asgi_lifespan import LifespanManager

from responsibleai.db import OrgRepository, create_engine
from responsibleai.mcp.server import (
    _AuthFailureLimiter,
    _build_transport_security,
    _env_bool,
    _env_value,
    _split_csv,
)
from responsibleai.rbac.models import Plan, Role


class TestSplitCsv:
    def test_empty_string(self) -> None:
        assert _split_csv("") == []

    def test_strips_whitespace_and_drops_blanks(self) -> None:
        assert _split_csv(" a , b,, c ") == ["a", "b", "c"]


class TestEnvBool:
    def test_unset_uses_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAI_TEST_FLAG", raising=False)
        assert _env_bool("RAI_TEST_FLAG", default=True) is True
        assert _env_bool("RAI_TEST_FLAG", default=False) is False

    @pytest.mark.parametrize("raw", ["1", "true", "True", "yes", "on"])
    def test_truthy_values(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("RAI_TEST_FLAG", raw)
        assert _env_bool("RAI_TEST_FLAG", default=False) is True

    @pytest.mark.parametrize("raw", ["0", "false", "no", "off", "garbage"])
    def test_falsy_values(self, monkeypatch: pytest.MonkeyPatch, raw: str) -> None:
        monkeypatch.setenv("RAI_TEST_FLAG", raw)
        assert _env_bool("RAI_TEST_FLAG", default=True) is False


class TestEnvValue:
    def test_preferred_whitepact_name_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WHITEPACT_TEST_SETTING", "preferred")
        monkeypatch.setenv("RAI_TEST_SETTING", "legacy")
        assert _env_value("WHITEPACT_TEST_SETTING", "RAI_TEST_SETTING", "default") == "preferred"

    def test_legacy_name_remains_compatible(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("WHITEPACT_TEST_SETTING", raising=False)
        monkeypatch.setenv("RAI_TEST_SETTING", "legacy")
        assert _env_value("WHITEPACT_TEST_SETTING", "RAI_TEST_SETTING", "default") == "legacy"

    def test_default_when_both_are_unset(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("WHITEPACT_TEST_SETTING", raising=False)
        monkeypatch.delenv("RAI_TEST_SETTING", raising=False)
        assert _env_value("WHITEPACT_TEST_SETTING", "RAI_TEST_SETTING", "default") == "default"


class TestBuildTransportSecurity:
    def test_disabled_by_default_with_no_allowlists(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.delenv("RAI_MCP_HTTP_ALLOWED_HOSTS", raising=False)
        monkeypatch.delenv("RAI_MCP_HTTP_ALLOWED_ORIGINS", raising=False)
        monkeypatch.delenv("RAI_MCP_HTTP_DNS_REBINDING_PROTECTION", raising=False)
        settings = _build_transport_security()
        assert settings.enable_dns_rebinding_protection is False

    def test_auto_enabled_once_hosts_configured(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAI_MCP_HTTP_ALLOWED_HOSTS", "mcp.example.com")
        monkeypatch.delenv("RAI_MCP_HTTP_ALLOWED_ORIGINS", raising=False)
        monkeypatch.delenv("RAI_MCP_HTTP_DNS_REBINDING_PROTECTION", raising=False)
        settings = _build_transport_security()
        assert settings.enable_dns_rebinding_protection is True
        assert settings.allowed_hosts == ["mcp.example.com"]

    def test_explicit_flag_overrides_auto_enable(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("RAI_MCP_HTTP_ALLOWED_HOSTS", "mcp.example.com")
        monkeypatch.setenv("RAI_MCP_HTTP_DNS_REBINDING_PROTECTION", "false")
        settings = _build_transport_security()
        assert settings.enable_dns_rebinding_protection is False

    def test_preferred_whitepact_allowlist_wins(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("WHITEPACT_MCP_HTTP_ALLOWED_HOSTS", "preferred.example")
        monkeypatch.setenv("RAI_MCP_HTTP_ALLOWED_HOSTS", "legacy.example")
        settings = _build_transport_security()
        assert settings.allowed_hosts == ["preferred.example"]


class TestAuthFailureLimiter:
    class _FakeRedis:
        def __init__(self) -> None:
            self.sets: dict[str, dict[str, float]] = {}
            self.commands: list[tuple] = []

        def pipeline(self, transaction=True):
            self.commands = []
            return self

        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        def zremrangebyscore(self, key, minimum, maximum):
            self.commands.append(("remove", key, float(maximum)))
            return self

        def zcard(self, key):
            self.commands.append(("count", key))
            return self

        def zadd(self, key, values):
            self.commands.append(("add", key, values))
            return self

        def expire(self, key, seconds):
            self.commands.append(("expire", key, seconds))
            return self

        async def execute(self):
            results = []
            for command in self.commands:
                operation, key, *args = command
                values = self.sets.setdefault(key, {})
                if operation == "remove":
                    cutoff = args[0]
                    removed = [member for member, score in values.items() if score <= cutoff]
                    for member in removed:
                        values.pop(member)
                    results.append(len(removed))
                elif operation == "count":
                    results.append(len(values))
                elif operation == "add":
                    values.update(args[0])
                    results.append(len(args[0]))
                else:
                    results.append(True)
            return results

    async def test_not_blocked_before_threshold(self) -> None:
        limiter = _AuthFailureLimiter(max_failures=3, window_seconds=60)
        for _ in range(2):
            await limiter.record_failure("1.2.3.4")
        assert await limiter.is_blocked("1.2.3.4") is False

    async def test_blocked_at_threshold(self) -> None:
        limiter = _AuthFailureLimiter(max_failures=3, window_seconds=60)
        for _ in range(3):
            await limiter.record_failure("1.2.3.4")
        assert await limiter.is_blocked("1.2.3.4") is True

    async def test_keys_are_independent(self) -> None:
        limiter = _AuthFailureLimiter(max_failures=1, window_seconds=60)
        await limiter.record_failure("1.2.3.4")
        assert await limiter.is_blocked("1.2.3.4") is True
        assert await limiter.is_blocked("5.6.7.8") is False

    async def test_window_expiry_unblocks(self) -> None:
        limiter = _AuthFailureLimiter(max_failures=1, window_seconds=0.05)
        await limiter.record_failure("1.2.3.4")
        assert await limiter.is_blocked("1.2.3.4") is True
        await asyncio.sleep(0.1)
        assert await limiter.is_blocked("1.2.3.4") is False

    async def test_redis_backend_is_shared_across_replicas(self, monkeypatch) -> None:
        redis = self._FakeRedis()
        first = _AuthFailureLimiter(2, 60, redis_url="redis://test")
        second = _AuthFailureLimiter(2, 60, redis_url="redis://test")

        async def shared_redis():
            return redis

        monkeypatch.setattr(first, "_get_redis", shared_redis)
        monkeypatch.setattr(second, "_get_redis", shared_redis)
        await first.record_failure("1.2.3.4")
        await second.record_failure("1.2.3.4")
        assert await first.is_blocked("1.2.3.4") is True


@pytest.fixture()
async def app_factory(monkeypatch: pytest.MonkeyPatch):
    """Yields a callable that builds the hosted-MCP app fresh — env vars
    set *before* calling it take effect, since `_build_http_app` and its
    helpers read `os.environ` at call time, not import time."""
    import responsibleai.db as db_module
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)

    org_repo = OrgRepository(engine)
    org = await org_repo.create_org("Acme", "acme", plan=Plan.ENTERPRISE)
    _key_rec, raw_key = await org_repo.create_key(org.id, "test-key", role=Role.ANALYST)

    built_apps = []

    async def _build():
        app = _build_http_app()
        manager = LifespanManager(app)
        await manager.__aenter__()
        built_apps.append(manager)
        return manager.app, raw_key

    yield _build

    for manager in built_apps:
        await manager.__aexit__(None, None, None)
    await engine.close()


async def _raw_client(app) -> httpx.AsyncClient:
    return httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://testserver")


class TestDnsRebindingProtectionIntegration:
    async def test_mismatched_host_rejected_when_enabled(
        self, app_factory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAI_MCP_HTTP_ALLOWED_HOSTS", "mcp.example.com")
        app, raw_key = await app_factory()
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": f"Bearer {raw_key}"},
            )
        # base_url="http://testserver" sends Host: testserver, which isn't
        # in the allowlist — 421 per the MCP SDK's own DNS rebinding check.
        assert response.status_code == 421

    async def test_matching_host_allowed_through_to_auth(
        self, app_factory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAI_MCP_HTTP_ALLOWED_HOSTS", "testserver")
        app, _raw_key = await app_factory()
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            )
        # No auth header -- rejected by our own auth check (401), not by
        # DNS rebinding protection (which would be 421). Proves the
        # allowlisted host passed the SDK's own check.
        assert response.status_code == 401

    async def test_disabled_by_default_any_host_reaches_auth(self, app_factory) -> None:
        app, _raw_key = await app_factory()
        async with await _raw_client(app) as client:
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
            )
        assert response.status_code == 401


class TestAuthRateLimitIntegration:
    async def test_blocked_after_repeated_failures_on_mcp(
        self, app_factory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setenv("RAI_MCP_HTTP_AUTH_MAX_FAILURES", "3")
        monkeypatch.setenv("RAI_MCP_HTTP_AUTH_WINDOW_SECONDS", "60")
        app, _raw_key = await app_factory()
        async with await _raw_client(app) as client:
            statuses = []
            for _ in range(5):
                response = await client.post(
                    "/mcp",
                    json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                    headers={"Authorization": "Bearer wrong-key"},
                )
                statuses.append(response.status_code)
        assert statuses[:3] == [401, 401, 401]
        assert statuses[3:] == [429, 429]

    async def test_failure_budget_is_shared_between_transports(
        self, app_factory, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """A probe against /sse shouldn't get a fresh budget by switching
        to /mcp -- both hosted transports share one `auth_limiter`."""
        monkeypatch.setenv("RAI_MCP_HTTP_AUTH_MAX_FAILURES", "2")
        monkeypatch.setenv("RAI_MCP_HTTP_AUTH_WINDOW_SECONDS", "60")
        app, _raw_key = await app_factory()
        async with await _raw_client(app) as client:
            await client.get("/sse", headers={"Authorization": "Bearer wrong-key"})
            await client.get("/sse", headers={"Authorization": "Bearer wrong-key"})
            response = await client.post(
                "/mcp",
                json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                headers={"Authorization": "Bearer wrong-key"},
            )
        assert response.status_code == 429

    async def test_successful_auth_not_rate_limited(self, app_factory) -> None:
        app, raw_key = await app_factory()
        async with await _raw_client(app) as client:
            for _ in range(5):
                response = await client.post(
                    "/mcp",
                    json={"jsonrpc": "2.0", "method": "ping", "id": 1},
                    headers={"Authorization": f"Bearer {raw_key}"},
                )
                assert response.status_code != 429
                assert response.status_code != 401
