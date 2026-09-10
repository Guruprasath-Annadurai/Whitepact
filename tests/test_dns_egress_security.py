# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial DNS rebinding, SSRF, and outbound egress security tests."""

from __future__ import annotations

import asyncio
import os
import socket
from typing import Any

import pytest

from responsibleai.webhooks.manager import UnsafeWebhookURLError, WebhookManager, validate_webhook_url
from responsibleai.webhooks.models import WebhookConfig, WebhookEvent


class _SyntheticLoopbackServer:
    """A minimal raw asyncio TCP server on loopback to detect unauthorized outbound connections."""

    def __init__(self, host: str = "127.0.0.1") -> None:
        self.host = host
        self.port = 0
        self.server: asyncio.Server | None = None
        self.received_requests: list[bytes] = []

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        data = await reader.read(4096)
        self.received_requests.append(data)
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: application/json\r\n"
            b"Content-Length: 15\r\n"
            b"Connection: close\r\n\r\n"
            b'{"status":"ok"}'
        )
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def __aenter__(self) -> _SyntheticLoopbackServer:
        self.server = await asyncio.start_server(self._handle_client, self.host, 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


class _SyntheticRedirectServer:
    """HTTP server that issues redirects (302) to a specified target."""

    def __init__(self, target_location: str, host: str = "127.0.0.1") -> None:
        self.host = host
        self.port = 0
        self.target_location = target_location
        self.server: asyncio.Server | None = None
        self.redirect_requests: list[bytes] = []

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        data = await reader.read(4096)
        self.redirect_requests.append(data)
        response = (
            b"HTTP/1.1 302 Found\r\n"
            b"Location: " + self.target_location.encode("utf-8") + b"\r\n"
            b"Content-Length: 0\r\n"
            b"Connection: close\r\n\r\n"
        )
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def __aenter__(self) -> _SyntheticRedirectServer:
        self.server = await asyncio.start_server(self._handle_client, self.host, 0)
        self.port = self.server.sockets[0].getsockname()[1]
        return self

    async def __aexit__(self, *args: Any) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


# ── Canonical Reproduction Test ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_reproduce_unpatched_dns_rebinding_reaches_loopback(monkeypatch: pytest.MonkeyPatch) -> None:
    """RED TEST: Prove that unpatched WebhookManager allows a TOCTOU DNS rebinding attack

    where validate_webhook_url sees a public IP, but the subsequent httpx connection
    re-resolves to loopback and reaches a synthetic internal listener.
    """
    async with _SyntheticLoopbackServer() as internal_target:
        call_count = 0
        original_getaddrinfo = socket.getaddrinfo

        def rebinding_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
            nonlocal call_count
            hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
            if hostname == "rebind.example":
                call_count += 1
                if call_count == 1:
                    # Resolution 1: validate_webhook_url sees a benign public IP
                    return [
                        (
                            socket.AF_INET,
                            socket.SOCK_STREAM,
                            6,
                            "",
                            ("93.184.216.34", port or 0),
                        )
                    ]
                else:
                    # Resolution 2: httpx independently connects to the loopback target!
                    return [
                        (
                            socket.AF_INET,
                            socket.SOCK_STREAM,
                            6,
                            "",
                            ("127.0.0.1", internal_target.port),
                        )
                    ]
            return original_getaddrinfo(host, port, *args, **kwargs)

        monkeypatch.setattr(socket, "getaddrinfo", rebinding_getaddrinfo)

        manager = WebhookManager()
        cfg = WebhookConfig(
            url=f"http://rebind.example:{internal_target.port}/webhook",
            events=[WebhookEvent.DRIFT_ALERT],
        )
        manager.register(cfg)

        await manager.fire(WebhookEvent.DRIFT_ALERT, {"test": "data"})

        # IN UNPATCHED CODE: The internal target receives the request!
        assert len(internal_target.received_requests) == 1, (
            "Vulnerability verification: unpatched WebhookManager allowed HTTP request to hit loopback!"
        )
        assert b"POST /webhook" in internal_target.received_requests[0]
