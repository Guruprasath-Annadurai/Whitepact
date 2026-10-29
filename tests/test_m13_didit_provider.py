# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Didit wire-contract tests. Locally signed fixtures are never provider proof."""

import hashlib
import hmac
import json
import time
import uuid

import httpx
import pytest

from responsibleai.enterprise.errors import EnterpriseError


def event(**changes):
    body = dict(
        event_id=str(uuid.uuid4()),
        webhook_type="status.updated",
        timestamp=int(time.time()),
        created_at=int(time.time()) - 1,
        application_id="app",
        environment="sandbox",
        workflow_id="workflow",
        session_id=str(uuid.uuid4()),
        vendor_data="user",
        status="Approved",
    )
    body.update(changes)
    return body


def signed(body):
    payload = json.dumps(body, ensure_ascii=False).encode()
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode()
    return (
        payload,
        hmac.new(b"local-contract-secret", canonical, hashlib.sha256).hexdigest(),
        str(body["timestamp"]),
    )


def provider(transport=None):
    from responsibleai.enterprise.didit import DiditProvider

    return DiditProvider(
        api_key="local-contract-key",
        webhook_secret="local-contract-secret",
        workflow_id="workflow",
        application_id="app",
        environment="sandbox",
        transport=transport,
    )


def test_v2_unicode_full_body_and_timestamp_binding():
    body = event(metadata={"name": "Jos\u00e9"})
    payload, sig, ts = signed(body)
    assert (
        provider().verify_webhook(payload=payload, signature=sig, timestamp=ts)["event_id"]
        == body["event_id"]
    )
    with pytest.raises(EnterpriseError):
        provider().verify_webhook(
            payload=payload.replace(b"Approved", b"Declined"), signature=sig, timestamp=ts
        )
    with pytest.raises(EnterpriseError):
        provider().verify_webhook(payload=payload, signature=sig, timestamp=str(int(ts) + 1))


@pytest.mark.parametrize(
    "change",
    [
        {"timestamp": 1},
        {"application_id": "other"},
        {"environment": "live"},
        {"workflow_id": "other"},
        {"webhook_type": "auth.login"},
        {"event_id": ""},
    ],
)
def test_untrusted_scope_and_stale_events_fail(change):
    payload, sig, ts = signed(event(**change))
    with pytest.raises(EnterpriseError):
        provider().verify_webhook(payload=payload, signature=sig, timestamp=ts)


def test_session_wire_contract_and_no_application_uuid_in_request():
    def server(req):
        assert req.url == httpx.URL("https://verification.didit.me/v3/session/")
        assert req.headers["x-api-key"] == "local-contract-key"
        assert json.loads(req.content) == {"workflow_id": "workflow", "vendor_data": "user"}
        return httpx.Response(
            201,
            json={
                "session_id": "session",
                "url": "https://verify.didit.me/session/test",
                "workflow_id": "workflow",
                "vendor_data": "user",
            },
        )

    p = provider(httpx.MockTransport(server))
    assert p.start_session(subject_id="user", return_url=None) == {
        "provider": "didit-sandbox",
        "session_id": "session",
        "subject_id": "user",
        "hosted_url": "https://verify.didit.me/session/test",
    }


@pytest.mark.parametrize(
    "url", ["http://verify.didit.me/x", "https://evil.invalid/x", "javascript:alert(1)"]
)
def test_hosted_redirect_urls_fail_closed(url):
    p = provider(
        httpx.MockTransport(lambda req: httpx.Response(201, json={"session_id": "s", "url": url}))
    )
    with pytest.raises(EnterpriseError):
        p.start_session(subject_id="user", return_url=None)


def test_transport_failure_is_sanitized():
    def server(req):
        raise httpx.ConnectError("secret=/private/path key=do-not-leak")

    with pytest.raises(EnterpriseError) as caught:
        provider(httpx.MockTransport(server)).start_session(subject_id="u", return_url=None)
    assert "private" not in str(caught.value) and "do-not-leak" not in str(caught.value)
