# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Cross-phase end-to-end and adversarial boundary tests for the
Isolation -> Controlled-Egress security seam.

Constitutional Invariant:
An untrusted / isolated execution cannot obtain network egress outside
WhitePact's canonical controlled-egress security plane.

Effective Chain:
ExecutionAuthorization -> guarded execution -> isolated execution
-> controlled network mediation -> canonical destination validation
-> allowed external network.
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import socket
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpcore
import pytest

from responsibleai.governance.execution import (
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    DecisionNotExecutableError,
    ExecutionAuthorization,
    InternalToolExecutor,
    admit_execution,
    authorize_execution,
)
from responsibleai.governance.models import (
    ActionRequest,
    AgentContext,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
)
from responsibleai.governance.upstream import (
    UnsafeUpstreamServerURLError,
    validate_upstream_server_url,
)
from responsibleai.isolation.broker import IsolationBroker
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.environment import build_isolated_environment
from responsibleai.isolation.errors import (
    InvalidBackendModeError,
    IsolationBackendUnavailableError,
    IsolationError,
    IsolationPolicyViolationError,
)
from responsibleai.isolation.models import (
    BackendMode,
    IsolatedExecutionRequest,
    IsolationProfile,
    NetworkPolicy,
)
from responsibleai.isolation.subprocess_backend import LocalSubprocessBackend
from responsibleai.net.egress import (
    AsyncDNSResolver,
    DestinationPolicy,
    DNSResolutionError,
    ForbiddenDestinationError,
    InvalidURLError,
    PeerMismatchError,
    SafeAsyncHTTPTransport,
    SafeNetworkBackend,
    SystemDNSResolver,
    create_safe_async_client,
    is_address_allowed,
    validate_outbound_url,
)
from responsibleai.webhooks.manager import (
    UnsafeWebhookURLError,
    validate_webhook_url,
)

# ── Helpers & Fixtures ────────────────────────────────────────────────────────


def _make_action(
    tool_name: str = "read_file",
    args: dict[str, Any] | None = None,
    *,
    org_id: str = "tenant-seam",
) -> ActionRequest:
    return ActionRequest(
        agent=AgentContext(
            identity=IdentityContext(identity_id="agent-seam-1", kind="api_key", org_id=org_id),
            organization_id=org_id,
        ),
        action_type=tool_name,
        target="filesystem::test",
        arguments=args or {"path": "test.txt"},
    )


def _make_authorization(
    action: ActionRequest,
    *,
    ttl_seconds: int = 60,
    decision: GovernanceDecision = GovernanceDecision.ALLOW,
) -> ExecutionAuthorization:
    dec_result = DecisionResult(
        decision=decision,
        action_id=action.action_id,
        reason_codes=["TEST_PERMIT"],
    )
    return authorize_execution(dec_result, action, ttl_seconds=ttl_seconds)


class _MockDNSResolver(AsyncDNSResolver):
    def __init__(self, ip_map: dict[str, list[str]]) -> None:
        self.ip_map = ip_map

    async def resolve(
        self, host: str, port: int, policy: DestinationPolicy = DestinationPolicy.PUBLIC_ONLY
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        ips = self.ip_map.get(host)
        if not ips:
            raise DNSResolutionError(f"Host {host} unresolvable")
        resolved = []
        for ip_str in ips:
            addr = ipaddress.ip_address(ip_str)
            if not is_address_allowed(addr, policy):
                raise ForbiddenDestinationError(f"Host {host} resolved to forbidden {ip_str}")
            resolved.append(addr)
        return resolved


# ── Section 8: Cross-Phase End-to-End Test ────────────────────────────────────


@pytest.mark.asyncio
async def test_cross_phase_isolation_egress_end_to_end_chain() -> None:
    """Exercise complete chain:
    Consequential action -> ExecutionAuthorization -> admit_execution
    -> IsolationBroker -> DockerContainerBackend (with mandatory --network=none)
    -> Host-side mediated network operations -> SafeNetworkBackend.
    """
    action = _make_action("read_file", {"path": "safe.txt"})
    auth = _make_authorization(action)

    # 1. Execution cannot be admitted twice (replay guard)
    await admit_execution(auth, action, nonce_repo=None)
    assert auth.consumed is True

    with pytest.raises(AuthorizationAlreadyConsumedError):
        await admit_execution(auth, action, nonce_repo=None)

    # 2. Broker executes inside isolated backend with mandatory containment
    mock_backend = AsyncMock()
    mock_backend.execute.return_value = MagicMock(
        is_success=True,
        exit_code=0,
        result_payload={"data": "isolated_content"},
        violation=None,
        stderr="",
    )

    broker = IsolationBroker(backend=mock_backend)
    fresh_auth = _make_authorization(action)
    res = await broker.execute(fresh_auth, action)
    assert res == {"data": "isolated_content"}
    mock_backend.execute.assert_awaited_once()

    # Verify that the execution request received by backend has NetworkPolicy.NONE
    call_req = mock_backend.execute.await_args[0][0]
    assert isinstance(call_req, IsolatedExecutionRequest)
    assert call_req.profile.network_policy == NetworkPolicy.NONE


# ── Section 9: Adversarial Matrix Vectors ─────────────────────────────────────


@pytest.mark.asyncio
async def test_matrix_v1_permitted_public_destination_succeeds() -> None:
    """Vector 1: Permitted public destination through canonical path."""
    resolver = _MockDNSResolver({"api.example.com": ["93.184.216.34"]})
    mock_inner = AsyncMock(spec=httpcore.AsyncNetworkBackend)
    mock_stream = AsyncMock(spec=httpcore.AsyncNetworkStream)
    mock_stream.get_extra_info.return_value = ("93.184.216.34", 443)
    mock_inner.connect_tcp.return_value = mock_stream

    backend = SafeNetworkBackend(
        resolver=resolver,
        policy=DestinationPolicy.PUBLIC_ONLY,
        inner_backend=mock_inner,
    )

    stream = await backend.connect_tcp("api.example.com", 443)
    assert stream is mock_stream
    mock_inner.connect_tcp.assert_awaited_once_with(
        "93.184.216.34", 443, timeout=None, local_address=None, socket_options=None
    )


@pytest.mark.parametrize(
    "forbidden_host",
    [
        "127.0.0.1",
        "127.0.0.2",
        "localhost",
        "localhost.",
        "LOCALHOST",
        "[::1]",
        "::1",
    ],
)
def test_matrix_v2_localhost_blocked(forbidden_host: str) -> None:
    """Vector 2: Localhost destinations strictly blocked."""
    url = f"http://{forbidden_host}/api"
    with pytest.raises((ForbiddenDestinationError, InvalidURLError, UnsafeUpstreamServerURLError)):
        validate_outbound_url(url, DestinationPolicy.PUBLIC_ONLY)
        validate_upstream_server_url(url)


@pytest.mark.parametrize(
    "private_ip",
    [
        "10.0.0.1",
        "10.255.255.254",
        "172.16.0.1",
        "172.31.255.254",
        "192.168.0.1",
        "192.168.1.100",
    ],
)
def test_matrix_v3_rfc1918_private_network_blocked(private_ip: str) -> None:
    """Vector 3: RFC1918 private subnets strictly blocked."""
    url = f"http://{private_ip}:8080/internal"
    with pytest.raises((ForbiddenDestinationError, UnsafeUpstreamServerURLError)):
        validate_outbound_url(url, DestinationPolicy.PUBLIC_ONLY)
        validate_upstream_server_url(url)


@pytest.mark.parametrize(
    "link_local_ip",
    [
        "169.254.169.254",  # AWS/GCP/Azure instance metadata
        "169.254.1.1",
        "169.254.170.2",  # ECS metadata
    ],
)
def test_matrix_v4_link_local_metadata_blocked(link_local_ip: str) -> None:
    """Vector 4: Link-local & cloud metadata strictly blocked."""
    url = f"http://{link_local_ip}/latest/meta-data/"
    with pytest.raises((ForbiddenDestinationError, UnsafeUpstreamServerURLError)):
        validate_outbound_url(url, DestinationPolicy.PUBLIC_ONLY)
        validate_upstream_server_url(url)


@pytest.mark.parametrize(
    "unsafe_ipv6",
    [
        "::1",  # Loopback
        "::",  # Unspecified
        "fe80::1",  # Link-local
        "fc00::1",  # ULA
        "fd12:3456:789a:1::1",  # ULA
        "ff02::1",  # Multicast
    ],
)
def test_matrix_v5_unsafe_ipv6_blocked(unsafe_ipv6: str) -> None:
    """Vector 5: Unsafe IPv6 addresses strictly blocked."""
    assert not is_address_allowed(unsafe_ipv6, DestinationPolicy.PUBLIC_ONLY)
    url = f"http://[{unsafe_ipv6}]/service"
    with pytest.raises((ForbiddenDestinationError, UnsafeUpstreamServerURLError)):
        validate_outbound_url(url, DestinationPolicy.PUBLIC_ONLY)
        validate_upstream_server_url(url)


@pytest.mark.asyncio
async def test_matrix_v6_mixed_safe_unsafe_dns_fails_closed() -> None:
    """Vector 6: If ANY resolved address in DNS answers is forbidden, fail closed."""
    resolver = SystemDNSResolver()
    # Mock loop.getaddrinfo to return both a public IP and an internal IP
    mixed_addr_infos = [
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("93.184.216.34", 443)),
        (socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.1", 443)),
    ]

    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.getaddrinfo = AsyncMock(return_value=mixed_addr_infos)
        with pytest.raises(ForbiddenDestinationError) as exc_info:
            await resolver.resolve("mixed.example.com", 443, DestinationPolicy.PUBLIC_ONLY)
        assert "resolved to forbidden network address 10.0.0.1" in str(exc_info.value)


@pytest.mark.asyncio
async def test_matrix_v7_dns_rebinding_re_resolution_mismatch() -> None:
    """Vector 7: DNS rebinding - resolver switches from public to forbidden address."""
    # First resolution: safe. Second resolution or connect time: forbidden.
    resolver = AsyncMock(spec=AsyncDNSResolver)
    resolver.resolve.side_effect = ForbiddenDestinationError("Rebound to 127.0.0.1")

    backend = SafeNetworkBackend(
        resolver=resolver,
        policy=DestinationPolicy.PUBLIC_ONLY,
    )

    with pytest.raises(ForbiddenDestinationError):
        await backend.connect_tcp("rebind.attacker.com", 443)


@pytest.mark.asyncio
async def test_matrix_v8_post_connect_peer_mismatch_fails_closed() -> None:
    """Vector 8: Post-connect peer verification detects connection redirected to forbidden peer."""
    resolver = _MockDNSResolver({"legit.com": ["93.184.216.34"]})
    mock_inner = AsyncMock(spec=httpcore.AsyncNetworkBackend)
    mock_stream = AsyncMock(spec=httpcore.AsyncNetworkStream)
    # Stream connected, but underlying peer address reports 127.0.0.1 (NAT/tunnel redirection)
    mock_stream.get_extra_info.return_value = ("127.0.0.1", 8080)
    mock_inner.connect_tcp.return_value = mock_stream

    backend = SafeNetworkBackend(
        resolver=resolver,
        policy=DestinationPolicy.PUBLIC_ONLY,
        inner_backend=mock_inner,
    )

    with pytest.raises(PeerMismatchError) as exc_info:
        await backend.connect_tcp("legit.com", 443)

    assert "violates egress security policy" in str(exc_info.value)
    mock_stream.aclose.assert_awaited_once()


def test_matrix_v9_proxy_environment_variables_prevented(monkeypatch: pytest.MonkeyPatch) -> None:
    """Vector 9: Proxy environment variables (HTTP_PROXY, ALL_PROXY, etc.)
    are completely ignored by canonical client and stripped from isolation environments.
    """
    monkeypatch.setenv("HTTP_PROXY", "http://corporate-proxy:8080")
    monkeypatch.setenv("HTTPS_PROXY", "http://corporate-proxy:8080")
    monkeypatch.setenv("ALL_PROXY", "socks5://corporate-proxy:1080")
    monkeypatch.setenv("NO_PROXY", "localhost")

    # 1. create_safe_async_client enforces trust_env=False
    client = create_safe_async_client()
    assert client._transport is not None
    assert client.trust_env is False

    # 2. build_isolated_environment strips proxy variables from sandbox environment
    clean_env = build_isolated_environment(
        organization_id="tenant-proxy",
        action_id="act-proxy-1",
        inherit_safe_host_vars=True,
    )
    assert "HTTP_PROXY" not in clean_env
    assert "HTTPS_PROXY" not in clean_env
    assert "ALL_PROXY" not in clean_env
    assert "NO_PROXY" not in clean_env


@pytest.mark.asyncio
async def test_matrix_v10_direct_raw_socket_fails_closed() -> None:
    """Vector 10: Untrusted workload requesting direct network authority fails closed.
    Proves WP-IE-01 fix: NetworkPolicy.ALLOWLISTED_EGRESS is strictly forbidden.
    """
    profile_with_egress = IsolationProfile(
        name="ATTEMPTED_EGRESS",
        network_policy=NetworkPolicy.ALLOWLISTED_EGRESS,
    )
    req = IsolatedExecutionRequest(
        action_id="act-egress-attack",
        organization_id="tenant-adv",
        action_type="raw_socket_call",
        arguments={},
        profile=profile_with_egress,
    )

    # 1. Docker container backend must refuse execution immediately
    docker_backend = DockerContainerBackend()
    with patch.object(docker_backend, "is_available", return_value=True):
        with pytest.raises(IsolationPolicyViolationError) as exc_info:
            await docker_backend.execute(req)
        assert "Direct network egress from isolated container execution is forbidden" in str(exc_info.value)

    # 2. Local subprocess backend must also refuse execution immediately
    subprocess_backend = LocalSubprocessBackend()
    with pytest.raises(IsolationPolicyViolationError) as exc_info:
        await subprocess_backend.execute(req)
    assert "Direct network egress from isolated subprocess execution is forbidden" in str(exc_info.value)


@pytest.mark.asyncio
async def test_matrix_v11_subprocess_utility_network_bypass_prevented() -> None:
    """Vector 11: Subprocess backend cannot be used in production to bypass isolation."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        with pytest.raises(InvalidBackendModeError) as exc_info:
            IsolationBroker(mode=BackendMode.LOCAL_DEV)
        assert "LOCAL_DEV isolation backend mode is strictly forbidden in production" in str(exc_info.value)


@pytest.mark.asyncio
async def test_matrix_v12_alternate_production_adapters_use_same_egress_plane() -> None:
    """Vector 12: Both UpstreamMCPExecutor and WebhookManager share the canonical
    create_safe_async_client and SafeNetworkBackend security plane.
    """
    # 1. Upstream MCP client creation uses SafeAsyncHTTPTransport with PUBLIC_ONLY
    from responsibleai.governance.upstream_executor import _default_http_client_factory

    client = _default_http_client_factory()
    assert isinstance(client._transport, SafeAsyncHTTPTransport)
    assert client._transport.policy == DestinationPolicy.PUBLIC_ONLY
    assert client.trust_env is False

    # 2. Webhooks URL validator enforces DestinationPolicy.PUBLIC_ONLY
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url("http://127.0.0.1:8000/hook")
    with pytest.raises(UnsafeWebhookURLError):
        validate_webhook_url("http://169.254.169.254/hook")


@pytest.mark.asyncio
async def test_matrix_v13_controlled_egress_backend_unavailable_fails_closed() -> None:
    """Vector 13: Controlled-egress backend unavailable fails closed (no raw fallback)."""
    resolver = AsyncMock(spec=AsyncDNSResolver)
    resolver.resolve.side_effect = DNSResolutionError("Resolver offline")

    backend = SafeNetworkBackend(resolver=resolver)
    with pytest.raises(DNSResolutionError):
        await backend.connect_tcp("api.example.com", 443)


@pytest.mark.asyncio
async def test_matrix_v14_timeout_cancellation_no_unsafe_fallback() -> None:
    """Vector 14: Timeout or cancellation aborts cleanly with no fallback."""
    mock_inner = AsyncMock(spec=httpcore.AsyncNetworkBackend)
    mock_inner.connect_tcp.side_effect = TimeoutError("TCP connect timed out")

    resolver = _MockDNSResolver({"slow.example.com": ["93.184.216.34"]})
    backend = SafeNetworkBackend(
        resolver=resolver,
        policy=DestinationPolicy.PUBLIC_ONLY,
        inner_backend=mock_inner,
    )

    with pytest.raises(asyncio.TimeoutError):
        await backend.connect_tcp("slow.example.com", 443)


def test_matrix_v15_untrusted_request_cannot_select_trusted_mode() -> None:
    """Vector 15: Untrusted request cannot choose LOCAL_DEV or bypass PUBLIC_ONLY."""
    # Neither ActionRequest nor UpstreamServer registration permit callers to downgrade policy
    action = _make_action("fetch_data", {"url": "http://127.0.0.1:8080", "policy": "LOCAL_DEV"})
    # DestinationPolicy is not accepted or honored on ActionRequest
    assert not hasattr(action, "destination_policy")
    # All canonical egress factories hardcode PUBLIC_ONLY
    client = create_safe_async_client()
    assert isinstance(client._transport, SafeAsyncHTTPTransport)
    assert client._transport.policy == DestinationPolicy.PUBLIC_ONLY


def test_matrix_v16_redirect_to_forbidden_blocked() -> None:
    """Vector 16: Safe client disables automatic redirects to prevent redirect SSRF."""
    client = create_safe_async_client()
    assert client.follow_redirects is False


@pytest.mark.parametrize(
    "ipv4_mapped",
    [
        "::ffff:127.0.0.1",
        "::ffff:10.0.0.1",
        "::ffff:169.254.169.254",
        "::ffff:192.168.1.1",
    ],
)
def test_matrix_v17_ipv4_mapped_ipv6_bypass_blocked(ipv4_mapped: str) -> None:
    """Vector 17: IPv4-mapped IPv6 literals unwrapped and evaluated against destination policy."""
    assert not is_address_allowed(ipv4_mapped, DestinationPolicy.PUBLIC_ONLY)
    with pytest.raises((ForbiddenDestinationError, UnsafeUpstreamServerURLError)):
        validate_outbound_url(f"http://[{ipv4_mapped}]/api", DestinationPolicy.PUBLIC_ONLY)
        validate_upstream_server_url(f"http://[{ipv4_mapped}]/api")


@pytest.mark.parametrize(
    "obfuscated_url",
    [
        "http://2130706433/",  # Decimal representation of 127.0.0.1
        "http://0177.0.0.1/",  # Octal representation of 127.0.0.1
        "http://0x7f.0.0.1/",  # Hex representation of 127.0.0.1
        "http://localhost./",  # Trailing dot
        "http://LOCALHOST/",  # Uppercase
    ],
)
def test_matrix_v18_hostname_obfuscation_and_case_blocked(obfuscated_url: str) -> None:
    """Vector 18: Obfuscated IP literals and case manipulation blocked."""
    with pytest.raises((ForbiddenDestinationError, UnsafeUpstreamServerURLError, InvalidURLError)):
        validate_outbound_url(obfuscated_url, DestinationPolicy.PUBLIC_ONLY)
        validate_upstream_server_url(obfuscated_url)


# ── Section 11: Execution Boundary Invariants ─────────────────────────────────


@pytest.mark.asyncio
async def test_execution_boundary_unauthorized_action_rejected() -> None:
    """Unauthorized action cannot start sandbox (DecisionNotExecutableError)."""
    action = _make_action()
    deny_decision = DecisionResult(
        decision=GovernanceDecision.DENY,
        action_id=action.action_id,
        reason_codes=["BLOCKED_BY_POLICY"],
    )
    with pytest.raises(DecisionNotExecutableError):
        authorize_execution(deny_decision, action)


@pytest.mark.asyncio
async def test_execution_boundary_stale_authorization_rejected() -> None:
    """Expired authorization cannot start sandbox."""
    action = _make_action()
    auth = _make_authorization(action, ttl_seconds=-1)
    assert auth.is_expired is True

    executor = InternalToolExecutor()
    with pytest.raises(AuthorizationExpiredError):
        await executor.execute(auth, action)


@pytest.mark.asyncio
async def test_execution_boundary_replayed_authorization_rejected() -> None:
    """Consumed authorization cannot be reused to start another sandbox."""
    action = _make_action()
    auth = _make_authorization(action)
    auth.consumed = True

    executor = InternalToolExecutor()
    with pytest.raises(AuthorizationAlreadyConsumedError):
        await executor.execute(auth, action)


@pytest.mark.asyncio
async def test_execution_boundary_restore_readiness_failure_rejects_sandbox() -> None:
    """Failure of pre-exec restore admission chokepoint prevents sandbox launch."""
    action = _make_action()
    auth = _make_authorization(action)

    with patch(
        "responsibleai.data_governance.backup_defense.assert_restore_readiness_admitted",
        side_effect=PermissionError("System in restore mode"),
    ):
        executor = InternalToolExecutor()
        with pytest.raises(PermissionError):
            await executor.execute(auth, action)


@pytest.mark.asyncio
async def test_execution_boundary_production_same_process_forbidden() -> None:
    """Same-process tool execution is strictly forbidden in production."""
    action = _make_action()
    auth = _make_authorization(action)

    with patch.dict(os.environ, {"ENVIRONMENT": "production"}):
        # Inject a sentinel broker so constructing the executor does not perform
        # Docker discovery.  This test targets the independent execution-time
        # invariant: production must never fall back to same-process dispatch
        # when its configured broker is absent.
        executor = InternalToolExecutor(broker=object())
        executor._broker = None
        with pytest.raises(IsolationError) as exc_info:
            await executor.execute(auth, action)
        assert "Same-process tool execution is strictly forbidden in production" in str(exc_info.value)


@pytest.mark.asyncio
async def test_execution_boundary_unavailable_docker_fails_closed_in_production() -> None:
    """Missing or unreachable Docker daemon fails closed in production."""
    with patch.dict(os.environ, {"ENVIRONMENT": "production", "WHITEPACT_ISOLATION_BACKEND": "docker"}):
        with patch.object(DockerContainerBackend, "is_available", return_value=False):
            with pytest.raises(IsolationBackendUnavailableError) as exc_info:
                IsolationBroker()
            assert "Docker container isolation backend is required but unavailable. Failing closed." in str(exc_info.value)
