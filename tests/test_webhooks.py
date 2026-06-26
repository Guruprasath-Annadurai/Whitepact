"""Tests for the WebhookManager — delivery, retry, HMAC signing, formatters."""

from __future__ import annotations

import hashlib
import hmac
from unittest.mock import patch

import httpx
import pytest
import respx

from responsibleai.webhooks.manager import WebhookManager
from responsibleai.webhooks.models import (
    WebhookConfig,
    WebhookEvent,
    WebhookProvider,
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
        assert manager.list() == []

    def test_list_after_register(self, manager, generic_config):
        manager.register(generic_config)
        assert len(manager.list()) == 1

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
        assert len(manager.list()) == 5


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
