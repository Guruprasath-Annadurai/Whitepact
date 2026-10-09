# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WAR-8 P2 remediation regression — DEFECT-WAR8-01 (malformed ports) and DEFECT-WAR8-02 (SIEM safe egress)."""

from __future__ import annotations

import ipaddress
from unittest.mock import patch

import httpx
import pytest
import respx

from responsibleai.audit.siem_delivery import SiemEventForwarder
from responsibleai.net.egress import (
    AsyncDNSResolver,
    DestinationPolicy,
    ForbiddenDestinationError,
    InvalidURLError,
    SafeAsyncHTTPTransport,
    create_safe_async_client,
    normalize_and_validate_url,
)


class _RebindingDNSResolver(AsyncDNSResolver):
    def __init__(self, initial_ip: str, rebind_ip: str) -> None:
        self.initial_ip = ipaddress.ip_address(initial_ip)
        self.rebind_ip = ipaddress.ip_address(rebind_ip)
        self.query_count = 0

    async def resolve(
        self, host: str, port: int, policy: DestinationPolicy
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        self.query_count += 1
        chosen = self.initial_ip if self.query_count == 1 else self.rebind_ip
        from responsibleai.net.egress import is_address_allowed

        if not is_address_allowed(chosen, policy):
            raise ForbiddenDestinationError(
                f"Host {host!r} resolved to forbidden network address {chosen}"
            )
        return [chosen]


# --- DEFECT-WAR8-01: malformed ports -------------------------------------------------


@pytest.mark.parametrize(
    "url",
    [
        "https://example.com:abc",
        "https://example.com:99999",
        "https://example.com:-1",
        "https://example.com:+80",
        "https://example.com:65536",
    ],
)
def test_malformed_ports_raise_invalid_url_error(url: str) -> None:
    with pytest.raises(InvalidURLError, match="port|Port"):
        normalize_and_validate_url(url)


def test_malformed_port_never_leaks_raw_value_error() -> None:
    with pytest.raises(InvalidURLError):
        normalize_and_validate_url("https://example.com:abc")
    with pytest.raises(InvalidURLError):
        normalize_and_validate_url("https://example.com:99999")


def test_valid_explicit_port_unchanged() -> None:
    _, host, port = normalize_and_validate_url("https://example.com:8443/path")
    assert host == "example.com"
    assert port == 8443


# --- DEFECT-WAR8-02: SIEM safe egress -----------------------------------------------


@pytest.mark.asyncio
async def test_siem_localhost_blocked() -> None:
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    result = await forwarder.forward_ndjson("http://localhost/ingest", '{"a":1}\n')
    assert not result.delivered
    assert result.error


@pytest.mark.asyncio
async def test_siem_127_0_0_1_blocked() -> None:
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    result = await forwarder.forward_ndjson("http://127.0.0.1/ingest", '{"a":1}\n')
    assert not result.delivered
    assert result.error


@pytest.mark.asyncio
async def test_siem_rfc1918_blocked_public_only_contract() -> None:
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    for url in (
        "http://10.0.0.1/ingest",
        "http://172.16.0.1/ingest",
        "http://192.168.1.1/ingest",
    ):
        result = await forwarder.forward_ndjson(url, '{"a":1}\n')
        assert not result.delivered
        assert result.error


@pytest.mark.asyncio
async def test_siem_metadata_blocked() -> None:
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    result = await forwarder.forward_ndjson("http://169.254.169.254/latest/meta-data/", '{"a":1}\n')
    assert not result.delivered
    assert result.error


@pytest.mark.asyncio
async def test_siem_ipv6_loopback_and_link_local_blocked() -> None:
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    for url in ("http://[::1]/ingest", "http://[fe80::1]/ingest"):
        result = await forwarder.forward_ndjson(url, '{"a":1}\n')
        assert not result.delivered
        assert result.error


@pytest.mark.asyncio
async def test_siem_dns_rebinding_blocked_via_safe_client() -> None:
    rebind_resolver = _RebindingDNSResolver("93.184.216.34", "169.254.169.254")

    def client_factory(**kwargs: object) -> httpx.AsyncClient:
        return create_safe_async_client(resolver=rebind_resolver, **kwargs)

    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    with patch(
        "responsibleai.audit.siem_delivery.create_safe_async_client", side_effect=client_factory
    ):
        result = await forwarder.forward_ndjson(
            "http://safe-then-poison.example/ingest", '{"a":1}\n'
        )
    assert not result.delivered
    assert result.attempts >= 1


@pytest.mark.asyncio
async def test_siem_redirect_to_private_blocked_when_redirects_enabled() -> None:
    transport = SafeAsyncHTTPTransport(
        policy=DestinationPolicy.PUBLIC_ONLY,
    )
    redirect_req = httpx.Request("POST", "http://127.0.0.1/stolen")
    with pytest.raises(ForbiddenDestinationError):
        await transport.handle_async_request(redirect_req)
    await transport.aclose()


def test_siem_ambient_proxy_ignored(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("HTTP_PROXY", "http://hostile-proxy.internal:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://hostile-proxy.internal:8080")
    monkeypatch.setenv("ALL_PROXY", "socks5://hostile-proxy.internal:1080")
    client = create_safe_async_client()
    assert client.trust_env is False


@pytest.mark.asyncio
@respx.mock
async def test_siem_legitimate_public_endpoint_can_send() -> None:
    route = respx.post("https://siem.example/ingest").mock(return_value=httpx.Response(200))
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    result = await forwarder.forward_ndjson(
        "https://siem.example/ingest",
        '{"schema":"whitepact.siem.audit.v1"}\n',
    )
    assert result.delivered
    assert route.call_count == 1


@pytest.mark.asyncio
@respx.mock
async def test_siem_bearer_and_hmac_headers_preserved() -> None:
    captured: dict[str, str] = {}

    def inspect(request: httpx.Request) -> httpx.Response:
        captured.update(dict(request.headers))
        return httpx.Response(200)

    respx.post("https://siem.example/ingest").mock(side_effect=inspect)
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    body = '{"event":"test"}\n'
    secret = "hmac-test-secret"
    await forwarder.forward_ndjson(
        "https://siem.example/ingest",
        body,
        bearer_token="test-bearer",
        hmac_secret=secret,
    )
    assert captured.get("authorization") == "Bearer test-bearer"
    assert captured.get("content-type") == "application/x-ndjson"
    assert captured.get("x-whitepact-idempotency-key")
    assert captured.get("x-whitepact-signature-256", "").startswith("sha256=")


@pytest.mark.asyncio
@respx.mock
async def test_siem_retries_preserved() -> None:
    route = respx.post("https://siem.example/ingest").mock(
        side_effect=[
            httpx.Response(503),
            httpx.Response(200),
        ]
    )
    forwarder = SiemEventForwarder(max_retries=3, retry_delays=(0.0, 0.0))
    result = await forwarder.forward_ndjson(
        "https://siem.example/ingest",
        '{"schema":"whitepact.siem.audit.v1"}\n',
    )
    assert result.delivered
    assert result.attempts == 2
    assert route.call_count == 2


@pytest.mark.asyncio
@respx.mock
async def test_siem_duplicate_suppression_preserved() -> None:
    route = respx.post("https://siem.example/ingest").mock(return_value=httpx.Response(200))
    forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
    body = '{"correlation_id":"war8-p2"}\n'
    first = await forwarder.forward_ndjson("https://siem.example/ingest", body)
    second = await forwarder.forward_ndjson("https://siem.example/ingest", body)
    assert first.delivered and not first.duplicate_skipped
    assert second.duplicate_skipped
    assert route.call_count == 1


@pytest.mark.asyncio
async def test_siem_uses_create_safe_async_client_not_raw_httpx() -> None:
    with patch(
        "responsibleai.audit.siem_delivery.create_safe_async_client",
        wraps=create_safe_async_client,
    ) as factory:
        forwarder = SiemEventForwarder(max_retries=1, retry_delays=(0.0,))
        await forwarder.forward_ndjson("http://127.0.0.1/x", "x\n")
    factory.assert_called_once()
    _, kwargs = factory.call_args
    assert kwargs.get("policy") == DestinationPolicy.PUBLIC_ONLY
    assert kwargs.get("follow_redirects") is False
