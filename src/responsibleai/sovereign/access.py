# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authenticated tenant boundary for /api/sovereign.

Uses the existing web principal (session cookie or bearer session token)
and EnterpriseIAM. Client-supplied organization ids never select a tenant.
"""

from __future__ import annotations

from contextvars import ContextVar

from fastapi import HTTPException, Request

from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.roles import Permission, has_rbac_permission, role_privilege
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.rbac.models import Role
from responsibleai.sovereign.api_deps import get_bound_engine, get_web_identity_repository

_sovereign_org: ContextVar[str | None] = ContextVar("sovereign_org", default=None)
_sovereign_principal: ContextVar[str | None] = ContextVar("sovereign_principal", default=None)

_PRIVILEGED_RANK = role_privilege(Role.SECURITY_ADMIN)


def is_sovereign_view_path(path: str) -> bool:
    """Status and capabilities are the only sovereign reads open to ORG_VIEW."""
    normalized = path.rstrip("/") or path
    return normalized.endswith("/sovereign/status") or normalized.endswith(
        "/sovereign/capabilities"
    )


def assert_sovereign_role(path: str, role: Role | None) -> None:
    """Shared browser and machine privilege policy.

    Status and capabilities require ORG_VIEW. Every other sovereign operation
    requires security-admin equivalent privilege so a browser route cannot
    undercut the machine route.
    """
    if role is None:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    if is_sovereign_view_path(path):
        if not has_rbac_permission(role, Permission.ORG_VIEW):
            raise HTTPException(status_code=403, detail="Forbidden.")
        return
    if role_privilege(role) < _PRIVILEGED_RANK:
        raise HTTPException(status_code=403, detail="Forbidden.")


async def authorize_org_view(principal) -> None:
    """Require an active tenant membership through the existing IAM service."""
    if principal is None or principal.role is None or not principal.org_id:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    engine = get_bound_engine()
    if engine is None:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    actor = Actor(
        actor_type="human",
        actor_id=principal.user_id,
        user_id=principal.user_id,
        org_id=principal.org_id,
        role=principal.role,
        membership_status="ACTIVE",
    )
    try:
        await EnterpriseIAM(engine).authorize(
            actor,
            Permission.ORG_VIEW,
            org_id=principal.org_id,
        )
    except EnterpriseError as exc:
        raise HTTPException(status_code=403, detail="Forbidden.") from exc


def bound_organization_id() -> str | None:
    return _sovereign_org.get()


def bound_principal_id() -> str | None:
    return _sovereign_principal.get()


def assert_same_tenant(requested_organization_id: str | None) -> str:
    """Return the principal org, or 404 when the client names another tenant."""
    org_id = _sovereign_org.get()
    if not org_id:
        raise HTTPException(status_code=401, detail="Sign in is required.")
    if requested_organization_id is not None and requested_organization_id != org_id:
        raise HTTPException(status_code=404, detail="Not found")
    return org_id


async def enforce_sovereign_access(request: Request):
    principal = await _principal_from_request(request)
    if principal is None or principal.role is None or not principal.org_id:
        raise HTTPException(status_code=401, detail="Sign in is required.")

    assert_sovereign_role(request.url.path, principal.role)
    await authorize_org_view(principal)

    org_token = _sovereign_org.set(principal.org_id)
    principal_token = _sovereign_principal.set(f"web:{principal.user_id}")
    request.state.audit_org_id = principal.org_id
    request.state.audit_key_id = f"web:{principal.user_id}"
    try:
        yield
    finally:
        _sovereign_org.reset(org_token)
        _sovereign_principal.reset(principal_token)


async def _principal_from_request(request: Request):
    try:
        repo = get_web_identity_repository()
    except RuntimeError:
        return None
    if get_bound_engine() is None:
        return None
    header = request.headers.get("Authorization", "")
    if header.startswith("Bearer "):
        token = header[7:].strip()
        if token:
            return await repo.get_principal(token)
    cookie = request.cookies.get("wp_session", "")
    if not cookie:
        return None
    principal = await repo.get_principal(cookie)
    if principal is None:
        return None
    if request.method.upper() not in {"GET", "HEAD", "OPTIONS"}:
        _require_cookie_csrf(request, principal.csrf_hash)
    return principal


def _require_cookie_csrf(request: Request, csrf_hash: str) -> None:
    import hashlib
    import hmac

    cookie_token = request.cookies.get("wp_csrf", "")
    header_token = request.headers.get("X-WP-CSRF", "")
    if not cookie_token or not header_token or not hmac.compare_digest(cookie_token, header_token):
        raise HTTPException(status_code=403, detail="Forbidden.")
    digest = hashlib.sha256(cookie_token.encode()).hexdigest()
    if not hmac.compare_digest(digest, csrf_hash):
        raise HTTPException(status_code=403, detail="Forbidden.")
