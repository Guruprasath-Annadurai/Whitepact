# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise Outbound Egress & DNS Rebinding Security Boundary.

Provides cryptographically and transport-bound destination verification for all
outbound HTTP requests. Guarantees that:
1. Destination URLs, schemes, ports, and IP literals are validated against
   forbidden ranges (loopback, private RFC1918, link-local, ULA, CGNAT, metadata).
2. DNS resolution is performed securely; if ANY candidate address is forbidden,
   the request fails closed immediately.
3. The actual TCP socket connection is bound to a validated safe IP candidate,
   preventing TOCTOU DNS rebinding attacks.
4. HTTP Host headers, TLS Server Name Indication (SNI), and certificate
   verification are preserved.
5. Ambient proxy environment variables (HTTP_PROXY, ALL_PROXY) cannot bypass
   destination security policy.
6. Unix domain sockets and non-HTTP schemes are strictly forbidden.
"""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
import ssl
import typing
from enum import StrEnum
from typing import Protocol
from urllib.parse import urlsplit

import httpcore
import httpx
from httpx._transports.default import AsyncResponseStream, map_httpcore_exceptions

logger = logging.getLogger(__name__)

# ── Destination Policies & Constants ──────────────────────────────────────────


class DestinationPolicy(StrEnum):
    PUBLIC_ONLY = "public_only"
    TRUSTED_PRIVATE = "trusted_private"
    LOCAL_DEV = "local_dev"


CGNAT_NET = ipaddress.ip_network("100.64.0.0/10")
METADATA_V4 = ipaddress.ip_address("169.254.169.254")
METADATA_V6 = ipaddress.ip_address("fd00:ec2::254")

ALLOWED_SCHEMES = frozenset({"http", "https"})
FORBIDDEN_HOSTNAMES = frozenset(
    {
        "localhost",
        "localhost.",
        "metadata.google.internal",
        "metadata.internal",
    }
)


# ── Exceptions ────────────────────────────────────────────────────────────────


class EgressSecurityError(ValueError):
    """Base exception for all outbound egress security violations."""


class ForbiddenDestinationError(EgressSecurityError):
    """Raised when an outbound URL or IP targets a forbidden network destination."""


class DNSResolutionError(EgressSecurityError):
    """Raised when DNS resolution fails or returns no routable candidates."""


class PeerMismatchError(EgressSecurityError):
    """Raised when the connected socket peer address violates destination policy."""


class InvalidURLError(EgressSecurityError):
    """Raised when an outbound URL is malformed or uses an unsupported scheme."""


# ── Address Validation ────────────────────────────────────────────────────────


def is_address_allowed(
    ip_str_or_obj: str | ipaddress.IPv4Address | ipaddress.IPv6Address,
    policy: DestinationPolicy = DestinationPolicy.PUBLIC_ONLY,
) -> bool:
    """Return True if the given IP address is permitted under the specified policy."""
    if policy == DestinationPolicy.LOCAL_DEV:
        return True

    if isinstance(ip_str_or_obj, str):
        try:
            ip = ipaddress.ip_address(ip_str_or_obj)
        except ValueError:
            return False
    else:
        ip = ip_str_or_obj

    # Recursively unwrap IPv4-mapped IPv6 addresses (e.g. ::ffff:127.0.0.1)
    if isinstance(ip, ipaddress.IPv6Address) and ip.ipv4_mapped is not None:
        return is_address_allowed(ip.ipv4_mapped, policy)

    if (
        ip.is_loopback
        or ip.is_link_local
        or ip.is_reserved
        or ip.is_multicast
        or ip.is_unspecified
        or ip == METADATA_V4
        or ip == METADATA_V6
        or (ip.version == 4 and ip in CGNAT_NET)
    ):
        return False

    if policy == DestinationPolicy.PUBLIC_ONLY:
        if ip.is_private:
            return False
        # Catch IPv6 Unique Local Addresses (fc00::/7) which may not all flag is_private
        if ip.version == 6 and ip in ipaddress.ip_network("fc00::/7"):
            return False

    return True


# ── URL & Host Validation ─────────────────────────────────────────────────────


def normalize_and_validate_url(
    url: str,
    policy: DestinationPolicy = DestinationPolicy.PUBLIC_ONLY,
) -> tuple[str, str, int]:
    """Parse, normalize, and validate an outbound URL.

    Returns (normalized_url, hostname, port).
    Raises EgressSecurityError if the URL violates scheme, syntax, or static IP policy.
    """
    if not url or not isinstance(url, str):
        raise InvalidURLError("Outbound URL must be a non-empty string")

    # Reject embedded CRLF or whitespace tricks
    if any(c in url for c in ("\r", "\n", "\t", " ")):
        raise InvalidURLError("Outbound URL contains illegal whitespace or control characters")

    try:
        parsed = urlsplit(url)
    except Exception as exc:
        raise InvalidURLError(f"Malformed URL: {exc}") from exc

    if parsed.scheme not in ALLOWED_SCHEMES:
        raise InvalidURLError(
            f"Unsupported URL scheme {parsed.scheme!r}; only {sorted(ALLOWED_SCHEMES)} are allowed"
        )

    host = parsed.hostname
    if not host:
        raise InvalidURLError("Outbound URL must contain a valid hostname")

    # Normalize host: strip trailing dot, case fold
    host_clean = host.strip().rstrip(".")
    if not host_clean:
        raise InvalidURLError("Outbound URL hostname cannot be empty")

    if host_clean.lower() in FORBIDDEN_HOSTNAMES:
        raise ForbiddenDestinationError(f"Target host {host!r} is a forbidden internal hostname")

    # Reject ambiguous or obfuscated IPv4 representations
    # 1. Plain integer IPv4 literal: http://2130706433
    if host_clean.isdigit():
        int_ip: ipaddress.IPv4Address | None = None
        try:
            val = int(host_clean)
            if 0 <= val <= 0xFFFFFFFF:
                int_ip = ipaddress.IPv4Address(val)
        except ValueError:
            pass
        if int_ip is not None and not is_address_allowed(int_ip, policy):
            raise ForbiddenDestinationError(
                f"Integer IPv4 literal {host!r} resolves to forbidden destination {int_ip}"
            )

    # 2. Dotted IPv4 with leading zeroes (octal) or hex notation: http://0177.0.0.1 or http://0x7f.0.0.1
    parts = host_clean.split(".")
    if len(parts) == 4:
        for part in parts:
            if (
                part.startswith("0") and len(part) > 1 and not part.startswith("0x")
            ) or part.lower().startswith("0x"):
                raise ForbiddenDestinationError(
                    f"Ambiguous or obfuscated IPv4 literal {host!r} is forbidden"
                )

    # 3. Direct IP address string: http://127.0.0.1 or http://[::1]
    parsed_ip: ipaddress.IPv4Address | ipaddress.IPv6Address | None = None
    try:
        parsed_ip = ipaddress.ip_address(host_clean)
    except ValueError:
        # Not a literal IP address; domain name will be resolved at connect time
        pass

    if parsed_ip is not None and not is_address_allowed(parsed_ip, policy):
        raise ForbiddenDestinationError(
            f"Target host {host!r} is a forbidden network address ({parsed_ip})"
        )

    port = parsed.port
    if port is None:
        port = 443 if parsed.scheme == "https" else 80
    elif not (1 <= port <= 65535):
        raise InvalidURLError(f"Invalid outbound destination port: {port}")

    return url, host_clean, port


def validate_outbound_url(
    url: str,
    policy: DestinationPolicy = DestinationPolicy.PUBLIC_ONLY,
) -> None:
    """Convenience helper to validate outbound URL syntax and static destination."""
    normalize_and_validate_url(url, policy)


# ── DNS Resolver Abstraction ──────────────────────────────────────────────────


class AsyncDNSResolver(Protocol):
    async def resolve(
        self, host: str, port: int, policy: DestinationPolicy
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]: ...


class SystemDNSResolver:
    """Standard system DNS resolver that collects all A and AAAA answers and validates

    each against the destination policy. Fails closed if any answer is forbidden.
    """

    async def resolve(
        self, host: str, port: int, policy: DestinationPolicy = DestinationPolicy.PUBLIC_ONLY
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        loop = asyncio.get_running_loop()
        try:
            addr_infos = await loop.getaddrinfo(
                host,
                port,
                family=socket.AF_UNSPEC,
                type=socket.SOCK_STREAM,
            )
        except socket.gaierror as exc:
            raise DNSResolutionError(f"DNS resolution failed for {host!r}: {exc}") from exc
        except Exception as exc:
            raise DNSResolutionError(f"DNS error resolving {host!r}: {exc}") from exc

        if not addr_infos:
            raise DNSResolutionError(f"DNS resolution returned no addresses for {host!r}")

        resolved_ips: list[ipaddress.IPv4Address | ipaddress.IPv6Address] = []
        for info in addr_infos:
            sockaddr = info[4]
            ip_str = sockaddr[0]
            try:
                ip_obj = ipaddress.ip_address(ip_str)
            except ValueError as exc:
                raise DNSResolutionError(f"DNS returned unparseable IP {ip_str!r}: {exc}") from exc

            # HARD INVARIANT: If ANY resolved IP is forbidden, fail closed!
            if not is_address_allowed(ip_obj, policy):
                raise ForbiddenDestinationError(
                    f"Host {host!r} resolved to forbidden network address {ip_str}"
                )
            if ip_obj not in resolved_ips:
                resolved_ips.append(ip_obj)

        if not resolved_ips:
            raise DNSResolutionError(f"No usable safe addresses resolved for {host!r}")

        return resolved_ips


# ── Safe Network Backend ──────────────────────────────────────────────────────


class SafeNetworkBackend(httpcore.AsyncNetworkBackend):
    """Pluggable httpcore network backend that enforces:

    1. DNS resolution and destination policy at connection time.
    2. Direct TCP connection to a validated IP candidate (preventing TOCTOU).
    3. Post-connect peer address verification.
    4. Explicit rejection of Unix domain sockets.
    """

    def __init__(
        self,
        resolver: AsyncDNSResolver | None = None,
        policy: DestinationPolicy = DestinationPolicy.PUBLIC_ONLY,
        inner_backend: httpcore.AsyncNetworkBackend | None = None,
    ) -> None:
        self.resolver = resolver or SystemDNSResolver()
        self.policy = policy
        self._inner = inner_backend or httpcore.AnyIOBackend()

    async def connect_tcp(
        self,
        host: str | bytes,
        port: int,
        timeout: float | None = None,
        local_address: str | None = None,
        socket_options: typing.Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        if isinstance(host, bytes):
            host_str = host.decode("ascii", errors="replace")
        else:
            host_str = str(host)

        # Normalize host string
        host_str = host_str.strip().rstrip(".")

        # Check if host is an explicit IP literal
        is_literal_ip = False
        try:
            ip_obj = ipaddress.ip_address(host_str)
            is_literal_ip = True
            if not is_address_allowed(ip_obj, self.policy):
                raise ForbiddenDestinationError(
                    f"Direct outbound connection to forbidden address {host_str} rejected"
                )
            candidate_ips = [ip_obj]
        except ValueError:
            pass

        if not is_literal_ip:
            if host_str.lower() in FORBIDDEN_HOSTNAMES:
                raise ForbiddenDestinationError(
                    f"Outbound connection to forbidden internal hostname {host_str!r} rejected"
                )
            # Resolve and validate all candidate addresses
            candidate_ips = await self.resolver.resolve(host_str, port, self.policy)

        # Connect strictly to a validated IP address
        stream: httpcore.AsyncNetworkStream | None = None
        last_error: Exception | None = None

        for ip in candidate_ips:
            try:
                stream = await self._inner.connect_tcp(
                    str(ip),
                    port,
                    timeout=timeout,
                    local_address=local_address,
                    socket_options=socket_options,
                )
                break
            except Exception as exc:
                last_error = exc
                continue

        if stream is None:
            if last_error is not None:
                raise last_error
            raise httpcore.ConnectError(f"Could not connect to any resolved address for {host_str}")

        # Post-connect peer verification (defense-in-depth). Fail closed if
        # the connected address cannot be verified — never skip the check.
        try:
            server_addr = stream.get_extra_info("server_addr")
            if not server_addr or len(server_addr) < 1:
                await stream.aclose()
                raise PeerMismatchError(
                    "Connected socket peer address unavailable; refusing outbound connection"
                )
            peer_ip = server_addr[0]
            if not is_address_allowed(peer_ip, self.policy):
                await stream.aclose()
                raise PeerMismatchError(
                    f"Connected socket peer address {peer_ip} violates egress security policy"
                )
        except PeerMismatchError:
            raise
        except Exception as exc:
            if stream is not None:
                await stream.aclose()
            raise PeerMismatchError(
                "Could not verify connected socket peer address; refusing outbound connection"
            ) from exc

        return stream

    async def connect_unix_socket(
        self,
        path: str,
        timeout: float | None = None,
        socket_options: typing.Iterable[httpcore.SOCKET_OPTION] | None = None,
    ) -> httpcore.AsyncNetworkStream:
        raise ForbiddenDestinationError(
            "Outbound connections via Unix domain sockets are forbidden"
        )

    async def sleep(self, seconds: float) -> None:
        await self._inner.sleep(seconds)


# ── Safe HTTP Transport & Client Factory ──────────────────────────────────────


class SafeAsyncHTTPTransport(httpx.AsyncBaseTransport):
    """Custom httpx transport backed by SafeNetworkBackend and an isolated connection pool.

    Enforces trust_env=False (ambient proxy variables are ignored) and preserves
    standard TLS SNI, certificate verification, and HTTP Host headers.
    """

    def __init__(
        self,
        *,
        verify: bool | ssl.SSLContext = True,
        resolver: AsyncDNSResolver | None = None,
        policy: DestinationPolicy = DestinationPolicy.PUBLIC_ONLY,
        retries: int = 0,
        max_connections: int = 20,
    ) -> None:
        if isinstance(verify, ssl.SSLContext):
            ssl_context = verify
        elif verify is True:
            ssl_context = httpcore.default_ssl_context()
        else:
            raise ValueError(
                "TLS certificate verification cannot be disabled in SafeAsyncHTTPTransport"
            )

        self.policy = policy
        self.backend = SafeNetworkBackend(resolver=resolver, policy=policy)
        self._pool = httpcore.AsyncConnectionPool(
            ssl_context=ssl_context,
            network_backend=self.backend,
            retries=retries,
            max_connections=max_connections,
            uds=None,
        )

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        # Pre-validate URL syntax and static destination
        normalize_and_validate_url(str(request.url), self.policy)

        req = httpcore.Request(
            method=request.method,
            url=httpcore.URL(
                scheme=request.url.raw_scheme,
                host=request.url.raw_host,
                port=request.url.port,
                target=request.url.raw_path,
            ),
            headers=request.headers.raw,
            content=request.stream,
            extensions=request.extensions,
        )

        with map_httpcore_exceptions():
            resp = await self._pool.handle_async_request(req)

        assert isinstance(resp.stream, typing.AsyncIterable)

        return httpx.Response(
            status_code=resp.status,
            headers=resp.headers,
            stream=AsyncResponseStream(resp.stream),
            extensions=resp.extensions,
        )

    async def aclose(self) -> None:
        await self._pool.aclose()


def create_safe_async_client(
    *,
    timeout: float = 10.0,
    follow_redirects: bool = False,
    max_redirects: int = 5,
    verify: bool | ssl.SSLContext = True,
    resolver: AsyncDNSResolver | None = None,
    policy: DestinationPolicy = DestinationPolicy.PUBLIC_ONLY,
    headers: dict[str, str] | None = None,
) -> httpx.AsyncClient:
    """Construct an httpx.AsyncClient equipped with SafeAsyncHTTPTransport.

    Guarantees:
    - DNS rebinding resistance via connect-time IP binding.
    - All resolved IP candidates must be non-forbidden.
    - trust_env=False strictly enforced (no ambient proxy leaks).
    - TLS hostname verification and SNI preserved.
    """
    transport = SafeAsyncHTTPTransport(
        verify=verify,
        resolver=resolver,
        policy=policy,
    )
    return httpx.AsyncClient(
        transport=transport,
        timeout=timeout,
        follow_redirects=follow_redirects,
        max_redirects=max_redirects,
        trust_env=False,  # CRITICAL: Do not read HTTP_PROXY/ALL_PROXY from environment
        headers=headers,
    )
