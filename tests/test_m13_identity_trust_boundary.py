# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Identity verification trust boundary.

These cases exercise the software contract. A passing reference-contract
event is not production identity proofing and is not canonical customer
acceptance.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select, update

from responsibleai.db import WebIdentityRepository, create_engine
from responsibleai.db.engine import (
    enterprise_environments,
    identity_verifications,
    org_api_keys,
    organization_verifications,
    organizations,
    web_memberships,
    web_users,
)
from responsibleai.enterprise.errors import EnterpriseError
from responsibleai.enterprise.identity_provider_http import HttpCallbackIdentityProvider
from responsibleai.enterprise.issuance import CredentialIssuancePolicy
from responsibleai.enterprise.verification import (
    HmacVerificationProvider,
    VerificationService,
)
from responsibleai.rbac.models import Role
from tests.identity_contract import enable_reference_contract, sign_identity_event


@pytest.fixture
async def engine():
    db = create_engine(":memory:")
    await db.init()
    yield db
    await db.close()


async def _development_org(engine, user_id: str) -> tuple[str, str]:
    now = datetime.now(UTC).isoformat()
    org_id = str(uuid.uuid4())
    env_id = str(uuid.uuid4())
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Boundary",
                slug=f"b-{uuid.uuid4().hex[:8]}",
                monthly_budget_usd=0,
                created_at=now,
                plan="FREE",
                governance_status="ACTIVE",
                workspace_kind="ORGANIZATION",
                owner_user_id=user_id,
            )
        )
        await conn.execute(
            insert(enterprise_environments).values(
                id=env_id,
                org_id=org_id,
                type="DEVELOPMENT",
                name="development",
                status="ACTIVE",
                created_at=now,
                metadata_json="{}",
            )
        )
        await conn.execute(
            insert(web_memberships).values(
                id=str(uuid.uuid4()),
                user_id=user_id,
                org_id=org_id,
                role=Role.OWNER.value,
                status="ACTIVE",
                created_at=now,
            )
        )
    return org_id, env_id


async def _user(engine, email: str) -> str:
    web = WebIdentityRepository(engine)
    user_id, token = await web.register("Human", email, "correct-horse-battery-staple-9")
    assert await web.verify_email(token)
    return user_id


def _service(engine) -> VerificationService:
    return VerificationService(engine, HmacVerificationProvider("test-webhook-secret"))


async def _session(engine, user_id: str) -> tuple[VerificationService, str]:
    service = _service(engine)
    started = await service.start_human_verification(user_id)
    return service, started["session_id"]


def _event(user_id: str, session_id: str, **overrides) -> dict:
    body = {
        "event_id": f"evt-{uuid.uuid4().hex}",
        "event_type": "identity.verification",
        "subject_id": user_id,
        "reference_id": session_id,
        "outcome": "VERIFIED",
        "assurance_level": "government_id",
    }
    body.update(overrides)
    return body


async def _apply(service: VerificationService, body: dict, **kwargs):
    payload, signature, timestamp = sign_identity_event(body)
    return await service.apply_provider_event(
        payload=payload, signature=signature, timestamp=timestamp, **kwargs
    )


@pytest.mark.asyncio
async def test_signed_event_without_session_cannot_verify(engine) -> None:
    enable_reference_contract()
    user_id = await _user(engine, "nosession@example.com")
    service = _service(engine)
    body = _event(user_id, "sess_not_issued")
    with pytest.raises(EnterpriseError) as exc:
        await _apply(service, body, expected_user_id=user_id)
    assert exc.value.code == "VERIFICATION_SESSION_UNKNOWN"
    status = await service.get_human_status(user_id)
    assert status["status"] != "IDENTITY_VERIFIED"


@pytest.mark.asyncio
async def test_subject_substitution_does_not_verify_the_other_account(engine) -> None:
    enable_reference_contract()
    victim = await _user(engine, "victim@example.com")
    attacker = await _user(engine, "attacker@example.com")
    service, session_id = await _session(engine, victim)
    body = _event(attacker, session_id)
    with pytest.raises(EnterpriseError) as exc:
        await _apply(service, body)
    assert exc.value.code == "CROSS_TENANT"
    assert (await service.get_human_status(victim))["status"] != "IDENTITY_VERIFIED"
    assert (await service.get_human_status(attacker))["status"] != "IDENTITY_VERIFIED"


@pytest.mark.asyncio
async def test_unapproved_assurance_and_sso_level_fail_closed(engine) -> None:
    user_id = await _user(engine, "policy@example.com")
    service, session_id = await _session(engine, user_id)
    with pytest.raises(EnterpriseError) as missing:
        await _apply(service, _event(user_id, session_id))
    assert missing.value.code == "ASSURANCE_NOT_APPROVED"
    enable_reference_contract()
    service, session_id = await _session(engine, user_id)
    with pytest.raises(EnterpriseError) as weak:
        await _apply(service, _event(user_id, session_id, assurance_level="sso"))
    assert weak.value.code == "ASSURANCE_NOT_APPROVED"
    assert (await service.get_human_status(user_id))["status"] != "IDENTITY_VERIFIED"


@pytest.mark.asyncio
async def test_expired_suspended_and_revoked_do_not_issue_credentials(engine) -> None:
    enable_reference_contract()
    user_id = await _user(engine, "lifecycle@example.com")
    service, session_id = await _session(engine, user_id)
    await _apply(service, _event(user_id, session_id))
    assert (await service.get_human_status(user_id))["status"] == "IDENTITY_VERIFIED"
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(identity_verifications)
            .where(identity_verifications.c.user_id == user_id)
            .values(expires_at=past)
        )
    assert (await service.get_human_status(user_id))["status"] == "EXPIRED"
    org_id, env_id = await _development_org(engine, user_id)
    policy = CredentialIssuancePolicy(engine, service)
    expired = await policy.evaluate(
        principal_user_id=user_id,
        organization_id=org_id,
        environment_id=env_id,
        requested_scopes=("usage:read",),
    )
    assert expired.allowed is False
    assert expired.reason_code == "IDENTITY_VERIFICATION_REQUIRED"

    fresh, fresh_session = await _session(engine, user_id)
    await _apply(fresh, _event(user_id, fresh_session))
    await fresh.suspend_human(user_id)
    suspended = await fresh.get_human_status(user_id)
    assert suspended["status"] == "SUSPENDED"
    decision = await policy.evaluate(
        principal_user_id=user_id,
        organization_id=org_id,
        environment_id=env_id,
        requested_scopes=("usage:read",),
    )
    assert decision.reason_code == "VERIFICATION_SUSPENDED"
    with pytest.raises(EnterpriseError) as replay_up:
        await _apply(
            fresh,
            _event(
                user_id,
                fresh_session,
                event_type="identity.verification",
                outcome="VERIFIED",
            ),
        )
    assert replay_up.value.code == "VERIFICATION_TRANSITION_DENIED"


@pytest.mark.asyncio
async def test_lower_assurance_and_replay_do_not_replace_verification(engine) -> None:
    enable_reference_contract()
    user_id = await _user(engine, "replay@example.com")
    service, session_id = await _session(engine, user_id)
    body = _event(user_id, session_id)
    await _apply(service, body)
    with pytest.raises(EnterpriseError) as replay:
        await _apply(service, body)
    assert replay.value.code == "PROVIDER_REPLAY"
    with pytest.raises(EnterpriseError) as lower:
        await _apply(service, _event(user_id, session_id, outcome="BASIC", assurance_level="email"))
    assert lower.value.code == "VERIFICATION_TRANSITION_DENIED"
    assert (await service.get_human_status(user_id))["status"] == "IDENTITY_VERIFIED"


@pytest.mark.asyncio
async def test_revocation_disables_previously_issued_key(engine) -> None:
    enable_reference_contract()
    user_id = await _user(engine, "revoke-key@example.com")
    service, session_id = await _session(engine, user_id)
    await _apply(service, _event(user_id, session_id))
    org_id, _env_id = await _development_org(engine, user_id)
    key_id = str(uuid.uuid4())
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(org_api_keys).values(
                id=key_id,
                org_id=org_id,
                key_hash=uuid.uuid4().hex,
                name="agent",
                role=Role.DEVELOPER.value,
                created_at=datetime.now(UTC).isoformat(),
                revoked=0,
                accountable_human_user_id=user_id,
                holder_kind="human_key",
            )
        )
    await _apply(
        service,
        _event(
            user_id,
            session_id,
            event_type="identity.revocation",
            outcome="SUSPENDED",
        ),
    )
    async with engine.raw.connect() as conn:
        key = (
            await conn.execute(select(org_api_keys).where(org_api_keys.c.id == key_id))
        ).fetchone()
    assert key.revoked == 1
    decision = await CredentialIssuancePolicy(engine, service).evaluate(
        principal_user_id=user_id,
        organization_id=org_id,
        environment_id=_env_id,
        requested_scopes=("usage:read",),
    )
    assert decision.allowed is False
    assert decision.reason_code == "VERIFICATION_SUSPENDED"


@pytest.mark.asyncio
async def test_stale_malformed_and_missing_reference_are_rejected(engine) -> None:
    user_id = await _user(engine, "malformed@example.com")
    service, session_id = await _session(engine, user_id)
    stale = (datetime.now(UTC) - timedelta(hours=1)).isoformat()
    body = _event(user_id, session_id)
    payload, signature, timestamp = sign_identity_event(body, ts=stale)
    with pytest.raises(EnterpriseError) as old:
        await service.apply_provider_event(
            payload=payload, signature=signature, timestamp=timestamp
        )
    assert old.value.code == "PROVIDER_SIGNATURE_INVALID"
    missing = dict(body)
    missing["event_id"] = "evt-missing-ref"
    missing.pop("reference_id")
    with pytest.raises(EnterpriseError) as no_ref:
        await _apply(service, missing)
    assert no_ref.value.code == "VERIFICATION_SESSION_REQUIRED"
    altered, signature, timestamp = sign_identity_event(body)
    altered = altered.replace(b"government_id", b"sso_elevated!")
    with pytest.raises(EnterpriseError):
        await service.apply_provider_event(
            payload=altered, signature=signature, timestamp=timestamp
        )


@pytest.mark.asyncio
async def test_http_provider_fails_closed_without_enrollment() -> None:
    with pytest.raises(EnterpriseError) as exc:
        HttpCallbackIdentityProvider.from_env()
    assert exc.value.code == "PROVIDER_NOT_ENROLLED"


@pytest.mark.asyncio
async def test_http_provider_binds_provider_issued_session(monkeypatch) -> None:
    import threading
    from http.server import BaseHTTPRequestHandler, HTTPServer

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            length = int(self.headers.get("Content-Length", "0"))
            raw = self.rfile.read(length)
            claim = json.loads(raw)
            if self.headers.get("Authorization") == "Bearer redirect":
                self.send_response(302)
                self.send_header("Location", "http://127.0.0.1/elsewhere")
                self.end_headers()
                return
            assert claim["subject_id"] == "user-1"
            assert self.headers.get("Authorization") == "Bearer token-1"
            body = json.dumps(
                {"session_id": "prov_sess_1", "hosted_url": "http://127.0.0.1/hosted"}
            ).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, fmt: str, *args) -> None:
            return

    server = HTTPServer(("127.0.0.1", 0), Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        monkeypatch.setenv("WHITEPACT_IDENTITY_PROVIDER_NAME", "example-vendor")
        monkeypatch.setenv(
            "WHITEPACT_IDENTITY_PROVIDER_BASE_URL",
            f"http://127.0.0.1:{server.server_address[1]}",
        )
        monkeypatch.setenv("WHITEPACT_IDENTITY_PROVIDER_API_TOKEN", "token-1")
        monkeypatch.setenv("WHITEPACT_IDENTITY_PROVIDER_WEBHOOK_SECRET", "webhook-secret")
        monkeypatch.setenv("WHITEPACT_IDENTITY_PROVIDER_ALLOW_INSECURE", "1")
        provider = HttpCallbackIdentityProvider.from_env()
        session = provider.start_session(
            subject_id="user-1", return_url="https://app.example/return"
        )
        assert session["session_id"] == "prov_sess_1"
        assert session["provider"] == "example-vendor"
        assert session["subject_id"] == "user-1"
        redirected = HttpCallbackIdentityProvider(
            name="example-vendor",
            base_url=f"http://127.0.0.1:{server.server_address[1]}",
            api_token="redirect",
            webhook_secret="webhook-secret",
            allow_insecure=True,
            timeout_seconds=1,
        )
        with pytest.raises(EnterpriseError) as redirect_error:
            redirected.start_session(subject_id="user-1", return_url=None)
        assert redirect_error.value.code == "PROVIDER_NOT_ENROLLED"
    finally:
        server.shutdown()
        thread.join(timeout=2)


@pytest.mark.asyncio
async def test_concurrent_duplicate_event_is_replay(engine) -> None:
    enable_reference_contract()
    user_id = await _user(engine, "concurrent@example.com")
    service, session_id = await _session(engine, user_id)
    body = _event(user_id, session_id)
    payload, signature, timestamp = sign_identity_event(body)

    async def once():
        try:
            return await service.apply_provider_event(
                payload=payload, signature=signature, timestamp=timestamp
            )
        except EnterpriseError as exc:
            return exc

    first, second = await asyncio.gather(once(), once())
    results = {type(item).__name__ for item in (first, second)}
    assert "EnterpriseError" in results or (
        isinstance(first, EnterpriseError) or isinstance(second, EnterpriseError)
    )
    errors = [item for item in (first, second) if isinstance(item, EnterpriseError)]
    assert errors
    assert errors[0].code == "PROVIDER_REPLAY"
    stored = await service.get_human_status(user_id)
    assert stored["status"] == "IDENTITY_VERIFIED"
    async with engine.raw.connect() as conn:
        user = (await conn.execute(select(web_users).where(web_users.c.id == user_id))).fetchone()
    assert user.verification_status == "IDENTITY_VERIFIED"


@pytest.mark.asyncio
async def test_concurrent_callback_on_postgresql() -> None:
    """Duplicate provider events under real PostgreSQL transactions."""
    from tests.pg_test_url import isolated_pg_url

    generator = isolated_pg_url("m13id")
    url = await generator.__anext__()
    db = create_engine(url)
    try:
        await db.init()
        enable_reference_contract()
        user_id = await _user(db, "pg-concurrent@example.com")
        service, session_id = await _session(db, user_id)
        body = _event(user_id, session_id)
        payload, signature, timestamp = sign_identity_event(body)

        async def once():
            try:
                return await service.apply_provider_event(
                    payload=payload, signature=signature, timestamp=timestamp
                )
            except EnterpriseError as exc:
                return exc

        first, second = await asyncio.gather(once(), once())
        errors = [item for item in (first, second) if isinstance(item, EnterpriseError)]
        assert len(errors) == 1
        assert errors[0].code == "PROVIDER_REPLAY"
        assert (await service.get_human_status(user_id))["status"] == "IDENTITY_VERIFIED"
    finally:
        await db.close()
        await generator.aclose()


@pytest.mark.asyncio
async def test_column_identity_without_provenance_cannot_issue(engine) -> None:
    user_id = await _user(engine, "column-only@example.com")
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(web_users)
            .where(web_users.c.id == user_id)
            .values(verification_status="IDENTITY_VERIFIED")
        )
    service = _service(engine)
    assert (await service.get_human_status(user_id))["status"] != "IDENTITY_VERIFIED"
    org_id, env_id = await _development_org(engine, user_id)
    decision = await CredentialIssuancePolicy(engine, service).evaluate(
        principal_user_id=user_id,
        organization_id=org_id,
        environment_id=env_id,
        requested_scopes=("usage:read",),
    )
    assert decision.allowed is False
    assert decision.reason_code == "IDENTITY_VERIFICATION_REQUIRED"


@pytest.mark.asyncio
async def test_suspended_identity_cannot_be_restored_by_a_new_session(engine) -> None:
    enable_reference_contract()
    user_id = await _user(engine, "suspended-restore@example.com")
    service, session_id = await _session(engine, user_id)
    await _apply(service, _event(user_id, session_id))
    await service.suspend_human(user_id)
    with pytest.raises(EnterpriseError) as started:
        await service.start_human_verification(user_id)
    assert started.value.code == "VERIFICATION_SUSPENDED"
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(identity_verifications).values(
                id=str(uuid.uuid4()),
                user_id=user_id,
                status="REVIEW_REQUIRED",
                provider="hmac-reference",
                provider_reference_id="sess_after_suspend",
                created_at=datetime.now(UTC).isoformat(),
                updated_at=datetime.now(UTC).isoformat(),
            )
        )
    with pytest.raises(EnterpriseError) as restored:
        await _apply(service, _event(user_id, "sess_after_suspend"))
    assert restored.value.code == "VERIFICATION_TRANSITION_DENIED"
    assert (await service.get_human_status(user_id))["status"] == "SUSPENDED"


@pytest.mark.asyncio
async def test_expired_individual_does_not_inherit_old_org_verification(engine) -> None:
    enable_reference_contract()
    user_id = await _user(engine, "individual-expire@example.com")
    service, session_id = await _session(engine, user_id)
    await _apply(service, _event(user_id, session_id))
    past = (datetime.now(UTC) - timedelta(days=1)).isoformat()
    now = datetime.now(UTC).isoformat()
    org_id = str(uuid.uuid4())
    async with engine.raw.begin() as conn:
        await conn.execute(
            update(identity_verifications)
            .where(identity_verifications.c.user_id == user_id)
            .values(expires_at=past)
        )
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name="Solo",
                slug=f"solo-{uuid.uuid4().hex[:8]}",
                monthly_budget_usd=0,
                created_at=now,
                plan="FREE",
                governance_status="ACTIVE",
                workspace_kind="INDIVIDUAL",
                owner_user_id=user_id,
            )
        )
        await conn.execute(
            insert(organization_verifications).values(
                id=str(uuid.uuid4()),
                org_id=org_id,
                status="ORGANIZATION_VERIFIED",
                provider="hmac-reference",
                created_at=now,
                updated_at=now,
            )
        )
    status = await service.get_org_status(org_id)
    assert status["status"] != "ORGANIZATION_VERIFIED"
    assert status["individual_status"] == "EXPIRED"


@pytest.mark.asyncio
async def test_removing_approved_assurance_invalidates_issuance(engine) -> None:
    enable_reference_contract()
    user_id = await _user(engine, "policy-drop@example.com")
    service, session_id = await _session(engine, user_id)
    await _apply(service, _event(user_id, session_id))
    org_id, env_id = await _development_org(engine, user_id)
    policy = CredentialIssuancePolicy(engine, service)
    allowed = await policy.evaluate(
        principal_user_id=user_id,
        organization_id=org_id,
        environment_id=env_id,
        requested_scopes=("usage:read",),
    )
    assert allowed.allowed is True
    os.environ.pop("WHITEPACT_IDENTITY_APPROVED_ASSURANCE_LEVELS", None)
    denied = await policy.evaluate(
        principal_user_id=user_id,
        organization_id=org_id,
        environment_id=env_id,
        requested_scopes=("usage:read",),
    )
    assert denied.allowed is False
    assert denied.reason_code == "IDENTITY_VERIFICATION_REQUIRED"
