# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch-coverage campaign batch 5: trust proofs, enterprise OIDC, MCP deny paths,
dashboard lifespan startup branches."""

from __future__ import annotations

import base64
import os
import time
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import jwt
import pytest
from asgi_lifespan import LifespanManager
from cryptography.hazmat.primitives.asymmetric import rsa
from httpx import ASGITransport, AsyncClient
from sqlalchemy import update

os.environ.setdefault("RAI_AUTH_ENABLED", "false")
os.environ.setdefault("RAI_LOG_JSON", "false")
os.environ.setdefault("RAI_LOG_LEVEL", "WARNING")
os.environ.setdefault("RAI_ALLOW_ALL_ORIGINS", "true")
os.environ.setdefault("RAI_AUTO_MIGRATE", "false")

from responsibleai.dashboard.app import app, settings
from responsibleai.db.engine import (
    create_engine,
    organizations,
    trust_fabric_conflicts,
    trust_fabric_identifiers,
    trust_fabric_principals,
)
from responsibleai.db.migrate import MigrationError
from responsibleai.enterprise.errors import PROVIDER_TOKEN_INVALID, EnterpriseError
from responsibleai.enterprise.security.oidc import (
    ALLOWED_ALGS,
    OIDCTokenValidator,
    TrustedJWKS,
    assert_https_issuer,
    fetch_discovery,
    issuer_host,
)
from responsibleai.trust_fabric.authority_graph import AuthorityGraph
from responsibleai.trust_fabric.directory import PrincipalDirectory
from responsibleai.trust_fabric.enums import (
    ConflictStatus,
    ConflictType,
    IdentifierType,
    IdentifierVerificationState,
    PrincipalState,
    PrincipalType,
    ProofStatus,
    RelationshipType,
    SourceTier,
)
from responsibleai.trust_fabric.proofs import TrustProofEngine
from responsibleai.trust_fabric.provenance import TrustProvenanceEngine

# ── Shared fixtures ──────────────────────────────────────────────────────────


@pytest.fixture
async def proof_db(tmp_path):
    url = f"sqlite+aiosqlite:///{tmp_path}/batch5_proof.db"
    engine = create_engine(url)
    await engine.init()
    async with engine.raw.begin() as conn:
        await conn.execute(
            organizations.insert(),
            [{"id": "org_corp", "name": "Global Corp", "slug": "gcorp", "created_at": "now"}],
        )
    try:
        yield engine
    finally:
        await engine.close()


@pytest.fixture()
async def dashboard_client():
    orig_database_url = settings.database_url
    orig_db_path = settings.db_path
    orig_auto_migrate = settings.auto_migrate
    orig_environment = settings.environment

    settings.database_url = None
    settings.db_path = ":memory:"
    settings.auto_migrate = False
    settings.environment = "development"
    try:
        async with LifespanManager(app, startup_timeout=15) as manager:
            async with AsyncClient(
                transport=ASGITransport(app=manager.app), base_url="http://test"
            ) as ac:
                yield ac
    finally:
        settings.database_url = orig_database_url
        settings.db_path = orig_db_path
        settings.auto_migrate = orig_auto_migrate
        settings.environment = orig_environment


@pytest.fixture()
async def mcp_http_app(monkeypatch: pytest.MonkeyPatch):
    import responsibleai.dashboard.config as config_module
    import responsibleai.db as db_module
    from responsibleai.mcp.server import _build_http_app

    engine = create_engine(":memory:")
    await engine.init()
    monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
    monkeypatch.setenv("RAI_MCP_HTTP_AUTH_MAX_FAILURES", "100")

    issuer = "https://testserver"
    resource = f"{issuer}/mcp"
    from responsibleai.dashboard.config import Settings

    oauth_settings = Settings(
        mcp_oauth_issuer=issuer,
        mcp_oauth_resource_uri=resource,
        mcp_oauth_scopes=["whitepact:review", "offline_access"],
    )
    monkeypatch.setattr(config_module, "get_settings", lambda: oauth_settings)

    built = _build_http_app()
    manager = LifespanManager(built)
    await manager.__aenter__()
    try:
        yield manager.app, engine, issuer, resource
    finally:
        await manager.__aexit__(None, None, None)
        await engine.close()


def _rsa_jwk(kid: str = "kid-batch5") -> tuple[rsa.RSAPrivateKey, dict]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    pub = key.public_key().public_numbers()

    def b64int(n: int) -> str:
        raw = n.to_bytes((n.bit_length() + 7) // 8, "big")
        return base64.urlsafe_b64encode(raw).rstrip(b"=").decode()

    jwk = {"kty": "RSA", "kid": kid, "n": b64int(pub.n), "e": b64int(pub.e)}
    return key, jwk


def _signed_id_token(
    key: rsa.RSAPrivateKey,
    *,
    iss: str,
    aud: str,
    sub: str = "sub-1",
    nonce: str | None = None,
    extra: dict | None = None,
) -> str:
    now = int(time.time())
    payload = {
        "iss": iss,
        "sub": sub,
        "aud": aud,
        "exp": now + 3600,
        "iat": now,
        "nonce": nonce,
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, key, algorithm="RS256", headers={"kid": "kid-batch5"})


async def _seed_source(proof_db, org_id: str = "org_corp"):
    prov = TrustProvenanceEngine(proof_db)
    return await prov.register_source(
        name="HR", source_tier=SourceTier.TIER_C, provider_type="IDP", org_id=org_id
    )


async def _set_lifecycle(proof_db, principal_id: str, state: PrincipalState) -> None:
    async with proof_db.raw.begin() as conn:
        await conn.execute(
            update(trust_fabric_principals)
            .where(trust_fabric_principals.c.id == principal_id)
            .values(lifecycle_state=state.value)
        )


async def _insert_domain_identifier(
    proof_db,
    *,
    org_id: str,
    principal_id: str,
    domain: str,
    verification_state: IdentifierVerificationState,
    revoked_at: str | None = None,
) -> None:
    norm = domain.lower()
    now = datetime.now(UTC).isoformat()
    async with proof_db.raw.begin() as conn:
        await conn.execute(
            trust_fabric_identifiers.insert().values(
                id=f"id_dom_{uuid.uuid4().hex[:8]}",
                org_id=org_id,
                principal_id=principal_id,
                identifier_type=IdentifierType.DOMAIN.value,
                raw_value=domain,
                normalized_value=norm,
                is_primary=1,
                verification_state=verification_state.value,
                verified_at=now,
                expires_at=None,
                revoked_at=revoked_at,
                source_id="src_dom",
                created_at=now,
            )
        )


# ── enterprise/security/oidc.py ──────────────────────────────────────────────


class TestOidcHelpers:
    def test_issuer_host_parses_https_url(self) -> None:
        assert issuer_host("https://login.example.com/path") == "login.example.com"

    def test_issuer_host_adds_https_when_missing_scheme(self) -> None:
        assert issuer_host("accounts.google.com") == "accounts.google.com"

    def test_assert_https_issuer_rejects_http(self) -> None:
        with pytest.raises(EnterpriseError) as exc:
            assert_https_issuer("http://login.example.com")
        assert exc.value.code == PROVIDER_TOKEN_INVALID

    def test_assert_https_issuer_rejects_missing_host(self) -> None:
        with pytest.raises(EnterpriseError):
            assert_https_issuer("https://")

    def test_trusted_jwks_rejects_mismatched_jwks_host(self) -> None:
        with pytest.raises(EnterpriseError) as exc:
            TrustedJWKS(
                "https://evil.example/jwks.json",
                issuer="https://login.example.com",
            )
        assert "JWKS host" in exc.value.message

    def test_trusted_jwks_allows_google_secondary_jwks_host(self) -> None:
        jwks = TrustedJWKS(
            "https://www.googleapis.com/oauth2/v3/certs",
            issuer="https://accounts.google.com",
        )
        assert jwks._url.endswith("/certs")

    def test_trusted_jwks_by_kid_selects_matching_key(self) -> None:
        jwks = TrustedJWKS(
            "https://login.example.com/jwks.json",
            issuer="https://login.example.com",
        )
        jwks._keys = [{"kid": "a"}, {"kid": "b"}]
        assert jwks._by_kid("b") == {"kid": "b"}

    def test_trusted_jwks_by_kid_unknown_returns_none(self) -> None:
        jwks = TrustedJWKS(
            "https://login.example.com/jwks.json",
            issuer="https://login.example.com",
        )
        jwks._keys = [{"kid": "a"}]
        assert jwks._by_kid("missing") is None

    def test_trusted_jwks_without_kid_single_key(self) -> None:
        jwks = TrustedJWKS(
            "https://login.example.com/jwks.json",
            issuer="https://login.example.com",
        )
        jwks._keys = [{"kid": "only"}]
        assert jwks._by_kid(None) == {"kid": "only"}

    def test_trusted_jwks_without_kid_ambiguous_returns_none(self) -> None:
        jwks = TrustedJWKS(
            "https://login.example.com/jwks.json",
            issuer="https://login.example.com",
        )
        jwks._keys = [{"kid": "a"}, {"kid": "b"}]
        assert jwks._by_kid(None) is None


class TestOidcTokenValidatorDeny:
    @pytest.mark.asyncio
    async def test_rejects_disallowed_algorithm(self) -> None:
        validator = OIDCTokenValidator(
            issuer="https://issuer.example",
            audience="client",
            jwks_url="https://issuer.example/jwks.json",
        )
        token = jwt.encode({"sub": "x"}, "secret", algorithm="HS256", headers={"alg": "HS256"})
        with pytest.raises(EnterpriseError) as exc:
            await validator.validate(token)
        assert exc.value.code == PROVIDER_TOKEN_INVALID
        assert "algorithm" in exc.value.message.lower()

    @pytest.mark.asyncio
    async def test_rejects_malformed_jwt(self) -> None:
        validator = OIDCTokenValidator(
            issuer="https://issuer.example",
            audience="client",
            jwks_url="https://issuer.example/jwks.json",
        )
        with pytest.raises(EnterpriseError) as exc:
            await validator.validate("not-a-jwt")
        assert "Malformed" in exc.value.message

    @pytest.mark.asyncio
    async def test_unknown_kid_after_refresh_denied(self) -> None:
        key, jwk = _rsa_jwk()
        validator = OIDCTokenValidator(
            issuer="https://issuer.example",
            audience="client",
            jwks_url="https://issuer.example/jwks.json",
        )
        token = _signed_id_token(key, iss="https://issuer.example", aud="client", nonce="n1")

        async def _empty_get(self, kid, allow_refresh=True):
            return None

        with patch.object(TrustedJWKS, "get", new=_empty_get):
            with pytest.raises(EnterpriseError) as exc:
                await validator.validate(token, expected_nonce="n1")
        assert "kid" in exc.value.message.lower()

    @pytest.mark.asyncio
    async def test_nonce_mismatch_denied(self) -> None:
        key, jwk = _rsa_jwk()

        async def _get(self, kid, allow_refresh=True):
            return jwk

        validator = OIDCTokenValidator(
            issuer="https://issuer.example",
            audience="client",
            jwks_url="https://issuer.example/jwks.json",
        )
        token = _signed_id_token(key, iss="https://issuer.example", aud="client", nonce="expected")
        with patch.object(TrustedJWKS, "get", new=_get):
            with pytest.raises(EnterpriseError) as exc:
                await validator.validate(token, expected_nonce="wrong")
        assert "nonce" in exc.value.message.lower()

    @pytest.mark.asyncio
    async def test_tenant_mismatch_denied(self) -> None:
        key, jwk = _rsa_jwk()

        async def _get(self, kid, allow_refresh=True):
            return jwk

        validator = OIDCTokenValidator(
            issuer="https://issuer.example",
            audience="client",
            jwks_url="https://issuer.example/jwks.json",
        )
        token = _signed_id_token(
            key,
            iss="https://issuer.example",
            aud="client",
            extra={"tid": "tenant-a"},
        )
        with patch.object(TrustedJWKS, "get", new=_get):
            with pytest.raises(EnterpriseError) as exc:
                await validator.validate(token, expected_tenant="tenant-b")
        assert "tenant" in exc.value.message.lower()

    @pytest.mark.parametrize("alg", ["none", "None", "HS384"])
    def test_allowed_algs_excludes_dangerous_values(self, alg: str) -> None:
        assert alg not in ALLOWED_ALGS


class TestOidcJwksRefreshDeny:
    @pytest.mark.asyncio
    async def test_refresh_rejects_oversized_document(self) -> None:
        jwks = TrustedJWKS(
            "https://issuer.example/jwks.json",
            issuer="https://issuer.example",
        )
        response = MagicMock()
        response.content = b"x" * 300_000
        response.raise_for_status = MagicMock()

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "responsibleai.enterprise.security.oidc.create_safe_async_client",
            return_value=mock_client,
        ):
            with pytest.raises(EnterpriseError) as exc:
                await jwks.refresh()
        assert "size" in exc.value.message.lower()

    @pytest.mark.asyncio
    async def test_refresh_rejects_malformed_json(self) -> None:
        jwks = TrustedJWKS(
            "https://issuer.example/jwks.json",
            issuer="https://issuer.example",
        )
        response = MagicMock()
        response.content = b'{"not":"keys"}'
        response.raise_for_status = MagicMock()
        response.json = MagicMock(return_value={"not": "keys"})

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "responsibleai.enterprise.security.oidc.create_safe_async_client",
            return_value=mock_client,
        ):
            with pytest.raises(EnterpriseError) as exc:
                await jwks.refresh()
        assert "malformed" in exc.value.message.lower()


class TestFetchDiscoveryDeny:
    @pytest.mark.asyncio
    async def test_discovery_issuer_mismatch_denied(self) -> None:
        issuer = "https://issuer.example"
        response = MagicMock()
        response.content = (
            b'{"issuer":"https://other.example","jwks_uri":"https://issuer.example/jwks"}'
        )
        response.raise_for_status = MagicMock()
        response.json = MagicMock(
            return_value={
                "issuer": "https://other.example",
                "jwks_uri": "https://issuer.example/jwks.json",
            }
        )

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "responsibleai.enterprise.security.oidc.create_safe_async_client",
            return_value=mock_client,
        ):
            with pytest.raises(EnterpriseError) as exc:
                await fetch_discovery(issuer)
        assert "issuer" in exc.value.message.lower()

    @pytest.mark.asyncio
    async def test_discovery_jwks_host_mismatch_denied(self) -> None:
        issuer = "https://issuer.example"
        response = MagicMock()
        response.content = b"{}"
        response.raise_for_status = MagicMock()
        response.json = MagicMock(
            return_value={
                "issuer": issuer,
                "jwks_uri": "https://evil.example/jwks.json",
            }
        )

        mock_client = MagicMock()
        mock_client.get = AsyncMock(return_value=response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch(
            "responsibleai.enterprise.security.oidc.create_safe_async_client",
            return_value=mock_client,
        ):
            with pytest.raises(EnterpriseError) as exc:
                await fetch_discovery(issuer)
        assert "JWKS" in exc.value.message


# ── trust_fabric/proofs.py ───────────────────────────────────────────────────


class TestProveEmploymentBranches:
    @pytest.mark.asyncio
    async def test_unknown_when_principal_missing(self, proof_db) -> None:
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_employment(principal_id="missing", org_id="org_corp")
            == ProofStatus.UNKNOWN
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "state",
        [PrincipalState.DISABLED, PrincipalState.DELETED],
    )
    async def test_inactive_principal_not_proven(self, proof_db, state: PrincipalState) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        person = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Inactive"
        )
        await _set_lifecycle(proof_db, person.id, state)
        engine = TrustProofEngine(proof_db)
        assert await engine.prove_employment(principal_id=person.id, org_id="org_corp") == (
            ProofStatus.NOT_PROVEN
        )

    @pytest.mark.asyncio
    async def test_revoked_lifecycle_returns_revoked(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        person = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Revoked"
        )
        await _set_lifecycle(proof_db, person.id, PrincipalState.REVOKED)
        engine = TrustProofEngine(proof_db)
        assert await engine.prove_employment(principal_id=person.id, org_id="org_corp") == (
            ProofStatus.REVOKED
        )

    @pytest.mark.asyncio
    async def test_conflicted_lifecycle_returns_conflicted(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        person = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Conflict"
        )
        await _set_lifecycle(proof_db, person.id, PrincipalState.CONFLICTED)
        engine = TrustProofEngine(proof_db)
        assert await engine.prove_employment(principal_id=person.id, org_id="org_corp") == (
            ProofStatus.CONFLICTED
        )

    @pytest.mark.asyncio
    async def test_unverified_relationship_not_proven(self, proof_db) -> None:
        src = await _seed_source(proof_db)
        dir_svc = PrincipalDirectory(proof_db)
        auth = AuthorityGraph(proof_db)
        person = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Bob"
        )
        company = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.ORGANIZATION,
            display_name="Corp Entity",
        )
        await auth.create_relationship(
            subject_principal_id=person.id,
            target_principal_id=company.id,
            org_id="org_corp",
            relationship_type=RelationshipType.EMPLOYED_BY,
            source_id=src.id,
            verification_state=IdentifierVerificationState.UNVERIFIED,
        )
        engine = TrustProofEngine(proof_db)
        assert await engine.prove_employment(principal_id=person.id, org_id="org_corp") == (
            ProofStatus.NOT_PROVEN
        )

    @pytest.mark.asyncio
    async def test_director_relationship_can_prove(self, proof_db) -> None:
        src = await _seed_source(proof_db)
        dir_svc = PrincipalDirectory(proof_db)
        auth = AuthorityGraph(proof_db)
        person = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Director"
        )
        company = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.ORGANIZATION,
            display_name="Board Co",
        )
        await auth.create_relationship(
            subject_principal_id=person.id,
            target_principal_id=company.id,
            org_id="org_corp",
            relationship_type=RelationshipType.DIRECTOR_OF,
            source_id=src.id,
            verification_state=IdentifierVerificationState.VERIFIED,
        )
        engine = TrustProofEngine(proof_db)
        assert await engine.prove_employment(principal_id=person.id, org_id="org_corp") == (
            ProofStatus.PROVEN
        )

    @pytest.mark.asyncio
    async def test_expired_relationship_returns_expired(self, proof_db) -> None:
        src = await _seed_source(proof_db)
        dir_svc = PrincipalDirectory(proof_db)
        auth = AuthorityGraph(proof_db)
        person = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Expired"
        )
        company = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.ORGANIZATION,
            display_name="Employer",
        )
        await auth.create_relationship(
            subject_principal_id=person.id,
            target_principal_id=company.id,
            org_id="org_corp",
            relationship_type=RelationshipType.EMPLOYED_BY,
            source_id=src.id,
            verification_state=IdentifierVerificationState.VERIFIED,
            expires_at="2000-01-01T00:00:00+00:00",
        )
        engine = TrustProofEngine(proof_db)
        assert await engine.prove_employment(principal_id=person.id, org_id="org_corp") == (
            ProofStatus.EXPIRED
        )


class TestProveSigningAuthorityBranches:
    @pytest.mark.asyncio
    async def test_no_edges_not_proven(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        grantee = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Signer"
        )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_signing_authority(principal_id=grantee.id, org_id="org_corp")
            == ProofStatus.NOT_PROVEN
        )

    @pytest.mark.asyncio
    async def test_unresolved_conflict_conflicted(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        grantee = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Signer"
        )
        now = datetime.now(UTC).isoformat()
        async with proof_db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_conflicts.insert().values(
                    id="conf_sign_1",
                    principal_id=grantee.id,
                    org_id="org_corp",
                    field_or_claim="signing",
                    assertion_id_a="a1",
                    assertion_id_b="a2",
                    conflict_type=ConflictType.VALUE_CONTRADICTION.value,
                    detected_at=now,
                    status=ConflictStatus.UNRESOLVED.value,
                    resolution_reason=None,
                    resolved_at=None,
                )
            )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_signing_authority(principal_id=grantee.id, org_id="org_corp")
            == ProofStatus.CONFLICTED
        )

    @pytest.mark.asyncio
    async def test_revoked_edge_returns_revoked(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        auth = AuthorityGraph(proof_db)
        grantor = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="CEO"
        )
        grantee = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Agent"
        )
        edge = await auth.grant_authority(
            grantor_principal_id=grantor.id,
            grantee_principal_id=grantee.id,
            org_id="org_corp",
            action_type="contract.sign",
        )
        await auth.revoke_authority(edge.id, org_id="org_corp", revoked_by_principal_id=grantor.id)
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_signing_authority(principal_id=grantee.id, org_id="org_corp")
            == ProofStatus.REVOKED
        )

    @pytest.mark.asyncio
    async def test_expired_edge_returns_expired(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        auth = AuthorityGraph(proof_db)
        grantor = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="CEO"
        )
        grantee = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Agent"
        )
        await auth.grant_authority(
            grantor_principal_id=grantor.id,
            grantee_principal_id=grantee.id,
            org_id="org_corp",
            action_type="payment.disburse",
            expires_at="2000-01-01T00:00:00+00:00",
        )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_signing_authority(principal_id=grantee.id, org_id="org_corp")
            == ProofStatus.EXPIRED
        )

    @pytest.mark.asyncio
    async def test_without_amount_ignores_ceiling(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        auth = AuthorityGraph(proof_db)
        grantor = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="CEO"
        )
        grantee = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="CFO"
        )
        await auth.grant_authority(
            grantor_principal_id=grantor.id,
            grantee_principal_id=grantee.id,
            org_id="org_corp",
            action_type="authority.sign",
            ceiling_limit_usd=100.0,
        )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_signing_authority(
                principal_id=grantee.id, org_id="org_corp", amount_usd=None
            )
            == ProofStatus.PROVEN
        )


class TestProveAgentOwnershipBranches:
    @pytest.mark.asyncio
    async def test_human_principal_not_proven(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        human = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Human"
        )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_agent_ownership(agent_principal_id=human.id, org_id="org_corp")
            == ProofStatus.NOT_PROVEN
        )

    @pytest.mark.asyncio
    async def test_suspended_agent_without_owned_by_not_proven(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        agent = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.AI_AGENT,
            display_name="Suspended Bot",
            lifecycle_state=PrincipalState.SUSPENDED,
        )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_agent_ownership(agent_principal_id=agent.id, org_id="org_corp")
            == ProofStatus.NOT_PROVEN
        )

    @pytest.mark.asyncio
    async def test_pending_active_agent_without_relationship_proven(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        agent = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.AI_AGENT,
            display_name="Pending Active Bot",
            lifecycle_state=PrincipalState.PENDING_VERIFICATION,
        )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_agent_ownership(agent_principal_id=agent.id, org_id="org_corp")
            == ProofStatus.PROVEN
        )

    @pytest.mark.asyncio
    async def test_owned_by_relationship_proven(self, proof_db) -> None:
        src = await _seed_source(proof_db)
        dir_svc = PrincipalDirectory(proof_db)
        auth = AuthorityGraph(proof_db)
        owner = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.ORGANIZATION,
            display_name="Owner Org",
        )
        agent = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.AI_AGENT,
            display_name="Owned Bot",
            lifecycle_state=PrincipalState.ACTIVE,
        )
        await auth.create_relationship(
            subject_principal_id=agent.id,
            target_principal_id=owner.id,
            org_id="org_corp",
            relationship_type=RelationshipType.OWNED_BY,
            source_id=src.id,
            verification_state=IdentifierVerificationState.VERIFIED,
        )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_agent_ownership(agent_principal_id=agent.id, org_id="org_corp")
            == ProofStatus.PROVEN
        )


class TestProveDomainAndCredentialBranches:
    @pytest.mark.asyncio
    async def test_domain_unknown_when_missing(self, proof_db) -> None:
        engine = TrustProofEngine(proof_db)
        assert await engine.prove_domain_control(org_id="org_corp", domain="example.com") == (
            ProofStatus.UNKNOWN
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        ("verification", "expected"),
        [
            (IdentifierVerificationState.VERIFIED, ProofStatus.PROVEN),
            (IdentifierVerificationState.EXPIRED, ProofStatus.EXPIRED),
            (IdentifierVerificationState.REVOKED, ProofStatus.REVOKED),
            (IdentifierVerificationState.UNVERIFIED, ProofStatus.NOT_PROVEN),
        ],
    )
    async def test_domain_verification_states(
        self, proof_db, verification: IdentifierVerificationState, expected: ProofStatus
    ) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        org_principal = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.ORGANIZATION,
            display_name="Corp Domain Holder",
        )
        await _insert_domain_identifier(
            proof_db,
            org_id="org_corp",
            principal_id=org_principal.id,
            domain="corp.example",
            verification_state=verification,
        )
        engine = TrustProofEngine(proof_db)
        assert await engine.prove_domain_control(org_id="org_corp", domain="corp.example") == (
            expected
        )

    @pytest.mark.asyncio
    async def test_credential_revoked_and_expired(self, proof_db) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        person = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Cred User"
        )
        now = datetime.now(UTC)
        async with proof_db.raw.begin() as conn:
            await conn.execute(
                trust_fabric_identifiers.insert().values(
                    id="id_cred_rev",
                    org_id="org_corp",
                    principal_id=person.id,
                    identifier_type=IdentifierType.EMAIL.value,
                    raw_value="user@corp.example",
                    normalized_value="user@corp.example",
                    is_primary=1,
                    verification_state=IdentifierVerificationState.VERIFIED.value,
                    verified_at=now.isoformat(),
                    expires_at=None,
                    revoked_at=now.isoformat(),
                    source_id="src_cred",
                    created_at=now.isoformat(),
                )
            )
            await conn.execute(
                trust_fabric_identifiers.insert().values(
                    id="id_cred_exp",
                    org_id="org_corp",
                    principal_id=person.id,
                    identifier_type=IdentifierType.EMAIL.value,
                    raw_value="expired@corp.example",
                    normalized_value="expired@corp.example",
                    is_primary=0,
                    verification_state=IdentifierVerificationState.VERIFIED.value,
                    verified_at=now.isoformat(),
                    expires_at=(now - timedelta(days=1)).isoformat(),
                    revoked_at=None,
                    source_id="src_cred",
                    created_at=now.isoformat(),
                )
            )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.prove_credential(
                principal_id=person.id,
                org_id="org_corp",
                identifier_type=IdentifierType.EMAIL,
                value="user@corp.example",
            )
            == ProofStatus.REVOKED
        )
        assert (
            await engine.prove_credential(
                principal_id=person.id,
                org_id="org_corp",
                identifier_type=IdentifierType.EMAIL,
                value="expired@corp.example",
            )
            == ProofStatus.EXPIRED
        )


class TestEvaluatePrivilegedLegitimacy:
    @pytest.mark.asyncio
    async def test_unknown_principal(self, proof_db) -> None:
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.evaluate_privileged_legitimacy(principal_id="ghost", org_id="org_corp")
            == ProofStatus.UNKNOWN
        )

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "ptype",
        [PrincipalType.WORKLOAD, PrincipalType.SERVICE, PrincipalType.MACHINE],
    )
    async def test_non_human_types_require_review(self, proof_db, ptype: PrincipalType) -> None:
        dir_svc = PrincipalDirectory(proof_db)
        principal = await dir_svc.create_principal(
            org_id="org_corp", principal_type=ptype, display_name="Workload"
        )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.evaluate_privileged_legitimacy(
                principal_id=principal.id, org_id="org_corp"
            )
            == ProofStatus.REQUIRES_REVIEW
        )

    @pytest.mark.asyncio
    async def test_human_routes_to_employment(self, proof_db) -> None:
        src = await _seed_source(proof_db)
        dir_svc = PrincipalDirectory(proof_db)
        auth = AuthorityGraph(proof_db)
        person = await dir_svc.create_principal(
            org_id="org_corp", principal_type=PrincipalType.HUMAN, display_name="Employee"
        )
        company = await dir_svc.create_principal(
            org_id="org_corp",
            principal_type=PrincipalType.ORGANIZATION,
            display_name="Employer",
        )
        await auth.create_relationship(
            subject_principal_id=person.id,
            target_principal_id=company.id,
            org_id="org_corp",
            relationship_type=RelationshipType.EMPLOYED_BY,
            source_id=src.id,
            verification_state=IdentifierVerificationState.VERIFIED,
        )
        engine = TrustProofEngine(proof_db)
        assert (
            await engine.evaluate_privileged_legitimacy(principal_id=person.id, org_id="org_corp")
            == ProofStatus.PROVEN
        )


# ── mcp/server.py deny paths ─────────────────────────────────────────────────


class TestMcpServerDenyPaths:
    @pytest.mark.asyncio
    async def test_oauth_register_invalid_json_is_400(self, mcp_http_app) -> None:
        app_http, *_ = mcp_http_app
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_http), base_url="https://testserver"
        ) as client:
            response = await client.post("/oauth/register", content=b"{not-json")
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_client_metadata"

    @pytest.mark.asyncio
    async def test_oauth_token_unsupported_grant_denied(self, mcp_http_app) -> None:
        app_http, *_ = mcp_http_app
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_http), base_url="https://testserver"
        ) as client:
            response = await client.post(
                "/oauth/token",
                data={"grant_type": "client_credentials", "resource": "https://testserver/mcp"},
            )
        assert response.status_code == 400
        assert response.json()["error"] == "unsupported_grant_type"

    @pytest.mark.asyncio
    async def test_oauth_authorize_deny_action_redirects_access_denied(self, mcp_http_app) -> None:
        import hashlib
        import secrets
        from base64 import urlsafe_b64encode

        app_http, _engine, issuer, resource = mcp_http_app
        redirect = "https://chatgpt.com/connector_platform_oauth_redirect"
        verifier = secrets.token_urlsafe(48)
        challenge = (
            urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        )
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_http),
            base_url=issuer,
            follow_redirects=False,
        ) as client:
            reg = await client.post(
                "/oauth/register",
                json={
                    "client_name": "Deny Client",
                    "redirect_uris": [redirect],
                    "grant_types": ["authorization_code", "refresh_token"],
                    "response_types": ["code"],
                    "token_endpoint_auth_method": "none",
                },
            )
            assert reg.status_code == 201, reg.text
            client_id = reg.json()["client_id"]
            start = await client.get(
                "/oauth/authorize",
                params={
                    "response_type": "code",
                    "client_id": client_id,
                    "redirect_uri": redirect,
                    "scope": "whitepact:review",
                    "state": "st-deny",
                    "code_challenge": challenge,
                    "code_challenge_method": "S256",
                    "resource": resource,
                },
            )
            assert start.status_code == 200, start.text
            request_id = start.headers["x-whitepact-oauth-request-id"]
            finish = await client.post(
                "/oauth/authorize",
                data={"request_id": request_id, "api_key": "ignored", "action": "deny"},
            )
        assert finish.status_code == 303
        assert "error=access_denied" in finish.headers["location"]
        assert "state=st-deny" in finish.headers["location"]

    @pytest.mark.asyncio
    async def test_mcp_missing_bearer_is_401(self, mcp_http_app) -> None:
        app_http, *_ = mcp_http_app
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_http), base_url="https://testserver"
        ) as client:
            response = await client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "ping"})
        assert response.status_code == 401
        assert response.json()["error"] == "unauthorized"

    @pytest.mark.asyncio
    async def test_oauth_revoke_invalid_body_is_400(self, mcp_http_app) -> None:
        app_http, *_ = mcp_http_app
        async with httpx.AsyncClient(
            transport=httpx.ASGITransport(app=app_http), base_url="https://testserver"
        ) as client:
            response = await client.post(
                "/oauth/revoke",
                content=b"\xff\xfe",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
        assert response.status_code == 400
        assert response.json()["error"] == "invalid_request"

    @pytest.mark.asyncio
    async def test_oauth_endpoints_404_when_disabled(self, monkeypatch: pytest.MonkeyPatch) -> None:
        import responsibleai.db as db_module
        from responsibleai.mcp.server import _build_http_app

        engine = create_engine(":memory:")
        await engine.init()
        monkeypatch.setattr(db_module, "create_engine", lambda _url: engine)
        monkeypatch.delenv("RAI_MCP_OAUTH_ISSUER", raising=False)
        from responsibleai.dashboard.config import Settings

        monkeypatch.setattr(
            "responsibleai.dashboard.config.get_settings",
            lambda: Settings(mcp_oauth_issuer=""),
        )
        bare = _build_http_app()
        manager = LifespanManager(bare)
        await manager.__aenter__()
        try:
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=manager.app), base_url="https://testserver"
            ) as client:
                reg = await client.post("/oauth/register", json={})
                meta = await client.get("/.well-known/oauth-authorization-server")
            assert reg.status_code == 404
            assert meta.status_code == 404
        finally:
            await manager.__aexit__(None, None, None)
            await engine.close()


# ── dashboard/app.py lifespan branches ───────────────────────────────────────


class TestDashboardLifespanBranches:
    @pytest.mark.asyncio
    async def test_auto_migrate_failure_aborts_startup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import responsibleai.dashboard.app as app_module

        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", True)
        monkeypatch.setattr(settings, "environment", "development")

        async def _fail(_url: str) -> None:
            raise MigrationError("simulated migration failure")

        monkeypatch.setattr(app_module, "run_migrations_or_raise", _fail)

        with pytest.raises(RuntimeError, match="Startup aborted"):
            async with LifespanManager(app, startup_timeout=15):
                pass

    @pytest.mark.asyncio
    async def test_auto_migrate_success_invokes_runner(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        import responsibleai.dashboard.app as app_module

        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", True)
        monkeypatch.setattr(settings, "environment", "development")
        monkeypatch.setattr(settings, "saml_idp_entity_id", None)

        calls: list[str] = []

        async def _ok(url: str) -> None:
            calls.append(url)

        monkeypatch.setattr(app_module, "run_migrations_or_raise", _ok)

        async with LifespanManager(app, startup_timeout=15):
            pass
        assert calls == [settings.effective_db_url]

    @pytest.mark.asyncio
    async def test_production_saml_rejects_in_memory_sqlite(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(
            "responsibleai.enterprise.preflight.assert_hosted_enterprise_boot_safe",
            lambda _settings: None,
        )
        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", False)
        monkeypatch.setattr(settings, "environment", "production")
        monkeypatch.setattr(settings, "saml_idp_entity_id", "https://idp.example/metadata")
        monkeypatch.setattr(settings, "saml_session_secret", "session-secret-value")

        with pytest.raises(RuntimeError, match="in-memory SQLite"):
            async with LifespanManager(app, startup_timeout=15):
                pass

    @pytest.mark.asyncio
    async def test_saml_without_session_secret_aborts_startup(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        monkeypatch.setattr(settings, "database_url", None)
        monkeypatch.setattr(settings, "db_path", ":memory:")
        monkeypatch.setattr(settings, "auto_migrate", False)
        monkeypatch.setattr(settings, "environment", "development")
        monkeypatch.setattr(settings, "saml_idp_entity_id", "https://idp.example/metadata")
        monkeypatch.setattr(settings, "saml_session_secret", None)

        with pytest.raises(RuntimeError, match="RAI_SAML_SESSION_SECRET"):
            async with LifespanManager(app, startup_timeout=15):
                pass

    @pytest.mark.asyncio
    async def test_health_still_available_after_normal_startup(self, dashboard_client) -> None:
        response = await dashboard_client.get("/api/health")
        assert response.status_code == 200
        assert response.json()["status"] in ("healthy", "degraded")
