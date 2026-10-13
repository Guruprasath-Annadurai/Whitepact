# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Billing sandbox and SaaS admin checks that do not make a commercial decision."""

from __future__ import annotations

import hashlib
import hmac
from datetime import UTC, datetime

import pytest

from responsibleai.billing.paddle_service import (
    PADDLE_API_BASES,
    PaddleBillingError,
    PaddleBillingService,
    PaddleWebhookRejected,
    verify_paddle_webhook_signature,
)
from responsibleai.enterprise.security.policy import (
    AuthenticationSecurityPolicy,
    AuthMethod,
    OrgAuthPolicy,
    SessionAssurance,
)
from responsibleai.rbac.models import Plan


def _sign(secret: str, body: bytes, timestamp: int) -> str:
    digest = hmac.new(secret.encode(), f"{timestamp}:".encode() + body, hashlib.sha256).hexdigest()
    return f"ts={timestamp};h1={digest}"


def test_unsigned_and_wrong_paddle_webhook_rejected() -> None:
    now = datetime(2026, 10, 9, 12, 0, tzinfo=UTC)
    body = b'{"event_id":"evt_sandbox","event_type":"subscription.activated"}'
    with pytest.raises(PaddleWebhookRejected, match="not configured") as missing:
        verify_paddle_webhook_signature("", body, "ts=1;h1=ab", now=now)
    assert missing.value.status_code == 503
    with pytest.raises(PaddleWebhookRejected, match="Missing Paddle-Signature") as absent:
        verify_paddle_webhook_signature("sandbox-webhook-secret", body, "", now=now)
    assert absent.value.status_code == 400
    stamped = int(now.timestamp())
    with pytest.raises(PaddleWebhookRejected, match="Invalid Paddle webhook signature"):
        verify_paddle_webhook_signature(
            "sandbox-webhook-secret",
            body,
            _sign("other-secret", body, stamped),
            now=now,
        )
    verify_paddle_webhook_signature(
        "sandbox-webhook-secret",
        body,
        _sign("sandbox-webhook-secret", body, stamped),
        now=now,
    )
    with pytest.raises(PaddleWebhookRejected, match="expired"):
        verify_paddle_webhook_signature(
            "sandbox-webhook-secret",
            body,
            _sign("sandbox-webhook-secret", body, stamped - 301),
            now=now,
        )


def test_sandbox_client_refuses_a_live_key_and_stays_on_the_sandbox_host() -> None:
    service = PaddleBillingService(
        "pdl_sdbx_apikey_test",  # gitleaks:allow
        {Plan.PRO: "pri_sandbox"},
        environment="sandbox",
    )
    assert service._api_base == PADDLE_API_BASES["sandbox"]
    assert "sandbox-api.paddle.com" in service._api_base
    with pytest.raises(PaddleBillingError, match="sandbox"):
        PaddleBillingService(
            "pdl_live_apikey_test", {Plan.PRO: "pri_sandbox"}, environment="sandbox"
        )


def test_saas_admin_downgrade_and_sso_do_not_require_a_commercial_plan() -> None:
    policy = AuthenticationSecurityPolicy()
    org = OrgAuthPolicy(sso_enforcement="SSO_REQUIRED", phishing_resistant_required=True)
    denied = policy.evaluate_login(methods=(AuthMethod.PASSWORD,), role="OWNER", org=org)
    assert denied.allowed is False
    assert denied.code == "SSO_REQUIRED"
    session = SessionAssurance(
        level="PASSWORD",
        methods=(AuthMethod.PASSWORD,),
        auth_time="2026-10-09T00:00:00Z",
        phishing_resistant=False,
        session_id="sess-offline",
        user_id="user-offline",
        org_id="org-offline",
    )
    downgrade = policy.evaluate_downgrade(
        action="DISABLE_MFA",
        remaining_strong_factors=0,
        session=session,
        org=org,
    )
    assert downgrade.allowed is False
    assert downgrade.code == "SECURITY_DOWNGRADE_BLOCKED"
