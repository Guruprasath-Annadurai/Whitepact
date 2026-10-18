# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Negative reproducers for M13-H1 Tenant Isolation vulnerabilities."""

from __future__ import annotations

import uuid
from unittest.mock import MagicMock

import httpx
import pytest

import responsibleai.isolation.in_flight as tracking
from responsibleai.dashboard.config import get_settings
from responsibleai.mcp.server import _build_http_app


@pytest.mark.asyncio
async def test_reproduce_sse_unscoped_credential_bypasses_tenant_check(monkeypatch):
    """DEFECT H1-01: An unscoped credential (ctx.org_id=None) bypasses the cross-tenant check.

    When owner_client_id is set to 'tenant-A', any caller with ctx.org_id=None or
    ctx.org_id != 'tenant-A' must be rejected with 403 Forbidden.
    """
    settings = get_settings()
    monkeypatch.setattr(settings, "mcp_http_allow_unauthenticated_demo", True)
    app = _build_http_app()
    endpoint = None
    for route in app.routes:
        if getattr(route, "path", None) in {"/messages", "/messages/"}:
            endpoint = getattr(route, "app", None) or getattr(route, "endpoint", None)
            break
    assert endpoint is not None, "Could not find /messages/ endpoint in app.routes"

    session_id = uuid.uuid4()
    endpoint.transport._read_stream_writers = {session_id: MagicMock()}
    endpoint.transport._session_owners = {session_id: {"client_id": "tenant-A"}}

    async def mock_handle_post_message(scope, receive, send):
        from starlette.responses import JSONResponse

        resp = JSONResponse({"status": "bypassed_to_handle_post_message"}, status_code=200)
        await resp(scope, receive, send)

    endpoint.transport.handle_post_message = mock_handle_post_message

    async with httpx.AsyncClient(
        transport=httpx.ASGITransport(app=app), base_url="http://test"
    ) as client:
        resp = await client.post(
            f"/messages/?session_id={session_id.hex}",
            json={"jsonrpc": "2.0", "method": "ping", "id": 1},
        )

    # In the unfixed code:
    # owner_client_id is "tenant-A"
    # ctx.org_id is None
    # `owner_client_id and ctx.org_id and owner_client_id != ctx.org_id` -> False!
    # `owner_subject and ctx.key_id and owner_subject != ctx.key_id` -> False!
    # So handle_post_message was called and resp is NOT 403!
    assert resp.status_code == 403, (
        f"VULNERABILITY CONFIRMED: Expected 403 Forbidden, but got {resp.status_code} "
        "(unscoped key bypassed tenant check)!"
    )


def test_reproduce_distributed_tracking_prefix_ambiguity(tmp_path):
    """DEFECT H1-02: Tracking prefix ambiguity causes cross-tenant false attribution.

    When tenant 'org' checks remote worker status, it matches 'org_corp_exec.json'.
    If 'org_corp_exec.json' is corrupt or locked, tenant 'org' is falsely marked
    as having unresolved remote executions!
    """
    tracking_dir = tmp_path / "tracking"
    tracking_dir.mkdir()

    # Create a corrupted file belonging to tenant 'org_corp'
    foreign_file = tracking_dir / "org_corp_exec999.json"
    foreign_file.write_text("CORRUPTED_JSON_NOT_VALID", encoding="utf-8")

    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(tracking, "_DISTRIBUTED_REGISTRY_DIR", tracking_dir)
        unresolved = tracking._check_remote_worker_active("org")

    # In the unfixed code, "org_corp_exec999.json".startswith("org_") is True!
    # So unresolved contains the error entry attributed to 'org'!
    assert len(unresolved) == 0, (
        f"VULNERABILITY CONFIRMED: Tenant 'org' inspected and was poisoned by 'org_corp' file: {unresolved}"
    )


def test_reproduce_h1_03_underscore_delimiter_tenant_collision():
    """DEFECT H1-03: Identifier collision between (org='a_', exec='b') and (org='a', exec='_b').

    In URL-quoted joining with '__':
    quote('a_') -> 'a_'
    quote('b') -> 'b'
    Filename: 'a___b.json'

    quote('a') -> 'a'
    quote('_b') -> '_b'
    Filename: 'a___b.json'

    In the fixed collision-resistant implementation, domain-separated length-prefixed
    canonical identity digests guarantee that f1 != f2.
    """
    f1 = tracking._tracking_filename("a_", "b")
    f2 = tracking._tracking_filename("a", "_b")
    assert f1 != f2, f"COLLISION VULNERABILITY: Both produced {f1}"
    assert f1.startswith("trk_v2_")
    assert f2.startswith("trk_v2_")
