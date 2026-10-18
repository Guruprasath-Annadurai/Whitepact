# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Experimental development-only authentication adapter to the existing kernel."""

from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import SQLAlchemyError

from responsibleai.enterprise.agent_auth import AUDIENCE, INTENT_PATH, DevelopmentAgentAuth, reject
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.router import _error_response, _request_id, _web_actor
from responsibleai.enterprise.runtime import get_enterprise_engine

router = APIRouter(tags=["development-agent-auth"])

# asyncpg may raise directly while opening a connection, before SQLAlchemy
# has wrapped a database error. Keep SQLite-only installations importable.
try:
    from asyncpg import PostgresError
except ImportError:
    STORAGE_ERRORS = (SQLAlchemyError, ValueError, TypeError, KeyError, OSError)
else:
    STORAGE_ERRORS = (SQLAlchemyError, ValueError, TypeError, KeyError, OSError, PostgresError)


class StrictBody(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BeginIssue(StrictBody):
    agent_id: str = Field(min_length=1, max_length=64)
    public_key: str = Field(pattern=r"^[0-9a-f]{64}$")
    rotate_from: str | None = Field(default=None, pattern=r"^[0-9a-f]{64}$")


class FinishIssue(StrictBody):
    challenge_id: str = Field(pattern=r"^[0-9a-f]{64}$")
    signature: str = Field(min_length=80, max_length=128)


class Intent(StrictBody):
    name: str = Field(min_length=1, max_length=100)
    arguments: dict[str, Any] = Field(default_factory=dict)
    purpose: str = Field(min_length=1, max_length=255)


class RequestChallenge(StrictBody):
    audience: str = Field(default=AUDIENCE, max_length=100)
    intent: Intent


class IntentProof(RequestChallenge, FinishIssue):
    pass


def service():
    from responsibleai.dashboard.app import settings

    svc = DevelopmentAgentAuth(get_enterprise_engine(), settings)
    svc.gate()
    return svc


def token(request):
    scheme, _, value = request.headers.get("authorization", "").partition(" ")
    if scheme != "B1-PoP" or not 32 <= len(value) <= 128:
        raise reject()
    return value


async def owner(request, org_id):
    actor = await _web_actor(request)
    if actor.org_id != org_id:
        raise reject()
    return actor


async def guarded(request, operation):
    try:
        return await operation()
    except EnterpriseError as exc:
        return _error_response(exc, _request_id(request))
    except STORAGE_ERRORS:
        return JSONResponse(status_code=503, content={"error": "B1_STORAGE_UNVERIFIED"})


@router.post("/api/enterprise/organizations/{org_id}/agent-auth/challenge")
async def begin_issue(org_id: str, request: Request, body: BeginIssue):
    async def operation():
        svc = service()
        return await svc.begin_issue(
            await owner(request, org_id),
            body.agent_id,
            body.public_key,
            rotate_from=body.rotate_from,
        )

    return await guarded(request, operation)


@router.post("/api/enterprise/organizations/{org_id}/agent-auth/issue")
async def finish_issue(org_id: str, request: Request, body: FinishIssue):
    async def operation():
        svc = service()
        return await svc.finish_issue(
            await owner(request, org_id), body.challenge_id, body.signature
        )

    return await guarded(request, operation)


@router.post("/api/enterprise/organizations/{org_id}/agent-auth/{credential_id}/revoke")
async def revoke(org_id: str, credential_id: str, request: Request):
    async def operation():
        svc = service()
        return await svc.revoke(await owner(request, org_id), credential_id)

    return await guarded(request, operation)


@router.post("/api/dev/agent-auth/request-challenge")
async def request_challenge(request: Request, body: RequestChallenge):
    async def operation():
        return await service().begin_request(
            token(request),
            audience=body.audience,
            method="POST",
            path=INTENT_PATH,
            body=body.intent.model_dump(),
        )

    return await guarded(request, operation)


@router.post(INTENT_PATH)
async def intent(request: Request, body: IntentProof):
    async def operation():
        svc = service()
        action = body.intent.model_dump()
        context = await svc.authenticate(
            token(request),
            body.challenge_id,
            body.signature,
            audience=body.audience,
            method="POST",
            path=INTENT_PATH,
            body=action,
        )
        # Only the real, harmless local tool is exposed by this prototype adapter.
        # Its actual execution still requires canonical authority/policy/approval.
        if body.intent.name != "rai_policy_check":
            raise EnterpriseError("B1_TOOL_UNAVAILABLE", "Unsupported prototype tool.", 400)
        from responsibleai.dashboard.app import _dashboard_governance_services
        from responsibleai.mcp.governance_integration import apply_governance

        outcome = await apply_governance(
            body.intent.name,
            body.intent.arguments,
            context,
            _dashboard_governance_services(),
            purpose=body.intent.purpose,
        )
        payload = outcome.result if outcome.proceed else outcome.blocked_response
        status = (
            200
            if outcome.proceed
            else 202
            if (payload or {}).get("error") == "governance_approval_required"
            else 403
        )
        return JSONResponse(
            status_code=status,
            content={
                "development_only": True,
                "decision": "REQUIRE_APPROVAL"
                if status == 202
                else "ALLOW"
                if outcome.proceed
                else "DENY",
                "result": payload,
            },
        )

    return await guarded(request, operation)
