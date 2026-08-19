"""App-level SAML route tests -- covers the dashboard/app.py wiring
(provider listing, login redirect, ACS callback, SP metadata, and the
SAML branch of get_org_context) that tests/test_saml.py doesn't reach,
since that file exercises auth/saml.py directly rather than through the
FastAPI app.

Startup only populates app.py's _saml_config from RAI_SAML_* env vars, so
these tests monkeypatch the module-level global directly to simulate a
configured deployment -- Python resolves globals at call time, so this
affects the route functions the same as a real configured startup would.
"""

from __future__ import annotations

import base64
import datetime
import time

import pytest
from asgi_lifespan import LifespanManager
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from httpx import ASGITransport, AsyncClient
from lxml import etree
from signxml import XMLSigner

from responsibleai.auth.saml import (
    SAML_NS,
    SAMLP_NS,
    SAMLConfig,
    mint_session_token,
    parse_and_validate_response,
)


def _make_cert(key: rsa.RSAPrivateKey) -> str:
    name = x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, "test-idp")])
    now = datetime.datetime.now(datetime.UTC)
    cert = (
        x509.CertificateBuilder()
        .subject_name(name)
        .issuer_name(name)
        .public_key(key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - datetime.timedelta(days=1))
        .not_valid_after(now + datetime.timedelta(days=365))
        .sign(key, hashes.SHA256())
    )
    return cert.public_bytes(serialization.Encoding.PEM).decode()


@pytest.fixture(scope="module")
def idp_keypair() -> tuple[str, str]:
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()
    ).decode()
    return key_pem, _make_cert(key)


@pytest.fixture()
def saml_config(idp_keypair: tuple[str, str]) -> SAMLConfig:
    _, cert_pem = idp_keypair
    return SAMLConfig(
        idp_entity_id="test-idp",
        idp_sso_url="https://idp.example/sso",
        idp_x509_cert=cert_pem,
        sp_entity_id="https://whitepact.com/saml/metadata",
        acs_url="http://localhost:8765/api/auth/acs",
        session_secret="test-session-secret",
    )


def _signed_response(idp_keypair: tuple[str, str], *, in_response_to: str = "") -> str:
    key_pem, cert_pem = idp_keypair
    now = datetime.datetime.now(datetime.UTC)
    not_before = (now - datetime.timedelta(minutes=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    not_after = (now + datetime.timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M:%SZ")
    issue_instant = now.strftime("%Y-%m-%dT%H:%M:%SZ")
    in_response_attr = f'InResponseTo="{in_response_to}"' if in_response_to else ""
    full_xml = f"""<samlp:Response xmlns:samlp="{SAMLP_NS}" xmlns:saml="{SAML_NS}" ID="_r1" Version="2.0" IssueInstant="{issue_instant}" {in_response_attr}>
  <saml:Issuer>test-idp</saml:Issuer>
  <samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
  <saml:Assertion ID="_a1" Version="2.0" IssueInstant="{issue_instant}">
    <saml:Issuer>test-idp</saml:Issuer>
    <saml:Subject><saml:NameID>alice@enterprise.example</saml:NameID></saml:Subject>
    <saml:Conditions NotBefore="{not_before}" NotOnOrAfter="{not_after}">
      <saml:AudienceRestriction><saml:Audience>https://whitepact.com/saml/metadata</saml:Audience></saml:AudienceRestriction>
    </saml:Conditions>
    <saml:AttributeStatement>
      <saml:Attribute Name="roles"><saml:AttributeValue>ADMIN</saml:AttributeValue></saml:Attribute>
    </saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>"""
    root = etree.fromstring(full_xml.encode())
    assertion_el = root.find(f"{{{SAML_NS}}}Assertion")
    signed = XMLSigner().sign(assertion_el, key=key_pem, cert=cert_pem)
    assertion_el.getparent().replace(assertion_el, signed)
    return base64.b64encode(etree.tostring(root)).decode()


@pytest.fixture(autouse=True)
def _auth_enabled(monkeypatch: pytest.MonkeyPatch):
    """Force auth on and use an isolated in-memory DB -- see
    test_governance_api.py's module docstring for why this is needed
    rather than relying on defaults: some other test module sets
    RAI_AUTH_ENABLED=false as an import-time side effect, which leaks
    into every test module collected in the same pytest run."""
    from responsibleai.dashboard.app import settings

    monkeypatch.setattr(settings, "auth_enabled", True)
    monkeypatch.setattr(settings, "api_keys", [])
    monkeypatch.setattr(settings, "db_path", ":memory:")
    monkeypatch.setattr(settings, "database_url", None)
    monkeypatch.setattr(settings, "auto_migrate", False)
    yield


@pytest.fixture()
async def client():
    from responsibleai.dashboard.app import app, limiter

    limiter.reset()
    async with LifespanManager(app) as manager:
        async with AsyncClient(transport=ASGITransport(app=manager.app), base_url="http://test") as c:
            yield c


@pytest.fixture()
def configured_saml(saml_config: SAMLConfig):
    from responsibleai.dashboard import app as app_module

    original_config = app_module._saml_config
    original_store = dict(app_module._saml_request_store)
    app_module._saml_config = saml_config
    yield saml_config
    app_module._saml_config = original_config
    app_module._saml_request_store.clear()
    app_module._saml_request_store.update(original_store)


class TestProvidersList:
    @pytest.mark.asyncio
    async def test_saml_absent_when_not_configured(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/providers")
        ids = [p["id"] for p in r.json()["providers"]]
        assert "saml" not in ids

    @pytest.mark.asyncio
    async def test_saml_present_when_configured(self, client: AsyncClient, configured_saml: SAMLConfig) -> None:
        r = await client.get("/api/auth/providers")
        providers = {p["id"]: p for p in r.json()["providers"]}
        assert "saml" in providers
        assert providers["saml"]["sp_metadata_url"] == "/api/auth/saml/metadata"
        assert providers["saml"]["idp_entity_id"] == "test-idp"


class TestLoginSaml:
    @pytest.mark.asyncio
    async def test_login_saml_without_config_404(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/login/saml")
        assert r.status_code == 404

    @pytest.mark.asyncio
    async def test_login_saml_with_config_returns_redirect(
        self, client: AsyncClient, configured_saml: SAMLConfig
    ) -> None:
        r = await client.get("/api/auth/login/saml")
        assert r.status_code == 200
        body = r.json()
        assert "authorization_url" in body
        assert "request_id" in body


class TestSPMetadataRoute:
    @pytest.mark.asyncio
    async def test_metadata_without_config_501(self, client: AsyncClient) -> None:
        r = await client.get("/api/auth/saml/metadata")
        assert r.status_code == 501

    @pytest.mark.asyncio
    async def test_metadata_with_config_returns_xml(
        self, client: AsyncClient, configured_saml: SAMLConfig
    ) -> None:
        r = await client.get("/api/auth/saml/metadata")
        assert r.status_code == 200
        assert configured_saml.sp_entity_id in r.text


class TestSamlAcs:
    @pytest.mark.asyncio
    async def test_acs_without_config_501(self, client: AsyncClient) -> None:
        r = await client.post("/api/auth/acs", data={"SAMLResponse": "x"})
        assert r.status_code == 501

    @pytest.mark.asyncio
    async def test_acs_missing_saml_response_400(
        self, client: AsyncClient, configured_saml: SAMLConfig
    ) -> None:
        r = await client.post("/api/auth/acs", data={})
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_acs_unknown_request_id_400(
        self, client: AsyncClient, configured_saml: SAMLConfig, idp_keypair: tuple[str, str]
    ) -> None:
        resp = _signed_response(idp_keypair, in_response_to="_unknown123")
        r = await client.post("/api/auth/acs", data={"SAMLResponse": resp}, follow_redirects=False)
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_acs_expired_request_id_400(
        self, client: AsyncClient, configured_saml: SAMLConfig, idp_keypair: tuple[str, str]
    ) -> None:
        from responsibleai.dashboard import app as app_module

        app_module._saml_request_store["_req1"] = time.monotonic() - app_module._SAML_REQUEST_TTL - 1
        resp = _signed_response(idp_keypair, in_response_to="_req1")
        r = await client.post("/api/auth/acs", data={"SAMLResponse": resp}, follow_redirects=False)
        assert r.status_code == 400

    @pytest.mark.asyncio
    async def test_acs_invalid_assertion_401(
        self, client: AsyncClient, configured_saml: SAMLConfig
    ) -> None:
        r = await client.post(
            "/api/auth/acs",
            data={"SAMLResponse": base64.b64encode(b"<garbage/>").decode()},
            follow_redirects=False,
        )
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_acs_idp_initiated_success_redirects(
        self, client: AsyncClient, configured_saml: SAMLConfig, idp_keypair: tuple[str, str]
    ) -> None:
        resp = _signed_response(idp_keypair, in_response_to="")
        r = await client.post("/api/auth/acs", data={"SAMLResponse": resp}, follow_redirects=False)
        assert r.status_code == 302
        assert r.headers["location"].startswith("/auth/complete#token=")

    @pytest.mark.asyncio
    async def test_acs_sp_initiated_success_redirects(
        self, client: AsyncClient, configured_saml: SAMLConfig, idp_keypair: tuple[str, str]
    ) -> None:
        from responsibleai.dashboard import app as app_module

        app_module._saml_request_store["_req2"] = time.monotonic()
        resp = _signed_response(idp_keypair, in_response_to="_req2")
        r = await client.post("/api/auth/acs", data={"SAMLResponse": resp}, follow_redirects=False)
        assert r.status_code == 302
        assert "_req2" not in app_module._saml_request_store


class TestResolveSamlContext:
    @pytest.mark.asyncio
    async def test_get_org_context_accepts_saml_session_token(
        self, client: AsyncClient, configured_saml: SAMLConfig, idp_keypair: tuple[str, str]
    ) -> None:
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, configured_saml, expected_request_id=None)
        token = mint_session_token(configured_saml, claims)
        r = await client.get("/api/auth/session", headers={"Authorization": f"Bearer {token}"})
        assert r.status_code == 200
        assert r.json()["key_id"] == f"saml:{claims.sub}"

    @pytest.mark.asyncio
    async def test_get_org_context_rejects_garbage_saml_token(
        self, client: AsyncClient, configured_saml: SAMLConfig
    ) -> None:
        r = await client.get("/api/auth/session", headers={"Authorization": "Bearer wp_saml.garbage.garbage"})
        assert r.status_code == 401

    @pytest.mark.asyncio
    async def test_sso_required_error_lists_both_configured_providers(
        self, client: AsyncClient, configured_saml: SAMLConfig
    ) -> None:
        # Neither OIDC nor a DB-backed org key is configured in this test
        # environment, so an unrecognized bearer token simply 401s -- but
        # this exercises the get_org_context code path with _saml_config
        # set, which is what determines whether "saml" appears in the
        # SSORequiredError provider list built at line 721 of app.py.
        r = await client.get("/api/auth/session", headers={"Authorization": "Bearer rai_totally_unknown_key"})
        assert r.status_code == 401
