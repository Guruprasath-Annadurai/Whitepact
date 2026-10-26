# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""SYNTHETIC protocol fixtures, not Persona-issued inquiries or assessments."""

import hashlib
import hmac
import json
import secrets
import sqlite3
import time
from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from responsibleai.data_governance.tenant_controller import postgres_identity
from responsibleai.enterprise.persona_sandbox import (
    PersonaSandboxAdapter,
    PersonaSandboxPolicy,
    PersonaSandboxRefusedError,
    verify_persona_signature,
)
from tests.test_stage3_controller_postgres import isolated_controller_context


def signed(body, secret, timestamp=None):
    stamp = str(int(time.time()) if timestamp is None else timestamp)
    digest = hmac.new(secret, stamp.encode() + b"." + body, hashlib.sha256).hexdigest()
    return f"t={stamp},v1={digest}"


def test_hosted_persona_step_has_explicit_disposable_pg16_target():
    """The strict PG16 runner must not rely on another pytest process's env."""
    import yaml

    workflow = yaml.safe_load(
        (Path(__file__).parents[1] / ".github/workflows/m13i1-integration.yml").read_text()
    )
    job = workflow["jobs"]["persona-sandbox-protocol"]
    step = next(
        value
        for value in job["steps"]
        if value.get("name") == "Isolated Persona synthetic protocol and HMAC denial regressions"
    )
    assert step["env"].get("WHITEPACT_TEST_PG_ADMIN_URL") == (
        "postgresql://wp:wp@127.0.0.1:55432/postgres"
    )
    assert job["services"]["postgres"]["ports"] == ["55432:5432"]
    assert "postgres:16-alpine@sha256:" in job["services"]["postgres"]["image"]
    assert "--diagnostic-no-coverage" not in step["run"]
    assert "skip_count" in step["run"]
    # Pin every pre-shard security command from c9fb5474, including its no-skip
    # check. Sharding may relocate commands, never shorten or waive them.
    expected = {
        "Independently execute original assertion suites": "c2f71fbb228fd0ccc870d0f0b9490d13dadbd1970dc238c3522313d3fe5e949d",
        "Revocation and egress regression scope": "393688a03037b7e86b4d52ee0d3c7d2b5c56c7a880a952307731748445c627f3",
        "Full MCP transport and session-binding regression": "fa29ffc98fa4852de56e951f56a474e2e0b68083415b3cde08dd423dca3c5023",
        "Mandatory passkey downgrade restriction and supported rollback": "93d0c84d4ca13c143d03b7deb2f442c21f69e5b07b273d736c654dca7ab0708b",
        "Mandatory root email and persisted owner denial boundaries": "0054ab195b51b17529548cd242b83cd2843ab9afb201028b71e68b1193a83a94",
        "WebAuthn product origin binding and unchanged identity security": "bfba3acda163eb6d3cf0ceeae0e0ff7e97ca3dcd29f942ba951fd3399747fafa",
        "Isolated Persona synthetic protocol and HMAC denial regressions": "291ac7f06637f4e8c8eb0fa0550fcdc2eac6c7ea7795a9b255353ca21b24de76",
    }
    found = {}
    for name, budget in (
        ("independent-security", 25),
        ("independent-mcp", 25),
        ("persona-sandbox-protocol", 15),
    ):
        shard = workflow["jobs"][name]
        assert shard["timeout-minutes"] == budget
        assert shard["strategy"]["matrix"]["python"] == ["3.11", "3.12"]
        assert shard["strategy"]["fail-fast"] is False
        assert not shard.get("continue-on-error")
        for command in shard["steps"]:
            if command.get("name") in expected:
                assert command["name"] not in found
                assert not command.get("continue-on-error")
                found[command["name"]] = hashlib.sha256(command["run"].encode()).hexdigest()
    assert found == expected


@pytest.fixture
async def persona(tmp_path, monkeypatch):
    async with isolated_controller_context(
        tmp_path, monkeypatch, "wp_persona_sandbox_qualification"
    ) as (service, _, user, token, csrf):
        tenant = await service.create(
            session_token=token,
            csrf=csrf,
            request_id="persona-protocol-fixture",
            name="Disposable Persona protocol",
            slug="persona-fixture",
            attach_session=True,
        )
        async with service.engine.raw.connect() as connection:
            identity = await postgres_identity(connection)
        policy = PersonaSandboxPolicy(
            "disposable-persona-protocol",
            identity,
            "env_sandboxfixture",
            "org_fixture",
            "itmpl_fixture",
            "itmplv_fixture",
            "fixture-policy-v1",
        )
        secret = secrets.token_bytes(32)
        config = {
            "reference": None,
            "status": "pending",
            "response_environment": policy.provider_environment_id,
            "response_status": 200,
            "calls": [],
            "cancel_get": False,
        }

        def data():
            return {
                "type": "inquiry",
                "id": "inq_SYNTHETICfixture",
                "attributes": {
                    "status": config["status"],
                    "reference-id": config["reference"],
                    "expires-at": None,
                },
                "relationships": {
                    "inquiry-template": {"data": {"id": policy.template_id}},
                    "inquiry-template-version": {"data": {"id": policy.template_version_id}},
                },
            }

        async def provider(request):
            config["calls"].append((request.method, request.url.path))
            assert request.url.host == "api.withpersona.com"
            assert request.headers["Persona-Version"] == "2026-09-29"
            if request.method == "POST":
                config["reference"] = json.loads(request.content)["data"]["attributes"][
                    "reference-id"
                ]
                assert request.headers["Idempotency-Key"] == config["reference"]
            if config["cancel_get"] and request.method == "GET":
                import asyncio

                raise asyncio.CancelledError
            return httpx.Response(
                201
                if request.method == "POST" and config["response_status"] == 200
                else config["response_status"],
                headers={
                    "Persona-Environment-Id": config["response_environment"],
                    "Persona-Organization-Id": policy.provider_organization_id,
                },
                json={"data": data()},
            )

        monkeypatch.setenv("WHITEPACT_ENV", "development")
        adapter = PersonaSandboxAdapter(
            service.engine,
            policy,
            api_key="persona_sandbox_" + secrets.token_urlsafe(32),
            webhook_secrets=(secret,),
            ledger_path=tmp_path / "persona.sqlite3",
            _test_transport=httpx.MockTransport(provider),
        )

        def event(name="inquiry.approved", event_id="evt_SYNTHETICapproved"):
            return json.dumps(
                {
                    "data": {
                        "id": event_id,
                        "type": "event",
                        "attributes": {
                            "name": name,
                            "created-at": datetime.now(UTC).isoformat(),
                            "payload": {"data": data()},
                        },
                    }
                },
                separators=(",", ":"),
            ).encode()

        yield adapter, config, event, secret, token, csrf, tenant, user


async def start(target):
    adapter, _, _, _, token, csrf, tenant, _ = target
    return await adapter.start(session_token=token, csrf=csrf, tenant_id=tenant)


@pytest.mark.asyncio
@pytest.mark.parametrize("falsey_transport", [False, True])
async def test_sandbox_approval_is_bound_simulated_and_never_canonical_identity(
    persona, falsey_transport
):
    adapter, config, event, secret, _, _, tenant, user = persona
    if falsey_transport:

        class FalseyMockTransport(httpx.MockTransport):
            def __bool__(self):
                return False

        adapter._transport = FalseyMockTransport(adapter._transport.handler)
    issued = await start(persona)
    config["status"] = "approved"
    body = event()
    receipt = await adapter.handle_webhook(body, signed(body, secret))
    assert receipt["outcome"] == "SANDBOX_APPROVED"
    assert receipt["provenance"] == "SANDBOX_SIMULATED"
    assert receipt["evidence_mode"] == "SYNTHETIC_PROTOCOL_FIXTURE"
    assert not receipt["canonical_issuance_allowed"]
    assert (receipt["customer_id"], receipt["tenant_id"]) == (user, tenant)
    assert receipt["inquiry_id"] == issued["inquiry_id"]
    assert config["calls"] == [
        ("POST", "/api/v1/inquiries"),
        ("GET", "/api/v1/inquiries/inq_SYNTHETICfixture"),
    ]
    with adapter._ledger() as store:
        assert store.execute("SELECT provenance FROM inquiries").fetchone() == (
            "SANDBOX_SIMULATED",
        )
    async with adapter.engine.raw.connect() as connection:
        status = await connection.scalar(
            text("SELECT verification_status FROM web_users WHERE id=:user"), {"user": user}
        )
        assert status != "IDENTITY_VERIFIED"
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM governance_execution_authorizations")
            )
            == 0
        )


@pytest.mark.asyncio
async def test_completed_alone_is_not_approval_then_real_decision_protocol_can_advance(persona):
    adapter, config, event, secret, *_ = persona
    await start(persona)
    config["status"] = "completed"
    body = event("inquiry.completed", "evt_SYNTHETICcompleted")
    assert (await adapter.handle_webhook(body, signed(body, secret)))["outcome"] == "PENDING"
    config["status"] = "approved"
    body = event()
    assert (await adapter.handle_webhook(body, signed(body, secret)))[
        "outcome"
    ] == "SANDBOX_APPROVED"


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault", ["reference", "template", "version", "environment", "declined", "expired", "api_error"]
)
async def test_signed_event_cannot_override_provider_or_binding_failure(persona, fault):
    adapter, config, event, secret, *_ = persona
    await start(persona)
    config["status"] = "approved"
    value = json.loads(event())
    inquiry = value["data"]["attributes"]["payload"]["data"]
    if fault == "reference":
        inquiry["attributes"]["reference-id"] = "another-tenant"
    elif fault == "template":
        inquiry["relationships"]["inquiry-template"]["data"]["id"] = "itmpl_other"
    elif fault == "version":
        inquiry["relationships"]["inquiry-template-version"]["data"]["id"] = "itmplv_other"
    elif fault == "environment":
        config["response_environment"] = "env_production"
    elif fault == "declined":
        config["status"] = "declined"
    elif fault == "expired":
        inquiry["attributes"]["expires-at"] = "2000-01-01T00:00:00Z"
    else:
        config["response_status"] = 503
    body = json.dumps(value).encode()
    result = await adapter.handle_webhook(body, signed(body, secret))
    assert result["outcome"] == "DENIED"
    assert not result["canonical_issuance_allowed"]


@pytest.mark.asyncio
async def test_duplicate_restart_and_conflicting_replay_preserve_denial(persona):
    adapter, config, event, secret, *_ = persona
    await start(persona)
    config["status"] = "approved"
    body = event()
    await adapter.handle_webhook(body, signed(body, secret))
    restarted = PersonaSandboxAdapter(
        adapter.engine,
        adapter.policy,
        api_key=adapter._key,
        webhook_secrets=(secret,),
        ledger_path=adapter.path,
        _test_transport=adapter._transport,
    )
    calls = len(config["calls"])
    assert (await restarted.handle_webhook(body, signed(body, secret)))["duplicate"]
    assert len(config["calls"]) == calls
    changed = json.loads(body)
    changed["data"]["attributes"]["name"] = "inquiry.declined"
    changed = json.dumps(changed).encode()
    with pytest.raises(PersonaSandboxRefusedError, match="Conflicting event replay"):
        await restarted.handle_webhook(changed, signed(changed, secret))
    result = await restarted.handle_webhook(body, signed(body, secret))
    assert result["outcome"] == "CONFLICT"


@pytest.mark.asyncio
async def test_decline_then_approval_never_resurrects_and_expiry_denies(persona):
    adapter, config, event, secret, *_ = persona
    await start(persona)
    config["status"] = "declined"
    body = event("inquiry.declined", "evt_SYNTHETICdeclined")
    assert (await adapter.handle_webhook(body, signed(body, secret)))["outcome"] == "DENIED"
    config["status"] = "approved"
    body = event()
    assert (await adapter.handle_webhook(body, signed(body, secret)))["outcome"] == "CONFLICT"
    with adapter._ledger() as store:
        store.execute("UPDATE inquiries SET expires=?", (time.time() - 1,))
    assert (await adapter.handle_webhook(body, signed(body, secret)))["outcome"] == "EXPIRED"


@pytest.mark.asyncio
async def test_cancelled_worker_never_reuses_incomplete_assessment(persona):
    import asyncio

    adapter, config, event, secret, *_ = persona
    await start(persona)
    config["status"], config["cancel_get"] = "approved", True
    body = event()
    with pytest.raises(asyncio.CancelledError):
        await adapter.handle_webhook(body, signed(body, secret))
    config["cancel_get"] = False
    receipt = await adapter.handle_webhook(body, signed(body, secret))
    assert receipt["duplicate"] and receipt["outcome"] == "REVIEW_REQUIRED"
    assert not receipt["canonical_issuance_allowed"]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "fault", ["csrf", "tenant", "session", "audience", "environment", "database"]
)
async def test_session_and_target_isolation(persona, monkeypatch, fault):
    adapter, config, _, _, token, csrf, tenant, _ = persona
    if fault == "audience":
        adapter.policy = replace(adapter.policy, audience="production")
    elif fault == "environment":
        monkeypatch.setenv("WHITEPACT_ENV", "staging")
    elif fault == "database":
        adapter.policy = replace(adapter.policy, database_identity="other")
    with pytest.raises(PersonaSandboxRefusedError):
        await adapter.start(
            session_token="expired" if fault == "session" else token,
            csrf="invalid" if fault == "csrf" else csrf,
            tenant_id="other" if fault == "tenant" else tenant,
        )
    assert config["calls"] == []


@pytest.mark.parametrize("fault", ["signature", "stale", "future", "body", "malformed"])
def test_signature_protocol_denies_untrusted_input(fault):
    body, secret = b'{"synthetic":true}', secrets.token_bytes(32)
    header = signed(body, secret)
    if fault == "signature":
        header = signed(body, secrets.token_bytes(32))
    elif fault == "stale":
        header = signed(body, secret, int(time.time()) - 301)
    elif fault == "future":
        header = signed(body, secret, int(time.time()) + 60)
    elif fault == "body":
        body += b" "
    else:
        header = "invalid"
    with pytest.raises(PersonaSandboxRefusedError):
        verify_persona_signature(body, header, (secret,))


def test_rotating_raw_body_signature_accepts_only_enrolled_secret():
    body, old, current = b'{ "synthetic": true }', secrets.token_bytes(32), secrets.token_bytes(32)
    verify_persona_signature(body, signed(body, old) + " " + signed(body, current), (current,))


@pytest.mark.asyncio
async def test_creation_failure_is_one_shot_and_retains_unknown(persona):
    adapter, config, *_ = persona
    config["response_status"] = 503
    with pytest.raises(PersonaSandboxRefusedError, match="Provider request refused"):
        await start(persona)
    assert config["calls"] == [("POST", "/api/v1/inquiries")]
    with adapter._ledger() as store:
        assert store.execute("SELECT inquiry,state FROM inquiries").fetchone() == (None, "UNKNOWN")


@pytest.mark.asyncio
@pytest.mark.parametrize("fault", ["production_key", "production_environment", "unrelated_ledger"])
async def test_unapproved_credentials_environment_and_ledger_are_refused(
    persona, monkeypatch, fault
):
    adapter, config, _, secret, *_ = persona
    path = adapter.path.with_name("not-enrolled.sqlite3")
    api_key = adapter._key
    before = None
    if fault == "production_key":
        api_key = "persona_production_" + secrets.token_urlsafe(32)
    elif fault == "production_environment":
        monkeypatch.setenv("WHITEPACT_ENV", "production")
    else:
        with sqlite3.connect(path) as store:
            store.execute("CREATE TABLE unrelated(evidence TEXT)")
        path.chmod(0o600)
        before = path.read_bytes()
    with pytest.raises(PersonaSandboxRefusedError):
        PersonaSandboxAdapter(
            adapter.engine,
            adapter.policy,
            api_key=api_key,
            webhook_secrets=(secret,),
            ledger_path=path,
            _test_transport=adapter._transport,
        )
    assert config["calls"] == []
    if before is None:
        assert not path.exists()
    else:
        assert path.read_bytes() == before


@pytest.mark.asyncio
async def test_concurrent_duplicate_is_consumed_once(persona):
    import asyncio

    adapter, config, event, secret, *_ = persona
    await start(persona)
    config["status"] = "approved"
    body = event()
    receipts = await asyncio.gather(
        adapter.handle_webhook(body, signed(body, secret)),
        adapter.handle_webhook(body, signed(body, secret)),
    )
    assert all(not receipt["canonical_issuance_allowed"] for receipt in receipts)
    assert sum(receipt["duplicate"] for receipt in receipts) == 1
    assert config["calls"].count(("GET", "/api/v1/inquiries/inq_SYNTHETICfixture")) == 1
    with adapter._ledger() as store:
        assert store.execute("SELECT count(*) FROM events").fetchone() == (1,)
