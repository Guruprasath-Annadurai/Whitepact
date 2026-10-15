# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Enterprise Customer Authority & Agent Management REST API Router."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from responsibleai.enterprise.authority.service import CustomerAuthorityService
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.router import _error_response, _request_id, _web_actor
from responsibleai.enterprise.runtime import get_enterprise_engine

router = APIRouter(prefix="/api/enterprise/organizations/{org_id}/authority", tags=["customer-authority"])


class InitiateBootstrapBody(BaseModel):
    ttl_seconds: int = Field(default=900, ge=60, le=86400)
    require_identity_assurance: bool = False


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


class RevokeRootBody(BaseModel):
    reason: str = Field(min_length=1, max_length=500)


class RegisterAgentBody(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(default="", max_length=1000)
    framework: str = Field(default="custom", max_length=100)
    purpose: str | None = Field(default=None, max_length=255)


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
async def revoke_root_authority(org_id: str, root_id: str, request: Request, body: RevokeRootBody) -> Any:
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


@router.post("/agents")
async def register_agent(org_id: str, request: Request, body: RegisterAgentBody) -> Any:
    try:
        actor = await _web_actor(request)
        return await _svc().register_agent(
            actor,
            org_id=org_id,
            name=body.name,
            description=body.description,
            framework=body.framework,
            purpose=body.purpose,
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
