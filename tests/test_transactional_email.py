# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

import httpx
import pytest
import respx

from responsibleai.dashboard.transactional_email import (
    AuthenticatedWebhookEmailProvider,
    EmailDeliveryError,
    password_reset_email,
    verification_email,
)


def test_templates_include_html_text_and_escape_untrusted_names():
    message = verification_email(
        "person@example.com",
        '<script>alert("x")</script>',
        "https://whitepact.com/verify-email?token=opaque",
    )
    assert "Verify email:" in message.text
    assert "<script>" not in message.html
    assert "&lt;script&gt;" in message.html
    assert message.webhook_payload()["verification_url"].endswith("token=opaque")


@respx.mock
async def test_provider_retries_transient_failures(monkeypatch):
    route = respx.post("https://mailer.example.com/send").mock(
        side_effect=[httpx.Response(503), httpx.Response(202)]
    )

    async def no_wait(_seconds):
        return None

    monkeypatch.setattr("responsibleai.dashboard.transactional_email.asyncio.sleep", no_wait)
    provider = AuthenticatedWebhookEmailProvider(
        "https://mailer.example.com/send", "delivery-token"
    )
    await provider.deliver(
        password_reset_email(
            "person@example.com",
            "Person",
            "https://whitepact.com/reset-password?token=opaque",
        )
    )
    assert route.call_count == 2
    request = route.calls.last.request
    assert request.headers["authorization"] == "Bearer delivery-token"
    assert b'"text"' in request.content and b'"html"' in request.content


@respx.mock
async def test_provider_does_not_retry_permanent_rejection():
    route = respx.post("https://mailer.example.com/send").mock(return_value=httpx.Response(401))
    provider = AuthenticatedWebhookEmailProvider("https://mailer.example.com/send", None)
    with pytest.raises(EmailDeliveryError, match="provider status 401"):
        await provider.deliver(
            verification_email("person@example.com", "Person", "https://example.com/opaque")
        )
    assert route.call_count == 1
