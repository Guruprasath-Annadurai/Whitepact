# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Versioned enterprise SaaS APIs for the future console. No fake frontend."""

from __future__ import annotations

import hmac
import os
from typing import Any

from fastapi import APIRouter, Header, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from responsibleai.enterprise.eligibility import EligibilityGate
from responsibleai.enterprise.errors import UNAUTHENTICATED, EnterpriseError, unauthenticated
from responsibleai.enterprise.roles import Permission, has_rbac_permission
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.enterprise.service import Actor, EnterpriseIAM
from responsibleai.enterprise.verification import HmacVerificationProvider, VerificationService
from responsibleai.rbac.models import Role
from responsibleai.rbac.permissions import role_from_str

router = APIRouter(prefix="/api/enterprise", tags=["enterprise-saas"])


class CreateWorkspaceBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    slug: str = Field(min_length=2, max_length=100)
    kind: str = Field(default="ORGANIZATION")


class UpdateOrgBody(BaseModel):
    display_name: str | None = None
    settings: dict[str, Any] | None = None


class TransferBody(BaseModel):
    new_owner_user_id: str
    confirmation: str


class InviteBody(BaseModel):
    email: str
    role: str


class AcceptInviteBody(BaseModel):
    token: str


class RoleBody(BaseModel):
    role: str


class EnvironmentBody(BaseModel):
    type: str
    name: str


class EnvironmentStatusBody(BaseModel):
    status: str


class CreateKeyBody(BaseModel):
    name: str
    environment_id: str
    scopes: list[str]
    expires_at: str | None = None


class RotateKeyBody(BaseModel):
    overlap_seconds: int = 0


class ServiceAccountBody(BaseModel):
    display_name: str
    role: str
    environment_ids: list[str] = Field(default_factory=list)


class EligibilityQuery(BaseModel):
    environment_id: str
    scopes: list[str] = Field(default_factory=list)


def _error_response(exc: EnterpriseError, request_id: str | None) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={**exc.as_detail(), "status_code": exc.http_status, "request_id": request_id},
    )


def _request_id(request: Request) -> str | None:
    return getattr(request.state, "request_id", None)


def _iam() -> EnterpriseIAM:
    return EnterpriseIAM(get_enterprise_engine())


def _verification() -> VerificationService:
    secret = os.environ.get("WHITEPACT_IDENTITY_WEBHOOK_SECRET", "dev-identity-webhook-secret")
    return VerificationService(get_enterprise_engine(), HmacVerificationProvider(secret))


async def _web_actor(request: Request) -> Actor:
    from responsibleai.db.web_identity_repository import WebIdentityRepository

    token = request.cookies.get("wp_session", "")
    if not token:
        raise unauthenticated()
    repo = WebIdentityRepository(get_enterprise_engine())
    principal = await repo.get_principal(token)
    if principal is None or principal.org_id is None or principal.role is None:
        raise unauthenticated("Sign in with an active organization membership is required.")
    if request.method.upper() not in {"GET", "HEAD"}:
        csrf_cookie = request.cookies.get("wp_csrf", "")
        csrf_header = request.headers.get("X-WP-CSRF", "")
        if not csrf_cookie or not hmac.compare_digest(csrf_cookie, csrf_header):
            raise EnterpriseError("FORBIDDEN", "CSRF validation failed.", 403)
        from responsibleai.db.web_identity_repository import _hash

        if _hash(csrf_cookie) != principal.csrf_hash:
            raise EnterpriseError("FORBIDDEN", "CSRF validation failed.", 403)
    return Actor(
        actor_type="human",
        actor_id=principal.user_id,
        user_id=principal.user_id,
        org_id=principal.org_id,
        role=principal.role,
        membership_status="ACTIVE",
        request_id=_request_id(request),
    )


@router.get("/session")
async def enterprise_session(request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        iam = _iam()
        orgs = await iam.list_visible_workspaces(actor.user_id or "")
        return {
            "user_id": actor.user_id,
            "active_org_id": actor.org_id,
            "role": actor.role.value,
            "organizations": orgs,
        }
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/workspaces")
async def create_workspace(request: Request, body: CreateWorkspaceBody) -> Any:
    try:
        actor = await _web_actor(request)
        org = await _iam().create_workspace(
            actor_user_id=actor.user_id or "",
            name=body.name,
            slug=body.slug,
            kind=body.kind,
            request_id=actor.request_id,
        )
        return {"organization": _public_org(org)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/organizations")
async def list_organizations(request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return {"organizations": await _iam().list_visible_workspaces(actor.user_id or "")}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.patch("/organizations/{org_id}")
async def update_organization(org_id: str, request: Request, body: UpdateOrgBody) -> Any:
    try:
        actor = await _require_org(request, org_id)
        org = await _iam().update_settings(
            actor, org_id, display_name=body.display_name, settings=body.settings
        )
        return {"organization": _public_org(org)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/organizations/{org_id}/deactivate")
async def deactivate_organization(org_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        await _iam().deactivate_organization(actor, org_id)
        return {"ok": True}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/organizations/{org_id}/transfer-ownership")
async def transfer_ownership(org_id: str, request: Request, body: TransferBody) -> Any:
    try:
        actor = await _require_org(request, org_id)
        await _iam().transfer_ownership(
            actor, org_id, new_owner_user_id=body.new_owner_user_id, confirmation=body.confirmation
        )
        return {"ok": True}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/organizations/{org_id}/members")
async def list_members(org_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        return {"members": await _iam().list_members(actor, org_id)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/organizations/{org_id}/invitations")
async def invite_member(org_id: str, request: Request, body: InviteBody) -> Any:
    try:
        actor = await _require_org(request, org_id)
        invitation_id, token = await _iam().invite_member(
            actor, org_id, email=body.email, role=role_from_str(body.role)
        )
        # Token is returned once to the inviting admin for delivery; never logged.
        return {"invitation_id": invitation_id, "token": token, "status": "INVITED"}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/invitations/accept")
async def accept_invitation(request: Request, body: AcceptInviteBody) -> Any:
    try:
        actor = await _web_actor(request)
        org_id = await _iam().accept_invitation(
            token=body.token, user_id=actor.user_id or "", request_id=actor.request_id
        )
        return {"org_id": org_id}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.patch("/organizations/{org_id}/members/{user_id}")
async def change_role(org_id: str, user_id: str, request: Request, body: RoleBody) -> Any:
    try:
        actor = await _require_org(request, org_id)
        await _iam().change_role(actor, org_id, user_id=user_id, role=role_from_str(body.role))
        return {"ok": True}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.delete("/organizations/{org_id}/members/{user_id}")
async def revoke_member(org_id: str, user_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        await _iam().revoke_member(actor, org_id, user_id=user_id)
        return {"ok": True}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/organizations/{org_id}/environments")
async def list_environments(org_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        return {"environments": await _iam().list_environments(actor, org_id)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/organizations/{org_id}/environments")
async def create_environment(org_id: str, request: Request, body: EnvironmentBody) -> Any:
    try:
        actor = await _require_org(request, org_id)
        env = await _iam().create_environment(actor, org_id, env_type=body.type, name=body.name)
        return {"environment": env}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.patch("/organizations/{org_id}/environments/{environment_id}")
async def change_environment(
    org_id: str, environment_id: str, request: Request, body: EnvironmentStatusBody
) -> Any:
    try:
        actor = await _require_org(request, org_id)
        await _iam().set_environment_status(actor, org_id, environment_id, body.status)
        return {"ok": True}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/organizations/{org_id}/api-keys")
async def list_keys(org_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        return {"api_keys": await _iam().list_api_keys(actor, org_id)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/organizations/{org_id}/api-keys/eligibility")
async def key_eligibility(org_id: str, request: Request, environment_id: str, scopes: str = "") -> Any:
    try:
        actor = await _require_org(request, org_id)
        requested = tuple(s for s in scopes.split(",") if s)
        gate = EligibilityGate(get_enterprise_engine(), _verification())
        decision = await gate.may_issue_api_key(
            principal_user_id=actor.user_id or "",
            organization_id=org_id,
            environment_id=environment_id,
            requested_scopes=requested,
            role=actor.role,
            request_id=actor.request_id,
        )
        await _iam().record_issuance_decision(
            org_id=org_id,
            principal_user_id=actor.user_id,
            environment_id=environment_id,
            allowed=decision.allowed,
            reason_code=decision.reason_code,
            requested_scopes=requested,
        )
        return {
            "allowed": decision.allowed,
            "reason_code": decision.reason_code,
            "message": decision.message,
            "environment_type": decision.environment_type,
        }
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/organizations/{org_id}/api-keys")
async def create_key(org_id: str, request: Request, body: CreateKeyBody) -> Any:
    try:
        actor = await _require_org(request, org_id)
        if not has_rbac_permission(actor.role, Permission.API_KEYS_CREATE):
            raise EnterpriseError("FORBIDDEN", "Role cannot issue API keys.", 403)
        gate = EligibilityGate(get_enterprise_engine(), _verification())
        decision = await gate.may_issue_api_key(
            principal_user_id=actor.user_id or "",
            organization_id=org_id,
            environment_id=body.environment_id,
            requested_scopes=tuple(body.scopes),
            role=actor.role,
            request_id=actor.request_id,
        )
        await _iam().record_issuance_decision(
            org_id=org_id,
            principal_user_id=actor.user_id,
            environment_id=body.environment_id,
            allowed=decision.allowed,
            reason_code=decision.reason_code,
            requested_scopes=tuple(body.scopes),
        )
        if not decision.allowed:
            raise EnterpriseError(decision.reason_code, decision.message, 403)
        record, raw = await _iam().create_api_key(
            actor,
            org_id,
            name=body.name,
            environment_id=body.environment_id,
            scopes=tuple(body.scopes),
            expires_at=body.expires_at,
        )
        return {"api_key": record, "secret": raw}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/organizations/{org_id}/api-keys/{key_id}/rotate")
async def rotate_key(org_id: str, key_id: str, request: Request, body: RotateKeyBody) -> Any:
    try:
        actor = await _require_org(request, org_id)
        record, raw = await _iam().rotate_api_key(
            actor, org_id, key_id, overlap_seconds=body.overlap_seconds
        )
        return {"api_key": record, "secret": raw}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.delete("/organizations/{org_id}/api-keys/{key_id}")
async def revoke_key(org_id: str, key_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        await _iam().revoke_api_key(actor, org_id, key_id)
        return {"ok": True}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/organizations/{org_id}/service-accounts")
async def list_service_accounts(org_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        return {"service_accounts": await _iam().list_service_accounts(actor, org_id)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/organizations/{org_id}/service-accounts")
async def create_service_account(org_id: str, request: Request, body: ServiceAccountBody) -> Any:
    try:
        actor = await _require_org(request, org_id)
        sa = await _iam().create_service_account(
            actor,
            org_id,
            display_name=body.display_name,
            role=role_from_str(body.role),
            environment_ids=tuple(body.environment_ids),
        )
        return {"service_account": sa}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.delete("/organizations/{org_id}/service-accounts/{service_account_id}")
async def revoke_service_account(org_id: str, service_account_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        await _iam().revoke_service_account(actor, org_id, service_account_id)
        return {"ok": True}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/organizations/{org_id}/security/sessions")
async def list_sessions(org_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        return {"sessions": await _iam().list_sessions(actor, org_id, actor.user_id or "")}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/organizations/{org_id}/security/logout-all")
async def logout_all(org_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        count = await _iam().logout_all(actor.user_id or "", request_id=actor.request_id)
        return {"revoked": count}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/identity/verification")
async def get_identity_verification(request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return await _verification().get_human_status(actor.user_id or "")
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/identity/verification/start")
async def start_identity_verification(request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return await _verification().start_human_verification(
            actor.user_id or "", request_id=actor.request_id
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/organizations/{org_id}/verification")
async def get_org_verification(org_id: str, request: Request) -> Any:
    try:
        await _require_org(request, org_id)
        return await _verification().get_org_status(org_id)
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/organizations/{org_id}/verification/start")
async def start_org_verification(org_id: str, request: Request) -> Any:
    try:
        actor = await _require_org(request, org_id)
        return await _verification().start_org_verification(
            org_id, actor_user_id=actor.user_id or "", request_id=actor.request_id
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/identity/verification/webhook")
async def identity_webhook(
    request: Request,
    x_identity_signature: str = Header(default=""),
    x_identity_timestamp: str = Header(default=""),
) -> Any:
    try:
        payload = await request.body()
        result = await _verification().apply_provider_event(
            payload=payload,
            signature=x_identity_signature,
            timestamp=x_identity_timestamp,
            request_id=_request_id(request),
        )
        return result
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


async def _require_org(request: Request, org_id: str) -> Actor:
    actor = await _web_actor(request)
    if actor.org_id != org_id:
        # Switching is explicit; deny rather than substituting another tenant.
        if not has_rbac_permission(actor.role, Permission.ORG_VIEW):
            raise EnterpriseError("FORBIDDEN", "Not permitted.", 403)
        from responsibleai.db.web_identity_repository import WebIdentityRepository
        from sqlalchemy import select

        from responsibleai.db.engine import web_memberships

        engine = get_enterprise_engine()
        async with engine.raw.connect() as conn:
            row = (
                await conn.execute(
                    select(web_memberships).where(
                        web_memberships.c.user_id == actor.user_id,
                        web_memberships.c.org_id == org_id,
                        web_memberships.c.status == "ACTIVE",
                    )
                )
            ).fetchone()
        if row is None:
            raise EnterpriseError("WRONG_TENANT", "Not a member of this organization.", 403)
        return Actor(
            actor_type="human",
            actor_id=actor.actor_id,
            user_id=actor.user_id,
            org_id=org_id,
            role=role_from_str(row.role),
            membership_status=row.status,
            request_id=actor.request_id,
        )
    return actor


def _public_org(org: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": org["id"],
        "name": org["name"],
        "slug": org["slug"],
        "workspace_kind": org.get("workspace_kind"),
        "governance_status": org.get("governance_status"),
        "owner_user_id": org.get("owner_user_id"),
        "created_at": org.get("created_at"),
    }


# Silence unused Role import if any type checkers complain via usage above.
_ = (Role, UNAUTHENTICATED)
