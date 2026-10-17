# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise Customer Authority & Agent Management REST API Router."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field, model_validator

from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.router import _error_response, _request_id, _web_actor
from responsibleai.enterprise.runtime import get_enterprise_engine

router = APIRouter(
    prefix="/api/enterprise/organizations/{org_id}/authority", tags=["customer-authority"]
)


class InitiateBootstrapBody(BaseModel):
    ttl_seconds: int = Field(default=900, ge=60, le=86400)
    require_identity_assurance: bool = False
    require_passkey_stepup: bool = False


class CompleteBootstrapBody(BaseModel):
    token: str = Field(min_length=1)
    nonce: str = Field(min_length=1)
    root_public_key: str = Field(min_length=1)
    scope_description: str = Field(min_length=1, max_length=1000)
    purpose: str = Field(min_length=1, max_length=255)
    allowed_action_types: list[str] = Field(min_length=1)
    allowed_targets: list[str] = Field(min_length=1)
    key_algorithm: str = "Ed25519"
    consent_method: str = "CRYPTOGRAPHIC_CEREMONY"
    evidence_refs: list[str] = Field(default_factory=list)
    webauthn_assertion: dict[str, Any] | None = None
    root_signature: str | None = None


class CreateStepUpChallengeBody(BaseModel):
    action: str = Field(min_length=1)
    operation_digest: str = Field(min_length=1)
    ttl_seconds: int = Field(default=300, ge=30, le=3600)


class EmergencyContainmentBody(BaseModel):
    target_type: str = Field(min_length=1)
    target_id: str = Field(min_length=1)
    containment_action: str = Field(min_length=1)
    reason: str = Field(min_length=1, max_length=1000)
    webauthn_assertion: dict[str, Any] | None = None


class CreateRecoveryRequestBody(BaseModel):
    request_type: str = Field(min_length=1)
    target_root_id: str = Field(min_length=1)
    proposed_parameters: dict[str, Any] = Field(default_factory=dict)
    required_quorum_m: int = Field(default=2, ge=1)
    eligible_quorum_n: int = Field(default=3, ge=1)
    ttl_seconds: int = Field(default=86400, ge=300)


class VoteRecoveryRequestBody(BaseModel):
    decision: str = Field(pattern="^(APPROVE|REJECT)$")
    action_digest: str = Field(min_length=1)
    notes: str = Field(default="", max_length=500)
    webauthn_assertion: dict[str, Any] | None = None


class ExecuteRecoveryRequestBody(BaseModel):
    action_digest: str = Field(min_length=1)
    webauthn_assertion: dict[str, Any] | None = None


class RevokeRootBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class RegisterApplicationBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    environment: str = Field(default="production", max_length=50)
    metadata: dict[str, Any] = Field(default_factory=dict)


class DisableApplicationBody(BaseModel):
    reason: str = Field(default="Disabled by administrator", max_length=500)


class RegisterAgentBody(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    display_name: str | None = Field(default=None, max_length=200)
    description: str = Field(default="", max_length=1000)
    framework: str = Field(default="custom", max_length=100)
    purpose: str | None = Field(default=None, max_length=255)
    application_id: str | None = Field(default=None, max_length=64)

    @model_validator(mode="after")
    def _ensure_name(self) -> RegisterAgentBody:
        val = (self.name or self.display_name or "").strip()
        if not val:
            raise ValueError("Either 'name' or 'display_name' must be a non-empty string.")
        self.name = val
        return self


class DelegateToAgentBody(BaseModel):
    granted_action_types: list[str] = Field(min_length=1)
    allowed_targets: list[str] = Field(min_length=1)
    purpose: str = Field(min_length=1, max_length=255)
    expires_at: str | None = None


class DisableAgentBody(BaseModel):
    reason: str = Field(default="Disabled by administrator", max_length=500)


def _svc() -> CustomerAuthorityService:
    return CustomerAuthorityService(get_enterprise_engine())


@router.post("/bootstrap/initiate")
async def initiate_bootstrap(org_id: str, request: Request, body: InitiateBootstrapBody) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().initiate_root_bootstrap(
            actor,
            org_id=org_id,
            ttl_seconds=body.ttl_seconds,
            require_identity_assurance=body.require_identity_assurance,
            require_passkey_stepup=body.require_passkey_stepup,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/bootstrap/complete")
async def complete_bootstrap(org_id: str, request: Request, body: CompleteBootstrapBody) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().complete_root_bootstrap(
            actor,
            org_id=org_id,
            token=body.token,
            nonce=body.nonce,
            root_public_key=body.root_public_key,
            scope_description=body.scope_description,
            purpose=body.purpose,
            allowed_action_types=body.allowed_action_types,
            allowed_targets=body.allowed_targets,
            key_algorithm=body.key_algorithm,
            consent_method=body.consent_method,
            evidence_refs=body.evidence_refs,
            webauthn_assertion=body.webauthn_assertion,
            root_signature=body.root_signature,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/bootstrap/reconcile")
async def reconcile_bootstrap(org_id: str, token: str, nonce: str, request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().reconcile_bootstrap_status(
            actor,
            org_id=org_id,
            token=token,
            nonce=nonce,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/webauthn/challenge")
async def create_stepup_challenge(
    org_id: str, request: Request, body: CreateStepUpChallengeBody
) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().create_authority_stepup_challenge(
            actor,
            org_id=org_id,
            action=body.action,
            operation_digest=body.operation_digest,
            ttl_seconds=body.ttl_seconds,
            request=request,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/status")
async def get_authority_status(org_id: str, request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().get_authority_status(actor, org_id=org_id)
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/root/{root_id}/revoke")
async def revoke_root_authority(
    org_id: str, root_id: str, request: Request, body: RevokeRootBody
) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().revoke_root_authority(
            actor,
            org_id=org_id,
            root_id=root_id,
            reason=body.reason,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/applications")
async def register_application(org_id: str, request: Request, body: RegisterApplicationBody) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().register_application(
            actor,
            org_id=org_id,
            name=body.name,
            description=body.description,
            environment=body.environment,
            metadata=body.metadata,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/applications")
async def list_applications(org_id: str, request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return {"applications": await _svc().list_applications(actor, org_id=org_id)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/applications/{app_id}")
async def get_application(org_id: str, app_id: str, request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().get_application(actor, org_id=org_id, app_id=app_id)
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/applications/{app_id}/disable")
async def disable_application(
    org_id: str, app_id: str, request: Request, body: DisableApplicationBody
) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().disable_application(
            actor, org_id=org_id, app_id=app_id, reason=body.reason
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/agents")
async def register_agent(org_id: str, request: Request, body: RegisterAgentBody) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().register_agent(
            actor,
            org_id=org_id,
            name=body.name or "",
            description=body.description,
            framework=body.framework,
            purpose=body.purpose,
            application_id=body.application_id,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/agents")
async def list_agents(org_id: str, request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return {"agents": await _svc().list_agents(actor, org_id=org_id)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/agents/{agent_id}/delegations")
async def delegate_to_agent(
    org_id: str,
    agent_id: str,
    request: Request,
    body: DelegateToAgentBody,
) -> Any:
    try:
        actor = await _web_actor(request)
        expires_at_dt = datetime.fromisoformat(body.expires_at) if body.expires_at else None
        return await _svc().delegate_to_agent(
            actor,
            org_id=org_id,
            agent_id=agent_id,
            granted_action_types=body.granted_action_types,
            allowed_targets=body.allowed_targets,
            purpose=body.purpose,
            expires_at=expires_at_dt,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/agents/{agent_id}/disable")
async def disable_agent(
    org_id: str,
    agent_id: str,
    request: Request,
    body: DisableAgentBody,
) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().disable_agent(
            actor,
            org_id=org_id,
            agent_id=agent_id,
            reason=body.reason,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/capabilities")
async def list_capabilities(org_id: str, request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return {"capabilities": await _svc().list_capabilities(actor, org_id=org_id)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/agents/{agent_id}/capabilities")
async def list_agent_capabilities(org_id: str, agent_id: str, request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return {
            "capabilities": await _svc().list_capabilities(actor, org_id=org_id, agent_id=agent_id)
        }
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/containment/emergency")
async def emergency_containment(
    org_id: str, request: Request, body: EmergencyContainmentBody
) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().execute_emergency_containment(
            actor,
            org_id=org_id,
            target_type=body.target_type,
            target_id=body.target_id,
            containment_action=body.containment_action,
            reason=body.reason,
            webauthn_assertion=body.webauthn_assertion,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/recovery/requests")
async def create_recovery_request(
    org_id: str, request: Request, body: CreateRecoveryRequestBody
) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().create_recovery_request(
            actor,
            org_id=org_id,
            request_type=body.request_type,
            target_root_id=body.target_root_id,
            proposed_parameters=body.proposed_parameters,
            required_quorum_m=body.required_quorum_m,
            eligible_quorum_n=body.eligible_quorum_n,
            ttl_seconds=body.ttl_seconds,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/recovery/requests")
async def list_recovery_requests(org_id: str, request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return {"requests": await _svc().list_recovery_requests(actor, org_id=org_id)}
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.get("/recovery/requests/{request_id}")
async def get_recovery_request(org_id: str, request_id: str, request: Request) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().get_recovery_request(actor, org_id=org_id, request_id=request_id)
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/recovery/requests/{request_id}/vote")
async def vote_recovery_request(
    org_id: str,
    request_id: str,
    request: Request,
    body: VoteRecoveryRequestBody,
) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().vote_recovery_request(
            actor,
            org_id=org_id,
            request_id=request_id,
            decision=body.decision,
            action_digest=body.action_digest,
            notes=body.notes,
            webauthn_assertion=body.webauthn_assertion,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))


@router.post("/recovery/requests/{request_id}/execute")
async def execute_recovery_request(
    org_id: str,
    request_id: str,
    request: Request,
    body: ExecuteRecoveryRequestBody,
) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().execute_recovery_request(
            actor,
            org_id=org_id,
            request_id=request_id,
            action_digest=body.action_digest,
            webauthn_assertion=body.webauthn_assertion,
        )
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))
