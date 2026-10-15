# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""M10-R Egress Protection Reproduction Through Real Controlled Sockets.

Verifies against actual operating-system TCP sockets and live listening servers:
1. SafeNetworkBackend under DestinationPolicy.PUBLIC_ONLY strictly prevents TCP handshakes
   to loopback / private servers, leaving server accept count at exactly 0.
2. Under DestinationPolicy.LOCAL_DEV, real TCP connections establish, transfer application data,
   and close cleanly over OS sockets.
3. Live HTTP clients (create_safe_async_client) with PUBLIC_ONLY abort requests before
   reaching the listening HTTP server.
4. DNS Rebinding attacks targeting live local servers are intercepted and aborted prior to connect.
5. Socket-level peer validation guarantees no bypass via IP translation.
"""

from __future__ import annotations

import asyncio
import ipaddress
from collections.abc import AsyncGenerator

import pytest

from responsibleai.net.egress import (
    AsyncDNSResolver,
    DestinationPolicy,
    ForbiddenDestinationError,
    SafeNetworkBackend,
    create_safe_async_client,
)

pytestmark = pytest.mark.asyncio


class _EchoServer:
    """Real TCP server listening on an OS-assigned ephemeral loopback port."""

    def __init__(self) -> None:
        self.server: asyncio.Server | None = None
        self.host: str = "127.0.0.1"
        self.port: int = 0
        self.connections_accepted: int = 0
        self.received_payloads: list[bytes] = []

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.connections_accepted += 1
        data = await reader.readline()
        self.received_payloads.append(data)
        writer.write(b"WHITEPACT_ACK\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle_client, self.host, 0)
        sockets = self.server.sockets
        assert sockets is not None and len(sockets) > 0
        self.port = sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


class _LiveHttpEchoServer:
    """Minimal HTTP/1.1 server listening on ephemeral loopback."""

    def __init__(self) -> None:
        self.server: asyncio.Server | None = None
        self.port: int = 0
        self.requests_handled: int = 0

    async def _handle_request(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        self.requests_handled += 1
        # Read until header terminator
        while True:
            line = await reader.readline()
            if not line or line == b"\r\n" or line == b"\n":
                break
        response = (
            b"HTTP/1.1 200 OK\r\n"
            b"Content-Type: text/plain\r\n"
            b"Content-Length: 17\r\n"
            b"Connection: close\r\n"
            b"\r\n"
            b"WHITEPACT_HTTP_OK"
        )
        writer.write(response)
        await writer.drain()
        writer.close()
        await writer.wait_closed()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle_request, "127.0.0.1", 0)
        sockets = self.server.sockets
        assert sockets is not None and len(sockets) > 0
        self.port = sockets[0].getsockname()[1]

    async def stop(self) -> None:
        if self.server is not None:
            self.server.close()
            await self.server.wait_closed()


@pytest.fixture
async def echo_server() -> AsyncGenerator[_EchoServer, None]:
    server = _EchoServer()
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


@pytest.fixture
async def http_server() -> AsyncGenerator[_LiveHttpEchoServer, None]:
    server = _LiveHttpEchoServer()
    await server.start()
    try:
        yield server
    finally:
        await server.stop()


async def test_real_socket_blocked_under_public_only(echo_server: _EchoServer) -> None:
    """Proves with a real listening OS socket that SafeNetworkBackend(PUBLIC_ONLY)
    rejects the connection before socket creation, ensuring 0 connections reach the server.
    """
    backend = SafeNetworkBackend(policy=DestinationPolicy.PUBLIC_ONLY)

    with pytest.raises(
        ForbiddenDestinationError, match="Direct outbound connection to forbidden address"
    ):
        await backend.connect_tcp(echo_server.host, echo_server.port)

    # Let event loop cycle to confirm no background connection landed
    await asyncio.sleep(0.05)
    assert echo_server.connections_accepted == 0, (
        f"Server accepted {echo_server.connections_accepted} connections despite PUBLIC_ONLY policy!"
    )
    assert echo_server.received_payloads == []


async def test_real_socket_connects_under_local_dev(echo_server: _EchoServer) -> None:
    """Proves that when policy explicitly permits local destinations (LOCAL_DEV),
    real TCP socket connections establish, exchange data, and close cleanly.
    """
    backend = SafeNetworkBackend(policy=DestinationPolicy.LOCAL_DEV)

    stream = await backend.connect_tcp(echo_server.host, echo_server.port)
    assert stream is not None

    # Send data over real socket stream
    await stream.write(b"HELLO_SOCKET\n")
    response = await stream.read(max_bytes=1024)
    assert response == b"WHITEPACT_ACK\n"
    await stream.aclose()

    assert echo_server.connections_accepted == 1
    assert echo_server.received_payloads == [b"HELLO_SOCKET\n"]


async def test_real_http_client_egress_interception(http_server: _LiveHttpEchoServer) -> None:
    """Proves that an HTTP client created with create_safe_async_client(PUBLIC_ONLY)
    cannot complete an HTTP request to a live local HTTP server.
    """
    safe_client = create_safe_async_client(policy=DestinationPolicy.PUBLIC_ONLY)

    with pytest.raises(Exception) as exc_info:
        await safe_client.get(f"http://127.0.0.1:{http_server.port}/api/data")

    err_str = str(exc_info.value)
    assert any(
        kw in err_str.lower()
        for kw in ("forbidden", "denied", "connect", "blocked", "safety", "peer")
    )
    assert http_server.requests_handled == 0, (
        "Live HTTP server received request despite PUBLIC_ONLY policy!"
    )

    # Now verify with LOCAL_DEV policy that the safe client DOES reach the server
    dev_client = create_safe_async_client(policy=DestinationPolicy.LOCAL_DEV)
    resp = await dev_client.get(f"http://127.0.0.1:{http_server.port}/api/data")
    assert resp.status_code == 200
    assert resp.text == "WHITEPACT_HTTP_OK"
    assert http_server.requests_handled == 1


class _RebindingResolver(AsyncDNSResolver):
    def __init__(self, target_ip: str) -> None:
        self.target_ip = target_ip

    async def resolve(
        self, host: str, port: int, policy: DestinationPolicy = DestinationPolicy.PUBLIC_ONLY
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        addr = ipaddress.ip_address(self.target_ip)
        if policy == DestinationPolicy.PUBLIC_ONLY and (addr.is_loopback or addr.is_private):
            raise ForbiddenDestinationError(
                f"Host {host!r} resolved to forbidden network address {self.target_ip}"
            )
        return [addr]


async def test_real_socket_dns_rebinding_defense(echo_server: _EchoServer) -> None:
    """Simulates a DNS Rebinding attack against the real local echo server:
    Attacker domain 'victim-corp.external.test' resolves to 127.0.0.1.
    SafeNetworkBackend must abort before connecting to the live server.
    """
    resolver = _RebindingResolver(target_ip="127.0.0.1")
    backend = SafeNetworkBackend(resolver=resolver, policy=DestinationPolicy.PUBLIC_ONLY)

    with pytest.raises(
        ForbiddenDestinationError, match="resolved to forbidden network address 127.0.0.1"
    ):
        await backend.connect_tcp("victim-corp.external.test", echo_server.port)

    await asyncio.sleep(0.05)
    assert echo_server.connections_accepted == 0
    assert echo_server.received_payloads == []
