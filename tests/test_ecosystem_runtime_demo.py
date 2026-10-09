# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The ecosystem demonstration must show real denials, not a simulated allow."""

from __future__ import annotations

from examples.ecosystem.runtime_authorization_demo import run_demo


def test_runtime_authorization_demo_never_executes_a_denied_action() -> None:
    report = run_demo()

    denied = report["denied_before_execution"]
    assert denied["decision"] == "DENY"
    assert denied["authorization_issued"] is False
    assert denied["executed"] is False
    assert denied["reason_codes"] == ["AUTHORITY_NOT_DELEGATED:action_type=payment"]

    approval = report["human_approval_required"]
    assert approval["decision"] == "REQUIRE_APPROVAL"
    assert approval["authorization_issued"] is False
    assert approval["executed"] is False

    grant = report["expired_grant"]
    assert grant["is_legitimate"] is True
    assert grant["is_expired"] is True
    assert grant["is_usable"] is False
    assert grant["executed"] is False

    replay = report["replay_refused"]
    assert replay["first_admission_consumed"] is True
    assert replay["replay_refused"] is True
    assert replay["executed"] is False

    assert report["tenant_isolation"]["cross_tenant_closed"] is True
    assert report["evidence"]["secret_absent"] is True
    assert report["evidence"]["argument_keys"] == ["api_token"]
    assert report["evidence"]["executed"] is False
