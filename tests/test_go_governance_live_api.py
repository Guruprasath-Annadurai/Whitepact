# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Native Go governance SDK against real TCP, PostgreSQL and canonical authority.

The ADMIN key is an explicit local fixture, not a production issuance guarantee.
No backend authentication, governance or revocation code is replaced.
"""

from __future__ import annotations

import asyncio
import json
import platform
from pathlib import Path

import pytest

import responsibleai.dashboard.app as dashboard
from responsibleai.db.org_repository import OrgRepository
from responsibleai.governance.synthetic_counter import SYNTHETIC_COUNTER_TOOL
from responsibleai.rbac.models import Role
from tests.test_customer_real_approval_journey import (
    _counter,
    _execute,
    _resolve,
)
from tests.test_v1_customer_journey import PURPOSE, _login
from tests.test_v1_exactly_one_effect import ADMIN_EMAIL

pytest_plugins = ("tests.test_customer_real_approval_journey",)


@pytest.mark.asyncio
async def test_go_governance_real_approval_replay_and_revocation(live_customer, tmp_path):
    browser, _, org_id, key = live_customer
    root = Path(__file__).resolve().parents[1]
    compiler = await asyncio.create_subprocess_exec(
        "docker",
        "run",
        "--rm",
        "--network",
        "none",
        "-v",
        f"{root / 'sdk/go'}:/src:ro",
        "-v",
        f"{tmp_path}:/out",
        "-w",
        "/src",
        "-e",
        f"GOOS={'darwin' if platform.system() == 'Darwin' else 'linux'}",
        "-e",
        f"GOARCH={'arm64' if platform.machine() in {'arm64', 'aarch64'} else 'amd64'}",
        "golang@sha256:1cf6c45ba39db9fd6db16922041d074a63c935556a05c5ccb62d181034df7f02",
        "go",
        "build",
        "-o",
        "/out/governancecheck",
        "./cmd/governancecheck",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await asyncio.wait_for(compiler.communicate(), 120)
    assert compiler.returncode == 0, "Native Go build failed"

    async def run(operation, payload, credential=key, expected=0):
        process = await asyncio.create_subprocess_exec(
            str(tmp_path / "governancecheck"),
            str(browser.base_url).rstrip("/"),
            operation,
            env={"WHITEPACT_API_KEY": credential},
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        output, error = await asyncio.wait_for(
            process.communicate(json.dumps(payload).encode()), 15
        )
        assert not credential or credential.encode() not in output + error
        assert process.returncode == expected
        return json.loads(output) if expected == 0 else error.decode()

    assert (await run("policy", {}))["has_rules"]
    assert (await run("pending", {}))["has_pending"]
    pending = await run("call", {"Name": SYNTHETIC_COUNTER_TOOL, "Purpose": PURPOSE})
    assert pending["state"] == "PENDING" and not pending["completed"]
    approval_id = pending["approval_id"]
    assert approval_id and await _counter(browser, key) == 0
    # A developer bearer cannot approve or execute: UI permission is not authority.
    assert "403" in await run("execute", {"ID": approval_id}, expected=1)
    assert "403" in await run("resolve", {"ID": approval_id, "Outcome": "APPROVED"}, expected=1)
    first = await _resolve(browser, approval_id, "APPROVED")
    assert first.status_code == 200 and first.json()["status"] == "PENDING"
    assert (await _execute(browser, approval_id)).status_code == 409
    await browser.post("/api/v1/web/logout", headers={"X-WP-CSRF": browser.cookies["wp_csrf"]})
    await _login(browser, ADMIN_EMAIL)
    second = await _resolve(browser, approval_id, "APPROVED")
    assert second.status_code == 200 and second.json()["status"] == "APPROVED"
    # Internal ADMIN fixture consumes exactly the server-held approved request.
    _, admin_key = await OrgRepository(dashboard._db_engine).create_key(
        org_id, "go-local-admin", Role.ADMIN, internal_unverified_fixture=True
    )
    result = await run("execute", {"ID": approval_id}, admin_key)
    assert result["state"] == "SUCCEEDED" and result["completed"]
    assert await _counter(browser, key) == 1
    assert "409" in await run("execute", {"ID": approval_id}, admin_key, expected=1)
    assert await _counter(browser, key) == 1
    assert (await run("evidence", {}))["has_evidence"]
    principal = await OrgRepository(dashboard._db_engine).authenticate(key)
    assert principal is not None
    await run("revoke", {"ID": principal.key_id}, admin_key)
    denied = await run("call", {"Name": SYNTHETIC_COUNTER_TOOL, "Purpose": PURPOSE})
    assert denied["state"] == "DENIED" and not denied["completed"]
    assert await _counter(browser, key) == 1
    assert "401" in await run("policy", {}, "invalid-local-key", expected=1)
