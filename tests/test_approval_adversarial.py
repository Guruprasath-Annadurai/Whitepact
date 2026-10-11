# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Approved-but-not-yet-executed actions under attack, through the real HTTP stack on PostgreSQL.

Each test reads the downstream effect counter at the end. A refusal that still ran the action is a
failure; a 200 that ran it twice is a failure.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import text

from responsibleai.db import create_engine
from tests import test_v1_exactly_one_effect as _effect_tests
from tests.test_v1_customer_journey import _login
from tests.test_v1_exactly_one_effect import ADMIN_EMAIL, _call, _prepare_org

journey_client = _effect_tests.journey_client
pg_url = _effect_tests.pg_url


async def _effect_count(pg: str) -> int:
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    try:
        async with engine.raw.connect() as conn:
            rows = (
                await conn.execute(text("SELECT counter FROM test_consequential_counters"))
            ).fetchall()
        return sum(int(r[0]) for r in rows)
    finally:
        await engine.close()


async def _approve_twice(client, approval_id: str) -> str:
    """Owner then admin approve (quorum of two); returns the admin's CSRF. Does NOT execute."""
    first = await client.post(
        f"/api/v1/web/approvals/{approval_id}/resolve",
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
        json={"outcome": "APPROVED"},
    )
    assert first.status_code == 200, first.text
    await client.post("/api/v1/web/auth/logout", headers={"X-WP-CSRF": client.cookies["wp_csrf"]})
    admin_csrf = await _login(client, ADMIN_EMAIL)
    second = await client.post(
        f"/api/v1/web/approvals/{approval_id}/resolve",
        headers={"X-WP-CSRF": admin_csrf},
        json={"outcome": "APPROVED"},
    )
    assert second.status_code == 200 and second.json()["status"] == "APPROVED", second.text
    return admin_csrf


@pytest.fixture
async def approved(journey_client, monkeypatch, seed_runtime_authority):
    client, pg = journey_client
    org_id, raw = await _prepare_org(client, monkeypatch, seed_runtime_authority, pg)
    pending = await _call(client, raw)
    approval_id = pending.json()["approval_id"]
    admin_csrf = await _approve_twice(client, approval_id)
    assert await _effect_count(pg) == 0
    return client, pg, org_id, raw, approval_id, admin_csrf


async def test_a_policy_change_after_approval_blocks_the_execution(approved) -> None:
    """Approval followed by policy change: the human approved under the old rules."""
    client, pg, _org, _raw, approval_id, csrf = approved
    changed = await client.post(
        "/api/v1/web/policy/rules",
        headers={"X-WP-CSRF": csrf},
        json={
            "rule_id": "tighten-after-approval",
            "reason_code": "TIGHTEN",
            "effect": "DENY",
            "action_types": ["something.else"],
        },
    )
    assert changed.status_code == 200, changed.text
    executed = await client.post(
        f"/api/v1/web/approvals/{approval_id}/execute", headers={"X-WP-CSRF": csrf}, json={}
    )
    assert executed.status_code == 409, executed.text
    assert await _effect_count(pg) == 0, "the action ran although policy changed after approval"


async def test_concurrent_execution_of_one_approval_runs_exactly_once(approved) -> None:
    client, pg, _org, _raw, approval_id, csrf = approved
    results = await asyncio.gather(
        *(
            client.post(
                f"/api/v1/web/approvals/{approval_id}/execute",
                headers={"X-WP-CSRF": csrf},
                json={},
            )
            for _ in range(10)
        )
    )
    statuses = sorted(r.status_code for r in results)
    assert statuses.count(200) == 1, statuses
    assert all(code in (200, 409) for code in statuses), statuses
    assert await _effect_count(pg) == 1, "the approved action ran more than once"


async def test_an_expired_approval_cannot_be_executed(approved) -> None:
    client, pg, _org, _raw, approval_id, csrf = approved
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text(
                "UPDATE governance_approvals SET expires_at = '2020-01-01T00:00:00+00:00' WHERE id = :i"
            ),
            {"i": approval_id},
        )
    await engine.close()
    executed = await client.post(
        f"/api/v1/web/approvals/{approval_id}/execute", headers={"X-WP-CSRF": csrf}, json={}
    )
    assert executed.status_code == 409, executed.text
    assert await _effect_count(pg) == 0


async def test_an_approval_whose_bound_action_digest_was_altered_is_refused(approved) -> None:
    """Approval substitution at rest: the stored digest no longer matches the stored action."""
    client, pg, _org, _raw, approval_id, csrf = approved
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE governance_approvals SET action_digest = :d WHERE id = :i"),
            {"d": "0" * 64, "i": approval_id},
        )
    await engine.close()
    executed = await client.post(
        f"/api/v1/web/approvals/{approval_id}/execute", headers={"X-WP-CSRF": csrf}, json={}
    )
    assert executed.status_code in (409, 422), executed.text
    assert await _effect_count(pg) == 0


async def test_a_non_admin_cannot_resolve_or_execute(approved) -> None:
    """A VIEWER-role session is refused; there is no approval power in a read-only role."""
    client, pg, org_id, _raw, approval_id, csrf = approved
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE web_memberships SET role = 'VIEWER' WHERE org_id = :o"), {"o": org_id}
        )
    await engine.close()
    for path, body in (
        (f"/api/v1/web/approvals/{approval_id}/resolve", {"outcome": "APPROVED"}),
        (f"/api/v1/web/approvals/{approval_id}/execute", {}),
    ):
        response = await client.post(path, headers={"X-WP-CSRF": csrf}, json=body)
        assert response.status_code in (401, 403), (path, response.status_code, response.text)
    assert await _effect_count(pg) == 0
