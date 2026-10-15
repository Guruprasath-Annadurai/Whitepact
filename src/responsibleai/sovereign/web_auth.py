# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Browser session authentication for Sovereign web adapters."""

from __future__ import annotations

import hashlib
import hmac

from fastapi import Depends, HTTPException, Request

from responsibleai.db.web_identity_repository import WebPrincipal
from responsibleai.sovereign.access import assert_sovereign_role, authorize_org_view
from responsibleai.sovereign.api_deps import get_web_identity_repository


def web_token_hash(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


async def get_web_principal(request: Request) -> WebPrincipal:
    token = request.cookies.get("wp_session", "")
    repo = get_web_identity_repository()
    principal = await repo.get_principal(token) if token else None
    if principal is None:
        raise HTTPException(401, "Sign in is required.")
    request.state.audit_org_id = principal.org_id
    request.state.audit_key_id = f"web:{principal.user_id}"
    return principal


async def require_web_csrf(
    request: Request, principal: WebPrincipal = Depends(get_web_principal)
) -> WebPrincipal:
    cookie_token = request.cookies.get("wp_csrf", "")
    header_token = request.headers.get("X-WP-CSRF", "")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(403, "CSRF validation failed.")
    if not hmac.compare_digest(web_token_hash(cookie_token), principal.csrf_hash):
        raise HTTPException(403, "CSRF validation failed.")
    assert_sovereign_role(request.url.path, principal.role)
    await authorize_org_view(principal)
    return principal


async def require_browser_sovereign_read(request: Request) -> WebPrincipal:
    """Canonical browser session for sovereign status and capabilities.

    Safe methods do not require CSRF. They still require a live principal,
    an active tenant, and the shared ORG_VIEW policy.
    """
    principal = await get_web_principal(request)
    if request.query_params.get("organization_id") or request.query_params.get("principal_id"):
        raise HTTPException(400, "organization_id must not be supplied by browser clients.")
    for header in ("organization_id", "x-organization-id", "X-Organization-Id", "x-principal-id"):
        if request.headers.get(header):
            raise HTTPException(400, "organization_id must not be supplied by browser clients.")
    if not principal.org_id or principal.role is None:
        raise HTTPException(401, "Sign in is required.")
    assert_sovereign_role(request.url.path, principal.role)
    await authorize_org_view(principal)
    return principal


async def guard_browser_tenant_override(request: Request) -> None:
    if request.query_params.get("organization_id"):
        raise HTTPException(400, "organization_id must not be supplied by browser clients.")
    for header in ("organization_id", "x-organization-id", "X-Organization-Id"):
        if request.headers.get(header):
            raise HTTPException(400, "organization_id must not be supplied by browser clients.")


def web_organization_id(principal: WebPrincipal) -> str:
    if not principal.org_id:
        raise HTTPException(409, "Complete organization onboarding first.")
    return principal.org_id
