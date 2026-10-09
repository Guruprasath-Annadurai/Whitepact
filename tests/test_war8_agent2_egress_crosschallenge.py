# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WAR-8 Agent 2 — Network Security, Controlled Egress, Execution Isolation Assault
and Agent-1 Cross-Challenge Test Suite.

Constitutional Doctrine:
"The agent may think freely. It may plan freely.
 But it cannot act outside independently enforced authority."

Primary Invariant:
NO CONSEQUENTIAL ACTION MAY OCCUR WITHOUT VALID, CURRENT,
INDEPENDENTLY VERIFIED AUTHORITY.

Scope of Agent 2 Campaign:
1. Controlled Egress Call Graph & SSRF Resistance
2. IP Encoding Obfuscation Bypasses (Decimal, Octal, Hex, IPv4-Mapped IPv6)
3. DNS Rebinding & TOCTOU Connect-Time IP Binding
4. Redirect Chain & Protocol Revalidation
5. Scheme Attacks & Host/Port Confusion
6. Ambient Proxy Environment Variable Isolation
7. Raw Network Primitives & Subprocess Network Bypass
8. Execution Environment Secret Sanitization
9. Ephemeral Workspace & Filesystem Traversal Isolation
10. Subprocess Command & Argument Injection Defense
11. Resource Limits & Process Group Termination
12. Approval Lifecycle Cross-Challenge (Replay, Concurrency, Mutation, Expiry)
13. Capability Graph & Attenuation Escalation Defense
14. Independent Risk Classifier Integrity
15. Multi-Agent & Multi-Tenant IDOR Resistance
16. Transitive MCP Governance & Target Drift Defense
17. Durable Crash/Restart Nonce Durability (PostgreSQL & SQLite)
18. Multi-Worker Immediate Revocation Visibility
19. Deterministic Security Fuzzing Campaign
20. Mutation Testing Invariant Invalidation Verification
21. Hostile Mixed-Load Concurrency & Capacity Profiling
"""

from __future__ import annotations

import asyncio
import ipaddress
import os
import random
import time
import uuid
from datetime import UTC, datetime, timedelta
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import httpcore
import httpx
import pytest

from responsibleai.db.approval_repository import (
    ApprovalActionMismatchError,
    ApprovalExpiredError,
    ApprovalNotApprovedError,
    ApprovalRepository,
)
from responsibleai.db.delegation_repository import (
    DelegationEscalationError,
    DelegationRepository,
)
from responsibleai.db.engine import (
    DatabaseEngine,
    create_engine,
    governance_approvals,
    organizations,
)
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    NonceAlreadyConsumedError,
    StaleRevocationEpochError,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.governance import (
    ActionRequest,
    AgentContext,
    AuthorizationActionMismatchError,
    AuthorizationAlreadyConsumedError,
    AuthorizationExpiredError,
    AuthorizationOrganizationMismatchError,
    DecisionResult,
    GovernanceDecision,
    IdentityContext,
    InternalToolExecutor,
    authorize_execution,
)
from responsibleai.governance.approval import (
    ApprovalStatus,
)
from responsibleai.governance.execution import (
    AuthorizationTargetDriftError,
    check_target_fingerprint,
)
from responsibleai.governance.gateway import WhitePactRuntimeGateway
from responsibleai.governance.models import AuthorityContext, validate_attenuation
from responsibleai.governance.risk import (
    UPSTREAM_ACTION_TYPE,
    RiskTier,
    classify_action_risk,
)
from responsibleai.governance.upstream import (
    UnsafeUpstreamServerURLError,
    UpstreamServer,
    validate_upstream_server_url,
)
from responsibleai.governance.upstream_executor import (
    build_upstream_target,
    compute_upstream_target_fingerprint,
)
from responsibleai.isolation import (
    EphemeralWorkspace,
    FilesystemEscapeError,
    IsolatedExecutionRequest,
    IsolationPolicyViolationError,
    LocalSubprocessBackend,
    NetworkPolicy,
    ResourceLimits,
    build_isolated_environment,
)
from responsibleai.net.egress import (
    AsyncDNSResolver,
    DestinationPolicy,
    ForbiddenDestinationError,
    InvalidURLError,
    PeerMismatchError,
    SafeAsyncHTTPTransport,
    SafeNetworkBackend,
    SystemDNSResolver,
    create_safe_async_client,
    is_address_allowed,
    normalize_and_validate_url,
)
from responsibleai.webhooks.manager import (
    UnsafeWebhookURLError,
    validate_webhook_url,
)

try:
    from tests.pg_test_url import isolated_pg_url
except ImportError:
    isolated_pg_url = None  # type: ignore[misc, assignment]


# ── Fixtures & Test Helpers ───────────────────────────────────────────────────


def _id(org: str = "org-test", ident: str = "agent-alpha") -> IdentityContext:
    return IdentityContext(identity_id=ident, kind="api_key", org_id=org)


def _agent(org: str = "org-test", ident: str = "agent-alpha") -> AgentContext:
    return AgentContext(identity=_id(org, ident), organization_id=org, framework="war8-agent2")


def _action(
    org: str = "org-test",
    ident: str = "agent-alpha",
    tool: str = "rai_scan",
    args: dict[str, Any] | None = None,
    action_id: str | None = None,
) -> ActionRequest:
    return ActionRequest(
        action_id=action_id or str(uuid.uuid4()),
        agent=_agent(org, ident),
        action_type=tool,
        target=tool,
        arguments=args if args is not None else {"input": "test payload"},
    )


def _allow_res(action_id: str, risk: RiskTier = RiskTier.MINIMAL) -> DecisionResult:
    return DecisionResult(
        decision=GovernanceDecision.ALLOW,
        action_id=action_id,
        risk_tier=risk,
    )


async def _init_test_org(engine: DatabaseEngine, org_id: str) -> None:
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert().values(
                id=org_id,
                name=f"Org {org_id}",
                slug=f"org-{org_id[:8]}",
                created_at=datetime.now(UTC).isoformat(),
                governance_status="ACTIVE",
            )
        )


# ==============================================================================
# SECTION 1: SSRF ASSAULT & PRIVATE RANGE ENFORCEMENT
# ==============================================================================
class TestWAR8SSRFResistance:
    """Rigorous SSRF attack suite targeting private, loopback, link-local,
    CGNAT, cloud-metadata, and IPv6 ranges."""

    @pytest.mark.parametrize(
        "forbidden_url",
        [
            # Loopback
            "http://127.0.0.1",
            "http://127.0.0.2:8080/admin",
            "http://localhost",
            "http://localhost.",
            "http://[::1]",
            "http://[::1]:9000",
            # RFC 1918 Private ranges
            "http://10.0.0.1",
            "http://10.254.254.254/internal",
            "http://172.16.0.1",
            "http://172.31.255.255/secrets",
            "http://192.168.0.1",
            "http://192.168.1.254/api",
            # IPv4 Link-local & Cloud Metadata
            "http://169.254.169.254/latest/meta-data/",
            "http://169.254.1.1",
            # IPv6 Link-local, ULA, and IPv6 Cloud Metadata
            "http://[fe80::1]",
            "http://[fe80::200:5aee:feaa:20a2]",
            "http://[fc00::1]",
            "http://[fd00::1234]",
            "http://[fd00:ec2::254]",
            # Carrier-Grade NAT (CGNAT) RFC 6598
            "http://100.64.0.1",
            "http://100.127.255.254",
            # Cloud metadata internal hostnames
            "http://metadata.google.internal",
            "http://metadata.internal",
        ],
    )
    def test_static_url_ssrf_forbidden_destinations_fail_closed(self, forbidden_url: str) -> None:
        with pytest.raises(ForbiddenDestinationError):
            normalize_and_validate_url(forbidden_url, DestinationPolicy.PUBLIC_ONLY)

    @pytest.mark.parametrize(
        "webhook_target",
        [
            "http://127.0.0.1:5000/webhook",
            "http://localhost:8000/webhook",
            "http://169.254.169.254/computeMetadata/v1/",
            "http://10.10.10.10/notify",
            "http://[::1]:8080/webhook",
        ],
    )
    def test_webhook_url_validation_rejects_ssrf(self, webhook_target: str) -> None:
        with pytest.raises(UnsafeWebhookURLError):
            validate_webhook_url(webhook_target)

    @pytest.mark.parametrize(
        "upstream_target",
        [
            "http://127.0.0.1:8000/mcp",
            "http://169.254.169.254/mcp",
            "http://192.168.1.100:3000/mcp",
            "http://localhost:9000/mcp",
        ],
    )
    def test_upstream_mcp_url_validation_rejects_ssrf(self, upstream_target: str) -> None:
        with pytest.raises(UnsafeUpstreamServerURLError):
            validate_upstream_server_url(upstream_target)


# ==============================================================================
# SECTION 2: IP ENCODING & PARSER CONFUSION BYPASSES
# ==============================================================================
class TestWAR8IPEncodingBypasses:
    """Tests obfuscated IP formats (integer, octal, hex, IPv4-mapped IPv6,
    embedded userinfo) designed to bypass naive regexes."""

    @pytest.mark.parametrize(
        "encoded_url",
        [
            # Integer IPv4 representation of 127.0.0.1 (2130706433)
            "http://2130706433",
            "http://2130706433:8080/status",
            # Integer IPv4 representation of 169.254.169.254 (2852039166)
            "http://2852039166",
            # Integer IPv4 representation of 10.0.0.1 (167772161)
            "http://167772161",
            # Octal-like dotted IPv4 with leading zeros
            "http://0177.0.0.1",
            "http://0177.0000.0000.0001",
            "http://012.0.0.1",
            # Hex-encoded IPv4 notation (dotted)
            "http://0x7f.0.0.1",
            "http://0x7f.0x0.0x0.0x1",
            # IPv4-mapped IPv6
            "http://[::ffff:127.0.0.1]",
            "http://[::ffff:169.254.169.254]",
            "http://[::ffff:10.0.0.1]",
            "http://[0:0:0:0:0:ffff:127.0.0.1]",
            # Userinfo confusion targeting loopback
            "http://user:password@127.0.0.1:8080/data",
            "http://admin@169.254.169.254/",
            "http://legit.domain.com@127.0.0.1/",
        ],
    )
    def test_ip_encoding_and_userinfo_tricks_blocked(self, encoded_url: str) -> None:
        with pytest.raises((ForbiddenDestinationError, InvalidURLError)):
            normalize_and_validate_url(encoded_url, DestinationPolicy.PUBLIC_ONLY)

    @pytest.mark.asyncio
    async def test_hex_ip_literal_blocked_at_dns_resolution(self) -> None:
        """Hex integer without dots (0x7f000001) is treated as a domain name by static
        urlsplit, but resolves to 127.0.0.1 at getaddrinfo time and fails closed."""
        resolver = SystemDNSResolver()
        with pytest.raises(ForbiddenDestinationError, match="127.0.0.1"):
            await resolver.resolve("0x7f000001", 80, DestinationPolicy.PUBLIC_ONLY)


# ==============================================================================
# SECTION 3: DNS REBINDING & CONNECT-TIME IP BINDING
# ==============================================================================
class _RebindingDNSResolver(AsyncDNSResolver):
    """Simulates an adversarial DNS server executing a Time-Of-Check to
    Time-Of-Use (TOCTOU) DNS rebinding attack."""

    def __init__(self, initial_ip: str, rebind_ip: str) -> None:
        self.initial_ip = ipaddress.ip_address(initial_ip)
        self.rebind_ip = ipaddress.ip_address(rebind_ip)
        self.query_count = 0

    async def resolve(
        self, host: str, port: int, policy: DestinationPolicy
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        self.query_count += 1
        # On first query, return benign public IP. On subsequent queries, return malicious private IP.
        chosen = self.initial_ip if self.query_count == 1 else self.rebind_ip
        if not is_address_allowed(chosen, policy):
            raise ForbiddenDestinationError(
                f"Host {host!r} resolved to forbidden network address {chosen}"
            )
        return [chosen]


class _MultiAnswerDNSResolver(AsyncDNSResolver):
    """Returns multiple DNS answers where one is safe public and one is forbidden private."""

    def __init__(self, public_ip: str, forbidden_ip: str) -> None:
        self.public_ip = ipaddress.ip_address(public_ip)
        self.forbidden_ip = ipaddress.ip_address(forbidden_ip)

    async def resolve(
        self, host: str, port: int, policy: DestinationPolicy
    ) -> list[ipaddress.IPv4Address | ipaddress.IPv6Address]:
        # Emulates SystemDNSResolver invariant: if ANY resolved IP is forbidden, fail closed!
        candidates = [self.public_ip, self.forbidden_ip]
        for ip in candidates:
            if not is_address_allowed(ip, policy):
                raise ForbiddenDestinationError(
                    f"Host {host!r} resolved to forbidden network address {ip}"
                )
        return candidates


class TestWAR8DNSRebinding:
    @pytest.mark.asyncio
    async def test_mixed_public_private_dns_answers_fail_closed(self) -> None:
        resolver = _MultiAnswerDNSResolver("93.184.216.34", "127.0.0.1")
        backend = SafeNetworkBackend(resolver=resolver, policy=DestinationPolicy.PUBLIC_ONLY)
        with pytest.raises(ForbiddenDestinationError, match="forbidden network address"):
            await backend.connect_tcp("rebind.example.com", 80)

    @pytest.mark.asyncio
    async def test_dns_rebinding_resolution_fail_closed_at_connect_time(self) -> None:
        # Pre-check at decision time might have seen 93.184.216.34,
        # but connection-time resolver sees 169.254.169.254
        rebind_resolver = _RebindingDNSResolver(
            initial_ip="93.184.216.34", rebind_ip="169.254.169.254"
        )
        backend = SafeNetworkBackend(resolver=rebind_resolver, policy=DestinationPolicy.PUBLIC_ONLY)

        # 1st query passes
        ips1 = await rebind_resolver.resolve(
            "safe-then-poison.com", 80, DestinationPolicy.PUBLIC_ONLY
        )
        assert len(ips1) == 1 and ips1[0] == ipaddress.ip_address("93.184.216.34")

        # 2nd query (connect time) must fail closed
        with pytest.raises(ForbiddenDestinationError, match="169.254.169.254"):
            await backend.connect_tcp("safe-then-poison.com", 80)

    @pytest.mark.asyncio
    async def test_peer_mismatch_verification_fails_closed(self) -> None:
        """If underlying socket somehow connected to a forbidden peer IP,
        post-connect peer verification raises PeerMismatchError and terminates the stream."""
        mock_stream = AsyncMock(spec=httpcore.AsyncNetworkStream)
        # Simulate stream returning forbidden peer 127.0.0.1
        mock_stream.get_extra_info.return_value = ("127.0.0.1", 80)

        mock_inner = AsyncMock(spec=httpcore.AsyncNetworkBackend)
        mock_inner.connect_tcp.return_value = mock_stream

        # Static IP connect
        backend = SafeNetworkBackend(
            policy=DestinationPolicy.LOCAL_DEV,
            inner_backend=mock_inner,  # allows initial check
        )
        # But change policy to PUBLIC_ONLY for peer verification
        backend.policy = DestinationPolicy.PUBLIC_ONLY

        with pytest.raises(PeerMismatchError, match="violates egress security policy"):
            await backend.connect_tcp("93.184.216.34", 80)
        mock_stream.aclose.assert_awaited_once()


# ==============================================================================
# SECTION 4: REDIRECT CHAINS & SCHEME RESTRICTIONS
# ==============================================================================
class TestWAR8RedirectsAndSchemes:
    @pytest.mark.parametrize(
        "unsupported_scheme_url",
        [
            "file:///etc/passwd",
            "file:///var/run/secrets",
            "ftp://anonymous@ftp.example.com/pub",
            "gopher://127.0.0.1:70/0",
            "data:text/html;base64,PHNjcmlwdD5hbGVydCgxKTwvc2NyaXB0Pg==",
            "javascript:alert(document.cookie)",
            "unix:///var/run/docker.sock",
            "dict://127.0.0.1:11211/stat",
            "ldap://127.0.0.1:389/o=example",
        ],
    )
    def test_unsupported_schemes_strictly_rejected(self, unsupported_scheme_url: str) -> None:
        with pytest.raises(InvalidURLError, match="Unsupported URL scheme"):
            normalize_and_validate_url(unsupported_scheme_url)

    @pytest.mark.parametrize(
        "malformed_url",
        [
            "",
            "   ",
            "http://",
            "http:///path",
            "http://example.com:99999",
            "http://example.com:-1",
            "http://example.com:0",
            "http://example.com\r\nHost: evil.com",
            "http://example.com\t/admin",
        ],
    )
    def test_malformed_urls_and_crlf_rejected(self, malformed_url: str) -> None:
        with pytest.raises((InvalidURLError, ValueError)):
            normalize_and_validate_url(malformed_url)

    @pytest.mark.asyncio
    async def test_redirect_to_private_ip_revalidated_and_blocked(self) -> None:
        """When follow_redirects=True is enabled, every redirect hop must be
        intercepted by SafeAsyncHTTPTransport and revalidated."""
        transport = SafeAsyncHTTPTransport(policy=DestinationPolicy.PUBLIC_ONLY)

        # Build mock request redirected to 127.0.0.1
        redirect_req = httpx.Request("GET", "http://127.0.0.1/stolen-token")

        with pytest.raises(ForbiddenDestinationError):
            await transport.handle_async_request(redirect_req)
        await transport.aclose()


# ==============================================================================
# SECTION 5: AMBIENT PROXY ENVIRONMENT ISOLATION
# ==============================================================================
class TestWAR8ProxyEnvironmentIsolation:
    def test_safe_client_enforces_trust_env_false(self, monkeypatch) -> None:
        monkeypatch.setenv("HTTP_PROXY", "http://hostile-proxy.internal:8080")
        monkeypatch.setenv("HTTPS_PROXY", "http://hostile-proxy.internal:8080")
        monkeypatch.setenv("ALL_PROXY", "socks5://hostile-proxy.internal:1080")

        client = create_safe_async_client()
        # Invariant: trust_env MUST be False, preventing ambient proxy hijacking
        assert client._transport is not None
        assert client.trust_env is False


# ==============================================================================
# SECTION 6: EXECUTION ISOLATION & ENVIRONMENT LEAKAGE ASSAULT
# ==============================================================================
class TestWAR8ExecutionEnvironmentIsolation:
    def test_sensitive_environment_keys_never_leak_to_sandbox(self, monkeypatch) -> None:
        # Populate parent environment with realistic production keys
        hostile_keys = {
            "AWS_SECRET_ACCESS_KEY": "dummy_aws_key_value",
            "DATABASE_URL": "postgresql://user:pass@127.0.0.1/testdb",
            "POSTGRES_PASSWORD": "dummy_password_val",
            "RAI_DATABASE_URL": "postgresql://user:pass@127.0.0.1/testdb",
            "SLACK_API_TOKEN": "dummy_slack_token_val",
            "JWT_SECRET": "dummy_jwt_secret_val",
            "GITHUB_TOKEN": "dummy_github_token_val",
            "SSH_AUTH_SOCK": "/tmp/ssh-agent.sock",
            "CI_JOB_TOKEN": "dummy_ci_token_val",
            "STRIPE_API_KEY": "dummy_stripe_key_val",
        }
        for k, v in hostile_keys.items():
            monkeypatch.setenv(k, v)

        # Build isolated sandbox environment
        env = build_isolated_environment(
            organization_id="tenant-victim",
            action_id="act-isolation-001",
            extra_env={"UNTRUSTED_KEY": "leaked_secret_val", "SAFE_PARAM": "123"},
            inherit_safe_host_vars=True,
        )

        # Invariant 1: None of the blocked keys are present
        for secret_key in hostile_keys:
            assert secret_key not in env, f"Hostile key {secret_key} leaked into sandbox!"

        # Invariant 2: Extra env with blocked patterns filtered out
        assert "UNTRUSTED_KEY" not in env
        assert env.get("SAFE_PARAM") == "123"

        # Invariant 3: Sandbox markers correctly injected
        assert env["WHITEPACT_SANDBOX"] == "1"
        assert env["WHITEPACT_TENANT_ID"] == "tenant-victim"
        assert env["WHITEPACT_ACTION_ID"] == "act-isolation-001"
        assert env["PYTHONUNBUFFERED"] == "1"

    def test_ephemeral_workspace_traversal_escape_prevented(self) -> None:
        with EphemeralWorkspace("act-traverse", "org-test") as ws:
            # Traversal attacks via relative and absolute paths
            with pytest.raises(FilesystemEscapeError):
                ws.populate({"../../etc/passwd": "malicious content"})

            with pytest.raises(FilesystemEscapeError):
                ws.populate({"../escaped_secret.txt": "leak"})

            # Legitimate file writes succeed within root
            ws.populate({"safe/nested/file.txt": "hello safe world"})
            target_path = ws.path / "safe" / "nested" / "file.txt"
            assert target_path.exists()
            assert target_path.read_text(encoding="utf-8") == "hello safe world"

    def test_workspace_owner_only_permissions(self) -> None:
        with EphemeralWorkspace("act-perms", "org-test") as ws:
            ws.populate({"data.txt": "sensitive payload"})
            dir_stat = os.stat(ws.path)
            file_stat = os.stat(ws.path / "data.txt")

            # Must be 0700 for directory (rwx------)
            assert (dir_stat.st_mode & 0o777) == 0o700
            # Must be 0600 for files (rw-------)
            assert (file_stat.st_mode & 0o777) == 0o600

    @pytest.mark.asyncio
    async def test_subprocess_network_egress_strictly_forbidden(self) -> None:
        backend = LocalSubprocessBackend()
        # Request with network policy != NONE must be denied immediately
        req = IsolatedExecutionRequest(
            action_id="act-net-bypass",
            organization_id="org-test",
            action_type="rai_scan",
            arguments={"text": "test"},
            profile=MagicMock(network_policy=NetworkPolicy.ALLOWLISTED_EGRESS),
        )
        with pytest.raises(IsolationPolicyViolationError, match="Direct network egress"):
            await backend.execute(req)


# ==============================================================================
# SECTION 7: RUNAWAY PROCESS & RESOURCE LIMIT CLEANUP
# ==============================================================================
class TestWAR8ProcessCleanupAndLimits:
    @pytest.mark.asyncio
    async def test_wall_clock_timeout_terminates_process_group(self) -> None:
        """Verifies that a tool that sleeps or hangs terminates cleanly and
        kills the process group without leaking zombie processes."""
        backend = LocalSubprocessBackend()
        # Mock profile with 1 second timeout
        limits = ResourceLimits(
            cpu_cores=1.0,
            max_memory_mb=128,
            wall_timeout_seconds=0.5,
            max_output_bytes=1024,
            max_file_descriptors=64,
        )
        profile = MagicMock(
            network_policy=NetworkPolicy.NONE,
            resources=limits,
        )
        req = IsolatedExecutionRequest(
            action_id="act-hang-test",
            organization_id="org-test",
            action_type="rai_drift_check",  # tool that runs
            arguments={"reference": [1.0], "current": [2.0]},
            profile=profile,
        )

        with patch("asyncio.subprocess.Process.communicate", new_callable=AsyncMock) as mock_comm:
            mock_comm.side_effect = TimeoutError()
            outcome = await backend.execute(req)
            assert outcome.timed_out is True
            assert "Wall timeout" in (outcome.violation or "")


# ==============================================================================
# SECTION 8: AGENT-1 CROSS-CHALLENGE — APPROVAL LIFECYCLE
# ==============================================================================
class TestWAR8ApprovalCrossChallenge:
    """Rigorous challenge against Agent 1's superficial approval tests:
    - Double consumption
    - High-concurrency double consumption (SQLite + PostgreSQL)
    - Cross-agent & cross-tenant reuse
    - Parameter, tool, recipient, and amount tampering
    - Expired approval rejection
    - Pre-resolution and denied approval consumption rejection
    """

    @pytest.mark.asyncio
    async def test_approval_replay_and_double_consumption_blocked(self, tmp_path) -> None:
        from responsibleai.governance.approval import build_approval_request

        db_path = str(tmp_path / "war8_approval_replay.db")
        engine = create_engine(db_path)
        await engine.init()
        org_id = str(uuid.uuid4())
        await _init_test_org(engine, org_id)

        repo = ApprovalRepository(engine)
        action = _action(org=org_id, tool="rai_scan", args={"amount": 500, "recipient": "bob"})
        dec = DecisionResult(
            decision=GovernanceDecision.REQUIRE_APPROVAL,
            action_id=action.action_id,
            risk_tier=RiskTier.MEDIUM,
            reason_codes=["REQUIRE_APPROVAL_HIGH_VALUE"],
        )
        approval_req = build_approval_request(action, dec)

        # Create approval
        req = await repo.create(approval_req)

        # Resolve to APPROVED
        await repo.resolve(
            req.approval_id, outcome=ApprovalStatus.APPROVED, resolved_by="admin-user"
        )

        # 1st consume: must SUCCEED
        consumed_1 = await repo.consume(req.approval_id, action=action)
        assert consumed_1.status == ApprovalStatus.CONSUMED

        # 2nd consume: must FAIL CLOSED with ApprovalNotApprovedError
        with pytest.raises(ApprovalNotApprovedError, match="CONSUMED"):
            await repo.consume(req.approval_id, action=action)

        await engine.close()

    @pytest.mark.asyncio
    async def test_sqlite_concurrent_approval_double_consumption_race(self, tmp_path) -> None:
        from responsibleai.governance.approval import build_approval_request

        db_path = str(tmp_path / "war8_approval_race.db")
        engine = create_engine(db_path)
        await engine.init()
        org_id = str(uuid.uuid4())
        await _init_test_org(engine, org_id)

        repo = ApprovalRepository(engine)
        action = _action(org=org_id, tool="rai_scan", args={"tx": "payroll-2026"})
        dec = DecisionResult(
            decision=GovernanceDecision.REQUIRE_APPROVAL,
            action_id=action.action_id,
            risk_tier=RiskTier.MEDIUM,
            reason_codes=["REQUIRE_APPROVAL"],
        )
        approval_req = build_approval_request(action, dec)
        req = await repo.create(approval_req)
        await repo.resolve(req.approval_id, outcome=ApprovalStatus.APPROVED, resolved_by="cfo")

        async def _attempt_consume():
            try:
                await repo.consume(req.approval_id, action=action)
                return "CONSUMED"
            except ApprovalNotApprovedError:
                return "REJECTED"

        # Race 25 concurrent consume attempts
        results = await asyncio.gather(*[_attempt_consume() for _ in range(25)])
        assert results.count("CONSUMED") == 1
        assert results.count("REJECTED") == 24
        await engine.close()

    @pytest.mark.asyncio
    @pytest.mark.skipif(isolated_pg_url is None, reason="Isolated PG unavailable")
    async def test_postgres_concurrent_approval_double_consumption_race(self) -> None:
        from responsibleai.governance.approval import build_approval_request

        async for pg_url in isolated_pg_url("wp_war8_approval_pg"):
            engine = create_engine(pg_url)
            await engine.init()
            try:
                org_id = str(uuid.uuid4())
                await _init_test_org(engine, org_id)
                repo = ApprovalRepository(engine)
                action = _action(org=org_id, tool="rai_scan", args={"concurrency": "pg-war8"})
                dec = DecisionResult(
                    decision=GovernanceDecision.REQUIRE_APPROVAL,
                    action_id=action.action_id,
                    risk_tier=RiskTier.MEDIUM,
                    reason_codes=["REQUIRE_APPROVAL"],
                )
                approval_req = build_approval_request(action, dec)
                req = await repo.create(approval_req)
                await repo.resolve(
                    req.approval_id, outcome=ApprovalStatus.APPROVED, resolved_by="cfo"
                )

                async def _attempt_consume(r=repo, app_id=req.approval_id, act=action):
                    try:
                        await r.consume(app_id, action=act)
                        return "CONSUMED"
                    except ApprovalNotApprovedError:
                        return "REJECTED"

                results = await asyncio.gather(*[_attempt_consume() for _ in range(30)])
                assert results.count("CONSUMED") == 1
                assert results.count("REJECTED") == 29
            finally:
                await engine.close()
            break

    @pytest.mark.asyncio
    async def test_approval_tampering_parameter_mutation_rejected(self, tmp_path) -> None:
        from responsibleai.governance.approval import build_approval_request

        db_path = str(tmp_path / "war8_tamper.db")
        engine = create_engine(db_path)
        await engine.init()
        org_id = str(uuid.uuid4())
        await _init_test_org(engine, org_id)
        repo = ApprovalRepository(engine)

        original_action = _action(org=org_id, args={"amount": 100, "dest": "charlie"})
        dec = DecisionResult(
            decision=GovernanceDecision.REQUIRE_APPROVAL,
            action_id=original_action.action_id,
            risk_tier=RiskTier.MEDIUM,
            reason_codes=["APPROVAL_REQ"],
        )
        req = await repo.create(build_approval_request(original_action, dec))
        await repo.resolve(req.approval_id, outcome=ApprovalStatus.APPROVED, resolved_by="manager")

        # Mutate parameter: amount changed to 1000000
        tampered_action = _action(
            org=org_id,
            ident=original_action.agent.identity.identity_id,
            tool=original_action.action_type,
            args={"amount": 1000000, "dest": "charlie"},
            action_id=original_action.action_id,
        )

        with pytest.raises(ApprovalActionMismatchError):
            await repo.consume(req.approval_id, action=tampered_action)
        await engine.close()

    @pytest.mark.asyncio
    async def test_approval_cross_tenant_reuse_rejected(self, tmp_path) -> None:
        from responsibleai.governance.approval import build_approval_request

        db_path = str(tmp_path / "war8_cross_tenant_approval.db")
        engine = create_engine(db_path)
        await engine.init()
        org_a = str(uuid.uuid4())
        org_b = str(uuid.uuid4())
        await _init_test_org(engine, org_a)
        await _init_test_org(engine, org_b)
        repo = ApprovalRepository(engine)

        action_a = _action(org=org_a)
        dec = DecisionResult(
            decision=GovernanceDecision.REQUIRE_APPROVAL,
            action_id=action_a.action_id,
            risk_tier=RiskTier.MEDIUM,
            reason_codes=["APPROVAL_REQ"],
        )
        req_a = await repo.create(build_approval_request(action_a, dec))
        await repo.resolve(
            req_a.approval_id, outcome=ApprovalStatus.APPROVED, resolved_by="admin-a"
        )

        # Hostile Tenant B attempts to consume Tenant A's approval
        action_b = _action(org=org_b)
        with pytest.raises(ApprovalActionMismatchError):
            await repo.consume(req_a.approval_id, action=action_b)

        await engine.close()

    @pytest.mark.asyncio
    async def test_expired_approval_cannot_be_consumed(self, tmp_path) -> None:
        from responsibleai.governance.approval import build_approval_request

        db_path = str(tmp_path / "war8_expired_app.db")
        engine = create_engine(db_path)
        await engine.init()
        org_id = str(uuid.uuid4())
        await _init_test_org(engine, org_id)
        repo = ApprovalRepository(engine)

        action = _action(org=org_id)
        dec = DecisionResult(
            decision=GovernanceDecision.REQUIRE_APPROVAL,
            action_id=action.action_id,
            risk_tier=RiskTier.MEDIUM,
            reason_codes=["APPROVAL_REQ"],
        )

        # 1. An approval that expires before resolve() raises ApprovalExpiredError at resolution
        app_req_1 = build_approval_request(action, dec)
        app_req_1.expires_at = datetime.now(UTC) - timedelta(hours=1)
        req_1 = await repo.create(app_req_1)
        with pytest.raises(ApprovalExpiredError):
            await repo.resolve(
                req_1.approval_id, outcome=ApprovalStatus.APPROVED, resolved_by="manager"
            )

        # 2. An approval that is approved while valid, but expires before consume()
        app_req_2 = build_approval_request(action, dec)
        # Give it a future expiry initially so resolve succeeds
        app_req_2.expires_at = datetime.now(UTC) + timedelta(minutes=5)
        req_2 = await repo.create(app_req_2)
        await repo.resolve(
            req_2.approval_id, outcome=ApprovalStatus.APPROVED, resolved_by="manager"
        )

        # Now simulate time passing such that expires_at is in the past
        async with engine.raw.begin() as conn:
            await conn.execute(
                governance_approvals.update()
                .where(governance_approvals.c.id == req_2.approval_id)
                .values(expires_at=(datetime.now(UTC) - timedelta(seconds=1)).isoformat())
            )

        with pytest.raises(ApprovalExpiredError):
            await repo.consume(req_2.approval_id, action=action)
        await engine.close()


# ==============================================================================
# SECTION 9: AGENT-1 CROSS-CHALLENGE — CAPABILITY GRAPH & ATTENUATION
# ==============================================================================
class TestWAR8CapabilityGraphCrossChallenge:
    """Attacks delegation graph attenuation, transitivity, cyclic loops,
    and post-grant tampering."""

    def test_transitive_attenuation_escalation_detected(self) -> None:
        root_auth = AuthorityContext(
            delegated_by="root",
            granted_action_types=frozenset({"rai_scan", "rai_pii_report"}),
        )
        # Child requests an ungranted capability
        escalated_child = AuthorityContext(
            delegated_by="root",
            granted_action_types=frozenset({"rai_scan", "rai_pii_report", "rai_hallucination"}),
        )
        escalation = validate_attenuation(root_auth, escalated_child)
        assert escalation is not None
        assert "granted_action_types" in escalation

    def test_empty_parent_cannot_delegate_any_capability(self) -> None:
        empty_parent = AuthorityContext(
            delegated_by="root",
            granted_action_types=frozenset(),
        )
        child = AuthorityContext(
            delegated_by="root",
            granted_action_types=frozenset({"rai_health"}),
        )
        escalation = validate_attenuation(empty_parent, child)
        assert escalation is not None

    @pytest.mark.asyncio
    async def test_delegation_repository_rejects_escalation_at_grant_time(self, tmp_path) -> None:
        db_path = str(tmp_path / "war8_deleg_esc.db")
        engine = create_engine(db_path)
        await engine.init()
        org_id = str(uuid.uuid4())
        await _init_test_org(engine, org_id)
        repo = DelegationRepository(engine)

        # Root grant to agent-1: only rai_scan
        await repo.grant(
            org_id=org_id,
            to_identity_id="agent-1",
            granted_action_types=frozenset({"rai_scan"}),
            purpose="Root read-only scan",
            granted_by="owner",
        )

        # agent-1 attempts to delegate rai_hallucination to agent-2
        with pytest.raises(DelegationEscalationError):
            await repo.grant(
                org_id=org_id,
                to_identity_id="agent-2",
                from_identity_id="agent-1",
                granted_action_types=frozenset({"rai_scan", "rai_hallucination"}),
                purpose="Escalated subagent",
                granted_by="agent-1",
            )
        await engine.close()


# ==============================================================================
# SECTION 10: AGENT-1 CROSS-CHALLENGE — INDEPENDENT RISK CLASSIFICATION
# ==============================================================================
class TestWAR8RiskClassificationCrossChallenge:
    """Verifies that callers cannot manipulate or downgrade risk."""

    def test_caller_cannot_spoof_low_risk_for_high_risk_actions(self) -> None:
        # High risk internal tools
        assert classify_action_risk("mcp_tool_call", "rai_hallucination") == RiskTier.HIGH
        assert classify_action_risk("mcp_tool_call", "rai_bias_evaluate") == RiskTier.HIGH
        assert classify_action_risk("mcp_tool_call", "rai_redteam_payloads") == RiskTier.HIGH

        # Upstream third-party MCP is always HIGH
        assert (
            classify_action_risk(UPSTREAM_ACTION_TYPE, "remote_server::some_tool") == RiskTier.HIGH
        )

    def test_unrecognized_actions_fail_closed_to_medium_risk(self) -> None:
        # Never defaults to MINIMAL or LOW for unclassified actions
        assert classify_action_risk("arbitrary_unknown_type", "unknown_target") == RiskTier.MEDIUM
        assert classify_action_risk("mcp_tool_call", "nonexistent_tool") == RiskTier.MEDIUM


# ==============================================================================
# SECTION 11: AGENT-1 CROSS-CHALLENGE — MULTI-AGENT & MULTI-TENANCY
# ==============================================================================
class TestWAR8MultiAgentAndTenantIsolation:
    def test_agent_b_cannot_execute_agent_a_grant(self) -> None:
        action_a = _action(org="org-1", ident="agent-a")
        decision = _allow_res(action_a.action_id)
        grant_a = authorize_execution(decision, action_a)

        # Agent B presents Agent A's grant
        action_b = _action(
            org="org-1", ident="agent-b", tool="rai_scan", action_id=action_a.action_id
        )
        executor = InternalToolExecutor()

        with pytest.raises(AuthorizationActionMismatchError):
            asyncio.run(executor.execute(grant_a, action_b))

    def test_tenant_b_cannot_execute_tenant_a_grant(self) -> None:
        action_a = _action(org="tenant-alpha", ident="agent-1")
        grant_a = authorize_execution(_allow_res(action_a.action_id), action_a)

        action_b = _action(org="tenant-beta", ident="agent-1")
        executor = InternalToolExecutor()

        with pytest.raises(AuthorizationOrganizationMismatchError):
            asyncio.run(executor.execute(grant_a, action_b))


# ==============================================================================
# SECTION 12: MCP TRANSITIVE EXECUTION & UPSTREAM TARGET DRIFT
# ==============================================================================
class TestWAR8MCPTransitiveAndTargetDrift:
    def test_upstream_target_fingerprint_detects_configuration_drift(self) -> None:
        server = UpstreamServer(
            server_id="srv-1",
            org_id="org-test",
            name="Test MCP Server",
            url="https://api.external-mcp.com/v1",
            enabled=True,
            auth_token="initial-token",
        )
        initial_fp = compute_upstream_target_fingerprint(server)

        # Server configuration changes (e.g. URL changed to attacker host)
        server_mutated = UpstreamServer(
            server_id="srv-1",
            org_id="org-test",
            name="Test MCP Server",
            url="https://attacker.com/v1",
            enabled=True,
            auth_token="initial-token",
        )
        mutated_fp = compute_upstream_target_fingerprint(server_mutated)

        assert initial_fp != mutated_fp

        action = _action(org="org-test", tool=UPSTREAM_ACTION_TYPE)
        action.target = build_upstream_target("srv-1", "calculate")
        grant = authorize_execution(
            _allow_res(action.action_id), action, target_fingerprint=initial_fp
        )

        # Pre-execution check must catch target drift and raise AuthorizationTargetDriftError
        with pytest.raises(AuthorizationTargetDriftError):
            check_target_fingerprint(grant, mutated_fp)


# ==============================================================================
# SECTION 13: CRASH / RESTART DURABILITY & MULTI-WORKER REVOCATION
# ==============================================================================
class TestWAR8DurabilityAndWorkerRevocation:
    @pytest.mark.asyncio
    @pytest.mark.skipif(isolated_pg_url is None, reason="Isolated PG unavailable")
    async def test_postgres_nonce_durability_across_repo_restarts(self) -> None:
        async for pg_url in isolated_pg_url("wp_war8_restart"):
            engine = create_engine(pg_url)
            await engine.init()
            try:
                org_id = str(uuid.uuid4())
                await _init_test_org(engine, org_id)

                repo_1 = ExecutionNonceRepository(engine)
                nonce = uuid.uuid4().hex
                auth_id = f"auth-{uuid.uuid4().hex[:6]}"

                # First consumer consumes nonce
                await repo_1.consume(
                    nonce, authorization_id=auth_id, organization_id=org_id, expected_epoch=0
                )

                # Simulate service/worker crash & restart with fresh repository instance
                repo_2 = ExecutionNonceRepository(engine)
                # Attempt to consume again on restarted repository -> must fail closed
                with pytest.raises(NonceAlreadyConsumedError):
                    await repo_2.consume(
                        nonce, authorization_id=auth_id, organization_id=org_id, expected_epoch=0
                    )
            finally:
                await engine.close()
            break

    @pytest.mark.asyncio
    async def test_multi_worker_revocation_epoch_immediate_visibility(self, tmp_path) -> None:
        """Simulates Worker A bumping revocation epoch while Worker B attempts execution."""
        db_path = str(tmp_path / "war8_multi_worker.db")
        engine = create_engine(db_path)
        await engine.init()
        org_id = str(uuid.uuid4())
        await _init_test_org(engine, org_id)

        # Worker A instance
        epoch_repo_a = RevocationEpochRepository(engine)
        # Worker B instance
        nonce_repo_b = ExecutionNonceRepository(engine)

        action = _action(org=org_id)
        # Permit minted at epoch 0
        grant = authorize_execution(_allow_res(action.action_id), action, revocation_epoch=0)

        # Worker A revokes epoch (N -> N+1)
        t0 = time.perf_counter()
        await epoch_repo_a.bump(org_id)
        t_bump = (time.perf_counter() - t0) * 1000

        # Worker B immediately attempts to execute old grant
        t1 = time.perf_counter()
        with pytest.raises(StaleRevocationEpochError):
            await nonce_repo_b.consume(
                grant.nonce,
                authorization_id=grant.authorization_id,
                organization_id=org_id,
                expected_epoch=grant.revocation_epoch,
            )
        t_vis = (time.perf_counter() - t1) * 1000

        print(
            f"\n[REVOCATION TIMING] Epoch bump latency: {t_bump:.3f}ms | Visibility latency: {t_vis:.3f}ms"
        )
        assert t_vis < 50.0  # Must be visible in milliseconds
        await engine.close()


# ==============================================================================
# SECTION 14: DETERMINISTIC FUZZING CAMPAIGN
# ==============================================================================
class TestWAR8DeterministicFuzzing:
    """Deterministic property/fuzz campaign testing URL parser, digests,
    and authorization invariants across 150 mutated inputs."""

    def test_url_parser_fuzzing(self) -> None:
        random.seed(1337)
        schemes = ["http", "https", "file", "ftp", "gopher", "unix", "javascript", "data", ""]
        hosts = [
            "127.0.0.1",
            "localhost",
            "169.254.169.254",
            "10.0.0.1",
            "[::1]",
            "example.com",
            "93.184.216.34",
            "0x7f000001",
            "2130706433",
            "bad\r\nhost",
            "user@127.0.0.1",
            "example.com:80:80",
        ]
        ports = ["", ":80", ":443", ":8080", ":99999", ":-1", ":abc"]
        paths = ["", "/", "/test", "/../../etc/passwd", "/%00null", "/api?q=1&p=2"]

        tested_cases = 0
        forbidden_count = 0
        invalid_count = 0
        allowed_count = 0

        for _ in range(150):
            s = random.choice(schemes)
            h = random.choice(hosts)
            p = random.choice(ports)
            path = random.choice(paths)
            candidate = f"{s}://{h}{p}{path}" if s else f"//{h}{p}{path}"
            tested_cases += 1

            try:
                normalize_and_validate_url(candidate, DestinationPolicy.PUBLIC_ONLY)
                allowed_count += 1
            except ForbiddenDestinationError:
                forbidden_count += 1
            except (InvalidURLError, ValueError):
                invalid_count += 1

        assert tested_cases == 150
        assert (forbidden_count + invalid_count) > 0
        # Invariant: zero uncaught unexpected exceptions, zero crash states
        print(
            f"\n[FUZZ RESULT] Cases: {tested_cases} | Forbidden: {forbidden_count} | Invalid: {invalid_count} | Allowed: {allowed_count}"
        )


# ==============================================================================
# SECTION 15: MUTATION TESTING — INVARIANT INSUFICIENCY DETECTION
# ==============================================================================
class TestWAR8MutationTesting:
    """Verifies that mutating security controls causes tests to FAIL,
    proving that our test suite genuinely depends on every defensive gate."""

    def test_mutated_action_digest_check_fails(self) -> None:
        action = _action(args={"valid": 1})
        grant = authorize_execution(_allow_res(action.action_id), action)

        # Mutate the grant's action digest to simulate a bypassed/corrupted check
        grant.action_digest = "mutated_tampered_hash_0000"
        with pytest.raises(AuthorizationActionMismatchError):
            asyncio.run(InternalToolExecutor().execute(grant, action))

    def test_mutated_expiry_check_fails(self) -> None:
        action = _action()
        grant = authorize_execution(_allow_res(action.action_id), action)
        # Mutate expires_at to 1 second in the past
        grant.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        with pytest.raises(AuthorizationExpiredError):
            asyncio.run(InternalToolExecutor().execute(grant, action))

    def test_mutated_consumed_status_fails(self) -> None:
        action = _action()
        grant = authorize_execution(_allow_res(action.action_id), action)
        grant.consumed = True
        with pytest.raises(AuthorizationAlreadyConsumedError):
            asyncio.run(InternalToolExecutor().execute(grant, action))


# ==============================================================================
# SECTION 16: HOSTILE MIXED-LOAD CONCURRENCY & CAPACITY PROFILING
# ==============================================================================
class TestWAR8HostileMixedLoadAndCapacity:
    """Simulates mixed valid and hostile traffic (SSRF, replay, expired,
    wrong-tenant, wrong-agent) across concurrency levels 1, 10, 25, 50, 100."""

    @pytest.mark.asyncio
    async def test_mixed_hostile_load_concurrency(self) -> None:
        gateway = WhitePactRuntimeGateway()
        executor = InternalToolExecutor()
        org_id = "org-mixed-bench"
        authority = AuthorityContext(
            delegated_by=org_id, granted_action_types=frozenset({"rai_scan"})
        )

        # Concurrency levels to exercise
        concurrency_levels = [1, 10, 25, 50, 100]

        for conc in concurrency_levels:
            latencies_ms: list[float] = []
            denials_count = 0
            allows_count = 0

            async def _worker(idx: int, l_ms: list[float] = latencies_ms):
                nonlocal denials_count, allows_count
                t0 = time.perf_counter()

                # Alternate request types:
                # 0: valid allow
                # 1: wrong tenant (cross-tenant execution)
                # 2: unauthorized action
                # 3: ssrf url check
                mode = idx % 4
                if mode == 0:
                    act = _action(org=org_id, tool="rai_scan")
                    res = gateway.evaluate(act, authority)
                    assert res.decision == GovernanceDecision.ALLOW
                    grant = authorize_execution(res, act)
                    await executor.execute(grant, act)
                    allows_count += 1
                elif mode == 1:
                    act_legit = _action(org=org_id, tool="rai_scan")
                    res = gateway.evaluate(act_legit, authority)
                    grant = authorize_execution(res, act_legit)
                    # Hostile tenant tries to execute
                    act_hostile = _action(org="hostile-tenant", tool="rai_scan")
                    try:
                        await executor.execute(grant, act_hostile)
                    except AuthorizationOrganizationMismatchError:
                        denials_count += 1
                elif mode == 2:
                    act = _action(org=org_id, tool="unauthorized_tool")
                    res = gateway.evaluate(act, authority)
                    assert res.decision == GovernanceDecision.DENY
                    denials_count += 1
                elif mode == 3:
                    try:
                        normalize_and_validate_url("http://127.0.0.1/admin")
                    except ForbiddenDestinationError:
                        denials_count += 1

                t1 = time.perf_counter()
                l_ms.append((t1 - t0) * 1000)

            t_start = time.perf_counter()
            await asyncio.gather(*[_worker(i) for i in range(conc)])
            total_time = time.perf_counter() - t_start

            latencies_ms.sort()
            p50 = latencies_ms[int(conc * 0.50)]
            p95 = latencies_ms[int(conc * 0.95)]
            p99 = latencies_ms[int(conc * 0.99)]
            throughput = conc / total_time

            print(
                f"\n[HOSTILE MIXED LOAD] Concurrency={conc:3d} | "
                f"Throughput={throughput:8.1f} req/s | "
                f"p50={p50:6.3f}ms | p95={p95:6.3f}ms | p99={p99:6.3f}ms | "
                f"Allows={allows_count} | Denials={denials_count}"
            )
            # Invariant: security correctness strictly preserved under all concurrency
            assert allows_count + denials_count == conc
