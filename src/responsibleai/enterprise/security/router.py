# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Layer 2 identity security HTTP APIs for the future console. No security logic in the frontend."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from responsibleai.enterprise.errors import EnterpriseError, unauthenticated
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.enterprise.security.policy import SensitiveAction
from responsibleai.enterprise.security.service import IdentitySecurityService

router = APIRouter(prefix="/api/enterprise", tags=["enterprise-identity-security"])


class PasskeyFinishBody(BaseModel):
    client_data_json: str
    authenticator_data: str
    signature: str | None = None
    credential_id: str | None = None
    display_name: str = "Passkey"
    transports: list[str] = Field(default_factory=list)
    grant: str | None = None


class TotpConfirmBody(BaseModel):
    code: str


class RecoveryCodesBody(BaseModel):
    grant: str


class RecoveryConsumeBody(BaseModel):
    token: str
    recovery_code: str | None = None


class StepUpBody(BaseModel):
    action: str
    grant: str | None = None


class OAuthCallbackBody(BaseModel):
    state: str
    code: str
    redirect_uri: str | None = None
    org_id: str | None = None


class FourEyesRequestBody(BaseModel):
    action: str
    parameters: dict[str, Any] = Field(default_factory=dict)
    grant: str | None = None


class FourEyesApproveBody(BaseModel):
    request_id: str
    grant: str | None = None


class SsoConfigBody(BaseModel):
    protocol: str
    issuer: str
    client_id: str
    client_secret: str | None = None
    redirect_uri: str
    enforcement: str = "SSO_OPTIONAL"
    provisioning: str = "INVITE_ONLY"
    grant: str
    idp_entity_id: str | None = None
    idp_sso_url: str | None = None
    idp_x509_cert: str | None = None
    four_eyes_id: str | None = None


def _error(exc: EnterpriseError, request: Request) -> JSONResponse:
    return JSONResponse(
        status_code=exc.http_status,
        content={
            **exc.as_detail(),
            "status_code": exc.http_status,
            "request_id": getattr(request.state, "request_id", None),
        },
    )


def _svc() -> IdentitySecurityService:
    return IdentitySecurityService(get_enterprise_engine())


async def _session(request: Request):
    token = request.cookies.get("wp_session", "")
    if not token:
        raise unauthenticated()
    if request.method.upper() not in {"GET", "HEAD"}:
        csrf_cookie = request.cookies.get("wp_csrf", "")
        header = (
            request.headers.get("x-whitepact-csrf") or request.headers.get("x-csrf-token") or ""
        )
        if not csrf_cookie or csrf_cookie != header:
            raise EnterpriseError("FORBIDDEN", "CSRF validation failed.", 403)
    return await _svc().load_session(
        token if "." in token else f"{token}.{request.cookies.get('wp_csrf', '')}"
    )


@router.post("/passkeys/register/begin")
async def passkey_register_begin(request: Request) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        return await _svc().begin_webauthn(
            user_id=assurance.user_id, session_id=assurance.session_id, ceremony="register"
        )
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/passkeys/register/finish")
async def passkey_register_finish(request: Request, body: PasskeyFinishBody) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        return await _svc().finish_passkey_registration(
            user_id=assurance.user_id,
            session=assurance,
            client_data_b64=body.client_data_json,
            authenticator_data_b64=body.authenticator_data,
            display_name=body.display_name,
            transports=body.transports,
            grant=body.grant,
        )
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/passkeys/authenticate/begin")
async def passkey_auth_begin(request: Request) -> Any:
    try:
        return await _svc().begin_webauthn(user_id=None, session_id=None, ceremony="authenticate")
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/passkeys/authenticate/finish")
async def passkey_auth_finish(request: Request, body: PasskeyFinishBody) -> Any:
    try:
        token, _csrf, assurance = await _svc().authenticate_passkey(
            client_data_b64=body.client_data_json,
            authenticator_data_b64=body.authenticator_data,
            signature_b64=body.signature or "",
            credential_id=body.credential_id or "",
        )
        return {"status": "AUTHENTICATED", "assurance": assurance.level, "session_token": token}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.get("/passkeys")
async def list_passkeys(request: Request) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        return {"passkeys": await _svc().list_passkeys(assurance.user_id)}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/mfa/totp/start")
async def totp_start(request: Request) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        return await _svc().start_totp(assurance.user_id)
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/mfa/totp/confirm")
async def totp_confirm(request: Request, body: TotpConfirmBody) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        await _svc().confirm_totp(assurance.user_id, body.code)
        return {"status": "ACTIVE"}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.get("/sessions")
async def sessions(request: Request) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        return {"sessions": await _svc().list_sessions(assurance.user_id)}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/sessions/logout-all")
async def logout_all(request: Request, body: RecoveryCodesBody) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        await _svc().require_step_up(
            assurance,
            SensitiveAction.REVOKE_ALL_SESSIONS,
            org_id=assurance.org_id,
            grant=body.grant,
        )
        count = await _svc().revoke_all_sessions(assurance.user_id)
        return {"revoked": count}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/recovery/codes")
async def recovery_codes(request: Request, body: RecoveryCodesBody) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        codes = await _svc().issue_recovery_codes(
            assurance.user_id, session=assurance, grant=body.grant
        )
        return {"codes": codes, "reveal": "once"}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/recovery/request")
async def recovery_request(request: Request) -> Any:
    payload = await request.json()
    await _svc().request_recovery(str(payload.get("email", "")))
    return {"status": "accepted"}


@router.post("/recovery/consume")
async def recovery_consume(request: Request, body: RecoveryConsumeBody) -> Any:
    try:
        user_id = await _svc().consume_recovery_token(body.token, recovery_code=body.recovery_code)
        return {"status": "RECOVERY_CONSUMED", "user_id": user_id}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/security/step-up")
async def step_up(request: Request, body: StepUpBody) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        grant = await _svc().issue_step_up(assurance, body.action, org_id=assurance.org_id)
        return {"grant": grant, "action": body.action}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/identity-providers/google/authorize")
async def google_authorize(request: Request) -> Any:
    try:
        payload = await request.json()
        return await _svc().begin_hosted_oauth(
            provider="GOOGLE",
            redirect_uri=payload.get("redirect_uri"),
            intended_org_id=payload.get("org_id"),
        )
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/identity-providers/google/callback")
async def google_callback(request: Request, body: OAuthCallbackBody) -> Any:
    try:
        return await _svc().complete_hosted_oauth(
            provider="GOOGLE",
            state=body.state,
            code=body.code,
            redirect_uri=body.redirect_uri,
        )
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/identity-providers/microsoft/authorize")
async def microsoft_authorize(request: Request) -> Any:
    try:
        payload = await request.json()
        return await _svc().begin_hosted_oauth(
            provider="MICROSOFT",
            redirect_uri=payload.get("redirect_uri"),
            intended_org_id=payload.get("org_id"),
        )
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/identity-providers/microsoft/callback")
async def microsoft_callback(request: Request, body: OAuthCallbackBody) -> Any:
    try:
        return await _svc().complete_hosted_oauth(
            provider="MICROSOFT",
            state=body.state,
            code=body.code,
            redirect_uri=body.redirect_uri,
        )
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/identity-providers/google/login")
async def google_login(request: Request) -> Any:
    return _error(
        EnterpriseError(
            "PROVIDER_TOKEN_INVALID",
            "Hosted Google login requires the authorization-code + PKCE callback.",
            401,
        ),
        request,
    )


@router.post("/identity-providers/microsoft/login")
async def microsoft_login(request: Request) -> Any:
    return _error(
        EnterpriseError(
            "PROVIDER_TOKEN_INVALID",
            "Hosted Microsoft login requires the authorization-code + PKCE callback.",
            401,
        ),
        request,
    )


@router.post("/security/four-eyes/request")
async def four_eyes_request(request: Request, body: FourEyesRequestBody) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        org_id = assurance.org_id
        if not org_id:
            raise unauthenticated("Organization context required.")
        await _svc().require_step_up(assurance, body.action, org_id=org_id, grant=body.grant)
        rec = await _svc().four_eyes.request(
            org_id=org_id,
            requester=assurance,
            action=body.action,
            parameters=body.parameters,
        )
        return {"id": rec.id, "status": rec.status, "digest": rec.digest}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/security/four-eyes/approve")
async def four_eyes_approve(request: Request, body: FourEyesApproveBody) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        org_id = assurance.org_id
        if not org_id:
            raise unauthenticated("Organization context required.")
        rec = await _svc().four_eyes.approve(
            org_id=org_id, request_id=body.request_id, approver=assurance
        )
        return {"id": rec.id, "status": rec.status}
    except EnterpriseError as exc:
        return _error(exc, request)


@router.post("/sso/configure")
async def sso_configure(request: Request, body: SsoConfigBody) -> Any:
    try:
        _token, _csrf, assurance = await _session(request)
        org_id = assurance.org_id
        if not org_id:
            raise unauthenticated("Organization context required.")
        await _svc().configure_sso(
            org_id=org_id,
            session=assurance,
            grant=body.grant,
            protocol=body.protocol,
            issuer=body.issuer,
            client_id=body.client_id,
            client_secret=body.client_secret,
            redirect_uri=body.redirect_uri,
            enforcement=body.enforcement,
            provisioning=body.provisioning,
            idp_entity_id=body.idp_entity_id,
            idp_sso_url=body.idp_sso_url,
            idp_x509_cert=body.idp_x509_cert,
            four_eyes_id=body.four_eyes_id,
        )
        return {"status": "configured"}
    except EnterpriseError as exc:
        return _error(exc, request)
