"""SAML 2.0 service-provider support — AuthnRequest generation, signed-
response validation, and WhitePact's own post-login session token.

Deliberately independent of ``auth/oidc.py``, not layered on top of it:
some enterprise identity providers support only SAML, some only OIDC, and
building one on the other would make the unsupported one a second-class
citizen. They share nothing but the shape of the claims they produce
(``SAMLAssertionClaims`` mirrors ``oidc.JWTClaims`` deliberately, so
``dashboard/app.py`` can treat both uniformly once a token is resolved).

SAML has no bearer-token concept the way OIDC does. A SAML assertion is
consumed once, at the Assertion Consumer Service, by a browser redirect —
it is not a credential a client re-presents on every API call. After a
successful login this module therefore mints WhitePact's own short-lived,
HMAC-signed session token (``mint_session_token`` / ``validate_session_token``)
— that token, not the original assertion, is what ``dashboard/app.py``
accepts as a Bearer credential afterward. This is the standard pattern
real SAML service providers use; forwarding the raw assertion as an API
credential (mirroring what the OIDC integration does with the IdP's own
JWT) would not work, since a consumed assertion has no ongoing validity.

Security-critical parsing note: XML signature verification is delegated
entirely to ``signxml`` rather than hand-rolled. Hand-rolled
"does the file contain a valid-looking <Signature>" checks are exactly how
XML signature wrapping attacks succeed — an attacker adds a second,
unsigned or differently-signed element with the victim's claims, and a
naive checker validates *a* signature in the document without checking it
covers *the element actually being trusted*. ``signxml.XMLVerifier`` binds
the signature to its ``Reference`` URI and returns only the specific
verified subtree; every claim extracted below reads from that returned
subtree, never from the original untrusted document.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import time
import zlib
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import TYPE_CHECKING, Any
from urllib.parse import quote, urlencode
from uuid import uuid4

if TYPE_CHECKING:
    from lxml import etree

# lxml/signxml are imported lazily inside the functions that need them (see
# _safe_xml_parser, parse_and_validate_response, peek_in_response_to,
# _verify_signature below) rather than at module level. dashboard/app.py
# imports this module unconditionally, and lxml/signxml are pulled in only
# by the optional `sso` extra — a top-level import here would break any
# `[dashboard]`-only install that never configures SAML. Same reasoning as
# oidc.py's lazy `import jwt` for PyJWT.

SAML_NS = "urn:oasis:names:tc:SAML:2.0:assertion"
SAMLP_NS = "urn:oasis:names:tc:SAML:2.0:protocol"
DS_NS = "http://www.w3.org/2000/09/xmldsig#"
_NSMAP = {"saml": SAML_NS, "samlp": SAMLP_NS, "ds": DS_NS}

# Common attribute names IdPs use for role/group and org claims — no single
# standard exists, so a handful of the ones actually seen in the wild
# (ADFS/Azure AD, Okta, generic SAML) are tried in order.
_ROLE_ATTR_NAMES = (
    "roles",
    "role",
    "groups",
    "http://schemas.xmlsoap.org/claims/Group",
    "http://schemas.microsoft.com/ws/2008/06/identity/claims/role",
)
_EMAIL_ATTR_NAMES = (
    "email",
    "Email",
    "emailaddress",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/emailaddress",
)
_NAME_ATTR_NAMES = (
    "name",
    "displayname",
    "http://schemas.xmlsoap.org/ws/2005/05/identity/claims/name",
)
_ORG_ATTR_NAMES = ("org_id", "organization", "tenant_id")

_CLOCK_SKEW_SECONDS = 120
_SESSION_TOKEN_PREFIX = "wp_saml."  # noqa: S105 -- not a secret, a format tag
_SESSION_TTL_SECONDS = 3600


class SAMLError(ValueError):
    """Any failure validating an AuthnRequest response — deliberately a
    single exception type so callers don't need to enumerate every XML
    parsing/signature/timing failure mode separately; the message says
    which one happened."""


@dataclass(frozen=True)
class SAMLConfig:
    idp_entity_id: str
    idp_sso_url: str
    idp_x509_cert: str
    sp_entity_id: str
    acs_url: str
    session_secret: str


@dataclass(frozen=True)
class SAMLAssertionClaims:
    """Mirrors ``oidc.JWTClaims`` in shape, deliberately — see module
    docstring."""

    sub: str
    email: str | None = None
    name: str | None = None
    roles: list[str] = field(default_factory=list)
    org_id: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


def _safe_xml_parser() -> etree.XMLParser:
    """A parser configured against XXE / entity-expansion attacks on the
    untrusted IdP response: no DTD loading, no entity resolution, no
    network access. Never parse a SAMLResponse with the default parser."""
    from lxml import etree

    return etree.XMLParser(
        resolve_entities=False,
        no_network=True,
        load_dtd=False,
        dtd_validation=False,
        huge_tree=False,
    )


def build_authn_request(config: SAMLConfig, relay_state: str | None = None) -> tuple[str, str]:
    """Build a SAML AuthnRequest and return (redirect_url, request_id).

    ``request_id`` is the AuthnRequest's own ID — callers store it (with a
    short expiry) and check it against the response's ``InResponseTo`` at
    the ACS endpoint, the same replay/CSRF-prevention role the OIDC ``state``
    parameter plays in ``auth/oidc.py``.
    """
    request_id = f"_wp{uuid4().hex}"
    issue_instant = datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")

    xml = (
        f'<samlp:AuthnRequest xmlns:samlp="{SAMLP_NS}" xmlns:saml="{SAML_NS}" '
        f'ID="{request_id}" Version="2.0" IssueInstant="{issue_instant}" '
        f'Destination="{config.idp_sso_url}" '
        f'AssertionConsumerServiceURL="{config.acs_url}" '
        f'ProtocolBinding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST">'
        f"<saml:Issuer>{config.sp_entity_id}</saml:Issuer>"
        f"</samlp:AuthnRequest>"
    )

    # HTTP-Redirect binding: raw DEFLATE (no zlib header/checksum), then
    # base64, then URL-encoded as a query parameter — per SAML Bindings
    # spec section 3.4.4.1, not an arbitrary compression choice.
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(xml.encode("utf-8")) + compressor.flush()
    encoded = base64.b64encode(compressed).decode("ascii")

    params = {"SAMLRequest": encoded}
    if relay_state:
        params["RelayState"] = relay_state
    redirect_url = f"{config.idp_sso_url}?{urlencode(params, quote_via=quote)}"
    return redirect_url, request_id


def peek_in_response_to(saml_response_b64: str) -> str | None:
    """Read the (still-untrusted) InResponseTo attribute off a SAMLResponse
    without checking its signature. Not a security decision by itself —
    callers use this only to decide *which* known request ID to require a
    match against in ``parse_and_validate_response`` (SP-initiated login),
    versus accepting an IdP-initiated response that carries none at all.
    The actual trust decision is the state-store membership check the
    caller performs on the returned value, not this function."""
    from lxml import etree

    try:
        xml_bytes = base64.b64decode(saml_response_b64)
        root = etree.fromstring(xml_bytes, parser=_safe_xml_parser())
    except Exception:
        return None
    return root.get("InResponseTo")


def parse_and_validate_response(
    saml_response_b64: str,
    config: SAMLConfig,
    expected_request_id: str | None,
) -> SAMLAssertionClaims:
    """Validate a POST-binding SAMLResponse and return the claims inside
    its signed Assertion. Raises SAMLError on any failure — expired
    assertion, wrong audience, unmatched InResponseTo, or (the one that
    matters most) a signature that doesn't verify against the configured
    IdP certificate."""
    try:
        from lxml import etree
    except ImportError as exc:
        raise SAMLError(
            "lxml is required for SAML support. Install with: pip install lxml signxml"
        ) from exc

    try:
        xml_bytes = base64.b64decode(saml_response_b64)
    except Exception as exc:
        raise SAMLError(f"SAMLResponse is not valid base64: {exc}") from exc

    try:
        root = etree.fromstring(xml_bytes, parser=_safe_xml_parser())
    except Exception as exc:
        raise SAMLError(f"SAMLResponse is not well-formed XML: {exc}") from exc

    status_code_el = root.find(".//samlp:Status/samlp:StatusCode", _NSMAP)
    if status_code_el is None or "Success" not in (status_code_el.get("Value") or ""):
        raise SAMLError("IdP did not return a Success status")

    if expected_request_id is not None:
        in_response_to = root.get("InResponseTo")
        if in_response_to != expected_request_id:
            raise SAMLError("InResponseTo does not match the AuthnRequest we sent (possible replay)")

    assertion = root.find(".//saml:Assertion", _NSMAP)
    if assertion is None:
        raise SAMLError("Response contains no Assertion")

    verified_assertion = _verify_signature(assertion, config.idp_x509_cert)

    _check_conditions(verified_assertion, config.sp_entity_id)
    claims = _extract_claims(verified_assertion)
    return claims


def _verify_signature(assertion: etree._Element, idp_x509_cert: str) -> etree._Element:
    try:
        from signxml import XMLVerifier
        from signxml.exceptions import InvalidSignature
    except ImportError as exc:
        raise SAMLError(
            "signxml is required for SAML support. Install with: pip install signxml"
        ) from exc

    cert_pem = idp_x509_cert.strip()
    if "BEGIN CERTIFICATE" not in cert_pem:
        cert_pem = f"-----BEGIN CERTIFICATE-----\n{cert_pem}\n-----END CERTIFICATE-----"

    signature_el = assertion.find(f".//{{{DS_NS}}}Signature")
    if signature_el is None:
        raise SAMLError("Assertion is not signed — refusing to trust an unsigned assertion")

    try:
        result = XMLVerifier().verify(assertion, x509_cert=cert_pem)
    except InvalidSignature as exc:
        raise SAMLError(f"Assertion signature verification failed: {exc}") from exc
    except Exception as exc:  # pragma: no cover -- signxml's own parse errors, etc.
        raise SAMLError(f"Assertion signature could not be verified: {exc}") from exc

    # We only ever expect one Reference (one Signature covering one
    # Assertion). signxml's return type technically allows a list — reject
    # outright rather than silently pick one if it's ever not a single
    # result, since "more than one signed reference than expected" is
    # exactly the shape of a signature-wrapping attempt, not a case to be
    # lenient about.
    if isinstance(result, list):
        if len(result) != 1:
            raise SAMLError(f"Expected exactly one signed reference, got {len(result)}")
        result = result[0]

    # signxml returns the specific verified subtree the Reference actually
    # covered — every claim below is read from *this*, never from the
    # original `assertion` element, which is the wrapping-attack defense.
    return result.signed_xml


def _parse_saml_instant(value: str) -> float:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%fZ").replace(tzinfo=UTC).timestamp()
    except ValueError:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=UTC).timestamp()


def _check_conditions(assertion: etree._Element, sp_entity_id: str) -> None:
    now = time.time()
    conditions = assertion.find("saml:Conditions", _NSMAP)
    if conditions is not None:
        not_before = conditions.get("NotBefore")
        not_on_or_after = conditions.get("NotOnOrAfter")
        if not_before and now < _parse_saml_instant(not_before) - _CLOCK_SKEW_SECONDS:
            raise SAMLError("Assertion is not yet valid (NotBefore)")
        if not_on_or_after and now >= _parse_saml_instant(not_on_or_after) + _CLOCK_SKEW_SECONDS:
            raise SAMLError("Assertion has expired (NotOnOrAfter)")

        audiences = [
            el.text
            for el in conditions.findall("saml:AudienceRestriction/saml:Audience", _NSMAP)
            if el.text
        ]
        if audiences and sp_entity_id not in audiences:
            raise SAMLError(
                f"Assertion audience {audiences!r} does not include our entity ID {sp_entity_id!r}"
            )

    subject_confirmation_data = assertion.find(
        "saml:Subject/saml:SubjectConfirmation/saml:SubjectConfirmationData", _NSMAP
    )
    if subject_confirmation_data is not None:
        not_on_or_after = subject_confirmation_data.get("NotOnOrAfter")
        if not_on_or_after and now >= _parse_saml_instant(not_on_or_after) + _CLOCK_SKEW_SECONDS:
            raise SAMLError("SubjectConfirmation has expired (NotOnOrAfter)")


def _extract_claims(assertion: etree._Element) -> SAMLAssertionClaims:
    name_id_el = assertion.find("saml:Subject/saml:NameID", _NSMAP)
    sub = (name_id_el.text or "").strip() if name_id_el is not None else ""
    if not sub:
        raise SAMLError("Assertion has no Subject/NameID")

    attrs: dict[str, list[str]] = {}
    for attr_el in assertion.findall(".//saml:AttributeStatement/saml:Attribute", _NSMAP):
        attr_name = attr_el.get("Name") or attr_el.get("FriendlyName") or ""
        values = [v.text for v in attr_el.findall("saml:AttributeValue", _NSMAP) if v.text]
        if attr_name and values:
            attrs.setdefault(attr_name, []).extend(values)

    def first_of(names: tuple[str, ...]) -> str | None:
        for n in names:
            if n in attrs and attrs[n]:
                return attrs[n][0]
        return None

    def all_of(names: tuple[str, ...]) -> list[str]:
        for n in names:
            if n in attrs and attrs[n]:
                return attrs[n]
        return []

    email = first_of(_EMAIL_ATTR_NAMES)
    name = first_of(_NAME_ATTR_NAMES)
    org_id = first_of(_ORG_ATTR_NAMES)
    roles = all_of(_ROLE_ATTR_NAMES)

    return SAMLAssertionClaims(
        sub=sub,
        email=email or (sub if "@" in sub else None),
        name=name,
        roles=roles,
        org_id=org_id,
        raw={"name_id": sub, "attributes": attrs},
    )


def build_sp_metadata(config: SAMLConfig) -> str:
    """SP metadata XML — most IdPs need this (or the equivalent fields
    typed by hand) to configure the integration on their side."""
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<md:EntityDescriptor xmlns:md="urn:oasis:names:tc:SAML:2.0:metadata" '
        f'entityID="{config.sp_entity_id}">'
        f'<md:SPSSODescriptor AuthnRequestsSigned="false" WantAssertionsSigned="true" '
        f'protocolSupportEnumeration="urn:oasis:names:tc:SAML:2.0:protocol">'
        f'<md:NameIDFormat>urn:oasis:names:tc:SAML:1.1:nameid-format:emailAddress</md:NameIDFormat>'
        f'<md:AssertionConsumerService '
        f'Binding="urn:oasis:names:tc:SAML:2.0:bindings:HTTP-POST" '
        f'Location="{config.acs_url}" index="0" isDefault="true"/>'
        f"</md:SPSSODescriptor>"
        f"</md:EntityDescriptor>"
    )


def mint_session_token(config: SAMLConfig, claims: SAMLAssertionClaims) -> str:
    """WhitePact's own post-login bearer token — see module docstring for
    why this exists instead of forwarding the (already-consumed) assertion."""
    payload = {
        "sub": claims.sub,
        "email": claims.email,
        "name": claims.name,
        "roles": claims.roles,
        "org_id": claims.org_id,
        "exp": time.time() + _SESSION_TTL_SECONDS,
    }
    payload_b64 = base64.urlsafe_b64encode(json.dumps(payload).encode("utf-8")).decode("ascii").rstrip("=")
    signature = hmac.new(config.session_secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256).hexdigest()
    return f"{_SESSION_TOKEN_PREFIX}{payload_b64}.{signature}"


def validate_session_token(config: SAMLConfig, token: str) -> SAMLAssertionClaims | None:
    """Validate a token minted by mint_session_token. Returns None (not a
    raise) for "this isn't a SAML session token at all" so callers can
    fall through to other auth methods without a try/except per call."""
    if not token.startswith(_SESSION_TOKEN_PREFIX):
        return None
    body = token[len(_SESSION_TOKEN_PREFIX):]
    try:
        payload_b64, signature = body.rsplit(".", 1)
    except ValueError:
        return None

    expected_signature = hmac.new(
        config.session_secret.encode("utf-8"), payload_b64.encode("ascii"), hashlib.sha256
    ).hexdigest()
    if not hmac.compare_digest(expected_signature, signature):
        return None

    try:
        padded = payload_b64 + "=" * (-len(payload_b64) % 4)
        payload = json.loads(base64.urlsafe_b64decode(padded))
    except Exception:
        return None

    if payload.get("exp", 0) < time.time():
        return None

    return SAMLAssertionClaims(
        sub=payload.get("sub", ""),
        email=payload.get("email"),
        name=payload.get("name"),
        roles=payload.get("roles") or [],
        org_id=payload.get("org_id"),
        raw=payload,
    )
