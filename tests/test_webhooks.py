"""Tests for the WebhookManager — delivery, retry, HMAC signing, formatters."""

from __future__ import annotations

import asyncio
import hashlib
import hmac
from unittest.mock import AsyncMock, patch

import httpx
import pytest
import respx

from responsibleai.webhooks.manager import (
    UnsafeWebhookURLError,
    WebhookManager,
    validate_webhook_url,
)
from responsibleai.webhooks.models import (
    WebhookConfig,
    WebhookEvent,
    WebhookProvider,
)


@pytest.fixture(autouse=True)
def _fake_public_dns(monkeypatch):
    """Delivery tests use synthetic hostnames (hooks.example.com, etc.) that
    aren't real DNS records. The SSRF guard (validate_webhook_url) does a
    real getaddrinfo() lookup before every delivery — resolve every test
    hostname to a fixed public IP so the guard's logic still runs (and still
    rejects a genuinely private-IP config, see TestSSRFGuard below) without
    depending on real network access."""

    def _fake_getaddrinfo(host, *args, **kwargs):
        return [(2, 1, 6, "", ("93.184.216.34", 0))]

    monkeypatch.setattr(
        "responsibleai.webhooks.manager.socket.getaddrinfo", _fake_getaddrinfo
    )


@pytest.fixture()
def manager() -> WebhookManager:
    return WebhookManager()


@pytest.fixture()
def generic_config() -> WebhookConfig:
    return WebhookConfig(
        url="https://hooks.example.com/generic",
        events=[WebhookEvent.DRIFT_ALERT, WebhookEvent.BUDGET_EXCEEDED],
        provider=WebhookProvider.GENERIC,
    )


@pytest.fixture()
def slack_config() -> WebhookConfig:
    return WebhookConfig(
        url="https://hooks.slack.com/test",
        events=[WebhookEvent.DRIFT_ALERT],
        provider=WebhookProvider.SLACK,
    )


# ── Registration ───────────────────────────────────────────────────────────────

class TestRegistration:
    def test_register_returns_config(self, manager, generic_config):
        result = manager.register(generic_config)
        assert result.id == generic_config.id

    def test_list_empty_initially(self, manager):
        assert manager.list_webhooks() == []

    def test_list_after_register(self, manager, generic_config):
        manager.register(generic_config)
        assert len(manager.list_webhooks()) == 1

    def test_remove_returns_true(self, manager, generic_config):
        manager.register(generic_config)
        assert manager.remove(generic_config.id) is True

    def test_remove_missing_returns_false(self, manager):
        assert manager.remove("nonexistent") is False

    def test_get_returns_config(self, manager, generic_config):
        manager.register(generic_config)
        assert manager.get(generic_config.id) is generic_config

    def test_get_missing_returns_none(self, manager):
        assert manager.get("missing") is None

    def test_multiple_webhooks(self, manager):
        for i in range(5):
            c = WebhookConfig(url=f"https://hooks.example.com/{i}", events=[WebhookEvent.DRIFT_ALERT])
            manager.register(c)
        assert len(manager.list_webhooks()) == 5

    def test_update_changes_field(self, manager, generic_config):
        manager.register(generic_config)
        updated = manager.update(generic_config.id, enabled=False)
        assert updated is not None
        assert updated.enabled is False
        assert manager.get(generic_config.id).enabled is False

    def test_update_ignores_unknown_field(self, manager, generic_config):
        manager.register(generic_config)
        updated = manager.update(generic_config.id, nonexistent_field="x")
        assert updated is not None
        assert not hasattr(updated, "nonexistent_field")

    def test_update_missing_webhook_returns_none(self, manager):
        assert manager.update("missing-id", enabled=False) is None


# ── Delivery ───────────────────────────────────────────────────────────────────

class TestDelivery:
    @respx.mock
    async def test_successful_delivery(self, manager, generic_config):
        respx.post(generic_config.url).mock(return_value=httpx.Response(200))
        manager.register(generic_config)
        deliveries = await manager.fire(WebhookEvent.DRIFT_ALERT, {"model": "gpt-4o", "delta": 10.0})
        assert len(deliveries) == 1
        assert deliveries[0].success is True
        assert deliveries[0].status_code == 200

    @respx.mock
    async def test_no_delivery_for_unregistered_event(self, manager, generic_config):
        manager.register(generic_config)
        # GUARDRAIL_TRIGGERED not in generic_config.events
        deliveries = await manager.fire(WebhookEvent.GUARDRAIL_TRIGGERED, {})
        assert deliveries == []

    @respx.mock
    async def test_delivery_to_matching_event_only(self, manager):
        c1 = WebhookConfig(url="https://a.com", events=[WebhookEvent.DRIFT_ALERT])
        c2 = WebhookConfig(url="https://b.com", events=[WebhookEvent.BUDGET_EXCEEDED])
        respx.post("https://a.com").mock(return_value=httpx.Response(200))
        manager.register(c1)
        manager.register(c2)
        deliveries = await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        assert len(deliveries) == 1
        assert deliveries[0].webhook_id == c1.id

    @respx.mock
    async def test_disabled_webhook_skipped(self, manager):
        c = WebhookConfig(url="https://a.com", events=[WebhookEvent.DRIFT_ALERT], enabled=False)
        manager.register(c)
        deliveries = await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        assert deliveries == []

    @respx.mock
    async def test_failed_delivery_records_error(self, manager, generic_config):
        respx.post(generic_config.url).mock(return_value=httpx.Response(500))
        manager.register(generic_config)
        with patch("responsibleai.webhooks.manager._RETRY_DELAYS", []):
            deliveries = await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        assert deliveries[0].success is False
        assert deliveries[0].last_error is not None

    @respx.mock
    async def test_delivery_attempts_increment(self, manager, generic_config):
        respx.post(generic_config.url).mock(return_value=httpx.Response(200))
        manager.register(generic_config)
        deliveries = await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        assert deliveries[0].attempts >= 1

    @respx.mock
    async def test_concurrent_delivery_to_multiple_webhooks(self, manager):
        urls = [f"https://hook{i}.example.com" for i in range(3)]
        for url in urls:
            c = WebhookConfig(url=url, events=[WebhookEvent.DRIFT_ALERT])
            respx.post(url).mock(return_value=httpx.Response(200))
            manager.register(c)
        deliveries = await manager.fire(WebhookEvent.DRIFT_ALERT, {"test": True})
        assert len(deliveries) == 3
        assert all(d.success for d in deliveries)


# ── HMAC signing ───────────────────────────────────────────────────────────────

class TestHMACSigning:
    @respx.mock
    async def test_signature_header_present(self, manager):
        url = "https://secure.example.com/hook"
        c = WebhookConfig(url=url, events=[WebhookEvent.DRIFT_ALERT], secret="my-secret")
        received_headers: dict = {}

        def capture(request: httpx.Request):
            received_headers.update(dict(request.headers))
            return httpx.Response(200)

        respx.post(url).mock(side_effect=capture)
        manager.register(c)
        await manager.fire(WebhookEvent.DRIFT_ALERT, {"model": "test"})
        assert "x-rai-signature-256" in received_headers

    @respx.mock
    async def test_signature_is_valid_hmac(self, manager):
        url = "https://secure.example.com/hook2"
        secret = "super-secret"
        c = WebhookConfig(url=url, events=[WebhookEvent.DRIFT_ALERT], secret=secret)
        captured: dict = {}

        def capture(request: httpx.Request):
            captured["body"] = request.content
            captured["sig"] = request.headers.get("x-rai-signature-256", "")
            return httpx.Response(200)

        respx.post(url).mock(side_effect=capture)
        manager.register(c)
        await manager.fire(WebhookEvent.DRIFT_ALERT, {"model": "test"})

        expected = "sha256=" + hmac.new(secret.encode(), captured["body"], hashlib.sha256).hexdigest()
        assert captured["sig"] == expected

    @respx.mock
    async def test_no_signature_without_secret(self, manager):
        url = "https://nosig.example.com/hook"
        c = WebhookConfig(url=url, events=[WebhookEvent.DRIFT_ALERT], secret="")
        received_headers: dict = {}

        def capture(request: httpx.Request):
            received_headers.update(dict(request.headers))
            return httpx.Response(200)

        respx.post(url).mock(side_effect=capture)
        manager.register(c)
        await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        assert "x-rai-signature-256" not in received_headers


# ── Payload formatters ─────────────────────────────────────────────────────────

class TestPayloadFormatters:
    def test_generic_payload_structure(self, manager):
        p = manager._format_payload(WebhookProvider.GENERIC, WebhookEvent.DRIFT_ALERT, {"delta": 5})
        assert p["event"] == "drift_alert"
        assert "timestamp" in p
        assert p["data"]["delta"] == 5

    def test_slack_payload_has_blocks(self, manager):
        p = manager._format_payload(WebhookProvider.SLACK, WebhookEvent.DRIFT_ALERT, {"model": "gpt-4o"})
        assert "blocks" in p
        assert any(b.get("type") == "header" for b in p["blocks"])

    def test_teams_payload_has_message_card(self, manager):
        p = manager._format_payload(WebhookProvider.TEAMS, WebhookEvent.BUDGET_EXCEEDED, {"limit": 1000})
        assert p["@type"] == "MessageCard"
        assert len(p["sections"]) > 0

    def test_pagerduty_payload_has_routing_key(self, manager):
        p = manager._format_payload(WebhookProvider.PAGERDUTY, WebhookEvent.BUDGET_EXCEEDED, {"routing_key": "abc123"})
        assert "routing_key" in p
        assert p["payload"]["severity"] == "critical"

    def test_pagerduty_drift_alert_is_warning(self, manager):
        p = manager._format_payload(WebhookProvider.PAGERDUTY, WebhookEvent.DRIFT_ALERT, {})
        assert p["payload"]["severity"] == "warning"

    def test_teams_color_red_for_alert(self, manager):
        p = manager._format_payload(WebhookProvider.TEAMS, WebhookEvent.DRIFT_ALERT, {})
        assert p["themeColor"] == "FF6B6B"

    def test_teams_color_green_for_score_change(self, manager):
        p = manager._format_payload(WebhookProvider.TEAMS, WebhookEvent.TRUST_SCORE_CHANGED, {})
        assert p["themeColor"] == "4CAF50"


# ── Delivery log ───────────────────────────────────────────────────────────────

class TestDeliveryLog:
    @respx.mock
    async def test_delivery_log_records_success(self, manager):
        url = "https://log.example.com"
        c = WebhookConfig(url=url, events=[WebhookEvent.DRIFT_ALERT])
        respx.post(url).mock(return_value=httpx.Response(200))
        manager.register(c)
        await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        log = manager.delivery_log()
        assert len(log) == 1
        assert log[0]["success"] is True

    @respx.mock
    async def test_total_deliveries_counter(self, manager):
        url = "https://counter.example.com"
        c = WebhookConfig(url=url, events=[WebhookEvent.DRIFT_ALERT])
        respx.post(url).mock(return_value=httpx.Response(200))
        manager.register(c)
        await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        assert manager.total_deliveries == 2

    @respx.mock
    async def test_failed_deliveries_counter(self, manager):
        url = "https://fail.example.com"
        c = WebhookConfig(url=url, events=[WebhookEvent.DRIFT_ALERT], max_retries=1)
        respx.post(url).mock(return_value=httpx.Response(500))
        manager.register(c)
        with patch("responsibleai.webhooks.manager._RETRY_DELAYS", []):
            await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        assert manager.failed_deliveries == 1

    def test_delivery_log_respects_limit(self, manager):
        log = manager.delivery_log(limit=10)
        assert isinstance(log, list)


# ── Retry worker lifecycle ───────────────────────────────────────────────────────

class TestRetryWorkerLifecycle:
    def test_start_without_repo_is_noop(self, manager):
        manager.start_retry_worker()
        assert manager._retry_task is None

    async def test_start_with_repo_launches_task(self, manager):
        manager.set_repository(AsyncMock())
        manager.start_retry_worker()
        assert manager._retry_task is not None
        manager.stop_retry_worker()

    async def test_start_twice_does_not_duplicate_task(self, manager):
        manager.set_repository(AsyncMock())
        manager.start_retry_worker()
        first_task = manager._retry_task
        manager.start_retry_worker()
        assert manager._retry_task is first_task
        manager.stop_retry_worker()

    async def test_stop_cancels_task(self, manager):
        manager.set_repository(AsyncMock())
        manager.start_retry_worker()
        manager.stop_retry_worker()
        assert manager._retry_task is None
        assert manager._stop_event.is_set()

    def test_stop_without_start_is_safe(self, manager):
        manager.stop_retry_worker()
        assert manager._retry_task is None


# ── Repo-backed persistence ──────────────────────────────────────────────────────

class TestRepoBackedDelivery:
    @respx.mock
    async def test_create_called_on_delivery(self, manager, generic_config):
        repo = AsyncMock()
        repo.pending_retries.return_value = []
        manager.set_repository(repo)
        respx.post(generic_config.url).mock(return_value=httpx.Response(200))
        manager.register(generic_config)
        await manager.fire(WebhookEvent.DRIFT_ALERT, {"model": "gpt-4o"})
        repo.create.assert_awaited_once()
        repo.record_attempt.assert_awaited()

    @respx.mock
    async def test_repo_create_failure_degrades_gracefully(self, manager, generic_config):
        repo = AsyncMock()
        repo.create.side_effect = RuntimeError("db down")
        manager.set_repository(repo)
        respx.post(generic_config.url).mock(return_value=httpx.Response(200))
        manager.register(generic_config)
        deliveries = await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        assert deliveries[0].success is True

    @respx.mock
    async def test_repo_record_attempt_failure_degrades_gracefully(self, manager, generic_config):
        repo = AsyncMock()
        repo.record_attempt.side_effect = RuntimeError("db down")
        manager.set_repository(repo)
        respx.post(generic_config.url).mock(return_value=httpx.Response(200))
        manager.register(generic_config)
        deliveries = await manager.fire(WebhookEvent.DRIFT_ALERT, {})
        assert deliveries[0].success is True

    async def test_retry_worker_redelivers_pending(self, manager, generic_config):
        manager.register(generic_config)
        repo = AsyncMock()
        repo.pending_retries.return_value = [
            {
                "id": "delivery-1",
                "webhook_id": generic_config.id,
                "event": WebhookEvent.DRIFT_ALERT.value,
                "payload": {"model": "gpt-4o"},
                "attempts": 1,
            }
        ]
        manager.set_repository(repo)

        with (
            respx.mock,
            patch("responsibleai.webhooks.manager._RETRY_POLL_INTERVAL", 0.01),
        ):
            respx.post(generic_config.url).mock(return_value=httpx.Response(200))
            manager.start_retry_worker()
            await asyncio.sleep(0.05)
            manager.stop_retry_worker()

        repo.pending_retries.assert_awaited()

    async def test_retry_worker_skips_unknown_webhook(self, manager):
        repo = AsyncMock()
        repo.pending_retries.return_value = [
            {
                "id": "delivery-2",
                "webhook_id": "unknown-webhook-id",
                "event": WebhookEvent.DRIFT_ALERT.value,
                "payload": {},
                "attempts": 0,
            }
        ]
        manager.set_repository(repo)

        with patch("responsibleai.webhooks.manager._RETRY_POLL_INTERVAL", 0.01):
            manager.start_retry_worker()
            await asyncio.sleep(0.05)
            manager.stop_retry_worker()

        # Should not raise — unknown webhook_id is silently skipped.
        repo.pending_retries.assert_awaited()

    async def test_retry_worker_skips_invalid_event(self, manager, generic_config):
        manager.register(generic_config)
        repo = AsyncMock()
        repo.pending_retries.return_value = [
            {
                "id": "delivery-3",
                "webhook_id": generic_config.id,
                "event": "not_a_real_event",
                "payload": {},
                "attempts": 0,
            }
        ]
        manager.set_repository(repo)

        with patch("responsibleai.webhooks.manager._RETRY_POLL_INTERVAL", 0.01):
            manager.start_retry_worker()
            await asyncio.sleep(0.05)
            manager.stop_retry_worker()

        repo.pending_retries.assert_awaited()

    async def test_retry_worker_handles_repo_exception(self, manager):
        repo = AsyncMock()
        repo.pending_retries.side_effect = RuntimeError("db unreachable")
        manager.set_repository(repo)

        with patch("responsibleai.webhooks.manager._RETRY_POLL_INTERVAL", 0.01):
            manager.start_retry_worker()
            await asyncio.sleep(0.05)
            manager.stop_retry_worker()
        # Should not raise — worker logs and keeps polling.


# ── SSRF guard ───────────────────────────────────────────────────────────────

class TestSSRFGuard:
    def test_rejects_non_http_scheme(self):
        with pytest.raises(UnsafeWebhookURLError, match="scheme"):
            validate_webhook_url("ftp://example.com/x")

    def test_rejects_url_with_no_host(self, monkeypatch):
        with pytest.raises(UnsafeWebhookURLError, match="no host"):
            validate_webhook_url("http:///path")

    def test_rejects_loopback(self, monkeypatch):
        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            lambda host, *a, **k: [(2, 1, 6, "", ("127.0.0.1", 0))],
        )
        with pytest.raises(UnsafeWebhookURLError, match="non-public"):
            validate_webhook_url("http://localhost/hook")

    def test_rejects_private_rfc1918(self, monkeypatch):
        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            lambda host, *a, **k: [(2, 1, 6, "", ("10.0.0.5", 0))],
        )
        with pytest.raises(UnsafeWebhookURLError, match="non-public"):
            validate_webhook_url("http://internal.corp/hook")

    def test_rejects_cloud_metadata_link_local(self, monkeypatch):
        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            lambda host, *a, **k: [(2, 1, 6, "", ("169.254.169.254", 0))],
        )
        with pytest.raises(UnsafeWebhookURLError, match="non-public"):
            validate_webhook_url("http://metadata.internal/latest/meta-data")

    def test_allows_public_ip(self, monkeypatch):
        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo",
            lambda host, *a, **k: [(2, 1, 6, "", ("93.184.216.34", 0))],
        )
        validate_webhook_url("https://hooks.example.com/generic")  # should not raise

    def test_unresolvable_host_raises(self, monkeypatch):
        import socket as socket_module

        def _raise(host, *a, **k):
            raise socket_module.gaierror("nodename nor servname provided")

        monkeypatch.setattr(
            "responsibleai.webhooks.manager.socket.getaddrinfo", _raise
        )
        with pytest.raises(UnsafeWebhookURLError, match="could not resolve"):
            validate_webhook_url("http://does-not-exist.invalid/hook")
