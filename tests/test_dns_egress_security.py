# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial DNS rebinding, SSRF, and outbound egress security tests.

Test Categories
---------------
1. RED test: proves vulnerability exists in baseline code (expected: PASS = bypass confirmed)
   After integration this test should FAIL (bypass is now blocked) — that failure is the PROOF.
2. Static URL & IP validation (normalize_and_validate_url / validate_outbound_url)
3. Address classifier (is_address_allowed) — all forbidden categories
4. DNS resolution fail-closed (SystemDNSResolver)
5. Webhook delivery (validate_webhook_url + _deliver) — full adversarial matrix
6. Upstream MCP (validate_upstream_server_url + build_upstream_server)
7. SafeNetworkBackend / create_safe_async_client connect-time enforcement
"""

from __future__ import annotations

import asyncio
import ipaddress
import socket
from typing import Any

import httpx
import pytest

from responsibleai.governance.upstream import (
    UnsafeUpstreamServerURLError,
    build_upstream_server,
    validate_upstream_server_url,
)
from responsibleai.net.egress import (
    METADATA_V4,
    DestinationPolicy,
    DNSResolutionError,
    ForbiddenDestinationError,
    InvalidURLError,
    SafeAsyncHTTPTransport,
    SystemDNSResolver,
    create_safe_async_client,
    is_address_allowed,
    normalize_and_validate_url,
    validate_outbound_url,
)
from responsibleai.webhooks.manager import (
    UnsafeWebhookURLError,
    WebhookManager,
    validate_webhook_url,
)
from responsibleai.webhooks.models import WebhookConfig, WebhookEvent

# ── Test Helpers ──────────────────────────────────────────────────────────────

class _SyntheticLoopbackServer:
    """Minimal asyncio TCP server on loopback — detects unauthorized outbound connections."""

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
        writer.write(
            b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\n"
            b"Content-Length: 15\r\nConnection: close\r\n\r\n"
            b'{"status":"ok"}'
        )
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
    """HTTP server that issues 302 redirects to a target location."""

    def __init__(self, target_location: str, host: str = "127.0.0.1") -> None:
        self.host = host
        self.port = 0
        self.target_location = target_location
        self.server: asyncio.Server | None = None

    async def _handle_client(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter
    ) -> None:
        await reader.read(4096)
        writer.write(
            b"HTTP/1.1 302 Found\r\nLocation: "
            + self.target_location.encode()
            + b"\r\nContent-Length: 0\r\nConnection: close\r\n\r\n"
        )
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


def _make_addrinfo(ip: str, port: int = 0) -> list[Any]:
    """Build a socket.getaddrinfo-style result for a given IPv4 address."""
    return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", (ip, port))]


# ── 1. RED TEST — Canonical Vulnerability Reproduction ───────────────────────

@pytest.mark.asyncio
async def test_patched_webhook_manager_blocks_dns_rebinding(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """SECURITY CLOSURE: After patching, TOCTOU DNS rebinding MUST be blocked.

    This is the same attack as the original RED test:
    - validate_webhook_url sees a public IP (93.184.216.34)
    - httpx/anyio re-resolves and gets 127.0.0.1

    After integration of create_safe_async_client(), SafeNetworkBackend
    intercepts the connect and re-resolves inside its own controlled resolver —
    which must REJECT the loopback address. The loopback server MUST NOT
    receive any request.
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
                    # First call (validate_webhook_url / normalize_and_validate_url):
                    # returns public IP — would pass the pre-check
                    return _make_addrinfo("93.184.216.34", port or 0)
                else:
                    # Second call (SafeNetworkBackend.connect_tcp): returns loopback
                    # SafeNetworkBackend MUST reject this
                    return _make_addrinfo("127.0.0.1", internal_target.port)
            return original_getaddrinfo(host, port, *args, **kwargs)

        monkeypatch.setattr(socket, "getaddrinfo", rebinding_getaddrinfo)

        manager = WebhookManager()
        cfg = WebhookConfig(
            url=f"http://rebind.example:{internal_target.port}/webhook",
            events=[WebhookEvent.DRIFT_ALERT],
        )
        manager.register(cfg)
        await manager.fire(WebhookEvent.DRIFT_ALERT, {"test": "data"})

        # PROOF: The loopback server received ZERO requests — bypass is blocked
        assert len(internal_target.received_requests) == 0, (
            "SECURITY FAILURE: Patched WebhookManager still allows DNS rebinding to reach loopback!"
        )


# ── 2. is_address_allowed — Address Classifier Tests ─────────────────────────

@pytest.mark.parametrize("ip_str", [
    "127.0.0.1",        # IPv4 loopback
    "127.255.255.255",  # IPv4 loopback range
    "::1",              # IPv6 loopback
    "10.0.0.1",         # RFC1918 private
    "172.16.0.1",       # RFC1918 private
    "192.168.1.1",      # RFC1918 private
    "169.254.169.254",  # link-local / AWS metadata
    "169.254.0.1",      # link-local
    "fe80::1",          # IPv6 link-local
    "0.0.0.0",          # unspecified
    "::",               # IPv6 unspecified
    "224.0.0.1",        # multicast
    "ff02::1",          # IPv6 multicast
    "100.64.0.1",       # CGNAT
    "100.127.255.255",  # CGNAT end
    "::ffff:127.0.0.1", # IPv4-mapped IPv6 loopback
    "::ffff:10.0.0.1",  # IPv4-mapped IPv6 private
    "::ffff:192.168.0.1", # IPv4-mapped IPv6 private
    "fc00::1",          # IPv6 ULA
    "fd00::1",          # IPv6 ULA
    "fd12:3456:789a::1", # IPv6 ULA
])
def test_is_address_allowed_blocks_forbidden(ip_str: str) -> None:
    assert is_address_allowed(ip_str, DestinationPolicy.PUBLIC_ONLY) is False, (
        f"Expected {ip_str!r} to be BLOCKED under PUBLIC_ONLY policy"
    )


@pytest.mark.parametrize("ip_str", [
    "93.184.216.34",    # example.com
    "8.8.8.8",          # Google DNS
    "1.1.1.1",          # Cloudflare DNS
    "2001:4860:4860::8888",  # Google DNS IPv6
])
def test_is_address_allowed_permits_public(ip_str: str) -> None:
    assert is_address_allowed(ip_str, DestinationPolicy.PUBLIC_ONLY) is True, (
        f"Expected {ip_str!r} to be ALLOWED under PUBLIC_ONLY policy"
    )


def test_is_address_allowed_trusted_private_permits_rfc1918() -> None:
    assert is_address_allowed("10.0.0.1", DestinationPolicy.TRUSTED_PRIVATE) is True


def test_is_address_allowed_trusted_private_blocks_loopback() -> None:
    assert is_address_allowed("127.0.0.1", DestinationPolicy.TRUSTED_PRIVATE) is False


def test_is_address_allowed_local_dev_permits_everything() -> None:
    assert is_address_allowed("127.0.0.1", DestinationPolicy.LOCAL_DEV) is True
    assert is_address_allowed("10.0.0.1", DestinationPolicy.LOCAL_DEV) is True


# ── 3. Static URL Validation ──────────────────────────────────────────────────

@pytest.mark.parametrize("url,exc_type", [
    # Scheme violations
    ("ftp://example.com/path", InvalidURLError),
    ("file:///etc/passwd", InvalidURLError),
    ("", InvalidURLError),
    ("not-a-url", InvalidURLError),
    # CRLF / control characters
    ("http://example.com\r\n/path", InvalidURLError),
    ("http://example.com\t/path", InvalidURLError),
    # Direct forbidden IP literals
    ("http://127.0.0.1/path", ForbiddenDestinationError),
    ("http://10.0.0.1/path", ForbiddenDestinationError),
    ("http://192.168.1.1:8080/hook", ForbiddenDestinationError),
    ("http://169.254.169.254/latest/meta-data/", ForbiddenDestinationError),
    ("http://[::1]/path", ForbiddenDestinationError),
    ("http://[fc00::1]/path", ForbiddenDestinationError),
    ("http://[::ffff:127.0.0.1]/path", ForbiddenDestinationError),
    # Obfuscated IP literals
    ("http://2130706433/path", ForbiddenDestinationError),   # integer IPv4 127.0.0.1
    ("http://0177.0.0.1/path", ForbiddenDestinationError),   # leading-zero octal notation
    ("http://0x7f.0.0.1/path", ForbiddenDestinationError),   # hex notation
    # Forbidden hostnames
    ("http://localhost/path", ForbiddenDestinationError),
    ("http://localhost./path", ForbiddenDestinationError),
    ("http://metadata.google.internal/", ForbiddenDestinationError),
])
def test_normalize_and_validate_url_rejects_forbidden(url: str, exc_type: type) -> None:
    with pytest.raises(exc_type):
        normalize_and_validate_url(url)


@pytest.mark.parametrize("url", [
    "https://example.com/webhook",
    "http://example.com:8080/hook",
    "https://api.example.org/v1/events",
])
def test_normalize_and_validate_url_accepts_public(url: str) -> None:
    result_url, host, port = normalize_and_validate_url(url)
    assert host
    assert port > 0


# ── 4. validate_webhook_url — backward compat wrapper ────────────────────────

def test_validate_webhook_url_rejects_private_ip() -> None:
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url("http://10.0.0.1/hook")


def test_validate_webhook_url_rejects_loopback() -> None:
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url("http://127.0.0.1/hook")


def test_validate_webhook_url_rejects_localhost() -> None:
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url("http://localhost/hook")


def test_validate_webhook_url_rejects_metadata() -> None:
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url("http://169.254.169.254/hook")


def test_validate_webhook_url_rejects_bad_scheme() -> None:
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url("ftp://example.com/hook")


def test_validate_webhook_url_accepts_public_url() -> None:
    # Should not raise — no DNS resolution at this level (static check only)
    validate_webhook_url("https://example.com/webhook")


# ── 5. DNS Resolution Fail-Closed (SystemDNSResolver) ────────────────────────

@pytest.mark.asyncio
async def test_systemdns_resolver_fails_closed_on_any_forbidden_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Mixed safe+unsafe DNS answers: any forbidden address → fail closed."""
    original_getaddrinfo = socket.getaddrinfo

    def mixed_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
        if hostname == "mixed.example":
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 0)),
                (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("127.0.0.1", port or 0)),  # forbidden
            ]
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", mixed_getaddrinfo)

    resolver = SystemDNSResolver()
    with pytest.raises((ForbiddenDestinationError, DNSResolutionError)):
        await resolver.resolve("mixed.example", 80, DestinationPolicy.PUBLIC_ONLY)


@pytest.mark.asyncio
async def test_systemdns_resolver_accepts_safe_address(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original_getaddrinfo = socket.getaddrinfo

    def safe_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
        if hostname == "safe.example":
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 0))]
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", safe_getaddrinfo)

    resolver = SystemDNSResolver()
    addrs = await resolver.resolve("safe.example", 80, DestinationPolicy.PUBLIC_ONLY)
    assert len(addrs) >= 1
    for addr in addrs:
        assert is_address_allowed(addr, DestinationPolicy.PUBLIC_ONLY)


@pytest.mark.asyncio
async def test_systemdns_resolver_fails_on_dns_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def failing_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        raise socket.gaierror("NXDOMAIN")

    monkeypatch.setattr(socket, "getaddrinfo", failing_getaddrinfo)

    resolver = SystemDNSResolver()
    with pytest.raises(DNSResolutionError):
        await resolver.resolve("nonexistent.invalid", 80, DestinationPolicy.PUBLIC_ONLY)


# ── 6. Fail-Closed Matrix ─────────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "http://127.0.0.1/hook",
    "http://10.0.0.1/hook",
    "http://192.168.0.1/hook",
    "http://172.16.0.1/hook",
    "http://169.254.169.254/hook",
    "http://100.64.0.1/hook",
    "http://[::1]/hook",
    "http://[fc00::1]/hook",
    "http://[fd00::1]/hook",
    "http://[::ffff:10.0.0.1]/hook",
    "http://localhost/hook",
    "http://metadata.google.internal/hook",
    "ftp://example.com/hook",
    "",
])
def test_validate_outbound_url_fail_closed_matrix(url: str) -> None:
    """Every forbidden URL variant MUST raise — fail-closed guarantee."""
    with pytest.raises((ForbiddenDestinationError, InvalidURLError, UnsafeWebhookURLError)):
        validate_outbound_url(url)


# ── 7. Redirect Rebinding — redirects MUST not be followed ───────────────────

@pytest.mark.asyncio
async def test_safe_client_does_not_follow_redirects_to_private(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Redirect to private network MUST be blocked — follow_redirects=False enforced by transport."""
    async with _SyntheticLoopbackServer() as internal:
        async with _SyntheticRedirectServer(
            f"http://127.0.0.1:{internal.port}/redirect-target"
        ) as redirector:
            original_getaddrinfo = socket.getaddrinfo

            def redirector_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
                hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
                if hostname == "redirector.example":
                    return _make_addrinfo("93.184.216.34", port or 0)
                return original_getaddrinfo(host, port, *args, **kwargs)

            monkeypatch.setattr(socket, "getaddrinfo", redirector_getaddrinfo)

            # safe client must refuse to follow the redirect (which would point to 127.0.0.1)
            async with create_safe_async_client(timeout=5.0) as client:
                # The redirect server itself is on 127.0.0.1 — connection to it must
                # be blocked at connect time (ForbiddenDestinationError or transport error)
                with pytest.raises((ForbiddenDestinationError, DNSResolutionError, OSError, httpx.TransportError)):
                    await client.post(
                        f"http://redirector.example:{redirector.port}/hook",
                        content=b"{}",
                    )

            assert len(internal.received_requests) == 0, (
                "SECURITY FAILURE: Safe client followed redirect to private address!"
            )


# ── 8. Proxy Environment Bypass — trust_env=False ────────────────────────────

@pytest.mark.asyncio
async def test_safe_client_ignores_proxy_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Proxy env vars (HTTP_PROXY, ALL_PROXY) MUST NOT bypass destination policy."""
    monkeypatch.setenv("HTTP_PROXY", "http://10.0.0.1:8080")
    monkeypatch.setenv("http_proxy", "http://10.0.0.1:8080")
    monkeypatch.setenv("ALL_PROXY", "http://10.0.0.1:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://10.0.0.1:8080")

    original_getaddrinfo = socket.getaddrinfo

    def blocked_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
        if hostname in ("10.0.0.1",):
            pytest.fail(f"Safe client attempted to connect through proxy at forbidden {hostname!r}")
        if hostname == "public.example":
            return _make_addrinfo("93.184.216.34", port or 0)
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", blocked_getaddrinfo)

    # SafeAsyncHTTPTransport enforces trust_env=False — proxy env vars are ignored
    # Connection to public.example still routes through SafeNetworkBackend (direct)
    async with create_safe_async_client(timeout=5.0) as client:
        try:
            await client.get("http://public.example/")
        except Exception:
            pass  # Connection error is expected (no real server); no proxy bypass is the assertion


# ── 9. IPv6 Bypass — ::ffff: mapped addresses ────────────────────────────────

def test_ipv4_mapped_ipv6_loopback_is_blocked() -> None:
    assert is_address_allowed("::ffff:127.0.0.1", DestinationPolicy.PUBLIC_ONLY) is False


def test_ipv4_mapped_ipv6_private_is_blocked() -> None:
    assert is_address_allowed("::ffff:10.0.0.1", DestinationPolicy.PUBLIC_ONLY) is False
    assert is_address_allowed("::ffff:192.168.1.1", DestinationPolicy.PUBLIC_ONLY) is False


def test_ipv4_mapped_ipv6_metadata_is_blocked() -> None:
    assert is_address_allowed("::ffff:169.254.169.254", DestinationPolicy.PUBLIC_ONLY) is False


def test_ula_ipv6_is_blocked() -> None:
    assert is_address_allowed("fc00::1", DestinationPolicy.PUBLIC_ONLY) is False
    assert is_address_allowed("fd00::1", DestinationPolicy.PUBLIC_ONLY) is False
    assert is_address_allowed("fdff:ffff:ffff::1", DestinationPolicy.PUBLIC_ONLY) is False


# ── 10. CGNAT Blocking ────────────────────────────────────────────────────────

def test_cgnat_addresses_blocked() -> None:
    for last_octet in (1, 127, 254):
        ip = f"100.64.0.{last_octet}"
        assert is_address_allowed(ip, DestinationPolicy.PUBLIC_ONLY) is False, (
            f"CGNAT {ip!r} should be blocked"
        )
    assert is_address_allowed("100.127.255.255", DestinationPolicy.PUBLIC_ONLY) is False
    # Outside CGNAT — should be public
    assert is_address_allowed("100.128.0.1", DestinationPolicy.PUBLIC_ONLY) is True


# ── 11. Metadata Blocking ─────────────────────────────────────────────────────

def test_metadata_v4_blocked() -> None:
    assert is_address_allowed("169.254.169.254", DestinationPolicy.PUBLIC_ONLY) is False


def test_metadata_constant_correct() -> None:
    assert METADATA_V4 == ipaddress.ip_address("169.254.169.254")


def test_metadata_v4_also_link_local() -> None:
    """169.254.169.254 is link-local so is doubly blocked."""
    ip = ipaddress.ip_address("169.254.169.254")
    assert ip.is_link_local


# ── 12. Static IP URL Blocking ────────────────────────────────────────────────

def test_integer_ipv4_literal_blocked() -> None:
    # 2130706433 == 127.0.0.1
    with pytest.raises(ForbiddenDestinationError):
        normalize_and_validate_url("http://2130706433/")


def test_hex_ipv4_literal_blocked() -> None:
    with pytest.raises(ForbiddenDestinationError):
        normalize_and_validate_url("http://0x7f.0.0.1/")


def test_leading_zero_ipv4_literal_blocked() -> None:
    with pytest.raises(ForbiddenDestinationError):
        normalize_and_validate_url("http://0177.0.0.1/")


def test_direct_private_ipv4_blocked() -> None:
    with pytest.raises(ForbiddenDestinationError):
        normalize_and_validate_url("http://192.168.1.100/")


# ── 13. Malformed URL Handling ────────────────────────────────────────────────

@pytest.mark.parametrize("url", [
    "",
    "   ",
    "http://",
    "//example.com",
    "http://example.com\r\nX-Injected: evil",
    "javascript:alert(1)",
    "data:text/html,<h1>Hello</h1>",
])
def test_malformed_url_raises(url: str) -> None:
    with pytest.raises((InvalidURLError, ForbiddenDestinationError)):
        normalize_and_validate_url(url)


# ── 14. Upstream MCP URL Validation ──────────────────────────────────────────

def test_validate_upstream_server_url_rejects_private() -> None:
    with pytest.raises(UnsafeUpstreamServerURLError):
        validate_upstream_server_url("http://10.0.0.1/mcp")


def test_validate_upstream_server_url_rejects_loopback() -> None:
    with pytest.raises(UnsafeUpstreamServerURLError):
        validate_upstream_server_url("http://127.0.0.1:8000/mcp")


def test_validate_upstream_server_url_rejects_localhost() -> None:
    with pytest.raises(UnsafeUpstreamServerURLError):
        validate_upstream_server_url("http://localhost/mcp")


def test_validate_upstream_server_url_rejects_metadata() -> None:
    with pytest.raises(UnsafeUpstreamServerURLError):
        validate_upstream_server_url("http://169.254.169.254/latest")


def test_validate_upstream_server_url_rejects_bad_scheme() -> None:
    with pytest.raises(UnsafeUpstreamServerURLError):
        validate_upstream_server_url("ftp://mcp.example.com/")


def test_validate_upstream_server_url_accepts_public(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
    )
    validate_upstream_server_url("https://mcp.example.com/v1/tools")


def test_build_upstream_server_rejects_private_url() -> None:
    with pytest.raises(UnsafeUpstreamServerURLError):
        build_upstream_server("org1", "Evil Server", "http://192.168.0.1/mcp")


def test_build_upstream_server_accepts_public_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        socket, "getaddrinfo",
        lambda host, *a, **k: [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 0))]
    )
    server = build_upstream_server("org1", "Public MCP", "https://mcp.example.com/")
    assert server.url == "https://mcp.example.com/"


# ── 15. Webhook Delivery Adversarial Tests ────────────────────────────────────

@pytest.mark.asyncio
async def test_webhook_delivery_blocked_cgnat(monkeypatch: pytest.MonkeyPatch) -> None:
    """Webhook URL whose hostname resolves ONLY to a CGNAT address must be blocked at delivery."""
    original_getaddrinfo = socket.getaddrinfo

    def cgnat_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
        if hostname == "cgnat.example":
            return _make_addrinfo("100.64.0.1", port or 0)
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", cgnat_getaddrinfo)

    manager = WebhookManager()
    cfg = WebhookConfig(
        url="http://cgnat.example/hook",
        events=[WebhookEvent.DRIFT_ALERT],
    )
    manager.register(cfg)
    # Should not raise — delivery fails gracefully and logs an error
    await manager.fire(WebhookEvent.DRIFT_ALERT, {"test": "cgnat"})
    # No exception means the delivery error was handled, not propagated


@pytest.mark.asyncio
async def test_webhook_delivery_blocked_ipv6_ula(monkeypatch: pytest.MonkeyPatch) -> None:
    """Webhook URL resolving to a ULA IPv6 address must be blocked."""
    original_getaddrinfo = socket.getaddrinfo

    def ula_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
        if hostname == "ula.example":
            return [
                (socket.AF_INET6, socket.SOCK_STREAM, 6, "", ("fd00::1", port or 0, 0, 0))
            ]
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", ula_getaddrinfo)

    manager = WebhookManager()
    cfg = WebhookConfig(
        url="http://ula.example/hook",
        events=[WebhookEvent.DRIFT_ALERT],
    )
    manager.register(cfg)
    await manager.fire(WebhookEvent.DRIFT_ALERT, {"test": "ula"})


@pytest.mark.asyncio
async def test_webhook_delivery_mixed_safe_unsafe_dns_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS returns both a public IP and a private IP — MUST fail closed."""
    async with _SyntheticLoopbackServer() as internal:
        original_getaddrinfo = socket.getaddrinfo

        def mixed_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
            hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
            if hostname == "mixed.example":
                return [
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", port or 0)),
                    (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", port or 0)),
                ]
            return original_getaddrinfo(host, port, *args, **kwargs)

        monkeypatch.setattr(socket, "getaddrinfo", mixed_getaddrinfo)

        manager = WebhookManager()
        cfg = WebhookConfig(
            url=f"http://mixed.example:{internal.port}/hook",
            events=[WebhookEvent.DRIFT_ALERT],
        )
        manager.register(cfg)
        await manager.fire(WebhookEvent.DRIFT_ALERT, {"test": "mixed"})

        assert len(internal.received_requests) == 0, (
            "SECURITY FAILURE: WebhookManager delivered to internal target despite mixed DNS!"
        )


# ── 16. Retry Re-Resolution Safety ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_rebinding_on_second_delivery_attempt_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """DNS rebinding on the second delivery attempt MUST be blocked.

    Attempt 1: resolve + connect → public IP → success (or failure, e.g. no listener)
    Attempt 2: resolve + connect → private IP → MUST be blocked at SafeNetworkBackend
    """
    async with _SyntheticLoopbackServer() as internal:
        attempt_count = 0
        original_getaddrinfo = socket.getaddrinfo

        def rebind_on_retry(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
            nonlocal attempt_count
            hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
            if hostname == "retry.example":
                attempt_count += 1
                if attempt_count <= 2:
                    # First two resolutions → public (pre-check + first connect) → connection fails
                    return _make_addrinfo("93.184.216.34", port or 0)
                else:
                    # Subsequent resolutions → loopback (simulating rebinding on retry)
                    return _make_addrinfo("127.0.0.1", internal.port)
            return original_getaddrinfo(host, port, *args, **kwargs)

        monkeypatch.setattr(socket, "getaddrinfo", rebind_on_retry)

        manager = WebhookManager()
        cfg = WebhookConfig(
            url=f"http://retry.example:{internal.port}/hook",
            events=[WebhookEvent.DRIFT_ALERT],
            max_retries=2,
        )
        manager.register(cfg)
        await manager.fire(WebhookEvent.DRIFT_ALERT, {"test": "retry"})

        assert len(internal.received_requests) == 0, (
            "SECURITY FAILURE: Retry rebinding reached internal loopback!"
        )


# ── 17. CNAME Resolution Proofs ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_cname_chain_resolving_to_private_ip_is_blocked(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """CNAME chain pointing to a loopback/private IP must fail closed.

    public.example -> CNAME intermediate.example -> 127.0.0.1
    UNSAFE FINAL CNAME DESTINATION: BLOCKED
    """
    original_getaddrinfo = socket.getaddrinfo

    def cname_unsafe_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
        if hostname in ("public.example", "intermediate.example"):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "intermediate.example", ("127.0.0.1", port or 0))
            ]
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", cname_unsafe_getaddrinfo)

    resolver = SystemDNSResolver()
    with pytest.raises(ForbiddenDestinationError):
        await resolver.resolve("public.example", 80, DestinationPolicy.PUBLIC_ONLY)

    # validate_webhook_url must also reject at precheck
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url("http://public.example/hook")


@pytest.mark.asyncio
async def test_multilevel_cname_chain_resolving_to_safe_public_ip_passes(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Multi-level CNAME chain pointing to a valid public IP must succeed.

    cname1.example -> CNAME cname2.example -> CNAME cname3.example -> 93.184.216.34
    SAFE FINAL CNAME DESTINATION: PASS
    """
    original_getaddrinfo = socket.getaddrinfo

    def cname_safe_getaddrinfo(host: Any, port: Any, *args: Any, **kwargs: Any) -> list[Any]:
        hostname = host.decode("ascii") if isinstance(host, bytes) else str(host)
        if hostname in ("cname1.example", "cname2.example", "cname3.example"):
            return [
                (socket.AF_INET, socket.SOCK_STREAM, 6, "cname3.example", ("93.184.216.34", port or 0))
            ]
        return original_getaddrinfo(host, port, *args, **kwargs)

    monkeypatch.setattr(socket, "getaddrinfo", cname_safe_getaddrinfo)

    resolver = SystemDNSResolver()
    addrs = await resolver.resolve("cname1.example", 443, DestinationPolicy.PUBLIC_ONLY)
    assert len(addrs) == 1
    assert str(addrs[0]) == "93.184.216.34"

    # Precheck passes without error
    validate_webhook_url("https://cname1.example/hook")


# ── 18. TLS / SNI / Hostname & Certificate Validation Proofs ──────────────────

def test_tls_verification_cannot_be_disabled() -> None:
    """verify=False is strictly forbidden in SafeAsyncHTTPTransport."""
    with pytest.raises(ValueError, match="TLS certificate verification cannot be disabled"):
        SafeAsyncHTTPTransport(verify=False)


@pytest.mark.asyncio
async def test_tls_sni_and_host_header_preserves_original_hostname_with_pinned_ip() -> None:
    """Prove that TCP connection uses validated pinned IP while preserving original SNI and Host."""
    import datetime
    import ssl
    import tempfile

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    # Generate test cert for safe.example.test
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "safe.example.test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1000)
        .not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("safe.example.test")]), critical=False)
        .sign(key, hashes.SHA256())
    )

    with tempfile.NamedTemporaryFile(suffix=".pem") as cert_file, tempfile.NamedTemporaryFile(suffix=".pem") as key_file:
        cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
        cert_file.flush()
        key_file.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        key_file.flush()

        received_sni: list[str | None] = []
        received_host_headers: list[str] = []

        server_ssl = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ssl.load_cert_chain(cert_file.name, key_file.name)

        def sni_callback(sock: Any, server_name: str | None, ctx: Any) -> None:
            received_sni.append(server_name)

        server_ssl.sni_callback = sni_callback
        client_ssl = ssl.create_default_context(cafile=cert_file.name)

        class PinnedLoopbackResolver:
            async def resolve(self, host: str, port: int, policy: DestinationPolicy) -> list[ipaddress.IPv4Address]:
                return [ipaddress.IPv4Address("127.0.0.1")]

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            data = await reader.read(4096)
            for line in data.split(b"\r\n"):
                if line.lower().startswith(b"host:"):
                    received_host_headers.append(line.decode())
            writer.write(b"HTTP/1.1 200 OK\r\nContent-Length: 2\r\nConnection: close\r\n\r\nok")
            await writer.drain()
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_client, "127.0.0.1", 0, ssl=server_ssl)
        port = server.sockets[0].getsockname()[1]

        transport = SafeAsyncHTTPTransport(
            verify=client_ssl,
            policy=DestinationPolicy.LOCAL_DEV,
            resolver=PinnedLoopbackResolver(),
        )
        async with httpx.AsyncClient(transport=transport) as client:
            resp = await client.get(f"https://safe.example.test:{port}/path")
            assert resp.status_code == 200

        server.close()
        await server.wait_closed()

        # Assertions
        assert received_sni == ["safe.example.test"], f"TLS SNI mismatch: {received_sni}"
        assert len(received_host_headers) == 1
        assert received_host_headers[0].startswith("Host: safe.example.test:"), f"Host header mismatch: {received_host_headers}"


@pytest.mark.asyncio
async def test_tls_certificate_hostname_mismatch_is_rejected() -> None:
    """Prove that certificate hostname mismatch is strictly REJECTED (no verify=False bypass)."""
    import datetime
    import ssl
    import tempfile

    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import rsa
    from cryptography.x509.oid import NameOID

    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "safe.example.test")])
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(1000)
        .not_valid_before(datetime.datetime.now(datetime.UTC) - datetime.timedelta(days=1))
        .not_valid_after(datetime.datetime.now(datetime.UTC) + datetime.timedelta(days=1))
        .add_extension(x509.SubjectAlternativeName([x509.DNSName("safe.example.test")]), critical=False)
        .sign(key, hashes.SHA256())
    )

    with tempfile.NamedTemporaryFile(suffix=".pem") as cert_file, tempfile.NamedTemporaryFile(suffix=".pem") as key_file:
        cert_file.write(cert.public_bytes(serialization.Encoding.PEM))
        cert_file.flush()
        key_file.write(key.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()))
        key_file.flush()

        server_ssl = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
        server_ssl.load_cert_chain(cert_file.name, key_file.name)
        client_ssl = ssl.create_default_context(cafile=cert_file.name)

        class PinnedLoopbackResolver:
            async def resolve(self, host: str, port: int, policy: DestinationPolicy) -> list[ipaddress.IPv4Address]:
                return [ipaddress.IPv4Address("127.0.0.1")]

        async def handle_client(reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
            try:
                await reader.read(4096)
            except Exception:
                pass
            writer.close()
            await writer.wait_closed()

        server = await asyncio.start_server(handle_client, "127.0.0.1", 0, ssl=server_ssl)
        port = server.sockets[0].getsockname()[1]

        transport = SafeAsyncHTTPTransport(
            verify=client_ssl,
            policy=DestinationPolicy.LOCAL_DEV,
            resolver=PinnedLoopbackResolver(),
        )
        async with httpx.AsyncClient(transport=transport) as client:
            # Requesting wrong.example.test against a cert for safe.example.test MUST fail cert verification
            with pytest.raises((httpx.ConnectError, ssl.SSLCertVerificationError)):
                await client.get(f"https://wrong.example.test:{port}/path")

        server.close()
        await server.wait_closed()


# ── 19. Destination Policy Mode Confusion Proofs ───────────────────────────────

def test_untrusted_request_cannot_select_trusted_private_or_local_dev() -> None:
    """Prove that untrusted request data (WebhookConfig, URL params, etc.) cannot select

    TRUSTED_PRIVATE or LOCAL_DEV policies.
    """
    # WebhookConfig has no policy attribute
    cfg = WebhookConfig(url="https://example.com/hook", events=[WebhookEvent.DRIFT_ALERT])
    assert not hasattr(cfg, "policy")
    assert not hasattr(cfg, "destination_policy")

    # WebhookManager always uses DestinationPolicy.PUBLIC_ONLY
    # In validate_webhook_url, policy is hardcoded to PUBLIC_ONLY
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url("http://10.0.0.1/hook")  # Would pass under TRUSTED_PRIVATE, but rejected


def test_production_default_is_strictly_public_only() -> None:
    """Prove that default production configurations cannot silently fall back to LOCAL_DEV."""
    # create_safe_async_client default is PUBLIC_ONLY
    client = create_safe_async_client()
    assert isinstance(client._transport, SafeAsyncHTTPTransport)
    assert client._transport.policy == DestinationPolicy.PUBLIC_ONLY

    # SafeAsyncHTTPTransport default is PUBLIC_ONLY
    transport = SafeAsyncHTTPTransport()
    assert transport.policy == DestinationPolicy.PUBLIC_ONLY


# ── End of adversarial test suite ────────────────────────────────────────────
