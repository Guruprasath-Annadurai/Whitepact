# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Server-side confidential OAuth/OIDC authorization-code + PKCE transactions.

Hosted login never accepts a browser-supplied id_token as the login artifact.
Transaction state is durable in PostgreSQL (or the active DatabaseEngine).
Authorization codes, tokens, PKCE verifiers, and client secrets are never logged.
"""

from __future__ import annotations

import hashlib
import logging
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import urlencode, urlparse

from sqlalchemy import insert, select, update
from sqlalchemy.exc import IntegrityError, SQLAlchemyError

from responsibleai.db.engine import (
    DatabaseEngine,
    auth_replay_records,
    identity_oauth_transactions,
)
from responsibleai.enterprise.errors import (
    CHALLENGE_REPLAY,
    PROVIDER_TOKEN_INVALID,
    EnterpriseError,
    forbidden,
)
from responsibleai.enterprise.security.oidc import OIDCTokenValidator, VerifiedIDToken, issuer_host
from responsibleai.net.egress import (
    DestinationPolicy,
    create_safe_async_client,
    validate_outbound_url,
)

logger = logging.getLogger(__name__)

TRANSACTION_TTL_SECONDS = 300
GOOGLE_AUTH_ENDPOINT = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_ENDPOINT = "https://oauth2.googleapis.com/token"
GOOGLE_ISSUER = "https://accounts.google.com"
MICROSOFT_AUTH_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/authorize"
MICROSOFT_TOKEN_ENDPOINT = "https://login.microsoftonline.com/common/oauth2/v2.0/token"
MICROSOFT_JWKS = "https://login.microsoftonline.com/common/discovery/v2.0/keys"


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime | None = None) -> str:
    return (value or _now()).isoformat()


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()  # codeql[py/weak-sensitive-data-hashing]


def _b64url_nopad(raw: bytes) -> str:
    import base64

    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def generate_pkce() -> tuple[str, str]:
    verifier = _b64url_nopad(secrets.token_bytes(32))
    challenge = _b64url_nopad(hashlib.sha256(verifier.encode("ascii")).digest())
    return verifier, challenge


def raw_id_token_login_allowed() -> bool:
    import os

    from responsibleai.dashboard.config import is_production_environment

    env = os.environ.get("WHITEPACT_ENV") or os.environ.get("RAI_ENV") or "development"
    if is_production_environment(env):
        return False
    flag = (
        os.environ.get("WHITEPACT_OIDC_ALLOW_RAW_ID_TOKEN")
        or os.environ.get("RAI_OIDC_ALLOW_RAW_ID_TOKEN")
        or ""
    )
    return flag.strip().lower() in {"1", "true", "yes"}


@dataclass(frozen=True)
class OAuthTransaction:
    provider: str
    state: str
    nonce: str
    redirect_uri: str
    pkce_verifier: str
    intended_org_id: str | None
    session_id: str | None


class HostedOAuthService:
    def __init__(self, engine: DatabaseEngine) -> None:
        self.engine = engine

    async def begin(
        self,
        *,
        provider: str,
        redirect_uri: str,
        client_id: str,
        intended_org_id: str | None = None,
        session_id: str | None = None,
        extra_auth_params: dict[str, str] | None = None,
    ) -> dict[str, str]:
        parsed = urlparse(redirect_uri)
        if parsed.scheme not in {"https", "http"} or not parsed.netloc or "*" in redirect_uri:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Callback redirect URI is not pre-registered.")
        state = secrets.token_urlsafe(32)
        nonce = secrets.token_urlsafe(32)
        verifier, challenge = generate_pkce()
        provider_key = provider.upper()
        try:
            async with self.engine.raw.begin() as conn:
                await conn.execute(
                    insert(identity_oauth_transactions).values(
                        state_hash=_hash(state),
                        provider=provider_key,
                        nonce=_hash(nonce),
                        pkce_verifier=verifier,
                        redirect_uri=redirect_uri,
                        intended_org_id=intended_org_id,
                        session_id=session_id,
                        status="PENDING",
                        created_at=_iso(),
                        expires_at=_iso(_now() + timedelta(seconds=TRANSACTION_TTL_SECONDS)),
                        consumed_at=None,
                        code_hash=None,
                    )
                )
        except SQLAlchemyError as exc:
            raise EnterpriseError(
                "IDENTITY_PROTECTION_UNAVAILABLE",
                "OAuth transaction storage is unavailable.",
                503,
            ) from exc
        if provider_key == "GOOGLE":
            auth_ep = GOOGLE_AUTH_ENDPOINT
            scope = "openid email profile"
        elif provider_key == "MICROSOFT":
            auth_ep = MICROSOFT_AUTH_ENDPOINT
            scope = "openid email profile"
        else:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Unknown hosted identity provider.")
        params = {
            "response_type": "code",
            "client_id": client_id,
            "redirect_uri": redirect_uri,
            "scope": scope,
            "state": state,
            "nonce": nonce,
            "code_challenge": challenge,
            "code_challenge_method": "S256",
        }
        if extra_auth_params:
            params.update(extra_auth_params)
        return {
            "authorization_url": f"{auth_ep}?{urlencode(params)}",
            "state": state,
            "nonce": nonce,
            "redirect_uri": redirect_uri,
        }

    async def consume_and_validate_callback(
        self,
        *,
        provider: str,
        state: str,
        code: str,
        redirect_uri: str,
        client_id: str,
        client_secret: str,
        jwks_url: str,
        issuer: str,
        expected_tenant: str | None = None,
        microsoft_issuer_hosts: bool = False,
    ) -> tuple[VerifiedIDToken, OAuthTransaction]:
        if not code or not state:
            raise forbidden(
                PROVIDER_TOKEN_INVALID, "Authorization code flow requires state and code."
            )
        now = _iso()
        try:
            async with self.engine.raw.begin() as conn:
                row = (
                    await conn.execute(
                        select(identity_oauth_transactions).where(
                            identity_oauth_transactions.c.state_hash == _hash(state)
                        )
                    )
                ).fetchone()
                if row is None:
                    raise forbidden(PROVIDER_TOKEN_INVALID, "Unknown OAuth state.")
                if row.status != "PENDING" or row.consumed_at is not None:
                    raise EnterpriseError(CHALLENGE_REPLAY, "OAuth state already consumed.", 401)
                if now >= row.expires_at:
                    raise forbidden(PROVIDER_TOKEN_INVALID, "OAuth transaction expired.")
                if row.provider != provider.upper():
                    raise forbidden(PROVIDER_TOKEN_INVALID, "OAuth provider mismatch.")
                if row.redirect_uri != redirect_uri:
                    raise forbidden(PROVIDER_TOKEN_INVALID, "Callback redirect binding mismatch.")
                result = await conn.execute(
                    update(identity_oauth_transactions)
                    .where(
                        identity_oauth_transactions.c.state_hash == _hash(state),
                        identity_oauth_transactions.c.status == "PENDING",
                        identity_oauth_transactions.c.consumed_at.is_(None),
                    )
                    .values(consumed_at=now, status="CONSUMED", code_hash=_hash(code))
                )
                if (result.rowcount or 0) != 1:
                    raise EnterpriseError(CHALLENGE_REPLAY, "OAuth state already consumed.", 401)
                txn = OAuthTransaction(
                    provider=row.provider,
                    state=state,
                    nonce=row.nonce,
                    redirect_uri=row.redirect_uri,
                    pkce_verifier=row.pkce_verifier,
                    intended_org_id=row.intended_org_id,
                    session_id=row.session_id,
                )
        except EnterpriseError:
            raise
        except SQLAlchemyError as exc:
            raise EnterpriseError(
                "IDENTITY_PROTECTION_UNAVAILABLE",
                "OAuth transaction storage is unavailable.",
                503,
            ) from exc
        try:
            await self._reject_code_replay(code)
        except IntegrityError as exc:
            raise EnterpriseError(
                CHALLENGE_REPLAY, "Authorization code replay denied.", 401
            ) from exc
        tokens = await exchange_authorization_code(
            token_url=GOOGLE_TOKEN_ENDPOINT
            if provider.upper() == "GOOGLE"
            else MICROSOFT_TOKEN_ENDPOINT,
            client_id=client_id,
            client_secret=client_secret,
            code=code,
            redirect_uri=redirect_uri,
            code_verifier=txn.pkce_verifier,
        )
        id_token = str(tokens.get("id_token") or "")
        if not id_token:
            raise forbidden(PROVIDER_TOKEN_INVALID, "Token response omitted id_token.")
        validator = OIDCTokenValidator(
            issuer=issuer,
            audience=client_id,
            jwks_url=jwks_url,
            strict_issuer=not microsoft_issuer_hosts,
            allowed_issuer_hosts=frozenset({"login.microsoftonline.com"})
            if microsoft_issuer_hosts
            else None,
        )
        claims = await validator.validate(
            id_token, expected_nonce=None, expected_tenant=expected_tenant
        )
        if _hash(str(claims.nonce or "")) != txn.nonce:
            raise forbidden(PROVIDER_TOKEN_INVALID, "OIDC nonce mismatch.")
        return claims, txn

    async def _reject_code_replay(self, code: str) -> None:
        async with self.engine.raw.begin() as conn:
            await conn.execute(
                insert(auth_replay_records).values(
                    id=secrets.token_hex(16),
                    kind="oidc_authorization_code",
                    replay_key=_hash(code)[:128],
                    created_at=_iso(),
                )
            )


async def exchange_authorization_code(
    *,
    token_url: str,
    client_id: str,
    client_secret: str,
    code: str,
    redirect_uri: str,
    code_verifier: str,
) -> dict[str, Any]:
    if issuer_host(token_url) not in {
        "oauth2.googleapis.com",
        "www.googleapis.com",
        "accounts.google.com",
        "login.microsoftonline.com",
    }:
        raise forbidden(
            PROVIDER_TOKEN_INVALID, "Token endpoint host is not a trusted identity provider."
        )
    validate_outbound_url(token_url, DestinationPolicy.PUBLIC_ONLY)
    body = {
        "grant_type": "authorization_code",
        "code": code,
        "redirect_uri": redirect_uri,
        "client_id": client_id,
        "client_secret": client_secret,
        "code_verifier": code_verifier,
    }
    try:
        async with create_safe_async_client(
            timeout=5.0, policy=DestinationPolicy.PUBLIC_ONLY
        ) as client:
            response = await client.post(token_url, data=body)
            if response.status_code >= 400:
                logger.warning("oidc_token_exchange_failed status=%s", response.status_code)
                raise forbidden(
                    PROVIDER_TOKEN_INVALID, "Authorization code exchange failed closed."
                )
            data = response.json()
    except EnterpriseError:
        raise
    except Exception as exc:
        logger.warning("oidc_token_exchange_error")
        raise forbidden(
            PROVIDER_TOKEN_INVALID, "Authorization code exchange failed closed."
        ) from exc
    if not isinstance(data, dict):
        raise forbidden(PROVIDER_TOKEN_INVALID, "Token response is malformed.")
    if data.get("error"):
        logger.warning("oidc_token_exchange_provider_error")
        raise forbidden(PROVIDER_TOKEN_INVALID, "Authorization code exchange failed closed.")
    return data
