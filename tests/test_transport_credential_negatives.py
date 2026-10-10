# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real negative tests for credentials and approvals at the hosted REST transport.

Real PostgreSQL, the real ASGI app, real API keys. Each test ends by reading the downstream
counter: the question is never only "did the server answer 401" but "did a consequential effect
happen". ``tests/test_executor_bypass_invariant.py`` covers the executor in isolation; this covers
the credential and approval layer in front of it.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import select, text

from responsibleai.db import create_engine
from responsibleai.db.engine import governance_approvals
from responsibleai.db.org_repository import OrgRepository
from tests.test_v1_customer_journey import _quorum_approve_and_execute
from tests.test_v1_exactly_one_effect import (  # noqa: F401  (fixtures)
    ADMIN_EMAIL,
    OWNER_EMAIL,
    _call,
    _prepare_org,
    journey_client,
    pg_url,
)

COUNTER = "/api/v1/governance/test-counter"


async def _counter(client, raw: str) -> dict:
    response = await client.get(COUNTER, headers={"Authorization": f"Bearer {raw}"})
    assert response.status_code == 200, response.text
    return response.json()


async def _approval_rows(pg: str) -> int:
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    try:
        async with engine.raw.connect() as conn:
            return len((await conn.execute(select(governance_approvals.c.id))).fetchall())
    finally:
        await engine.close()


async def _key_context(pg: str, raw: str):
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    try:
        return await OrgRepository(engine).authenticate(raw)
    finally:
        await engine.close()


@pytest.fixture
async def org(journey_client, monkeypatch, seed_runtime_authority):  # noqa: F811
    client, pg = journey_client
    org_id, raw = await _prepare_org(client, monkeypatch, seed_runtime_authority, pg)
    return client, pg, org_id, raw


async def test_forged_or_malformed_credentials_cause_no_effect(org) -> None:
    client, pg, _org_id, raw = org
    approvals_before = await _approval_rows(pg)
    forged_values = [
        raw[:-1] + ("A" if raw[-1] != "A" else "B"),  # one character off
        raw + "x",
        raw.upper(),
        "wp_live_" + "0" * 40,
        "",
        "Bearer",
    ]
    for value in forged_values:
        response = await client.post(
            "/api/v1/governance/tools/call",
            headers={"Authorization": f"Bearer {value}"},
            json={"name": "test.counter.increment", "arguments": {}, "purpose": "x"},
        )
        assert response.status_code in (401, 403), (value, response.status_code, response.text)
    for header in ({"Authorization": f"Basic {raw}"}, {"Authorization": raw}, {}):
        response = await client.post(
            "/api/v1/governance/tools/call",
            headers=header,
            json={"name": "test.counter.increment", "arguments": {}, "purpose": "x"},
        )
        assert response.status_code in (401, 403), (header, response.status_code)
    assert (await _counter(client, raw))["counter"] == 0
    assert await _approval_rows(pg) == approvals_before, "a rejected credential created an approval"


async def test_an_expired_key_is_rejected_and_causes_no_effect(org) -> None:
    client, pg, _org_id, raw = org
    ctx = await _key_context(pg, raw)
    assert ctx is not None
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE org_api_key_metadata SET expires_at = :t WHERE key_id = :id"),
            {"t": (datetime.now(UTC) - timedelta(seconds=5)).isoformat(), "id": ctx.key_id},
        )
    await engine.close()
    response = await _call(client, raw)
    assert response.status_code in (401, 403), response.text
    assert await _key_context(pg, raw) is None


async def test_a_revoked_key_is_rejected_immediately(org) -> None:
    client, pg, org_id, raw = org
    ctx = await _key_context(pg, raw)
    assert ctx is not None
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    assert await OrgRepository(engine).revoke_key(ctx.key_id, org_id=org_id) is True
    await engine.close()
    response = await _call(client, raw)
    assert response.status_code in (401, 403), response.text
    read = await client.get(COUNTER, headers={"Authorization": f"Bearer {raw}"})
    assert read.status_code in (401, 403)


async def test_revoking_the_requesting_key_while_an_approval_is_pending_blocks_the_effect(
    org,
) -> None:
    """Revocation during the approval window: the human approves, the credential is already dead."""
    client, pg, org_id, raw = org
    pending = await _call(client, raw)
    assert pending.json()["error"] == "governance_approval_required"
    approval_id = pending.json()["approval_id"]
    ctx = await _key_context(pg, raw)
    assert ctx is not None
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    assert await OrgRepository(engine).revoke_key(ctx.key_id, org_id=org_id) is True
    await engine.close()

    outcomes: list[object] = []
    executed = None
    try:
        executed = await _quorum_approve_and_execute(
            client, approval_id, owner_email=OWNER_EMAIL, admin_email=ADMIN_EMAIL
        )
    except AssertionError as exc:  # the flow refused part-way: that is a block
        outcomes.append(str(exc)[:300])
    # The effect counter is read through a fresh, valid credential check: the old key is dead, so
    # read the table directly.
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.connect() as conn:
        counters = (
            await conn.execute(text("SELECT counter FROM test_consequential_counters"))
        ).fetchall()
    await engine.close()
    effect = sum(int(row[0]) for row in counters)
    assert executed is None and outcomes and "409" in outcomes[0], (
        "the resume was expected to be refused with a 409 security-state conflict, "
        f"got executed={executed} outcomes={outcomes}"
    )
    assert effect == 0, (
        "a consequential effect ran after the requesting credential was revoked: "
        f"outcomes={outcomes} executed={executed}"
    )


async def test_a_read_only_key_cannot_request_a_consequential_action(org) -> None:
    client, pg, org_id, _raw = org
    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.begin() as conn:
        await conn.execute(
            text("UPDATE organizations SET plan = 'ENTERPRISE' WHERE id = :i"), {"i": org_id}
        )
    await engine.close()
    created = await client.post(
        "/api/v1/web/api-keys",
        headers={"X-WP-CSRF": client.cookies["wp_csrf"]},
        json={"name": "reader", "environment": "test", "scopes": ["governance:read"]},
    )
    assert created.status_code == 201, created.text
    reader = created.json()["api_key"]
    approvals_before = await _approval_rows(pg)
    response = await _call(client, reader)
    assert response.status_code == 403, response.text
    assert await _approval_rows(pg) == approvals_before
    assert (await _counter(client, reader))["counter"] == 0


async def test_another_tenant_cannot_resolve_or_execute_this_tenants_approval(org) -> None:
    from httpx import AsyncClient

    from tests.test_v1_customer_journey import _onboard, _register, _token_from_url, _verify_login

    client, pg, org_id, raw = org
    pending = await _call(client, raw)
    approval_id = pending.json()["approval_id"]

    other = AsyncClient(transport=client._transport, base_url="http://test")
    try:
        _, body = await _register(other, name="Other Owner", email="other.owner@example.com")
        csrf = await _verify_login(
            other, "other.owner@example.com", _token_from_url(body["verification_url"])
        )
        session = await _onboard(other, csrf, "Other Org")
        assert session["organization"]["id"] != org_id
        for path, payload in (
            (f"/api/v1/web/approvals/{approval_id}/resolve", {"outcome": "APPROVED"}),
            (f"/api/v1/web/approvals/{approval_id}/resolve", {"outcome": "DENIED"}),
            (f"/api/v1/web/approvals/{approval_id}/execute", {}),
        ):
            response = await other.post(
                path, headers={"X-WP-CSRF": other.cookies["wp_csrf"]}, json=payload
            )
            assert response.status_code in (403, 404), (path, response.status_code, response.text)
        listing = await other.get("/api/v1/web/approvals")
        assert approval_id not in listing.text, "another tenant's approval id is visible"
    finally:
        await other.aclose()

    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.connect() as conn:
        row = (
            await conn.execute(
                select(governance_approvals.c.status).where(
                    governance_approvals.c.id == approval_id
                )
            )
        ).fetchone()
    await engine.close()
    assert row is not None and str(row[0]).upper() in {"PENDING", "REQUIRE_APPROVAL"}, row
    assert (await _counter(client, raw))["counter"] == 0


async def test_another_tenant_cannot_read_or_annotate_this_tenants_evidence(org) -> None:
    from httpx import AsyncClient

    from responsibleai.db.engine import governance_evidence, governance_outcomes
    from responsibleai.rbac.models import Role
    from tests.test_v1_customer_journey import _onboard, _register, _token_from_url, _verify_login

    client, pg, org_id, raw = org
    await _call(client, raw)  # writes tenant A evidence

    engine = create_engine(pg)
    await engine.init(auto_create_tables=False)
    async with engine.raw.connect() as conn:
        evidence_id = (
            await conn.execute(
                select(governance_evidence.c.id).where(governance_evidence.c.org_id == org_id)
            )
        ).scalar()
    assert evidence_id

    other = AsyncClient(transport=client._transport, base_url="http://test")
    try:
        _, body = await _register(other, name="Evidence Other", email="evidence.other@example.com")
        csrf = await _verify_login(
            other, "evidence.other@example.com", _token_from_url(body["verification_url"])
        )
        session = await _onboard(other, csrf, "Evidence Other Org")
        other_org = session["organization"]["id"]
        assert other_org != org_id

        # Web session of tenant B.
        assert (await other.get(f"/api/v1/web/evidence/{evidence_id}")).status_code == 404
        assert (
            await other.get(f"/api/v1/web/evidence/{evidence_id}/attestation")
        ).status_code == 404
        listing = await other.get("/api/v1/web/evidence")
        assert evidence_id not in listing.text

        # API key of tenant B.
        _record, other_raw = await OrgRepository(engine).create_key(
            other_org, "b-key", role=Role.ANALYST
        )
        headers = {"Authorization": f"Bearer {other_raw}"}
        attestation = await client.get(
            f"/api/v1/governance/evidence/{evidence_id}/attestation", headers=headers
        )
        assert attestation.status_code == 404, attestation.text
        from responsibleai.dashboard.app import OutcomeReportRequest

        # The payload is valid for its owner, so the 404 below is about tenancy, not validation.
        OutcomeReportRequest(status="SUCCEEDED", result_summary="forged by another tenant")
        annotate = await client.post(
            f"/api/v1/governance/evidence/{evidence_id}/outcome",
            headers=headers,
            json={"status": "SUCCEEDED", "result_summary": "forged by another tenant"},
        )
        assert annotate.status_code == 404, annotate.text
    finally:
        await other.aclose()

    async with engine.raw.connect() as conn:
        outcomes = (
            await conn.execute(
                select(governance_outcomes).where(governance_outcomes.c.evidence_id == evidence_id)
            )
        ).fetchall()
    await engine.close()
    assert outcomes == [], "another tenant attached an outcome to this tenant's evidence"
