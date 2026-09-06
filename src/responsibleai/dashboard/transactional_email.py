# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Provider-neutral transactional email rendering and delivery.

Raw action URLs stay in memory only. They are not logged or persisted because
they contain short-lived authentication tokens. A durable outbox would require
an externally managed encryption key and rotation policy.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from html import escape
from typing import Protocol

import httpx


class EmailDeliveryError(RuntimeError):
    """A provider rejected or could not deliver a message."""


@dataclass(frozen=True)
class TransactionalEmail:
    template: str
    recipient: str
    recipient_name: str
    subject: str
    text: str
    html: str
    action_field: str
    action_url: str

    def webhook_payload(self) -> dict[str, str]:
        return {
            "template": self.template,
            "to": self.recipient,
            "name": self.recipient_name,
            "subject": self.subject,
            "text": self.text,
            "html": self.html,
            self.action_field: self.action_url,
        }


class EmailProvider(Protocol):
    async def deliver(self, message: TransactionalEmail) -> None: ...


class AuthenticatedWebhookEmailProvider:
    """Generic HTTPS webhook adapter with bounded transient-failure retries."""

    def __init__(self, endpoint: str, bearer_token: str | None, *, attempts: int = 3) -> None:
        self._endpoint = endpoint
        self._bearer_token = bearer_token
        self._attempts = attempts

    async def deliver(self, message: TransactionalEmail) -> None:
        headers = {"Content-Type": "application/json"}
        if self._bearer_token:
            headers["Authorization"] = f"Bearer {self._bearer_token}"
        last_status: int | None = None
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=False) as client:
            for attempt in range(self._attempts):
                try:
                    response = await client.post(
                        self._endpoint,
                        headers=headers,
                        json=message.webhook_payload(),
                    )
                    last_status = response.status_code
                    if 200 <= response.status_code < 300:
                        return
                    if response.status_code < 500:
                        break
                except httpx.RequestError:
                    pass
                if attempt + 1 < self._attempts:
                    await asyncio.sleep(0.25 * (2**attempt))
        suffix = f" (provider status {last_status})" if last_status is not None else ""
        raise EmailDeliveryError(f"Transactional email delivery failed{suffix}.")


def verification_email(recipient: str, name: str, action_url: str) -> TransactionalEmail:
    return _action_email(
        template="whitepact-email-verification",
        recipient=recipient,
        name=name,
        subject="Verify your WhitePact account",
        intro="Verify your email address before creating an organization or API key.",
        button="Verify email",
        action_field="verification_url",
        action_url=action_url,
        expiry="This link expires after 24 hours.",
    )


def password_reset_email(recipient: str, name: str, action_url: str) -> TransactionalEmail:
    return _action_email(
        template="whitepact-password-reset",
        recipient=recipient,
        name=name,
        subject="Reset your WhitePact password",
        intro="A password reset was requested for your WhitePact account.",
        button="Reset password",
        action_field="reset_url",
        action_url=action_url,
        expiry="This link expires after one hour. Ignore this email if you did not request it.",
    )


def _action_email(
    *,
    template: str,
    recipient: str,
    name: str,
    subject: str,
    intro: str,
    button: str,
    action_field: str,
    action_url: str,
    expiry: str,
) -> TransactionalEmail:
    safe_name, safe_url = escape(name), escape(action_url, quote=True)
    text = f"Hello {name},\n\n{intro}\n\n{button}: {action_url}\n\n{expiry}\n\nWhitePact"
    html = (
        '<div style="background:#09090b;color:#f7f7f8;padding:32px;font-family:Arial,sans-serif">'
        '<div style="max-width:560px;margin:auto;border:1px solid #303036;padding:32px">'
        '<p style="color:#ef233c;letter-spacing:.12em">WHITEPACT</p>'
        f"<h1>{subject}</h1><p>Hello {safe_name},</p><p>{intro}</p>"
        f'<p><a href="{safe_url}" style="display:inline-block;background:#d91427;color:white;'
        f'text-decoration:none;padding:14px 20px">{button}</a></p>'
        f'<p style="color:#b6b6bd">{expiry}</p></div></div>'
    )
    return TransactionalEmail(
        template=template,
        recipient=recipient,
        recipient_name=name,
        subject=subject,
        text=text,
        html=html,
        action_field=action_field,
        action_url=action_url,
    )
