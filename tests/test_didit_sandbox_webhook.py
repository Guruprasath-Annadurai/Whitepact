# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Didit sandbox webhook contract. These events are not identity proofs."""

import hashlib
import hmac
import json
from pathlib import Path

from fastapi.testclient import TestClient

from responsibleai.enterprise.didit_sandbox import canonical_json
from responsibleai.enterprise.didit_sandbox_app import app
from responsibleai.enterprise.router import _verification

SECRET = "sandbox-webhook-secret-not-a-live-credential"
APPLICATION = "11111111-2222-3333-4444-555555555555"
WORKFLOW = "66666666-7777-8888-9999-000000000000"
SESSION = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
OTHER_SESSION = "bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee"
NOW = 1_775_000_000


def _body(**overrides):
    body = {
        "event_id": "9c0c8b8a-1111-4222-9333-444444444444",
        "webhook_type": "status.updated",
        "timestamp": NOW,
        "application_id": APPLICATION,
        "environment": "sandbox",
        "session_id": SESSION,
        "status": "Declined",
        "workflow_id": WORKFLOW,
        "decision": {"name": "José Example", "document_number": "should-not-be-stored"},
    }
    body.update(overrides)
    return body


def _sign(body, secret=SECRET):
    canonical = canonical_json(body)
    return hmac.new(secret.encode(), canonical.encode(), hashlib.sha256).hexdigest()


def _simple(body, secret=SECRET):
    signed = f"{body['timestamp']}:{body['session_id']}:{body['status']}:{body['webhook_type']}"
    return hmac.new(secret.encode(), signed.encode(), hashlib.sha256).hexdigest()


def _client(monkeypatch, tmp_path: Path, *, sessions: str = SESSION):
    monkeypatch.setenv("WHITEPACT_DIDIT_SANDBOX", "1")
    monkeypatch.setenv("WHITEPACT_ENV", "sandbox")
    monkeypatch.setenv("WHITEPACT_DIDIT_SANDBOX_WEBHOOK_SECRET", SECRET)
    monkeypatch.setenv("WHITEPACT_DIDIT_SANDBOX_APPLICATION_ID", APPLICATION)
    monkeypatch.setenv("WHITEPACT_DIDIT_SANDBOX_WORKFLOW_ID", WORKFLOW)
    monkeypatch.setenv("WHITEPACT_DIDIT_SANDBOX_SESSION_IDS", sessions)
    monkeypatch.setenv("WHITEPACT_DIDIT_SANDBOX_LEDGER", str(tmp_path / "ledger.sqlite"))
    monkeypatch.delenv("WHITEPACT_DIDIT_SANDBOX_WEBHOOK_SECRET_PREVIOUS", raising=False)
    return TestClient(app)


def _post(client, body, *, signature=None, timestamp=None, simple=None, now=NOW):
    from responsibleai.enterprise import didit_sandbox

    original = didit_sandbox.time.time
    didit_sandbox.time.time = lambda: now
    try:
        headers = {
            "X-Timestamp": str(body["timestamp"] if timestamp is None else timestamp),
            "X-Signature-V2": _sign(body) if signature is None else signature,
        }
        if simple is not None:
            headers["X-Signature-Simple"] = simple
        return client.post(
            "/api/enterprise/identity/verification/didit/sandbox",
            content=json.dumps(body, ensure_ascii=False).encode(),
            headers=headers,
        )
    finally:
        didit_sandbox.time.time = original


def test_unicode_declined_event_is_stored_without_identity_elevation(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = _post(client, _body())
    assert response.status_code == 200
    assert response.json()["result"] == "sandbox_receipt_stored"
    assert response.json()["status"] == "Declined"
    assert "IDENTITY_VERIFIED" not in response.text
    stored = (tmp_path / "ledger.sqlite").read_bytes()
    assert b"Jos" not in stored
    assert b"should-not-be-stored" not in stored
    assert (tmp_path / "ledger.sqlite").stat().st_mode & 0o077 == 0


def test_invalid_signature_is_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = _post(client, _body(), signature="ab" * 32)
    assert response.status_code == 401
    assert response.json()["error"] == "signature_rejected"


def test_simple_signature_alone_is_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    body = _body()
    response = _post(client, body, signature="", simple=_simple(body))
    assert response.status_code == 401
    assert response.json()["error"] == "simple_signature_rejected"


def test_replayed_event_is_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    body = _body(status="Approved")
    assert _post(client, body).status_code == 200
    replay = _post(client, body)
    assert replay.status_code == 409
    assert replay.json()["error"] == "replayed_event"


def test_stale_timestamp_is_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    body = _body(timestamp=NOW - 301)
    response = _post(client, body, now=NOW)
    assert response.status_code == 401
    assert response.json()["error"] == "stale_timestamp"


def test_mismatched_workflow_is_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    body = _body(workflow_id="99999999-9999-9999-9999-999999999999")
    response = _post(client, body)
    assert response.status_code == 403
    assert response.json()["error"] == "workflow_mismatch"


def test_mismatched_session_is_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = _post(client, _body(session_id=OTHER_SESSION))
    assert response.status_code == 403
    assert response.json()["error"] == "session_mismatch"


def test_live_environment_is_rejected(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    response = _post(client, _body(environment="live"))
    assert response.status_code == 403
    assert response.json()["error"] == "environment_rejected"


def test_production_process_disables_the_receiver(monkeypatch, tmp_path):
    client = _client(monkeypatch, tmp_path)
    monkeypatch.setenv("WHITEPACT_ENV", "production")
    response = _post(client, _body())
    assert response.status_code == 404
    assert response.json()["error"] == "sandbox_disabled"


def test_reference_webhook_constructor_is_unchanged():
    source = Path(__file__).parents[1].joinpath("src/responsibleai/enterprise/router.py").read_text()
    function = source.split("def _verification", 1)[1].split("\nasync def ", 1)[0]
    assert "HmacVerificationProvider" in function
    assert "didit" not in function.lower()
    assert _verification.__defaults__ is None
