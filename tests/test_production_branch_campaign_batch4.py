# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch-coverage campaign batch 4: backup defense, container backend, web identity deny paths, MCP OAuth, egress."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import secrets
import socket
import subprocess
import uuid
from base64 import urlsafe_b64encode
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy import update

from responsibleai.auth.mcp_oauth import McpOAuthAuthorizationServer, OAuthProtocolError
from responsibleai.data_governance.backup_defense import (
    InMemoryLifecycleStateProvider,
    LifecycleIntegrityError,
    LifecycleRollbackError,
    LifecycleState,
    LifecycleStateRecord,
    MissingLifecycleProviderError,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    RestoreReconciliationEngine,
    RestoreReconciliationError,
    SqliteDurableLifecycleStateProvider,
    StoreBUnavailableError,
    compute_lifecycle_digest,
    is_production_environment,
    is_restore_pending_default,
    resolve_store_b_path,
)
from responsibleai.db.engine import create_engine, oauth_credentials, organizations, web_users
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.web_identity_repository import (
    InvitationError,
    SoleOwnerError,
    WebIdentityRepository,
)
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import (
    IsolationBackendUnavailableError,
    IsolationPolicyViolationError,
)
from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    NetworkPolicy,
)
from responsibleai.net.egress import (
    ForbiddenDestinationError,
    InvalidURLError,
    PeerMismatchError,
    SafeNetworkBackend,
    SystemDNSResolver,
    is_address_allowed,
    normalize_and_validate_url,
    validate_outbound_url,
)
from responsibleai.rbac.models import Plan, Role

ISSUER = "https://issuer.example"
RESOURCE = f"{ISSUER}/mcp"
REDIRECT = "https://chatgpt.com/connector_platform_oauth_redirect"
REVIEW_SCOPE = "whitepact:review"


def _pkce() -> tuple[str, str]:
    verifier = secrets.token_urlsafe(48)
    digest = hashlib.sha256(verifier.encode()).digest()
    challenge = urlsafe_b64encode(digest).decode().rstrip("=")
    return verifier, challenge


def _lifecycle_record(
    tenant_id: str = "org-1",
    state: LifecycleState = LifecycleState.ACTIVE,
    *,
    epoch: int = 1,
    effective_at: str = "2026-01-01T00:00:00+00:00",
) -> LifecycleStateRecord:
    digest = compute_lifecycle_digest(
        tenant_id=tenant_id,
        generation_id="gen-1",
        state=state.value,
        effective_at=effective_at,
        security_epoch=epoch,
    )
    return LifecycleStateRecord(
        tenant_id=tenant_id,
        generation_id="gen-1",
        state=state,
        effective_at=effective_at,
        security_epoch=epoch,
        digest=digest,
    )


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


@pytest.fixture
async def web_repo(engine):
    return WebIdentityRepository(engine)


@pytest.fixture
async def oauth_server(engine):
    return McpOAuthAuthorizationServer(
        engine,
        OrgRepository(engine),
        issuer=ISSUER,
        resource=RESOURCE,
        scopes=[REVIEW_SCOPE, "offline_access"],
    )


async def _verified_user(web: WebIdentityRepository, email: str) -> str:
    user_id, token = await web.register("Human", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


# ── backup_defense ───────────────────────────────────────────────────────────


def test_compute_lifecycle_digest_hmac_vs_plain() -> None:
    plain = compute_lifecycle_digest("t", "g", "ACTIVE", "2026-01-01T00:00:00+00:00")
    keyed = compute_lifecycle_digest(
        "t", "g", "ACTIVE", "2026-01-01T00:00:00+00:00", secret_key="sekrit"
    )
    assert plain != keyed
    assert len(plain) == 64


def test_resolve_store_b_path_rejects_empty_and_forbidden_name(tmp_path: Path) -> None:
    with pytest.raises(MissingLifecycleProviderError, match="no shared /tmp fallback"):
        resolve_store_b_path(None)
    with pytest.raises(MissingLifecycleProviderError, match="well-known"):
        resolve_store_b_path(tmp_path / "whitepact_store_b_lifecycle.db")


def test_resolve_store_b_path_resolves_relative(tmp_path: Path) -> None:
    rel = tmp_path / "nested" / "store.db"
    resolved = resolve_store_b_path(rel)
    assert resolved.is_absolute()
    assert resolved.name == "store.db"


@pytest.mark.parametrize(
    "env_key,env_val",
    [
        ("WHITEPACT_ENV", "production"),
        ("RAI_ENV", "prod"),
        ("ENVIRONMENT", "PRODUCTION"),
        ("ENV", "prod"),
    ],
)
def test_is_production_environment_true(
    env_key: str, env_val: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    for key in ("WHITEPACT_ENV", "RAI_ENV", "ENVIRONMENT", "ENV"):
        monkeypatch.delenv(key, raising=False)
    monkeypatch.setenv(env_key, env_val)
    assert is_production_environment() is True


def test_in_memory_provider_rejects_rollback_and_tamper() -> None:
    provider = InMemoryLifecycleStateProvider()
    provider.record_state(_lifecycle_record(state=LifecycleState.DELETION_IN_PROGRESS))
    with pytest.raises(LifecycleRollbackError, match="rollback rejected"):
        provider.record_state(_lifecycle_record(state=LifecycleState.ACTIVE))
    bad = _lifecycle_record()
    bad = LifecycleStateRecord(
        tenant_id=bad.tenant_id,
        generation_id=bad.generation_id,
        state=bad.state,
        effective_at=bad.effective_at,
        security_epoch=bad.security_epoch,
        digest="deadbeef",
    )
    with pytest.raises(LifecycleIntegrityError, match="Tampered"):
        provider.record_state(bad)


def test_in_memory_provider_unavailable_fail_closed() -> None:
    provider = InMemoryLifecycleStateProvider()
    provider.set_available(False)
    with pytest.raises(StoreBUnavailableError):
        provider.get_state("x")
    with pytest.raises(StoreBUnavailableError):
        provider.list_tombstones()


def test_restore_readiness_gate_blocks_traffic_until_ready() -> None:
    gate = RestoreReadinessGate(initial_state=RestoreReadinessState.RESTORE_PENDING)
    assert gate.is_admitted() is False
    with pytest.raises(RestoreQuarantineError, match="RESTORE_PENDING"):
        gate.assert_traffic_admitted()
    gate.set_state(RestoreReadinessState.READY)
    gate.assert_traffic_admitted()


def test_restore_gate_fails_closed_when_provider_read_fails() -> None:
    provider = InMemoryLifecycleStateProvider()
    gate = RestoreReadinessGate(provider=provider)
    provider.set_available(False)
    assert gate.state == RestoreReadinessState.FAILED


def test_sqlite_provider_epoch_rollback_rejected(tmp_path: Path) -> None:
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "lifecycle.db")
    provider.record_state(_lifecycle_record(epoch=2))
    with pytest.raises(LifecycleRollbackError, match="Security epoch rollback"):
        provider.record_state(_lifecycle_record(epoch=1))


def test_sqlite_provider_verify_integrity_detects_corruption(tmp_path: Path) -> None:
    provider = SqliteDurableLifecycleStateProvider(tmp_path / "lifecycle.db")
    provider.record_state(_lifecycle_record())
    provider.set_corrupted(True)
    assert provider.verify_integrity() is False


@pytest.mark.asyncio
async def test_restore_engine_strict_production_requires_durable_store(engine) -> None:
    gate = RestoreReadinessGate()
    with patch.dict(os.environ, {"WHITEPACT_ENV": "production"}, clear=False):
        os.environ.pop("WHITEPACT_STORE_B_PATH", None)
        os.environ.pop("WHITEPACT_LIFECYCLE_STORE_PATH", None)
        with pytest.raises(MissingLifecycleProviderError, match="Durable Store-B"):
            RestoreReconciliationEngine(engine, gate=gate, require_durable=True)


@pytest.mark.asyncio
async def test_restore_reconcile_fails_closed_on_provider_integrity(engine) -> None:
    provider = InMemoryLifecycleStateProvider()
    provider.set_corrupted(True)
    reconciler = RestoreReconciliationEngine(engine, lifecycle_provider=provider)
    with pytest.raises(RestoreReconciliationError, match="integrity check failed"):
        await reconciler.reconcile_post_restore("auditor")
    assert reconciler.gate.state == RestoreReadinessState.FAILED


def test_is_restore_pending_default_env_flags() -> None:
    with patch.dict(os.environ, {"WHITEPACT_RESTORE_MODE": "1"}, clear=False):
        assert is_restore_pending_default() is True
    with patch.dict(os.environ, {}, clear=True):
        assert is_restore_pending_default() is False


# ── container_backend ────────────────────────────────────────────────────────


def test_docker_is_available_false_for_missing_which(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("responsibleai.isolation.container_backend.shutil.which", lambda _c: None)
    assert DockerContainerBackend(docker_cmd="docker").is_available() is False


def test_docker_is_available_false_for_non_executable_path(tmp_path: Path) -> None:
    fake = tmp_path / "not-docker"
    fake.write_text("#!/bin/sh\n", encoding="utf-8")
    backend = DockerContainerBackend(docker_cmd=str(fake))
    assert backend.is_available() is False


def test_docker_is_available_false_on_nonzero_return(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv, **kwargs):
        return subprocess.CompletedProcess(argv, 1)

    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.shutil.which", lambda _c: "/usr/bin/docker"
    )
    monkeypatch.setattr("responsibleai.isolation.container_backend.subprocess.run", fake_run)
    assert DockerContainerBackend().is_available() is False


def test_docker_is_available_false_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(argv, **kwargs):
        raise subprocess.TimeoutExpired(argv, kwargs.get("timeout", 1))

    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.shutil.which", lambda _c: "/usr/bin/docker"
    )
    monkeypatch.setattr("responsibleai.isolation.container_backend.subprocess.run", fake_run)
    assert DockerContainerBackend().is_available() is False


@pytest.mark.asyncio
async def test_container_execute_fails_closed_when_unavailable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(DockerContainerBackend, "is_available", lambda self: False)
    backend = DockerContainerBackend()
    req = IsolatedExecutionRequest(
        action_id="act-1",
        organization_id="org-1",
        action_type="noop",
        arguments={},
    )
    with pytest.raises(IsolationBackendUnavailableError, match="Failing closed"):
        await backend.execute(req)


@pytest.mark.asyncio
async def test_container_execute_rejects_non_none_network_policy() -> None:
    backend = DockerContainerBackend()
    profile = IsolationProfile(network_policy=NetworkPolicy.ALLOWLISTED_EGRESS)
    req = IsolatedExecutionRequest(
        action_id="act-net",
        organization_id="org-1",
        action_type="noop",
        arguments={},
        profile=profile,
    )
    with patch.object(backend, "is_available", return_value=True):
        with pytest.raises(IsolationPolicyViolationError, match="Direct network egress"):
            await backend.execute(req)


def test_remove_containers_tolerates_inspect_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")

    def boom(*_a, **_k):
        raise OSError("inspect failed")

    monkeypatch.setattr("responsibleai.isolation.container_backend.subprocess.run", boom)
    backend._remove_containers(["wp_iso_missing"], stable_seconds=0, wait_seconds=0.1)


# ── web_identity_repository deny paths ───────────────────────────────────────


@pytest.mark.asyncio
async def test_get_principal_denies_revoked_disabled_and_bad_membership(web_repo, engine) -> None:
    user_id = await _verified_user(web_repo, "principal@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="Org", slug=f"o-{uuid.uuid4().hex[:6]}"
    )
    token, _ = await web_repo.create_session(user_id, org_id=org_id)
    await web_repo.revoke_session(token)
    assert await web_repo.get_principal(token) is None

    token2, _ = await web_repo.create_session(user_id, org_id=org_id)
    async with engine.raw.begin() as conn:
        await conn.execute(update(web_users).where(web_users.c.id == user_id).values(disabled=1))
    assert await web_repo.get_principal(token2) is None

    other = await _verified_user(web_repo, "other@example.com")
    token3, _ = await web_repo.create_session(other, org_id=org_id)
    assert await web_repo.get_principal(token3) is None


@pytest.mark.asyncio
async def test_get_principal_denies_suspended_org(web_repo, engine) -> None:
    user_id = await _verified_user(web_repo, "suspended@example.com")
    org_id = await web_repo.attach_organization(
        user_id, name="Suspended Org", slug=f"sus-{uuid.uuid4().hex[:6]}"
    )
    token, _ = await web_repo.create_session(user_id, org_id=org_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(organizations)
            .where(organizations.c.id == org_id)
            .values(governance_status="SUSPENDED")
        )
    assert await web_repo.get_principal(token) is None


@pytest.mark.asyncio
async def test_create_invitation_rejects_owner_role(web_repo) -> None:
    owner = await _verified_user(web_repo, "owner@example.com")
    org_id = await web_repo.attach_organization(owner, name="O", slug=f"own-{uuid.uuid4().hex[:6]}")
    with pytest.raises(InvitationError, match="Cannot invite a direct owner"):
        await web_repo.create_invitation(
            org_id=org_id,
            email="new@example.com",
            role=Role.OWNER,
            invited_by_user_id=owner,
        )


@pytest.mark.asyncio
async def test_accept_invitation_denies_wrong_account(web_repo) -> None:
    owner = await _verified_user(web_repo, "inviter@example.com")
    org_id = await web_repo.attach_organization(owner, name="O", slug=f"inv-{uuid.uuid4().hex[:6]}")
    _, invite_token = await web_repo.create_invitation(
        org_id=org_id,
        email="guest@example.com",
        role=Role.VIEWER,
        invited_by_user_id=owner,
    )
    wrong_user = await _verified_user(web_repo, "wrong@example.com")
    with pytest.raises(InvitationError, match="invalid, expired, or belongs to another"):
        await web_repo.accept_invitation(invite_token, wrong_user)


@pytest.mark.asyncio
async def test_update_membership_role_rejects_owner_promotion(web_repo) -> None:
    owner = await _verified_user(web_repo, "promo@example.com")
    org_id = await web_repo.attach_organization(owner, name="O", slug=f"pr-{uuid.uuid4().hex[:6]}")
    member = await _verified_user(web_repo, "member@example.com")
    _, tok = await web_repo.create_invitation(
        org_id=org_id,
        email="member@example.com",
        role=Role.VIEWER,
        invited_by_user_id=owner,
    )
    await web_repo.accept_invitation(tok, member)
    with pytest.raises(InvitationError, match="Ownership transfer requires"):
        await web_repo.update_membership_role(org_id, member, Role.OWNER)


@pytest.mark.asyncio
async def test_disable_account_denies_sole_owner(web_repo) -> None:
    owner = await _verified_user(web_repo, "sole@example.com")
    await web_repo.attach_organization(owner, name="Sole", slug=f"sole-{uuid.uuid4().hex[:6]}")
    with pytest.raises(SoleOwnerError, match="sole owner"):
        await web_repo.disable_account(owner)


@pytest.mark.asyncio
async def test_link_provider_identity_denies_unverified_and_cross_tenant(web_repo, engine) -> None:
    user_id = await _verified_user(web_repo, "link@example.com")
    with pytest.raises(ValueError, match="unverified email"):
        await web_repo.link_provider_identity(
            user_id=user_id,
            issuer="https://idp",
            subject="subj",
            email="link@example.com",
            email_verified=False,
        )
    with pytest.raises(ValueError, match="issuer and subject"):
        await web_repo.link_provider_identity(
            user_id=user_id, issuer="", subject="", email="link@example.com"
        )
    await web_repo.attach_organization(user_id, name="T", slug=f"t-{uuid.uuid4().hex[:6]}")
    other_org = str(uuid.uuid4())
    with pytest.raises(ValueError, match="not a member"):
        await web_repo.link_provider_identity(
            user_id=user_id,
            issuer="https://idp",
            subject="subj-2",
            email="link@example.com",
            tenant_id=other_org,
        )


@pytest.mark.asyncio
async def test_switch_organization_denies_without_active_membership(web_repo) -> None:
    user_id = await _verified_user(web_repo, "switch@example.com")
    token, _ = await web_repo.create_session(user_id)
    assert await web_repo.switch_organization(token, user_id, str(uuid.uuid4())) is None


# ── mcp_oauth fail-closed ────────────────────────────────────────────────────


def test_mcp_oauth_constructor_requires_https_and_review_scope(engine) -> None:
    org_repo = OrgRepository(engine)
    with pytest.raises(ValueError, match="HTTPS"):
        McpOAuthAuthorizationServer(
            engine,
            org_repo,
            issuer="http://insecure.example",
            resource=RESOURCE,
            scopes=[REVIEW_SCOPE],
        )
    with pytest.raises(ValueError, match="whitepact:review"):
        McpOAuthAuthorizationServer(
            engine,
            org_repo,
            issuer=ISSUER,
            resource=RESOURCE,
            scopes=["offline_access"],
        )


@pytest.mark.asyncio
async def test_register_client_denies_bad_metadata(oauth_server) -> None:
    with pytest.raises(OAuthProtocolError) as exc:
        await oauth_server.register_client({"redirect_uris": []})
    assert exc.value.error == "invalid_redirect_uri"

    with pytest.raises(OAuthProtocolError) as bad_uri:
        await oauth_server.register_client({"redirect_uris": ["https://evil.example/cb"]})
    assert bad_uri.value.error == "invalid_redirect_uri"

    with pytest.raises(OAuthProtocolError) as secret:
        await oauth_server.register_client(
            {
                "redirect_uris": [REDIRECT],
                "token_endpoint_auth_method": "client_secret_basic",
            }
        )
    assert secret.value.error == "invalid_client_metadata"


@pytest.mark.asyncio
async def test_begin_authorization_denies_pkce_and_resource(oauth_server) -> None:
    reg = await oauth_server.register_client({"redirect_uris": [REDIRECT]})
    client_id = reg["client_id"]
    _, challenge = _pkce()

    with pytest.raises(OAuthProtocolError) as rt:
        await oauth_server.begin_authorization(
            {
                "response_type": "token",
                "client_id": client_id,
                "redirect_uri": REDIRECT,
                "state": "s",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": RESOURCE,
            }
        )
    assert rt.value.error == "unsupported_response_type"

    with pytest.raises(OAuthProtocolError) as pkce:
        await oauth_server.begin_authorization(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": REDIRECT,
                "state": "s",
                "code_challenge": "short",
                "code_challenge_method": "S256",
                "resource": RESOURCE,
            }
        )
    assert pkce.value.error == "invalid_request"

    with pytest.raises(OAuthProtocolError) as res:
        await oauth_server.begin_authorization(
            {
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": REDIRECT,
                "state": "s",
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "resource": "https://wrong.example/mcp",
            }
        )
    assert res.value.error == "invalid_target"


@pytest.mark.asyncio
async def test_complete_authorization_denies_bad_credential(oauth_server, engine) -> None:
    reg = await oauth_server.register_client({"redirect_uris": [REDIRECT]})
    client_id = reg["client_id"]
    _, challenge = _pkce()
    request_id, _ = await oauth_server.begin_authorization(
        {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": REDIRECT,
            "state": "state-1",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": REVIEW_SCOPE,
            "resource": RESOURCE,
        }
    )
    with pytest.raises(OAuthProtocolError) as denied:
        await oauth_server.complete_authorization(request_id, "not-a-real-key", "allow")
    assert denied.value.status_code == 401
    assert denied.value.error == "access_denied"


@pytest.mark.asyncio
async def test_exchange_code_denies_client_secret(oauth_server) -> None:
    with pytest.raises(OAuthProtocolError) as exc:
        await oauth_server.exchange_authorization_code(
            {
                "client_secret": "leaked",
                "resource": RESOURCE,
                "client_id": "x",
                "code": "y",
                "redirect_uri": REDIRECT,
            }
        )
    assert exc.value.error == "invalid_client"
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_refresh_denies_wrong_resource(oauth_server) -> None:
    with pytest.raises(OAuthProtocolError) as exc:
        await oauth_server.refresh(
            {
                "client_id": "wp_client_x",
                "refresh_token": "wp_rt_fake",
                "resource": "https://other.example/mcp",
            }
        )
    assert exc.value.error == "invalid_target"


@pytest.mark.asyncio
async def test_resolve_access_token_denies_invalid_and_insufficient_scope(
    oauth_server, engine
) -> None:
    org_repo = OrgRepository(engine)
    org = await org_repo.create_org(
        "Reviewer Org", f"rev-{uuid.uuid4().hex[:6]}", plan=Plan.ENTERPRISE
    )
    _, raw_key = await org_repo.create_key(org.id, "viewer", role=Role.VIEWER)
    reg = await oauth_server.register_client({"redirect_uris": [REDIRECT]})
    verifier, challenge = _pkce()
    request_id, _ = await oauth_server.begin_authorization(
        {
            "response_type": "code",
            "client_id": reg["client_id"],
            "redirect_uri": REDIRECT,
            "state": "st",
            "code_challenge": challenge,
            "code_challenge_method": "S256",
            "scope": REVIEW_SCOPE,
            "resource": RESOURCE,
        }
    )
    redirect = await oauth_server.complete_authorization(request_id, raw_key, "allow")
    from urllib.parse import parse_qs, urlparse

    code = parse_qs(urlparse(redirect).query)["code"][0]
    tokens = await oauth_server.exchange_authorization_code(
        {
            "grant_type": "authorization_code",
            "client_id": reg["client_id"],
            "code": code,
            "redirect_uri": REDIRECT,
            "code_verifier": verifier,
            "resource": RESOURCE,
        }
    )
    access = str(tokens["access_token"])
    async with engine.raw.begin() as conn:
        from responsibleai.auth.mcp_oauth import _digest

        await conn.execute(
            update(oauth_credentials)
            .where(oauth_credentials.c.token_hash == _digest(access))
            .values(scopes=json.dumps(["offline_access"]))
        )
    with pytest.raises(OAuthProtocolError) as scope_exc:
        await oauth_server.resolve_access_token(access)
    assert scope_exc.value.error == "insufficient_scope"
    assert scope_exc.value.status_code == 403

    with pytest.raises(OAuthProtocolError) as bad:
        await oauth_server.resolve_access_token("wp_at_totally_invalid")
    assert bad.value.error == "invalid_token"


# ── net/egress invalid URLs ──────────────────────────────────────────────────


@pytest.mark.parametrize(
    "url",
    [
        "javascript:alert(1)",
        "gopher://example.com/",
        "http:///no-host",
        "https://example.com:0/path",
        "http://100.64.0.1/internal",
        "http://[fd00:ec2::254]/meta",
    ],
)
def test_validate_outbound_url_rejects_batch4_cases(url: str) -> None:
    with pytest.raises((InvalidURLError, ForbiddenDestinationError)):
        validate_outbound_url(url)


def test_is_address_allowed_rejects_garbage_and_cgnat() -> None:
    assert is_address_allowed("not-an-ip") is False
    assert is_address_allowed("100.64.1.1") is False
    assert is_address_allowed("::ffff:127.0.0.1") is False


def test_normalize_and_validate_url_rejects_none_like() -> None:
    with pytest.raises(InvalidURLError):
        normalize_and_validate_url("   ")


@pytest.mark.asyncio
async def test_safe_backend_unix_socket_forbidden() -> None:
    backend = SafeNetworkBackend()
    with pytest.raises(ForbiddenDestinationError, match="Unix domain sockets"):
        await backend.connect_unix_socket("/var/run/docker.sock")


@pytest.mark.asyncio
async def test_safe_backend_rejects_forbidden_hostname() -> None:
    backend = SafeNetworkBackend()
    with pytest.raises(ForbiddenDestinationError, match="forbidden internal hostname"):
        await backend.connect_tcp("localhost", 443)


@pytest.mark.asyncio
async def test_system_dns_resolver_fail_closed_on_private_answer(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    class _FakeLoop:
        async def getaddrinfo(self, host, port, *args, **kwargs):
            return [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("10.0.0.5", port or 80))]

    monkeypatch.setattr(asyncio, "get_running_loop", lambda: _FakeLoop())
    resolver = SystemDNSResolver()
    with pytest.raises(ForbiddenDestinationError, match="forbidden network address"):
        await resolver.resolve("internal.example", 443)


@pytest.mark.asyncio
async def test_safe_backend_peer_mismatch_closes_stream() -> None:
    stream = MagicMock()
    stream.get_extra_info.return_value = ("127.0.0.1", 443)
    stream.aclose = AsyncMock()
    inner = AsyncMock()
    inner.connect_tcp = AsyncMock(return_value=stream)
    backend = SafeNetworkBackend(inner_backend=inner)
    with pytest.raises(PeerMismatchError, match="violates egress"):
        await backend.connect_tcp("93.184.216.34", 443)
    stream.aclose.assert_awaited()
