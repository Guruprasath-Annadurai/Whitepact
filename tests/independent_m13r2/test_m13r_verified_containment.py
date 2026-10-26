# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent service retests with real cryptographic verification, not enrollment.

Credential/identity fixtures use isolated SQLite. No verifier is mocked. Failure
injection is confined to process termination. These are not the customer journey.
"""

import asyncio
import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy import select, update
from tests.test_m12fs_root_hardening import (
    _configure_test_env,  # noqa: F401 -- isolated autouse fixture
    _create_test_owner,
    _register_fake_passkey,
    api_client,  # noqa: F401 -- real ASGI HTTP client fixture
)
from tests.webauthn_fakes import assertion_blob

from responsibleai.db.engine import (
    authority_containment_records,
    authority_step_up_challenges,
    enterprise_security_audit,
    passkey_credentials,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.enterprise.authority.service import (
    CustomerAuthorityService,
    compute_canonical_operation_digest,
)
from responsibleai.enterprise.runtime import get_enterprise_engine
from responsibleai.enterprise.security.webauthn import b64url_decode
from responsibleai.isolation.in_flight import InFlightExecutionRegistry


async def verified_input():
    actor, user_id, org_id, _, _ = await _create_test_owner()
    engine = get_enterprise_engine()
    private, credential_id, public = _register_fake_passkey(user_id)
    async with engine.raw.begin() as conn:
        await conn.execute(
            passkey_credentials.insert().values(
                id=f"pk_{uuid.uuid4().hex[:12]}",
                user_id=user_id,
                credential_id=credential_id,
                public_key=public,
                sign_count=0,
                rp_id="localhost",
                transports_json="[]",
                backup_eligible=1,
                backup_state=1,
                display_name="Local cryptographic fixture",
                status="ACTIVE",
                created_at=datetime.now(UTC).isoformat(),
            )
        )
    service = CustomerAuthorityService(engine)
    operation = {
        "org_id": org_id,
        "target_type": "ORGANIZATION",
        "target_id": org_id,
        "containment_action": "LOCKDOWN",
    }
    challenge = await service.create_authority_stepup_challenge(
        actor,
        org_id=org_id,
        action="EMERGENCY_CONTAINMENT",
        operation_digest=compute_canonical_operation_digest("EMERGENCY_CONTAINMENT", operation),
    )
    client, auth, signature = assertion_blob(
        rp_id="localhost",
        origin=challenge["origin"],
        challenge=b64url_decode(challenge["challenge"]),
        private_key=private,
        sign_count=1,
    )
    kwargs = {
        **operation,
        "reason": "Independent local containment retest",
        "webauthn_assertion": {
            "credential_id": credential_id,
            "client_data_json": client,
            "authenticator_data": auth,
            "signature": signature,
        },
    }
    return actor, service, kwargs


@pytest.mark.asyncio
async def test_verified_stepup_exception_preserves_restriction_and_unresolved_record(monkeypatch):
    actor, service, kwargs = await verified_input()
    registry = InFlightExecutionRegistry()
    monkeypatch.setattr(InFlightExecutionRegistry, "_instance", registry)
    monkeypatch.setattr(
        registry,
        "terminate_in_flight",
        AsyncMock(side_effect=RuntimeError("local termination failure")),
    )
    before = await RevocationEpochRepository(get_enterprise_engine()).current(kwargs["org_id"])
    result = await service.execute_emergency_containment(actor, **kwargs)
    assert result["status"] == "UNRESOLVED"
    assert result["revocation_epoch"] > before.epoch
    async with get_enterprise_engine().raw.connect() as conn:
        stored = await conn.scalar(
            select(authority_containment_records.c.status).where(
                authority_containment_records.c.id == result["containment_id"]
            )
        )
    assert stored == "UNRESOLVED"


@pytest.mark.asyncio
async def test_verified_stepup_real_registry_partial_failure_must_not_confirm(monkeypatch):
    actor, service, kwargs = await verified_input()
    registry = InFlightExecutionRegistry()
    monkeypatch.setattr(InFlightExecutionRegistry, "_instance", registry)
    await registry.register(
        "local-execution", kwargs["org_id"], "local-action", terminate_callback=lambda: False
    )
    result = await service.execute_emergency_containment(actor, **kwargs)
    assert registry.has_unresolved(kwargs["org_id"])
    assert result["status"] == "UNRESOLVED", (
        "Real registry returns partial failure without throwing; must not claim CONTAINED"
    )


@pytest.mark.asyncio
async def test_verified_stepup_termination_failure_has_durable_failure_audit(monkeypatch):
    actor, service, kwargs = await verified_input()
    registry = InFlightExecutionRegistry()
    monkeypatch.setattr(InFlightExecutionRegistry, "_instance", registry)
    monkeypatch.setattr(
        registry, "terminate_in_flight", AsyncMock(side_effect=RuntimeError("local failure"))
    )
    result = await service.execute_emergency_containment(actor, **kwargs)
    async with get_enterprise_engine().raw.connect() as conn:
        events = (
            (
                await conn.execute(
                    select(enterprise_security_audit).where(
                        enterprise_security_audit.c.org_id == kwargs["org_id"]
                    )
                )
            )
            .mappings()
            .all()
        )
    assert result["status"] == "UNRESOLVED"
    assert any(event["result"] in {"UNRESOLVED", "FAILURE", "FAILED"} for event in events), (
        "Audit must record termination uncertainty, not only pre-termination SUCCESS"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "case", ["expired", "wrong-operation", "wrong-organization", "revoked-authenticator"]
)
async def test_real_verifier_rejects_invalid_bound_assertions(case, monkeypatch):
    actor, service, kwargs = await verified_input()
    registry = InFlightExecutionRegistry()
    monkeypatch.setattr(InFlightExecutionRegistry, "_instance", registry)
    terminate = AsyncMock(return_value=[])
    monkeypatch.setattr(registry, "terminate_in_flight", terminate)
    engine = get_enterprise_engine()
    if case == "expired":
        async with engine.raw.begin() as conn:
            await conn.execute(
                update(authority_step_up_challenges).values(expires_at="2000-01-01T00:00:00+00:00")
            )
    elif case == "wrong-operation":
        kwargs["containment_action"] = "SUSPEND"
    elif case == "wrong-organization":
        kwargs["org_id"] = "different-tenant"
    else:
        async with engine.raw.begin() as conn:
            await conn.execute(update(passkey_credentials).values(status="REVOKED"))
    with pytest.raises(Exception) as error:
        await service.execute_emergency_containment(actor, **kwargs)
    assert getattr(error.value, "code", None), (
        "Must be a structured security rejection, not a setup exception"
    )
    terminate.assert_not_awaited()


@pytest.mark.asyncio
async def test_real_verified_assertion_is_not_reusable(monkeypatch):
    actor, service, kwargs = await verified_input()
    monkeypatch.setattr(InFlightExecutionRegistry, "_instance", InFlightExecutionRegistry())
    await service.execute_emergency_containment(actor, **kwargs)
    with pytest.raises(Exception) as error:
        await service.execute_emergency_containment(actor, **kwargs)
    assert getattr(error.value, "code", None) == "WEBAUTHN_CHALLENGE_REPLAY"


@pytest.mark.asyncio
@pytest.mark.usefixtures("api_client")
async def test_api_key_cannot_substitute_for_interactive_session(request):
    client = request.getfixturevalue("api_client")
    response = await client.post(
        "/api/enterprise/organizations/local-org/authority/containment/emergency",
        headers={"Authorization": "Bearer m12fs-admin-key"},
        json={
            "target_type": "ORGANIZATION",
            "target_id": "local-org",
            "containment_action": "LOCKDOWN",
            "reason": "Local negative auth test",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_worker_cancellation_cannot_leave_durable_confirmed_containment(monkeypatch):
    actor, service, kwargs = await verified_input()
    registry = InFlightExecutionRegistry()
    monkeypatch.setattr(InFlightExecutionRegistry, "_instance", registry)
    monkeypatch.setattr(
        registry, "terminate_in_flight", AsyncMock(side_effect=asyncio.CancelledError())
    )
    with pytest.raises(asyncio.CancelledError):
        await service.execute_emergency_containment(actor, **kwargs)
    async with get_enterprise_engine().raw.connect() as conn:
        stored = await conn.scalar(
            select(authority_containment_records.c.status).where(
                authority_containment_records.c.org_id == kwargs["org_id"]
            )
        )
    assert stored != "CONTAINED", (
        "Worker interruption before termination confirmation must not leave a durable success"
    )
