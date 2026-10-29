"""Local fault-injection evidence, never genuine provider-delivery proof."""

import os
import time
import uuid

import httpx
import pytest
from sqlalchemy import select, update

from responsibleai.db import create_engine
from responsibleai.db.engine import (
    identity_provider_events,
    identity_verifications,
    web_memberships,
)
from responsibleai.enterprise.didit_service import DiditVerificationService
from responsibleai.enterprise.errors import EnterpriseError
from tests.test_m13_didit_provider import event, provider, signed
from tests.test_m13_identity_trust_boundary import _development_org, _user


@pytest.fixture
async def engine():
    if os.environ.get("WHITEPACT_DIDIT_TEST_BACKEND") == "postgresql":
        from tests.pg_test_url import isolated_pg_url

        async for url in isolated_pg_url("wp_didit"):
            db = create_engine(url)
            await db.init()
            try:
                yield db
            finally:
                await db.close()
        return
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def setup(engine, monkeypatch):
    monkeypatch.setenv("WHITEPACT_IDENTITY_APPROVED_PROVIDERS", "didit-sandbox")
    monkeypatch.setenv(
        "WHITEPACT_IDENTITY_APPROVED_ASSURANCE_LEVELS", "didit_sandbox_id_liveness_face"
    )
    monkeypatch.setenv("WHITEPACT_DIDIT_SANDBOX_ASSURANCE_ENABLED", "1")
    user = await _user(engine, "didit@example.com")
    org, _ = await _development_org(engine, user)
    sid = str(uuid.uuid4())
    body = event(session_id=sid, vendor_data=user, created_at=int(time.time()) - 10)

    def server(req):
        if req.method == "POST":
            return httpx.Response(
                201, json={"session_id": sid, "url": "https://verify.didit.me/session/" + sid}
            )
        return httpx.Response(
            200,
            json={
                **body,
                **{
                    k: [{"status": "Approved"}]
                    for k in ("id_verifications", "liveness_checks", "face_matches")
                },
            },
        )

    service = DiditVerificationService(engine, provider(httpx.MockTransport(server)))
    await service.start_human_verification(user, org_id=org)
    return service, body, user


async def apply(service, body, **kwargs):
    payload, sig, ts = signed(body)
    return await service.apply_didit_event(payload=payload, signature=sig, timestamp=ts, **kwargs)


async def rows(engine, table):
    async with engine.raw.connect() as conn:
        return (await conn.execute(select(table))).mappings().all()


@pytest.mark.asyncio
async def test_approved_binding_and_duplicate_are_durable(engine, monkeypatch):
    service, body, user = await setup(engine, monkeypatch)
    await apply(service, body)
    assert (await service.get_human_status(user))["status"] == "IDENTITY_VERIFIED"
    assert len(await rows(engine, identity_provider_events)) == 3
    retry = {**body, "timestamp": body["timestamp"] + 1}
    assert (await apply(service, retry))["duplicate"] is True
    assert len(await rows(engine, identity_provider_events)) == 3


@pytest.mark.asyncio
async def test_try_webhook_records_no_identity_authority(engine, monkeypatch):
    service, body, user = await setup(engine, monkeypatch)
    body.update(session_id=str(uuid.uuid4()), vendor_data="sample")
    assert (await apply(service, body, test_delivery=True))["identity_transition"] is False
    assert (await service.get_human_status(user))["status"] != "IDENTITY_VERIFIED"
    records = await rows(engine, identity_provider_events)
    assert len(records) == 2 and records[-1]["user_id"] is None


@pytest.mark.asyncio
async def test_cross_subject_cannot_change_identity(engine, monkeypatch):
    service, body, user = await setup(engine, monkeypatch)
    body["vendor_data"] = "attacker"
    with pytest.raises(EnterpriseError):
        await apply(service, body)
    assert (await service.get_human_status(user))["status"] != "IDENTITY_VERIFIED"
    assert len(await rows(engine, identity_provider_events)) == 1


@pytest.mark.asyncio
async def test_audit_failure_rolls_back_evidence_and_authority(engine, monkeypatch):
    service, body, user = await setup(engine, monkeypatch)

    async def outage(**kwargs):
        raise OSError("injected persistence outage")

    monkeypatch.setattr(service.audit, "record", outage)
    with pytest.raises(OSError):
        await apply(service, body)
    assert len(await rows(engine, identity_provider_events)) == 1
    assert (await rows(engine, identity_verifications))[0]["status"] == "REVIEW_REQUIRED"


@pytest.mark.asyncio
async def test_replayed_id_with_changed_payload_fails(engine, monkeypatch):
    service, body, user = await setup(engine, monkeypatch)
    await apply(service, body)
    with pytest.raises(EnterpriseError) as caught:
        await apply(service, {**body, "status": "Declined"})
    assert caught.value.code == "PROVIDER_REPLAY"
    assert len(await rows(engine, identity_provider_events)) == 3


@pytest.mark.asyncio
async def test_older_event_cannot_overwrite_newer_decision(engine, monkeypatch):
    service, body, user = await setup(engine, monkeypatch)
    await apply(service, body)
    body.update(event_id=str(uuid.uuid4()), created_at=body["created_at"] - 1)
    with pytest.raises(EnterpriseError) as caught:
        await apply(service, body)
    assert caught.value.code == "PROVIDER_EVENT_OUT_OF_ORDER"
    assert (await service.get_human_status(user))["status"] == "IDENTITY_VERIFIED"


@pytest.mark.asyncio
async def test_reconciliation_requires_bound_tenant_and_cannot_elevate(engine, monkeypatch):
    service, body, user = await setup(engine, monkeypatch)
    records = await rows(engine, identity_provider_events)
    org = records[0]["org_id"]
    with pytest.raises(EnterpriseError):
        await service.reconcile(body["session_id"], user_id=user, org_id="other")
    result = await service.reconcile(body["session_id"], user_id=user, org_id=org)
    assert result["provider_status"] == "Approved" and result["identity_transition"] is False
    assert (await service.get_human_status(user))["status"] != "IDENTITY_VERIFIED"


@pytest.mark.asyncio
async def test_http_persistence_failure_sanitized_and_rolled_back(engine, monkeypatch):
    from fastapi import FastAPI

    from responsibleai.enterprise import router as routes

    service, body, user = await setup(engine, monkeypatch)
    monkeypatch.setattr(routes, "_verification", lambda: service)

    async def outage(**kwargs):
        raise OSError("private C:/credentials/secret-token")

    monkeypatch.setattr(service.audit, "record", outage)
    app = FastAPI()
    app.include_router(routes.router)
    payload, sig, ts = signed(body)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://local"
    ) as client:
        response = await client.post(
            "/api/enterprise/identity/verification/webhook",
            content=payload,
            headers={"X-Signature-V2": sig, "X-Timestamp": ts},
        )
    assert response.status_code == 503
    assert "private" not in response.text and "secret-token" not in response.text
    assert response.json()["error"] == "DIDIT_PERSISTENCE_UNAVAILABLE"
    assert len(await rows(engine, identity_provider_events)) == 1
    assert (await service.get_human_status(user))["status"] != "IDENTITY_VERIFIED"


@pytest.mark.asyncio
async def test_http_forged_approval_cannot_persist(engine, monkeypatch):
    from fastapi import FastAPI

    from responsibleai.enterprise import router as routes

    service, body, user = await setup(engine, monkeypatch)
    monkeypatch.setattr(routes, "_verification", lambda: service)
    app = FastAPI()
    app.include_router(routes.router)
    payload, _, ts = signed(body)
    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://local"
    ) as client:
        response = await client.post(
            "/api/enterprise/identity/verification/webhook",
            content=payload,
            headers={"X-Signature-V2": "0" * 64, "X-Timestamp": ts},
        )
    assert response.status_code == 403
    assert len(await rows(engine, identity_provider_events)) == 1


@pytest.mark.parametrize(
    "status,expected",
    [
        ("In Review", "REVIEW_REQUIRED"),
        ("Declined", "REJECTED"),
        ("Expired", "REJECTED"),
        ("Kyc Expired", "SUSPENDED"),
    ],
)
@pytest.mark.asyncio
async def test_nonapproved_statuses_never_verify(engine, monkeypatch, status, expected):
    service, body, user = await setup(engine, monkeypatch)
    body["status"] = status
    await apply(service, body)
    assert (await rows(engine, identity_verifications))[0]["status"] == expected
    assert (await service.get_human_status(user))["status"] != "IDENTITY_VERIFIED"


@pytest.mark.asyncio
async def test_revoked_membership_rejects_late_approval(engine, monkeypatch):
    service, body, user = await setup(engine, monkeypatch)
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_memberships)
            .where(web_memberships.c.user_id == user)
            .values(status="REVOKED")
        )
    with pytest.raises(EnterpriseError):
        await apply(service, body)
    assert len(await rows(engine, identity_provider_events)) == 1


@pytest.mark.asyncio
async def test_sandbox_requires_explicit_allowlist_and_never_production(engine, monkeypatch):
    service, body, user = await setup(engine, monkeypatch)
    monkeypatch.delenv("WHITEPACT_DIDIT_SANDBOX_ASSURANCE_ENABLED")
    with pytest.raises(EnterpriseError):
        await apply(service, body)
    assert len(await rows(engine, identity_provider_events)) == 1
    monkeypatch.setenv("WHITEPACT_DIDIT_SANDBOX_ASSURANCE_ENABLED", "1")
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    with pytest.raises(EnterpriseError):
        await apply(service, body)
    assert len(await rows(engine, identity_provider_events)) == 1
