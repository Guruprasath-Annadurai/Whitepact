# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""OAuth 2.1 authorization server for the hosted WhitePact MCP resource.

The implementation is deliberately narrow: public clients, authorization code
with mandatory PKCE S256, rotating refresh tokens, exact ChatGPT redirect URI
validation, and one review scope. Every credential is opaque and persisted only
as a SHA-256 digest.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import re
import secrets
import uuid
from base64 import urlsafe_b64encode
from datetime import UTC, datetime, timedelta
from typing import Any
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from sqlalchemy import insert, select, update

from responsibleai.db.engine import (
    DatabaseEngine,
    oauth_auth_events,
    oauth_authorization_codes,
    oauth_authorization_requests,
    oauth_clients,
    oauth_credentials,
)
from responsibleai.db.org_repository import OrgRepository, SSORequiredError
from responsibleai.rbac.models import OrgContext, Role
from responsibleai.rbac.permissions import role_from_str

_CHATGPT_CALLBACK = re.compile(r"https://chatgpt\.com/connector/oauth/[A-Za-z0-9_-]{1,200}")
_CHATGPT_STABLE_CALLBACK = "https://chatgpt.com/connector_platform_oauth_redirect"
_PKCE_CHALLENGE = re.compile(r"[A-Za-z0-9_-]{43,128}")


class OAuthProtocolError(Exception):
    """A safe OAuth error suitable for a protocol response."""

    def __init__(self, error: str, description: str, *, status_code: int = 400) -> None:
        self.error = error
        self.description = description
        self.status_code = status_code
        super().__init__(description)


def _now() -> datetime:
    return datetime.now(UTC)


def _iso(value: datetime) -> str:
    return value.isoformat()


def _parse_iso(value: str) -> datetime:
    parsed = datetime.fromisoformat(value)
    return parsed if parsed.tzinfo else parsed.replace(tzinfo=UTC)


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _random(prefix: str) -> str:
    return prefix + secrets.token_urlsafe(48)


def _append_query(uri: str, values: dict[str, str]) -> str:
    parts = urlsplit(uri)
    query = parse_qsl(parts.query, keep_blank_values=True)
    query.extend(values.items())
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _valid_chatgpt_redirect(uri: str) -> bool:
    return uri == _CHATGPT_STABLE_CALLBACK or _CHATGPT_CALLBACK.fullmatch(uri) is not None


class McpOAuthAuthorizationServer:
    """Database-backed OAuth server for ChatGPT-hosted MCP connections."""

    def __init__(
        self,
        engine: DatabaseEngine,
        org_repository: OrgRepository,
        *,
        issuer: str,
        resource: str,
        scopes: list[str],
        access_token_ttl_seconds: int = 900,
        refresh_token_ttl_seconds: int = 2_592_000,
    ) -> None:
        self.engine = engine
        self.org_repository = org_repository
        self.issuer = issuer.rstrip("/")
        self.resource = resource
        self.scopes = tuple(dict.fromkeys(scopes))
        self.required_scope = "whitepact:review"
        self.access_token_ttl_seconds = access_token_ttl_seconds
        self.refresh_token_ttl_seconds = refresh_token_ttl_seconds
        if not self.issuer.startswith("https://") or not self.resource.startswith("https://"):
            raise ValueError("OAuth issuer and resource must use HTTPS")
        if self.required_scope not in self.scopes:
            raise ValueError(f"OAuth scopes must include {self.required_scope}")

    def authorization_server_metadata(self) -> dict[str, Any]:
        return {
            "issuer": self.issuer,
            "authorization_endpoint": f"{self.issuer}/oauth/authorize",
            "token_endpoint": f"{self.issuer}/oauth/token",
            "registration_endpoint": f"{self.issuer}/oauth/register",
            "revocation_endpoint": f"{self.issuer}/oauth/revoke",
            "response_types_supported": ["code"],
            "grant_types_supported": ["authorization_code", "refresh_token"],
            "code_challenge_methods_supported": ["S256"],
            "token_endpoint_auth_methods_supported": ["none"],
            "revocation_endpoint_auth_methods_supported": ["none"],
            "scopes_supported": list(self.scopes),
            "authorization_response_iss_parameter_supported": True,
        }

    def protected_resource_metadata(self) -> dict[str, Any]:
        return {
            "resource": self.resource,
            "authorization_servers": [self.issuer],
            "scopes_supported": [self.required_scope, "offline_access"],
            "bearer_methods_supported": ["header"],
            "resource_documentation": (
                "https://github.com/Guruprasath-Annadurai/Whitepact/"
                "blob/main/docs/security/AUTH_INCIDENT_RESPONSE.md"
            ),
        }

    async def register_client(self, payload: dict[str, Any]) -> dict[str, Any]:
        redirect_uris = payload.get("redirect_uris")
        if not isinstance(redirect_uris, list) or not redirect_uris:
            raise OAuthProtocolError("invalid_redirect_uri", "redirect_uris must be non-empty")
        if any(
            not isinstance(uri, str) or not _valid_chatgpt_redirect(uri) for uri in redirect_uris
        ):
            raise OAuthProtocolError(
                "invalid_redirect_uri", "Only exact ChatGPT connector redirect URIs are allowed"
            )
        if payload.get("token_endpoint_auth_method", "none") != "none":
            raise OAuthProtocolError(
                "invalid_client_metadata",
                "Only public clients using token auth method none are supported",
            )
        if set(payload.get("response_types", ["code"])) != {"code"}:
            raise OAuthProtocolError(
                "invalid_client_metadata", "response_types must contain only code"
            )
        grants = set(payload.get("grant_types", ["authorization_code", "refresh_token"]))
        if not grants or not grants.issubset({"authorization_code", "refresh_token"}):
            raise OAuthProtocolError("invalid_client_metadata", "Unsupported grant type")

        client_id = "wp_client_" + secrets.token_urlsafe(24)
        created_at = _now()
        client_name = str(payload.get("client_name") or "ChatGPT")[:200]
        async with self.engine.raw.begin() as connection:
            await connection.execute(
                insert(oauth_clients).values(
                    client_id=client_id,
                    client_name=client_name,
                    redirect_uris=json.dumps(redirect_uris),
                    created_at=_iso(created_at),
                    revoked=0,
                )
            )
        await self._event("client_registered", "success", client_id=client_id)
        return {
            "client_id": client_id,
            "client_id_issued_at": int(created_at.timestamp()),
            "client_name": client_name,
            "redirect_uris": redirect_uris,
            "grant_types": sorted(grants),
            "response_types": ["code"],
            "token_endpoint_auth_method": "none",
        }

    async def begin_authorization(self, params: dict[str, str]) -> tuple[str, str]:
        if params.get("response_type") != "code":
            raise OAuthProtocolError(
                "unsupported_response_type", "Only response_type=code is supported"
            )
        client_id = params.get("client_id", "")
        redirect_uri = params.get("redirect_uri", "")
        client = await self._client(client_id)
        if client is None or redirect_uri not in json.loads(client.redirect_uris):
            raise OAuthProtocolError("invalid_request", "Unknown client or redirect URI")
        state = params.get("state", "")
        if not state or len(state) > 512:
            raise OAuthProtocolError("invalid_request", "A bounded state parameter is required")
        challenge = params.get("code_challenge", "")
        if params.get("code_challenge_method") != "S256" or not _PKCE_CHALLENGE.fullmatch(
            challenge
        ):
            raise OAuthProtocolError("invalid_request", "PKCE S256 is required")
        if params.get("resource") != self.resource:
            raise OAuthProtocolError(
                "invalid_target", "The resource does not match this MCP server"
            )
        scopes = self._parse_scopes(params.get("scope", ""))
        if not scopes or not scopes.issubset(self.scopes):
            raise OAuthProtocolError("invalid_scope", "Requested scope is not supported")

        request_id = _random("wp_ar_")
        async with self.engine.raw.begin() as connection:
            await connection.execute(
                insert(oauth_authorization_requests).values(
                    request_hash=_digest(request_id),
                    client_id=client_id,
                    redirect_uri=redirect_uri,
                    state=state,
                    code_challenge=challenge,
                    scopes=json.dumps(sorted(scopes)),
                    resource=self.resource,
                    expires_at=_iso(_now() + timedelta(minutes=10)),
                    used=0,
                )
            )
        return request_id, str(client.client_name)

    async def complete_authorization(self, request_id: str, api_key: str, action: str) -> str:
        request_row = await self._authorization_request(request_id)
        if request_row is None or request_row.used or _parse_iso(request_row.expires_at) <= _now():
            raise OAuthProtocolError(
                "invalid_request", "Authorization request is invalid or expired"
            )
        if action != "allow":
            await self._consume_authorization_request(request_id)
            await self._event("authorization_denied", "denied", client_id=request_row.client_id)
            return _append_query(
                request_row.redirect_uri,
                {"error": "access_denied", "state": request_row.state, "iss": self.issuer},
            )

        try:
            context = await self.org_repository.authenticate(api_key)
        except SSORequiredError:
            context = None
        if context is None:
            await self._event("authorization_login", "denied", client_id=request_row.client_id)
            raise OAuthProtocolError(
                "access_denied", "Invalid reviewer credential", status_code=401
            )
        if context.role in {Role.OWNER, Role.ADMIN}:
            await self._event(
                "authorization_login",
                "denied",
                org_id=context.org_id,
                subject_id=context.key_id,
                client_id=request_row.client_id,
            )
            raise OAuthProtocolError(
                "access_denied",
                "Administrative credentials cannot authorize an MCP review",
                status_code=403,
            )
        if not context.org_id:
            raise OAuthProtocolError(
                "access_denied", "A tenant-bound credential is required", status_code=403
            )

        consumed = await self._consume_authorization_request(request_id)
        if not consumed:
            raise OAuthProtocolError("invalid_request", "Authorization request was already used")
        code = _random("wp_code_")
        async with self.engine.raw.begin() as connection:
            await connection.execute(
                insert(oauth_authorization_codes).values(
                    code_hash=_digest(code),
                    client_id=request_row.client_id,
                    redirect_uri=request_row.redirect_uri,
                    code_challenge=request_row.code_challenge,
                    org_id=context.org_id,
                    subject_id=context.key_id,
                    role=context.role.value,
                    scopes=request_row.scopes,
                    resource=request_row.resource,
                    expires_at=_iso(_now() + timedelta(minutes=5)),
                    used=0,
                )
            )
        await self._event(
            "authorization_granted",
            "success",
            org_id=context.org_id,
            subject_id=context.key_id,
            client_id=request_row.client_id,
        )
        return _append_query(
            request_row.redirect_uri,
            {"code": code, "state": request_row.state, "iss": self.issuer},
        )

    async def exchange_authorization_code(self, form: dict[str, str]) -> dict[str, Any]:
        if form.get("client_secret"):
            raise OAuthProtocolError(
                "invalid_client",
                "This public client must not send a client secret",
                status_code=401,
            )
        if form.get("resource") != self.resource:
            raise OAuthProtocolError(
                "invalid_target", "The resource does not match this MCP server"
            )
        client_id = form.get("client_id", "")
        if await self._client(client_id) is None:
            raise OAuthProtocolError("invalid_client", "Unknown OAuth client", status_code=401)
        code = form.get("code", "")
        async with self.engine.raw.connect() as connection:
            row = (
                await connection.execute(
                    select(oauth_authorization_codes).where(
                        oauth_authorization_codes.c.code_hash == _digest(code)
                    )
                )
            ).fetchone()
        if (
            row is None
            or row.used
            or _parse_iso(row.expires_at) <= _now()
            or row.client_id != client_id
            or row.redirect_uri != form.get("redirect_uri")
            or row.resource != self.resource
        ):
            raise OAuthProtocolError("invalid_grant", "Authorization code is invalid or expired")
        verifier = form.get("code_verifier", "")
        actual_challenge = (
            urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).decode().rstrip("=")
        )
        if not verifier or not hmac.compare_digest(actual_challenge, row.code_challenge):
            raise OAuthProtocolError("invalid_grant", "PKCE verification failed")
        async with self.engine.raw.begin() as connection:
            result = await connection.execute(
                update(oauth_authorization_codes)
                .where(oauth_authorization_codes.c.code_hash == _digest(code))
                .where(oauth_authorization_codes.c.used == 0)
                .values(used=1)
            )
        if result.rowcount != 1:
            raise OAuthProtocolError("invalid_grant", "Authorization code was already used")
        return await self._issue_tokens(row)

    async def refresh(self, form: dict[str, str]) -> dict[str, Any]:
        if form.get("client_secret"):
            raise OAuthProtocolError(
                "invalid_client",
                "This public client must not send a client secret",
                status_code=401,
            )
        if form.get("resource") != self.resource:
            raise OAuthProtocolError(
                "invalid_target", "The resource does not match this MCP server"
            )
        raw_token = form.get("refresh_token", "")
        row = await self._credential(raw_token)
        if (
            row is None
            or row.token_type != "refresh"
            or row.client_id != form.get("client_id")
            or row.resource != self.resource
        ):
            raise OAuthProtocolError("invalid_grant", "Refresh token is invalid")
        if await self._client(row.client_id) is None:
            raise OAuthProtocolError("invalid_grant", "Refresh token is invalid")
        if row.revoked or row.consumed_at or _parse_iso(row.expires_at) <= _now():
            await self._revoke_family(row.family_id)
            await self._event(
                "refresh_replay",
                "denied",
                org_id=row.org_id,
                subject_id=row.subject_id,
                client_id=row.client_id,
            )
            raise OAuthProtocolError(
                "invalid_grant", "Refresh token is expired, revoked, or replayed"
            )
        async with self.engine.raw.begin() as connection:
            consumed = await connection.execute(
                update(oauth_credentials)
                .where(oauth_credentials.c.token_hash == _digest(raw_token))
                .where(oauth_credentials.c.revoked == 0)
                .where(oauth_credentials.c.consumed_at.is_(None))
                .values(revoked=1, consumed_at=_iso(_now()))
            )
        if consumed.rowcount != 1:
            await self._revoke_family(row.family_id)
            raise OAuthProtocolError("invalid_grant", "Refresh token replay detected")
        return await self._issue_tokens(row, family_id=row.family_id)

    async def revoke(self, raw_token: str) -> None:
        row = await self._credential(raw_token)
        if row is None:
            return
        if row.token_type == "refresh":
            await self._revoke_family(row.family_id)
        else:
            async with self.engine.raw.begin() as connection:
                await connection.execute(
                    update(oauth_credentials)
                    .where(oauth_credentials.c.token_hash == _digest(raw_token))
                    .values(revoked=1)
                )
        await self._event(
            "token_revoked",
            "success",
            org_id=row.org_id,
            subject_id=row.subject_id,
            client_id=row.client_id,
        )

    async def resolve_access_token(self, raw_token: str) -> OrgContext:
        row = await self._credential(raw_token)
        if (
            row is None
            or row.token_type != "access"
            or row.revoked
            or _parse_iso(row.expires_at) <= _now()
            or row.resource != self.resource
        ):
            raise OAuthProtocolError(
                "invalid_token", "Access token is invalid or expired", status_code=401
            )
        scopes = set(json.loads(row.scopes))
        if self.required_scope not in scopes:
            raise OAuthProtocolError(
                "insufficient_scope", "The required review scope is missing", status_code=403
            )
        org = await self.org_repository.get_org(row.org_id)
        key = await self.org_repository.get_key(row.subject_id)
        if (
            org is None
            or key is None
            or key.revoked
            or key.org_id != row.org_id
            or org.sso_required
        ):
            raise OAuthProtocolError(
                "invalid_token", "OAuth session is no longer active", status_code=401
            )
        await self._event(
            "access_token_authenticated",
            "success",
            org_id=row.org_id,
            subject_id=row.subject_id,
            client_id=row.client_id,
        )
        return OrgContext(
            key_id=f"oauth:{row.subject_id}",
            role=role_from_str(row.role),
            org_id=row.org_id,
            org_name=org.name,
            key_name=key.name,
            mfa_enrolled=key.mfa_enrolled,
            is_legacy=False,
            plan=org.plan,
        )

    async def record_access_failure(self, error: str = "invalid_token") -> None:
        """Record a credential-free authentication failure for incident review."""
        await self._event("access_token_authenticated", error)

    async def _issue_tokens(self, grant: Any, *, family_id: str | None = None) -> dict[str, Any]:
        issued = _now()
        access = _random("wp_at_")
        refresh = _random("wp_rt_")
        family = family_id or "wp_family_" + secrets.token_urlsafe(18)
        scopes = set(json.loads(grant.scopes))
        rows = [
            {
                "token_hash": _digest(access),
                "token_type": "access",
                "family_id": family,
                "client_id": grant.client_id,
                "org_id": grant.org_id,
                "subject_id": grant.subject_id,
                "role": grant.role,
                "scopes": json.dumps(sorted(scopes)),
                "resource": self.resource,
                "issued_at": _iso(issued),
                "expires_at": _iso(issued + timedelta(seconds=self.access_token_ttl_seconds)),
                "revoked": 0,
                "consumed_at": None,
            }
        ]
        include_refresh = "offline_access" in scopes
        if include_refresh:
            rows.append(
                {
                    **rows[0],
                    "token_hash": _digest(refresh),
                    "token_type": "refresh",
                    "expires_at": _iso(issued + timedelta(seconds=self.refresh_token_ttl_seconds)),
                }
            )
        async with self.engine.raw.begin() as connection:
            await connection.execute(insert(oauth_credentials), rows)
        await self._event(
            "token_issued",
            "success",
            org_id=grant.org_id,
            subject_id=grant.subject_id,
            client_id=grant.client_id,
        )
        response: dict[str, Any] = {
            "access_token": access,
            "token_type": "Bearer",
            "expires_in": self.access_token_ttl_seconds,
            "scope": " ".join(sorted(scopes)),
        }
        if include_refresh:
            response["refresh_token"] = refresh
        return response

    @staticmethod
    def _parse_scopes(raw: str) -> set[str]:
        return {scope for scope in raw.replace(",", " ").split() if scope}

    async def _client(self, client_id: str) -> Any:
        async with self.engine.raw.connect() as connection:
            row = (
                await connection.execute(
                    select(oauth_clients).where(oauth_clients.c.client_id == client_id)
                )
            ).fetchone()
        return row if row is not None and not row.revoked else None

    async def _authorization_request(self, request_id: str) -> Any:
        async with self.engine.raw.connect() as connection:
            return (
                await connection.execute(
                    select(oauth_authorization_requests).where(
                        oauth_authorization_requests.c.request_hash == _digest(request_id)
                    )
                )
            ).fetchone()

    async def _consume_authorization_request(self, request_id: str) -> bool:
        async with self.engine.raw.begin() as connection:
            result = await connection.execute(
                update(oauth_authorization_requests)
                .where(oauth_authorization_requests.c.request_hash == _digest(request_id))
                .where(oauth_authorization_requests.c.used == 0)
                .values(used=1)
            )
        return result.rowcount == 1

    async def _credential(self, raw_token: str) -> Any:
        if not raw_token:
            return None
        async with self.engine.raw.connect() as connection:
            return (
                await connection.execute(
                    select(oauth_credentials).where(
                        oauth_credentials.c.token_hash == _digest(raw_token)
                    )
                )
            ).fetchone()

    async def _revoke_family(self, family_id: str) -> None:
        async with self.engine.raw.begin() as connection:
            await connection.execute(
                update(oauth_credentials)
                .where(oauth_credentials.c.family_id == family_id)
                .values(revoked=1)
            )

    async def _event(
        self,
        event_type: str,
        outcome: str,
        *,
        org_id: str | None = None,
        subject_id: str | None = None,
        client_id: str | None = None,
    ) -> None:
        async with self.engine.raw.begin() as connection:
            await connection.execute(
                insert(oauth_auth_events).values(
                    id=str(uuid.uuid4()),
                    event_type=event_type,
                    outcome=outcome,
                    org_id=org_id,
                    subject_id=subject_id,
                    client_id=client_id,
                    created_at=_iso(_now()),
                )
            )
