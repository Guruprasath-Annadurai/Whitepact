"""Tests for auth.oidc -- JWTClaims parsing, AsyncJWKSClient caching,
OIDCProvider.validate_token's error paths, unverified decode, authorization
URL building, and code exchange. Weak/strong-RSA-key rejection during real
signature verification is already covered end-to-end in
test_crypto_policy.py's TestOIDCProviderRejectsWeakJWKSKey; this file covers
the remaining branches around it."""

from __future__ import annotations

import base64
import json
import time

import httpx
import jwt as pyjwt
import pytest
import respx
from cryptography.hazmat.primitives.asymmetric import rsa

from responsibleai.auth.oidc import AsyncJWKSClient, JWTClaims, OIDCProvider


class TestJWTClaimsFromPayload:
    def test_roles_from_roles_key(self):
        claims = JWTClaims.from_payload({"sub": "u1", "roles": ["admin"]})
        assert claims.roles == ["admin"]

    def test_roles_fall_back_to_groups_key(self):
        claims = JWTClaims.from_payload({"sub": "u1", "groups": ["viewer"]})
        assert claims.roles == ["viewer"]

    def test_roles_absent_defaults_to_empty_list(self):
        claims = JWTClaims.from_payload({"sub": "u1"})
        assert claims.roles == []

    def test_roles_as_single_string_is_wrapped_in_list(self):
        claims = JWTClaims.from_payload({"sub": "u1", "roles": "admin"})
        assert claims.roles == ["admin"]

    def test_org_id_from_org_id_key(self):
        claims = JWTClaims.from_payload({"sub": "u1", "org_id": "org-1"})
        assert claims.org_id == "org-1"

    def test_org_id_falls_back_to_tenant_id(self):
        claims = JWTClaims.from_payload({"sub": "u1", "tenant_id": "tenant-1"})
        assert claims.org_id == "tenant-1"

    def test_org_id_absent_is_none(self):
        claims = JWTClaims.from_payload({"sub": "u1"})
        assert claims.org_id is None


class TestAsyncJWKSClient:
    async def test_refreshes_when_cache_empty(self, monkeypatch):
        client = AsyncJWKSClient("https://issuer.example.com/.well-known/jwks.json")
        calls = {"n": 0}

        async def _fake_refresh():
            calls["n"] += 1
            client._keys = [{"kid": "k1"}]
            client._fetched_at = time.monotonic()

        monkeypatch.setattr(client, "_refresh", _fake_refresh)
        key = await client.get_signing_key("k1")
        assert calls["n"] == 1
        assert key == {"kid": "k1"}

    async def test_refreshes_when_ttl_expired(self, monkeypatch):
        client = AsyncJWKSClient("https://issuer.example.com/.well-known/jwks.json")
        client._keys = [{"kid": "old"}]
        client._fetched_at = time.monotonic() - client._TTL - 1

        calls = {"n": 0}

        async def _fake_refresh():
            calls["n"] += 1
            client._keys = [{"kid": "new"}]
            client._fetched_at = time.monotonic()

        monkeypatch.setattr(client, "_refresh", _fake_refresh)
        key = await client.get_signing_key(None)
        assert calls["n"] == 1
        assert key == {"kid": "new"}

    async def test_returns_first_key_when_kid_not_found(self, monkeypatch):
        client = AsyncJWKSClient("https://issuer.example.com/.well-known/jwks.json")
        client._keys = [{"kid": "a"}, {"kid": "b"}]
        client._fetched_at = time.monotonic()
        key = await client.get_signing_key("nonexistent")
        assert key == {"kid": "a"}

    async def test_returns_none_when_no_keys_at_all(self, monkeypatch):
        client = AsyncJWKSClient("https://issuer.example.com/.well-known/jwks.json")

        async def _fake_refresh():
            client._keys = []
            client._fetched_at = time.monotonic()

        monkeypatch.setattr(client, "_refresh", _fake_refresh)
        assert await client.get_signing_key(None) is None

    @respx.mock
    async def test_refresh_fetches_and_caches_real_keys(self):
        client = AsyncJWKSClient("https://issuer.example.com/.well-known/jwks.json")
        respx.get("https://issuer.example.com/.well-known/jwks.json").mock(
            return_value=httpx.Response(200, json={"keys": [{"kid": "k1"}]})
        )
        await client._refresh()
        assert client._keys == [{"kid": "k1"}]
        assert client._fetched_at > 0


class TestOIDCProviderInit:
    def test_default_jwks_uri_derived_from_issuer(self):
        provider = OIDCProvider(issuer="https://issuer.example.com/", client_id="c1")
        assert provider._jwks._uri == "https://issuer.example.com/.well-known/jwks.json"

    def test_explicit_jwks_uri_used_when_given(self):
        provider = OIDCProvider(
            issuer="https://issuer.example.com",
            client_id="c1",
            jwks_uri="https://custom.example.com/jwks",
        )
        assert provider._jwks._uri == "https://custom.example.com/jwks"


class TestDiscover:
    @respx.mock
    async def test_fetches_and_caches_discovery_doc(self):
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")
        route = respx.get("https://issuer.example.com/.well-known/openid-configuration").mock(
            return_value=httpx.Response(
                200, json={"authorization_endpoint": "https://issuer.example.com/authorize"}
            )
        )
        doc = await provider.discover()
        assert doc["authorization_endpoint"] == "https://issuer.example.com/authorize"
        assert route.call_count == 1

        # Second call must use the cache, not hit the network again.
        doc2 = await provider.discover()
        assert doc2 is doc
        assert route.call_count == 1


class TestValidateTokenSkipVerification:
    async def test_skip_verification_uses_unverified_decode(self):
        provider = OIDCProvider(
            issuer="https://issuer.example.com", client_id="c1", skip_verification=True
        )
        payload = {"sub": "u1", "email": "a@b.com"}
        segment = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        token = f"header.{segment}.signature"
        claims = await provider.validate_token(token)
        assert claims.sub == "u1"
        assert claims.email == "a@b.com"


class TestDecodeUnverified:
    def test_malformed_token_wrong_part_count_raises(self):
        with pytest.raises(ValueError, match="Malformed JWT"):
            OIDCProvider._decode_unverified("only.two")

    def test_invalid_base64_payload_raises(self):
        with pytest.raises(ValueError, match="Failed to decode"):
            OIDCProvider._decode_unverified("header.not-valid-base64!!!.sig")

    def test_valid_token_decodes(self):
        payload = {"sub": "u1"}
        segment = base64.urlsafe_b64encode(json.dumps(payload).encode()).decode().rstrip("=")
        claims = OIDCProvider._decode_unverified(f"header.{segment}.sig")
        assert claims.sub == "u1"


class TestValidateTokenErrorPaths:
    async def test_missing_signing_key_raises(self, monkeypatch):
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")
        token = pyjwt.encode({"sub": "u1"}, "secret", algorithm="HS256")

        async def _no_key(kid):
            return None

        monkeypatch.setattr(provider._jwks, "get_signing_key", _no_key)
        with pytest.raises(ValueError, match="Unable to retrieve signing key"):
            await provider.validate_token(token)

    async def test_private_key_in_jwks_is_rejected(self, monkeypatch):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        # Deliberately serve the *private* key's JWK representation --
        # a malicious/misconfigured JWKS endpoint must never be trusted.
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(private)
        )
        jwk_dict["kid"] = "priv-key"
        token = pyjwt.encode(
            {"sub": "u1", "aud": "c1", "iss": "https://issuer.example.com"},
            private,
            algorithm="RS256",
            headers={"kid": "priv-key"},
        )
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(provider._jwks, "get_signing_key", _fake_get_signing_key)
        with pytest.raises(ValueError, match="expected public"):
            await provider.validate_token(token)

    async def test_expired_token_raises(self, monkeypatch):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(
                private.public_key()
            )
        )
        jwk_dict["kid"] = "k1"
        token = pyjwt.encode(
            {
                "sub": "u1",
                "aud": "c1",
                "iss": "https://issuer.example.com",
                "exp": int(time.time()) - 3600,
            },
            private,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(provider._jwks, "get_signing_key", _fake_get_signing_key)
        with pytest.raises(ValueError, match="expired"):
            await provider.validate_token(token)

    async def test_invalid_audience_raises_invalid_token_error(self, monkeypatch):
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        jwk_dict = json.loads(
            pyjwt.algorithms.RSAAlgorithm(pyjwt.algorithms.RSAAlgorithm.SHA256).to_jwk(
                private.public_key()
            )
        )
        jwk_dict["kid"] = "k1"
        token = pyjwt.encode(
            {"sub": "u1", "aud": "wrong-audience", "iss": "https://issuer.example.com"},
            private,
            algorithm="RS256",
            headers={"kid": "k1"},
        )
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")

        async def _fake_get_signing_key(kid):
            return jwk_dict

        monkeypatch.setattr(provider._jwks, "get_signing_key", _fake_get_signing_key)
        with pytest.raises(ValueError, match="Invalid token"):
            await provider.validate_token(token)

    async def test_pyjwt_missing_raises_import_error(self, monkeypatch):
        import sys

        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")
        monkeypatch.setitem(sys.modules, "jwt", None)
        with pytest.raises(ImportError, match="PyJWT"):
            await provider.validate_token("a.b.c")


class TestAuthorizationUrl:
    def test_uses_default_authorize_endpoint_when_no_discovery(self):
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")
        url = provider.authorization_url(
            "https://app.example.com/callback", "state123", ["openid", "email"]
        )
        assert url.startswith("https://issuer.example.com/authorize?")
        assert "state=state123" in url
        assert "client_id=c1" in url

    def test_uses_discovered_authorization_endpoint_when_present(self):
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")
        provider._discovery_doc = {
            "authorization_endpoint": "https://issuer.example.com/custom-authorize"
        }
        url = provider.authorization_url("https://app.example.com/callback", "s", ["openid"])
        assert url.startswith("https://issuer.example.com/custom-authorize?")

    def test_falls_back_to_default_when_discovery_doc_lacks_endpoint(self):
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")
        provider._discovery_doc = {"some_other_field": "x"}
        url = provider.authorization_url("https://app.example.com/callback", "s", ["openid"])
        assert url.startswith("https://issuer.example.com/authorize?")


class TestExchangeCode:
    @respx.mock
    async def test_successful_exchange_returns_tokens(self):
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")
        respx.get("https://issuer.example.com/.well-known/openid-configuration").mock(
            return_value=httpx.Response(
                200, json={"token_endpoint": "https://issuer.example.com/token"}
            )
        )
        respx.post("https://issuer.example.com/token").mock(
            return_value=httpx.Response(200, json={"access_token": "tok123"})
        )
        result = await provider.exchange_code("code1", "https://app.example.com/cb", "secret")
        assert result["access_token"] == "tok123"

    @respx.mock
    async def test_failed_exchange_raises_value_error(self):
        provider = OIDCProvider(issuer="https://issuer.example.com", client_id="c1")
        respx.get("https://issuer.example.com/.well-known/openid-configuration").mock(
            return_value=httpx.Response(200, json={})
        )
        respx.post("https://issuer.example.com/token").mock(
            return_value=httpx.Response(400, text="invalid_grant")
        )
        with pytest.raises(ValueError, match="Token exchange failed"):
            await provider.exchange_code("bad-code", "https://app.example.com/cb", "secret")
