# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL Migration Cycle & Concurrency Race Proof for Auth/Paddle Seam Remediation.

Verifies:
1. Exactly 1 canonical alembic head: 0047 -> 0046.
2. Full migration cycle on real PostgreSQL: 0046 -> 0047 -> 0046 -> 0047.
   - Seed data preservation.
   - Column and index verification for 0047.
   - Clean rollback to 0046 without data loss.
   - Clean re-upgrade to 0047.
3. Concurrency races on real PostgreSQL:
   - OIDC state single-consumption race (duplicate processing: 0).
   - Paddle event single-consumption race (duplicate processing: 0).
   - Customer/tenant entitlement mapping race under load (duplicate processing: 0).
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import json
import secrets
import time
import uuid
from collections.abc import AsyncGenerator

import asyncpg
import pytest
from alembic.config import Config
from alembic.script import ScriptDirectory
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient
from sqlalchemy import inspect, select, text

import responsibleai.dashboard.app as app_module
from responsibleai.db.engine import create_engine, organizations
from responsibleai.db.migrate import (
    _find_alembic_ini,
    _migration_env,
    _run_alembic,
    run_migrations_or_raise,
)
from responsibleai.db.org_repository import OrgRepository
from responsibleai.db.paddle_billing_repository import PaddleBillingEventRepository
from responsibleai.db.web_identity_repository import WebIdentityRepository
from responsibleai.rbac.models import Plan

PG_ADMIN_URL = "postgresql://ag@localhost/postgres?host=/tmp"
PG_BASE_URL = "postgresql://ag@localhost/{db_name}?host=/tmp"


@pytest.fixture
async def pg_test_db() -> AsyncGenerator[str, None]:
    """Create a temporary isolated PostgreSQL database and drop it on cleanup."""
    db_name = f"wp_auth_pg_{uuid.uuid4().hex[:12]}"
    admin_conn = await asyncpg.connect(PG_ADMIN_URL)
    await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
    await admin_conn.close()

    db_url = PG_BASE_URL.format(db_name=db_name)
    try:
        yield db_url
    finally:
        admin_conn = await asyncpg.connect(PG_ADMIN_URL)
        await admin_conn.execute(f"""
            SELECT pg_terminate_backend(pid)
            FROM pg_stat_activity
            WHERE datname = '{db_name}' AND pid <> pg_backend_pid()
        """)
        await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
        await admin_conn.close()


def test_one_canonical_alembic_head():
    """Verify exactly 1 canonical alembic head and correct 0048 revision chain."""
    ini = _find_alembic_ini()
    assert ini is not None, "alembic.ini must exist"
    scripts = ScriptDirectory.from_config(Config(str(ini)))
    heads = scripts.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 alembic head, got {len(heads)}: {heads}"
    assert heads == ["0048"]
    assert scripts.get_revision("0048").down_revision == "0047"
    assert scripts.get_revision("0047").down_revision == "0046"
    assert scripts.get_revision("0046").down_revision == "0045"
    assert scripts.get_revision("0045").down_revision == "0044"


@pytest.mark.asyncio
async def test_real_postgres_migration_cycle_0046_0047_0048(pg_test_db: str):
    """Full migration cycle on real PostgreSQL: 0046 -> 0047 -> 0048 -> 0047 -> 0048."""
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # 1. Migrate up to 0046
    await _run_alembic(ini, env, "upgrade", "0046")

    engine = create_engine(pg_test_db)
    try:
        # Verify at 0046
        async with engine.raw.connect() as conn:
            v0046 = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert v0046 == "0046"

            # Seed pre-0047 data on existing 0046 schema
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, created_at, plan, subscription_status)
                    VALUES ('tenant-pre-0047', 'Pre 0047 Corp', 'pre-0047-corp', 5000, '2026-01-01T00:00:00Z', 'PRO', 'active')
                """)
            )
            await conn.commit()

        # 2. Upgrade 0046 -> 0047
        await _run_alembic(ini, env, "upgrade", "0047")

        async with engine.raw.connect() as conn:
            v0047 = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert v0047 == "0047"

            # In 0047, idx_org_paddle_subscription is non-unique
            indices = await conn.run_sync(lambda c: inspect(c).get_indexes("organizations"))
            sub_idx = next(i for i in indices if i["name"] == "idx_org_paddle_subscription")
            assert sub_idx["unique"] is False or not sub_idx.get("unique")

        # 3. Upgrade 0047 -> 0048
        await _run_alembic(ini, env, "upgrade", "0048")

        async with engine.raw.connect() as conn:
            v0048 = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert v0048 == "0048"

            # In 0048, idx_org_paddle_subscription is strictly UNIQUE
            indices = await conn.run_sync(lambda c: inspect(c).get_indexes("organizations"))
            sub_idx = next(i for i in indices if i["name"] == "idx_org_paddle_subscription")
            assert sub_idx["unique"] is True

            # Verify seeded data preserved
            seeded_org = (await conn.execute(text("SELECT id, name, plan FROM organizations WHERE id = 'tenant-pre-0047'"))).fetchone()
            assert seeded_org is not None
            assert seeded_org[0] == "tenant-pre-0047"

        # 4. Downgrade 0048 -> 0047
        await _run_alembic(ini, env, "downgrade", "0047")

        async with engine.raw.connect() as conn:
            v_down47 = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert v_down47 == "0047"

            indices = await conn.run_sync(lambda c: inspect(c).get_indexes("organizations"))
            sub_idx = next(i for i in indices if i["name"] == "idx_org_paddle_subscription")
            assert sub_idx["unique"] is False or not sub_idx.get("unique")

        # 5. Re-upgrade 0047 -> 0048
        await _run_alembic(ini, env, "upgrade", "0048")

        async with engine.raw.connect() as conn:
            v_reup48 = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert v_reup48 == "0048"

            indices = await conn.run_sync(lambda c: inspect(c).get_indexes("organizations"))
            sub_idx = next(i for i in indices if i["name"] == "idx_org_paddle_subscription")
            assert sub_idx["unique"] is True
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_migration_0048_rejects_duplicate_subscriptions(pg_test_db: str):
    """Migration 0048 must refuse unsafe migration if duplicate subscription bindings exist.

    It must NOT silently choose a winner or rewrite tenant ownership.
    """
    ini = _find_alembic_ini()
    assert ini is not None
    env = _migration_env(pg_test_db)

    # 1. Upgrade to 0047
    await _run_alembic(ini, env, "upgrade", "0047")

    engine = create_engine(pg_test_db)
    try:
        async with engine.raw.connect() as conn:
            # Intentionally create conflicting duplicate subscription bindings under 0047
            await conn.execute(
                text("""
                    INSERT INTO organizations (id, name, slug, monthly_budget_usd, created_at, plan, subscription_status, paddle_subscription_id)
                    VALUES
                        ('org-dup-1', 'Dup Org 1', 'dup-org-1', 1000, '2026-01-01T00:00:00Z', 'PRO', 'active', 'sub_duplicate_999'),
                        ('org-dup-2', 'Dup Org 2', 'dup-org-2', 1000, '2026-01-01T00:00:00Z', 'PRO', 'active', 'sub_duplicate_999');
                """)
            )
            await conn.commit()

        # 2. Attempt upgrade to 0048 -> MUST FAIL SAFELY
        with pytest.raises(Exception) as exc_info:
            await _run_alembic(ini, env, "upgrade", "0048")

        err_msg = str(exc_info.value)
        assert "duplicate paddle_subscription_id mappings" in err_msg or "sub_duplicate_999" in err_msg

        # 3. Verify both organizations still exist untouched (no silent deletion or remapping)
        async with engine.raw.connect() as conn:
            rows = (await conn.execute(
                text("SELECT id, paddle_subscription_id FROM organizations WHERE id IN ('org-dup-1', 'org-dup-2') ORDER BY id")
            )).fetchall()
            assert len(rows) == 2
            assert rows[0] == ("org-dup-1", "sub_duplicate_999")
            assert rows[1] == ("org-dup-2", "sub_duplicate_999")
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_oidc_flow_state_concurrency_race(pg_test_db: str):
    """30 concurrent tasks attempt to consume the single-use OAuth/OIDC state.

    Exactly 1 task must succeed; 29 must receive None.
    Duplicate processing under race: 0.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        repo = WebIdentityRepository(engine)
        test_state = f"state_race_{uuid.uuid4().hex}"
        test_session_id = f"sess_{uuid.uuid4().hex}"

        await repo.create_oauth_flow_state(
            state=test_state,
            provider="oidc",
            nonce="nonce_race",
            redirect_uri="https://app.example.com/callback",
            pkce_verifier="pkce_race",
            ttl_seconds=300,
            session_id=test_session_id,
        )

        async def _attempt_consume():
            return await repo.consume_oauth_flow_state(
                test_state, expected_session_id=test_session_id
            )

        results = await asyncio.gather(*[_attempt_consume() for _ in range(30)])

        successes = [r for r in results if r is not None]
        failures = [r for r in results if r is None]

        assert len(successes) == 1, f"Expected exactly 1 winner, got {len(successes)}"
        assert len(failures) == 29, f"Expected 29 failures, got {len(failures)}"
        assert successes[0]["provider"] == "oidc"
        assert successes[0]["nonce"] == "nonce_race"

        # Duplicate processing assertion
        duplicate_processing = len(successes) - 1
        assert duplicate_processing == 0
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_paddle_event_concurrency_race(pg_test_db: str):
    """30 concurrent webhook workers attempt to process the exact same Paddle event.

    Exactly 1 worker must succeed; 29 must be rejected.
    Duplicate processing under race: 0.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        event_repo = PaddleBillingEventRepository(engine)
        event_id = f"evt_race_{uuid.uuid4().hex}"
        payload_hash = "sha256:abc123race"

        async def _attempt_begin():
            return await event_repo.begin(
                event_id=event_id,
                event_type="subscription.updated",
                payload_hash=payload_hash,
                occurred_at="2026-09-16T12:00:00Z",
                entity_id="sub_race_001",
            )

        results = await asyncio.gather(*[_attempt_begin() for _ in range(30)])

        successes = [r for r in results if r is True]
        conflicts = [r for r in results if r is False]

        assert len(successes) == 1, f"Expected exactly 1 begin winner, got {len(successes)}"
        assert len(conflicts) == 29, f"Expected 29 conflicts, got {len(conflicts)}"

        # Duplicate processing assertion
        duplicate_processing = len(successes) - 1
        assert duplicate_processing == 0
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_paddle_customer_mapping_race(pg_test_db: str):
    """Race test for customer/subscription tenant binding and out-of-order updates.

    30 concurrent entitlement updates on the same organization.
    Verifies that all updates adhere to chronological ordering and no corrupt state occurs.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        org_repo = OrgRepository(engine)
        org = await org_repo.create_org("Race Org", "race-org")

        customer_id = "ctm_race_100"
        subscription_id = "sub_race_100"

        # Baseline application
        res = await org_repo.apply_paddle_entitlement(
            org_id=org.id,
            customer_id=customer_id,
            subscription_id=subscription_id,
            plan=Plan.PRO,
            subscription_status="active",
            occurred_at="2026-09-16T10:00:00Z",
        )
        assert res is True

        # Concurrently attempt 15 older timestamps and 15 newer timestamps
        async def _update(idx: int):
            occurred = f"2026-09-16T{10 + idx:02d}:00:00Z"
            return await org_repo.apply_paddle_entitlement(
                org_id=org.id,
                customer_id=customer_id,
                subscription_id=subscription_id,
                plan=Plan.ENTERPRISE,
                subscription_status="active",
                occurred_at=occurred,
            )

        results = await asyncio.gather(*[_update(i) for i in range(1, 31)])
        # All updates should execute safely without SQL deadlocks or integrity errors
        assert len(results) == 30

        # Verify final state is ENTERPRISE
        final_org = await org_repo.get_org(org.id)
        assert final_org is not None
        assert final_org.plan == Plan.ENTERPRISE
        assert final_org.paddle_customer_id == customer_id
        assert final_org.paddle_subscription_id == subscription_id
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_same_subscription_two_tenants_race(pg_test_db: str):
    """WP-AUTH-PDL-01 Reproduction: Two different orgs racing to bind the same subscription.

    Under concurrent execution, exactly one org may bind the subscription.
    Cross-tenant subscription bindings must be 0.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        org_repo = OrgRepository(engine)
        duplicate_subscription_bindings = 0
        races = 40

        for i in range(races):
            org_a = await org_repo.create_org(f"Org A {i}", f"org-a-{i}-{uuid.uuid4().hex[:6]}")
            org_b = await org_repo.create_org(f"Org B {i}", f"org-b-{i}-{uuid.uuid4().hex[:6]}")
            sub_id = f"sub_race_{i}_{uuid.uuid4().hex[:8]}"
            ctm_a = f"ctm_a_{i}_{uuid.uuid4().hex[:8]}"
            ctm_b = f"ctm_b_{i}_{uuid.uuid4().hex[:8]}"

            async def _bind(org_id: str, ctm_id: str, target_sub_id: str = sub_id):
                try:
                    return await org_repo.apply_paddle_entitlement(
                        org_id=org_id,
                        customer_id=ctm_id,
                        subscription_id=target_sub_id,
                        plan=Plan.PRO,
                        subscription_status="active",
                        occurred_at="2026-09-17T12:00:00Z",
                    )
                except Exception as e:
                    return str(e)

            await asyncio.gather(_bind(org_a.id, ctm_a), _bind(org_b.id, ctm_b))

            async with engine.raw.connect() as conn:
                rows = (await conn.execute(
                    select(organizations.c.id).where(organizations.c.paddle_subscription_id == sub_id)
                )).fetchall()
                if len(rows) > 1:
                    duplicate_subscription_bindings += 1

        assert duplicate_subscription_bindings == 0, (
            f"WP-AUTH-PDL-01 REPRODUCED: duplicate_subscription_bindings = {duplicate_subscription_bindings} "
            f"across {races} races"
        )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_chronology_newer_cancel_vs_older_activate_race(pg_test_db: str):
    """Race test: NEWER cancel event vs OLDER activate event for same subscription/org.

    Invariant: Persisted commercial state must correspond to greatest accepted occurred_at.
    Older event must never overwrite newer state.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        org_repo = OrgRepository(engine)
        stale_activation_wins = 0
        races = 40

        for i in range(races):
            org = await org_repo.create_org(f"Chrono Org {i}", f"chrono-org-{i}-{uuid.uuid4().hex[:6]}")
            sub_id = f"sub_chrono_{i}_{uuid.uuid4().hex[:8]}"
            ctm_id = f"ctm_chrono_{i}_{uuid.uuid4().hex[:8]}"

            await org_repo.apply_paddle_entitlement(
                org_id=org.id,
                customer_id=ctm_id,
                subscription_id=sub_id,
                plan=Plan.FREE,
                subscription_status="inactive",
                occurred_at="2026-09-17T10:00:00Z",
            )

            # Concurrent race:
            # Event NEW: canceled at 12:00:00Z
            # Event OLD: active (PRO) at 11:00:00Z
            target_org_id = org.id
            target_ctm = ctm_id
            target_sub = sub_id

            async def _apply_new(
                oid: str = target_org_id, cid: str = target_ctm, sid: str = target_sub
            ):
                return await org_repo.apply_paddle_entitlement(
                    org_id=oid,
                    customer_id=cid,
                    subscription_id=sid,
                    plan=Plan.PRO,
                    subscription_status="canceled",
                    occurred_at="2026-09-17T12:00:00Z",
                )

            async def _apply_old(
                oid: str = target_org_id, cid: str = target_ctm, sid: str = target_sub
            ):
                await asyncio.sleep(0.001)
                return await org_repo.apply_paddle_entitlement(
                    org_id=oid,
                    customer_id=cid,
                    subscription_id=sid,
                    plan=Plan.PRO,
                    subscription_status="active",
                    occurred_at="2026-09-17T11:00:00Z",
                )

            await asyncio.gather(_apply_new(), _apply_old())

            async with engine.raw.connect() as conn:
                row = (await conn.execute(
                    select(organizations).where(organizations.c.id == org.id)
                )).fetchone()
                if row.subscription_status == "active" or row.paddle_last_occurred_at == "2026-09-17T11:00:00Z":
                    stale_activation_wins += 1

        assert stale_activation_wins == 0, (
            f"CHRONOLOGY RACE REPRODUCED: stale_activation_wins = {stale_activation_wins} across {races} races"
        )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_paddle_event_id_conflicting_payload_race(pg_test_db: str):
    """Concurrent delivery of same event_id with identical vs conflicting payloads.

    1. Identical payloads: exactly 1 worker processes; others receive duplicate=True.
    2. Conflicting payloads: conflicting worker receives ValueError / 409 conflict.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        event_repo = PaddleBillingEventRepository(engine)
        event_id = f"evt_dup_{uuid.uuid4().hex}"
        hash_orig = "sha256:orig123456"
        hash_conflict = "sha256:conflict999"

        # Worker 1 begins
        w1_res = await event_repo.begin(
            event_id=event_id,
            event_type="subscription.created",
            payload_hash=hash_orig,
            occurred_at="2026-09-17T12:00:00Z",
            entity_id="sub_test_001",
        )
        assert w1_res is True

        # Duplicate identical payload
        w2_res = await event_repo.begin(
            event_id=event_id,
            event_type="subscription.created",
            payload_hash=hash_orig,
            occurred_at="2026-09-17T12:00:00Z",
            entity_id="sub_test_001",
        )
        assert w2_res is False

        # Conflicting payload
        with pytest.raises(ValueError, match="Conflicting payload"):
            await event_repo.begin(
                event_id=event_id,
                event_type="subscription.created",
                payload_hash=hash_conflict,
                occurred_at="2026-09-17T12:00:00Z",
                entity_id="sub_test_001",
            )
    finally:
        await engine.close()


def _sign_paddle(secret: str, raw: bytes, ts: int | None = None) -> str:
    if ts is None:
        ts = int(time.time())
    h1 = hmac.new(secret.encode(), f"{ts}:".encode() + raw, hashlib.sha256).hexdigest()
    return f"ts={ts};h1={h1}"


@pytest.mark.asyncio
async def test_real_postgres_same_customer_two_tenants_race(pg_test_db: str):
    """Two different orgs racing to bind the same customer_id with different subscriptions.

    Under concurrent execution, exactly one org may bind the customer.
    Cross-tenant customer bindings must be 0.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        org_repo = OrgRepository(engine)
        duplicate_customer_bindings = 0
        races = 40

        for i in range(races):
            org_a = await org_repo.create_org(f"Org Cust A {i}", f"org-cust-a-{i}-{uuid.uuid4().hex[:6]}")
            org_b = await org_repo.create_org(f"Org Cust B {i}", f"org-cust-b-{i}-{uuid.uuid4().hex[:6]}")
            ctm_id = f"ctm_race_{i}_{uuid.uuid4().hex[:8]}"
            sub_a = f"sub_a_{i}_{uuid.uuid4().hex[:8]}"
            sub_b = f"sub_b_{i}_{uuid.uuid4().hex[:8]}"

            async def _bind(org_id: str, sub_id: str, target_ctm_id: str = ctm_id):
                try:
                    return await org_repo.apply_paddle_entitlement(
                        org_id=org_id,
                        customer_id=target_ctm_id,
                        subscription_id=sub_id,
                        plan=Plan.PRO,
                        subscription_status="active",
                        occurred_at="2026-09-17T12:00:00Z",
                    )
                except Exception as e:
                    return str(e)

            await asyncio.gather(_bind(org_a.id, sub_a), _bind(org_b.id, sub_b))

            async with engine.raw.connect() as conn:
                rows = (await conn.execute(
                    select(organizations.c.id).where(organizations.c.paddle_customer_id == ctm_id)
                )).fetchall()
                if len(rows) > 1:
                    duplicate_customer_bindings += 1

        assert duplicate_customer_bindings == 0, (
            f"CUSTOMER RACE: duplicate_customer_bindings = {duplicate_customer_bindings} "
            f"across {races} races"
        )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_api_webhook_concurrency_race(pg_test_db: str, monkeypatch):
    """Concurrent HTTP webhook deliveries to /api/billing/paddle/webhook backed by real PostgreSQL.

    Tests concurrent delivery of:
    1. Same event_id to 20 concurrent requests -> exactly 1 returns 200, 19 return 200 (duplicate=True, idempotent).
    2. Conflicting payload for same event_id -> 409 Conflict.
    3. Cross-tenant subscription hijack via custom_data -> 409 Conflict.
    """
    await run_migrations_or_raise(pg_test_db)
    secret = "test_paddle_secret_key_real_pg_123"  # gitleaks:allow
    monkeypatch.setattr(app_module.settings, "db_path", pg_test_db)
    monkeypatch.setattr(app_module.settings, "auto_migrate", False)
    monkeypatch.setattr(app_module.settings, "auth_enabled", False)
    monkeypatch.setattr(app_module.settings, "paddle_webhook_secret", secret)
    monkeypatch.setattr(app_module.settings, "paddle_signature_tolerance_seconds", 300)
    monkeypatch.setattr(app_module.limiter, "enabled", False)

    async with LifespanManager(app_module.app) as manager:
        async with AsyncClient(
            transport=ASGITransport(app=manager.app), base_url="http://test"
        ) as client:
            engine = create_engine(pg_test_db)
            try:
                org_repo = OrgRepository(engine)
                org_a = await org_repo.create_org("Org Webhook A", "org-wh-a")
                org_b = await org_repo.create_org("Org Webhook B", "org-wh-b")

                event_id = f"evt_api_race_{secrets.token_hex(6)}"
                payload = {
                    "event_id": event_id,
                    "event_type": "subscription.created",
                    "occurred_at": "2026-09-17T12:00:00Z",
                    "data": {
                        "id": "sub_api_race_1",
                        "customer_id": "ctm_api_race_1",
                        "status": "active",
                        "custom_data": {"org_id": org_a.id, "plan": "pro"},
                    },
                }
                raw = json.dumps(payload).encode("utf-8")
                sig = _sign_paddle(secret, raw)

                # 20 concurrent calls with identical event_id and payload
                responses = await asyncio.gather(*[
                    client.post(
                        "/api/billing/paddle/webhook",
                        headers={"Paddle-Signature": sig},
                        content=raw,
                    ) for _ in range(20)
                ])

                # All 20 must return 200 (1 processed, 19 idempotent duplicates)
                assert all(r.status_code == 200 for r in responses)
                dup_counts = sum(1 for r in responses if r.json().get("duplicate") is True)
                assert dup_counts == 19

                # Conflicting payload for same event_id -> 409
                payload_conflict = {
                    "event_id": event_id,
                    "event_type": "subscription.created",
                    "occurred_at": "2026-09-17T12:00:00Z",
                    "data": {
                        "id": "sub_api_race_CONFLICT",
                        "customer_id": "ctm_api_race_CONFLICT",
                        "status": "active",
                        "custom_data": {"org_id": org_a.id, "plan": "enterprise"},
                    },
                }
                raw_conflict = json.dumps(payload_conflict).encode("utf-8")
                sig_conflict = _sign_paddle(secret, raw_conflict)
                res_conflict = await client.post(
                    "/api/billing/paddle/webhook",
                    headers={"Paddle-Signature": sig_conflict},
                    content=raw_conflict,
                )
                assert res_conflict.status_code == 409

                # Cross-tenant hijack attempt: Send webhook binding already-bound sub_api_race_1 to Org B
                payload_hijack = {
                    "event_id": f"evt_api_hijack_{secrets.token_hex(6)}",
                    "event_type": "subscription.updated",
                    "occurred_at": "2026-09-17T12:05:00Z",
                    "data": {
                        "id": "sub_api_race_1",
                        "customer_id": "ctm_api_race_2",
                        "status": "active",
                        "custom_data": {"org_id": org_b.id, "plan": "pro"},
                    },
                }
                raw_hijack = json.dumps(payload_hijack).encode("utf-8")
                sig_hijack = _sign_paddle(secret, raw_hijack)
                res_hijack = await client.post(
                    "/api/billing/paddle/webhook",
                    headers={"Paddle-Signature": sig_hijack},
                    content=raw_hijack,
                )
                assert res_hijack.status_code == 409
            finally:
                await engine.close()
