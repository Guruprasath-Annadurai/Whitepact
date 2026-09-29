# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from responsibleai.whitepact_cloud.admin_grant import (
    GrantDecision,
    consume_grant,
    issue_admin_grant,
    revoke_grant,
    verify_admin_grant,
)
from responsibleai.whitepact_cloud.roles import CloudRole


def test_developer_cannot_receive_iam_write() -> None:
    key = b"test-signing-key-32-bytes-min!!!"
    try:
        issue_admin_grant(
            employee_id="emp-1",
            role=CloudRole.DEVELOPER,
            operation="iam.change",
            provider="hetzner",
            resource_target="project/production",
            permissions=["cloud.iam.write"],
            policy_id="pol-1",
            approval=GrantDecision.APPROVED,
            approved_by="owner",
            ttl_seconds=300,
            signing_key=key,
        )
    except PermissionError:
        return
    raise AssertionError("expected PermissionError")


def test_grant_expiry_and_revocation() -> None:
    key = b"test-signing-key-32-bytes-min!!!"
    grant, sig = issue_admin_grant(
        employee_id="emp-2",
        role=CloudRole.PLATFORM_ENGINEER,
        operation="infra.plan",
        provider="hetzner",
        resource_target="server/wp-prod-saas-1",
        permissions=["cloud.infra.read"],
        policy_id="pol-2",
        approval=GrantDecision.APPROVED,
        approved_by="owner",
        ttl_seconds=60,
        signing_key=key,
        founder_only_exception=True,
    )
    assert verify_admin_grant(grant, sig, key)["ok"] is True

    expired = grant.__class__(
        **{
            **grant.__dict__,
            "expires_at": datetime.now(UTC) - timedelta(seconds=1),
        }
    )
    assert verify_admin_grant(expired, sig, key)["ok"] is False

    revoked = revoke_grant(grant)
    assert verify_admin_grant(revoked, sig, key)["reason"] == "revoked"

    consumed = consume_grant(grant)
    assert verify_admin_grant(consumed, sig, key)["reason"] == "replay"
