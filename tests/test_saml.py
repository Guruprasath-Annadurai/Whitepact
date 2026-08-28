"""Tests for auth.saml -- AuthnRequest generation, signed-response
validation (including the security-critical failure modes: tampering,
wrong signer, expiry, replay), claim extraction, SP metadata, and the
session-token mint/validate round trip.

Uses real cryptographic signing (via signxml + a self-signed test cert),
not mocked verification -- these tests exercise the actual XML-DSig path
a real IdP integration goes through, not a stand-in for it.
"""

from __future__ import annotations

import base64
import datetime
import os
from urllib.parse import parse_qs, urlparse

import pytest
from cryptography import x509
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from lxml import etree
from signxml import XMLSigner

from responsibleai.auth.saml import (
    SAML_NS,
    SAMLP_NS,
    SAMLConfig,
    SAMLError,
    build_authn_request,
    build_sp_metadata,
    clear_session_signing_key,
    configure_session_signing_key,
    mint_session_token,
    parse_and_validate_response,
    peek_in_response_to,
    validate_session_token,
)
from responsibleai.governance.crypto import KeyId, KeyPurpose


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
    """(key_pem, cert_pem) for a self-signed test IdP."""
    key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    key_pem = key.private_bytes(
        serialization.Encoding.PEM,
        serialization.PrivateFormat.PKCS8,
        serialization.NoEncryption(),
    ).decode()
    return key_pem, _make_cert(key)


@pytest.fixture()
def config(idp_keypair: tuple[str, str]) -> SAMLConfig:
    _, cert_pem = idp_keypair
    return SAMLConfig(
        idp_entity_id="test-idp",
        idp_sso_url="https://idp.example/sso",
        idp_x509_cert=cert_pem,
        sp_entity_id="https://whitepact.com/saml/metadata",
        acs_url="http://localhost:8765/api/auth/acs",
        session_secret="test-session-secret",
    )


@pytest.fixture(autouse=True)
def _reset_session_signing_key():
    """`_active_session_signing_key` is process-global state in
    auth/saml.py -- reset it around every test in this module."""
    clear_session_signing_key()
    yield
    clear_session_signing_key()


def _signed_response(
    idp_keypair: tuple[str, str],
    *,
    in_response_to: str = "_wpREQ123",
    audience: str = "https://whitepact.com/saml/metadata",
    not_before_offset: datetime.timedelta = datetime.timedelta(minutes=-1),
    not_after_offset: datetime.timedelta = datetime.timedelta(minutes=5),
    attributes: dict[str, str] | None = None,
    sign_with_key: str | None = None,
    sign_with_cert: str | None = None,
    include_signature: bool = True,
    include_conditions: bool = True,
    name_id: str = "alice@enterprise.example",
    subject_confirmation: str | None = None,
    extra_attribute_xml: str = "",
) -> str:
    """Build a full, IdP-style SAMLResponse with the Assertion signed in
    its final document position (matching how real IdPs actually produce
    one) and return it base64-encoded, as it would arrive in the
    SAMLResponse POST field.

    ``subject_confirmation`` is None (no SubjectConfirmation element at
    all), "no_expiry" (element present, no NotOnOrAfter attribute), or a
    literal NotOnOrAfter timestamp string (e.g. an already-expired one) --
    covers the three real shapes IdPs send for this optional element.
    """
    key_pem, cert_pem = idp_keypair
    key_pem = sign_with_key or key_pem
    cert_pem = sign_with_cert or cert_pem

    attributes = attributes or {
        "email": "alice@enterprise.example",
        "roles": "ADMIN",
        "org_id": "org-acme",
    }
    now = datetime.datetime.now(datetime.UTC)
    not_before = (now + not_before_offset).strftime("%Y-%m-%dT%H:%M:%SZ")
    not_after = (now + not_after_offset).strftime("%Y-%m-%dT%H:%M:%SZ")
    issue_instant = now.strftime("%Y-%m-%dT%H:%M:%SZ")

    attr_xml = (
        "".join(
            f'<saml:Attribute Name="{name}"><saml:AttributeValue>{value}</saml:AttributeValue></saml:Attribute>'
            for name, value in attributes.items()
        )
        + extra_attribute_xml
    )
    in_response_attr = f'InResponseTo="{in_response_to}"' if in_response_to else ""

    conditions_xml = (
        f'<saml:Conditions NotBefore="{not_before}" NotOnOrAfter="{not_after}">'
        f"<saml:AudienceRestriction><saml:Audience>{audience}</saml:Audience></saml:AudienceRestriction>"
        f"</saml:Conditions>"
        if include_conditions
        else ""
    )

    if subject_confirmation is None:
        confirmation_xml = ""
    elif subject_confirmation == "no_expiry":
        confirmation_xml = (
            "<saml:SubjectConfirmation><saml:SubjectConfirmationData/></saml:SubjectConfirmation>"
        )
    else:
        confirmation_xml = (
            f"<saml:SubjectConfirmation><saml:SubjectConfirmationData "
            f'NotOnOrAfter="{subject_confirmation}"/></saml:SubjectConfirmation>'
        )

    name_id_xml = (
        f'<saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress">{name_id}</saml:NameID>'
        if name_id
        else '<saml:NameID Format="urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress"></saml:NameID>'
    )

    full_xml = f"""<samlp:Response xmlns:samlp="{SAMLP_NS}" xmlns:saml="{SAML_NS}" ID="_resp1" Version="2.0" IssueInstant="{issue_instant}" {in_response_attr}>
  <saml:Issuer>test-idp</saml:Issuer>
  <samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
  <saml:Assertion ID="_assertion123" Version="2.0" IssueInstant="{issue_instant}">
    <saml:Issuer>test-idp</saml:Issuer>
    <saml:Subject>
      {name_id_xml}
      {confirmation_xml}
    </saml:Subject>
    {conditions_xml}
    <saml:AttributeStatement>{attr_xml}</saml:AttributeStatement>
  </saml:Assertion>
</samlp:Response>"""

    root = etree.fromstring(full_xml.encode())
    assertion_el = root.find(f"{{{SAML_NS}}}Assertion")
    if include_signature:
        signed = XMLSigner().sign(assertion_el, key=key_pem, cert=cert_pem)
        assertion_el.getparent().replace(assertion_el, signed)

    return base64.b64encode(etree.tostring(root)).decode()


class TestBuildAuthnRequest:
    def test_returns_redirect_url_and_request_id(self, config: SAMLConfig):
        url, request_id = build_authn_request(config)
        assert request_id.startswith("_wp")
        assert url.startswith(config.idp_sso_url)

    def test_redirect_url_carries_deflated_base64_samlrequest(self, config: SAMLConfig):
        import zlib

        url, request_id = build_authn_request(config)
        query = parse_qs(urlparse(url).query)
        assert "SAMLRequest" in query
        raw = base64.b64decode(query["SAMLRequest"][0])
        xml = zlib.decompress(raw, wbits=-15).decode()
        assert request_id in xml
        assert config.acs_url in xml
        assert config.sp_entity_id in xml

    def test_relay_state_included_when_given(self, config: SAMLConfig):
        url, _ = build_authn_request(config, relay_state="/dashboard")
        query = parse_qs(urlparse(url).query)
        assert query["RelayState"] == ["/dashboard"]

    def test_relay_state_omitted_when_not_given(self, config: SAMLConfig):
        url, _ = build_authn_request(config)
        assert "RelayState" not in parse_qs(urlparse(url).query)

    def test_request_ids_are_unique(self, config: SAMLConfig):
        _, id1 = build_authn_request(config)
        _, id2 = build_authn_request(config)
        assert id1 != id2


class TestParseAndValidateResponseHappyPath:
    def test_valid_signed_assertion_is_accepted(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        assert claims.sub == "alice@enterprise.example"
        assert claims.email == "alice@enterprise.example"
        assert claims.roles == ["ADMIN"]
        assert claims.org_id == "org-acme"

    def test_idp_initiated_flow_with_no_in_response_to_is_accepted(
        self, config: SAMLConfig, idp_keypair
    ):
        resp = _signed_response(idp_keypair, in_response_to="")
        claims = parse_and_validate_response(resp, config, expected_request_id=None)
        assert claims.sub == "alice@enterprise.example"

    def test_email_falls_back_to_name_id_when_it_looks_like_an_email(
        self, config: SAMLConfig, idp_keypair
    ):
        resp = _signed_response(idp_keypair, attributes={})
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        assert claims.email == "alice@enterprise.example"


class TestParseAndValidateResponseRejections:
    def test_tampered_attribute_value_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair)
        tampered_xml = base64.b64decode(resp).decode().replace("org-acme", "org-EVIL")
        tampered = base64.b64encode(tampered_xml.encode()).decode()
        with pytest.raises(SAMLError, match="signature"):
            parse_and_validate_response(tampered, config, expected_request_id="_wpREQ123")

    def test_wrong_signing_cert_is_rejected(self, config: SAMLConfig, idp_keypair):
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_key_pem = other_key.private_bytes(
            serialization.Encoding.PEM,
            serialization.PrivateFormat.PKCS8,
            serialization.NoEncryption(),
        ).decode()
        other_cert_pem = _make_cert(other_key)
        resp = _signed_response(
            idp_keypair, sign_with_key=other_key_pem, sign_with_cert=other_cert_pem
        )
        with pytest.raises(SAMLError, match="signature"):
            parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")

    def test_unsigned_assertion_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair, include_signature=False)
        with pytest.raises(SAMLError, match="not signed"):
            parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")

    def test_expired_assertion_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(
            idp_keypair,
            not_before_offset=datetime.timedelta(minutes=-10),
            not_after_offset=datetime.timedelta(minutes=-5),
        )
        with pytest.raises(SAMLError, match="expired"):
            parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")

    def test_not_yet_valid_assertion_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(
            idp_keypair,
            not_before_offset=datetime.timedelta(minutes=10),
            not_after_offset=datetime.timedelta(minutes=20),
        )
        with pytest.raises(SAMLError, match="not yet valid"):
            parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")

    def test_wrong_audience_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair, audience="https://someone-else.example/saml")
        with pytest.raises(SAMLError, match="audience"):
            parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")

    def test_mismatched_in_response_to_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair, in_response_to="_wpREQ123")
        with pytest.raises(SAMLError, match="InResponseTo"):
            parse_and_validate_response(resp, config, expected_request_id="_wpOTHER")

    def test_not_base64_is_rejected(self, config: SAMLConfig):
        with pytest.raises(SAMLError, match="base64"):
            parse_and_validate_response("not-valid-base64!!!", config, expected_request_id=None)

    def test_not_well_formed_xml_is_rejected(self, config: SAMLConfig):
        garbage = base64.b64encode(b"<not><valid</xml>").decode()
        with pytest.raises(SAMLError, match="well-formed"):
            parse_and_validate_response(garbage, config, expected_request_id=None)

    def test_missing_status_success_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair)
        xml = (
            base64.b64decode(resp)
            .decode()
            .replace(
                "urn:oasis:names:tc:SAML:2.0:status:Success",
                "urn:oasis:names:tc:SAML:2.0:status:Requester",
            )
        )
        with pytest.raises(SAMLError, match="Success"):
            parse_and_validate_response(
                base64.b64encode(xml.encode()).decode(), config, expected_request_id=None
            )

    def test_response_without_assertion_is_rejected(self, config: SAMLConfig):
        xml = f"""<samlp:Response xmlns:samlp="{SAMLP_NS}" xmlns:saml="{SAML_NS}" ID="_r1" Version="2.0" IssueInstant="2026-01-01T00:00:00Z">
  <saml:Issuer>test-idp</saml:Issuer>
  <samlp:Status><samlp:StatusCode Value="urn:oasis:names:tc:SAML:2.0:status:Success"/></samlp:Status>
</samlp:Response>"""
        resp = base64.b64encode(xml.encode()).decode()
        with pytest.raises(SAMLError, match="no Assertion"):
            parse_and_validate_response(resp, config, expected_request_id=None)

    def test_cert_without_pem_headers_is_accepted(self, idp_keypair):
        key_pem, cert_pem = idp_keypair
        body_only = "\n".join(
            line
            for line in cert_pem.strip().splitlines()
            if "BEGIN CERTIFICATE" not in line and "END CERTIFICATE" not in line
        )
        headerless_config = SAMLConfig(
            idp_entity_id="test-idp",
            idp_sso_url="https://idp.example/sso",
            idp_x509_cert=body_only,
            sp_entity_id="https://whitepact.com/saml/metadata",
            acs_url="http://localhost:8765/api/auth/acs",
            session_secret="test-session-secret",
        )
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(
            resp, headerless_config, expected_request_id="_wpREQ123"
        )
        assert claims.sub == "alice@enterprise.example"

    def test_signxml_list_result_of_one_is_accepted(
        self, config: SAMLConfig, idp_keypair, monkeypatch
    ):
        import signxml

        original_verify = signxml.XMLVerifier.verify

        def fake_verify(self, *a, **kw):
            return [original_verify(self, *a, **kw)]

        monkeypatch.setattr(signxml.XMLVerifier, "verify", fake_verify)
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        assert claims.sub == "alice@enterprise.example"

    def test_signxml_list_result_of_two_is_rejected(
        self, config: SAMLConfig, idp_keypair, monkeypatch
    ):
        import signxml

        original_verify = signxml.XMLVerifier.verify

        def fake_verify(self, *a, **kw):
            result = original_verify(self, *a, **kw)
            return [result, result]

        monkeypatch.setattr(signxml.XMLVerifier, "verify", fake_verify)
        resp = _signed_response(idp_keypair)
        with pytest.raises(SAMLError, match="Expected exactly one"):
            parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")

    def test_no_conditions_element_is_accepted(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair, include_conditions=False)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        assert claims.sub == "alice@enterprise.example"

    def test_subject_confirmation_without_expiry_is_accepted(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair, subject_confirmation="no_expiry")
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        assert claims.sub == "alice@enterprise.example"

    def test_expired_subject_confirmation_is_rejected(self, config: SAMLConfig, idp_keypair):
        expired = (datetime.datetime.now(datetime.UTC) - datetime.timedelta(minutes=10)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        resp = _signed_response(idp_keypair, subject_confirmation=expired)
        with pytest.raises(SAMLError, match="SubjectConfirmation has expired"):
            parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")

    def test_empty_name_id_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair, name_id="")
        with pytest.raises(SAMLError, match="no Subject/NameID"):
            parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")

    def test_attribute_without_name_is_ignored(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(
            idp_keypair,
            extra_attribute_xml="<saml:Attribute><saml:AttributeValue>orphan</saml:AttributeValue></saml:Attribute>",
        )
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        assert claims.sub == "alice@enterprise.example"
        assert "orphan" not in claims.raw["attributes"].values()

    def test_role_matched_via_later_attribute_name_variant(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(
            idp_keypair,
            attributes={"email": "alice@enterprise.example", "groups": "eng-team"},
        )
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        assert claims.roles == ["eng-team"]

    def test_no_role_attribute_present_yields_empty_roles(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair, attributes={"email": "alice@enterprise.example"})
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        assert claims.roles == []


class TestPeekInResponseTo:
    def test_extracts_the_value(self, idp_keypair):
        resp = _signed_response(idp_keypair, in_response_to="_wpREQ999")
        assert peek_in_response_to(resp) == "_wpREQ999"

    def test_returns_none_when_absent(self, idp_keypair):
        resp = _signed_response(idp_keypair, in_response_to="")
        assert peek_in_response_to(resp) is None

    def test_returns_none_on_garbage_input(self):
        assert peek_in_response_to("not-valid-base64!!!") is None

    def test_does_not_require_a_valid_signature(self, idp_keypair):
        # peek is explicitly not a trust decision -- it should read the
        # attribute even off a response whose signature would later fail.
        resp = _signed_response(idp_keypair)
        tampered_xml = base64.b64decode(resp).decode().replace("org-acme", "org-EVIL")
        tampered = base64.b64encode(tampered_xml.encode()).decode()
        assert peek_in_response_to(tampered) == "_wpREQ123"


class TestSPMetadata:
    def test_contains_entity_id_and_acs_url(self, config: SAMLConfig):
        xml = build_sp_metadata(config)
        assert config.sp_entity_id in xml
        assert config.acs_url in xml

    def test_is_well_formed_xml(self, config: SAMLConfig):
        etree.fromstring(build_sp_metadata(config).encode())  # raises if malformed


class TestSessionToken:
    def test_mint_and_validate_round_trip(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        token = mint_session_token(config, claims)
        resolved = validate_session_token(config, token)
        assert resolved is not None
        assert resolved.sub == "alice@enterprise.example"
        assert resolved.roles == ["ADMIN"]
        assert resolved.org_id == "org-acme"

    def test_token_has_the_expected_prefix(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        token = mint_session_token(config, claims)
        assert token.startswith("wp_saml.")

    def test_non_saml_token_is_not_a_match(self, config: SAMLConfig):
        assert validate_session_token(config, "rai_some_static_key") is None
        assert validate_session_token(config, "some.jwt.looking.token") is None

    def test_tampered_signature_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        token = mint_session_token(config, claims)
        payload_part, sig_part = token[len("wp_saml.") :].rsplit(".", 1)
        tampered = f"wp_saml.{payload_part}." + ("0" if sig_part[0] != "0" else "1") + sig_part[1:]
        assert validate_session_token(config, tampered) is None

    def test_wrong_secret_is_rejected(self, config: SAMLConfig, idp_keypair):
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        token = mint_session_token(config, claims)
        wrong_secret_config = SAMLConfig(
            **{**config.__dict__, "session_secret": "a-different-secret"}
        )
        assert validate_session_token(wrong_secret_config, token) is None

    def test_malformed_token_body_is_rejected(self, config: SAMLConfig):
        assert validate_session_token(config, "wp_saml.no-dot-separator") is None

    def test_corrupted_payload_base64_is_rejected(self, config: SAMLConfig):
        assert validate_session_token(config, "wp_saml.%%%not-base64%%%.deadbeef") is None

    def test_expired_session_token_is_rejected(self, config: SAMLConfig, idp_keypair, monkeypatch):
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        import responsibleai.auth.saml as saml_module

        # Mock time only while minting, so the token's `exp` lands in the
        # past relative to the real clock validate_session_token reads
        # afterward -- mocking both calls would make them agree and the
        # token would never look expired.
        with monkeypatch.context() as m:
            m.setattr(saml_module.time, "time", lambda: 1_000_000_000.0)
            token = mint_session_token(config, claims)
        assert validate_session_token(config, token) is None


def _session_signing_key_id(version: int = 1) -> KeyId:
    return KeyId(
        purpose=KeyPurpose.SESSION_SIGNING, tenant_id=None, version=version, environment="test"
    )


class TestConfigureSessionSigningKey:
    def test_rejects_wrong_purpose(self):
        wrong_purpose_key_id = KeyId(
            purpose=KeyPurpose.WEBHOOK_SIGNING, tenant_id=None, version=1, environment="test"
        )
        with pytest.raises(ValueError, match="SESSION_SIGNING"):
            configure_session_signing_key(wrong_purpose_key_id, os.urandom(32))


class TestSessionTokenNewScheme:
    """Enterprise Neural Phase 2 Step 4 -- the governance/crypto-based
    session-signing scheme coexisting with legacy
    SAMLConfig.session_secret."""

    def test_round_trips_when_new_scheme_configured(self, config: SAMLConfig, idp_keypair):
        configure_session_signing_key(_session_signing_key_id(), os.urandom(32))
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        token = mint_session_token(config, claims)
        resolved = validate_session_token(config, token)
        assert resolved is not None
        assert resolved.sub == "alice@enterprise.example"

    def test_legacy_token_still_validates_after_new_scheme_activated(
        self, config: SAMLConfig, idp_keypair
    ):
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        legacy_token = mint_session_token(config, claims)  # minted before activation

        configure_session_signing_key(_session_signing_key_id(), os.urandom(32))
        resolved = validate_session_token(config, legacy_token)
        assert resolved is not None
        assert resolved.sub == "alice@enterprise.example"

    def test_new_scheme_tampered_token_is_rejected(self, config: SAMLConfig, idp_keypair):
        configure_session_signing_key(_session_signing_key_id(), os.urandom(32))
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        token = mint_session_token(config, claims)
        payload_part, sig_part = token[len("wp_saml.") :].rsplit(".", 1)
        tampered = f"wp_saml.{payload_part}." + ("0" if sig_part[0] != "0" else "1") + sig_part[1:]
        assert validate_session_token(config, tampered) is None

    def test_clear_reverts_to_legacy_only_path(self, config: SAMLConfig, idp_keypair):
        configure_session_signing_key(_session_signing_key_id(), os.urandom(32))
        clear_session_signing_key()
        resp = _signed_response(idp_keypair)
        claims = parse_and_validate_response(resp, config, expected_request_id="_wpREQ123")
        token = mint_session_token(config, claims)
        resolved = validate_session_token(config, token)
        assert resolved is not None
