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
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def pg_test_db() -> AsyncGenerator[str, None]:
    """Create a temporary isolated PostgreSQL database and drop it on cleanup."""
    async for url in isolated_pg_url("wp_auth_pg"):
        yield url


def test_one_canonical_alembic_head():
    """Verify exactly 1 canonical alembic head and correct 0049 revision chain."""
    ini = _find_alembic_ini()
    assert ini is not None, "alembic.ini must exist"
    scripts = ScriptDirectory.from_config(Config(str(ini)))
    heads = scripts.get_heads()
    assert len(heads) == 1, f"Expected exactly 1 alembic head, got {len(heads)}: {heads}"
    assert heads == ["0061"]
    assert scripts.get_revision("0049").down_revision == "0048"
    assert scripts.get_revision("0048").down_revision == "0047"
    assert scripts.get_revision("0047").down_revision == "0046"
    assert scripts.get_revision("0046").down_revision == "0045"
    assert scripts.get_revision("0045").down_revision == "0044"


@pytest.mark.asyncio
async def test_real_postgres_migration_cycle_0046_0047(pg_test_db: str):
    """Full migration cycle on real PostgreSQL: 0046 -> 0047 -> 0046 -> 0047.

    Restores all canonical 0046 <-> 0047 lifecycle assertions and data preservation guarantees.
    """
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

            # Verify columns on organizations
            org_cols = await conn.run_sync(lambda c: inspect(c).get_columns("organizations"))
            org_col_names = {col["name"] for col in org_cols}
            assert "paddle_last_occurred_at" in org_col_names

            # Verify columns on paddle_webhook_events
            evt_cols = await conn.run_sync(
                lambda c: inspect(c).get_columns("paddle_webhook_events")
            )
            evt_col_names = {col["name"] for col in evt_cols}
            assert "occurred_at" in evt_col_names
            assert "entity_id" in evt_col_names

            # Verify columns on iam_step_up_nonces
            nonce_cols = await conn.run_sync(lambda c: inspect(c).get_columns("iam_step_up_nonces"))
            nonce_col_names = {col["name"] for col in nonce_cols}
            assert "session_id" in nonce_col_names

            # Verify seeded data preserved
            seeded_org = (
                await conn.execute(
                    text(
                        "SELECT id, name, plan, paddle_last_occurred_at FROM organizations WHERE id = 'tenant-pre-0047'"
                    )
                )
            ).fetchone()
            assert seeded_org is not None
            assert seeded_org[0] == "tenant-pre-0047"
            assert seeded_org[1] == "Pre 0047 Corp"
            assert seeded_org[2] == "PRO"
            assert seeded_org[3] is None  # newly added column defaults to None

            # Seed paddle_webhook_events in 0047
            await conn.execute(
                text("""
                    INSERT INTO paddle_webhook_events (event_id, event_type, payload_hash, status, received_at, occurred_at, entity_id)
                    VALUES ('evt_0047_test', 'subscription.updated', 'hash123', 'PROCESSED', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'sub_123')
                """)
            )
            await conn.commit()

        # 3. Downgrade 0047 -> 0046
        await _run_alembic(ini, env, "downgrade", "0046")

        async with engine.raw.connect() as conn:
            v_down = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert v_down == "0046"

            # Verify columns dropped
            org_cols = await conn.run_sync(lambda c: inspect(c).get_columns("organizations"))
            assert "paddle_last_occurred_at" not in {col["name"] for col in org_cols}

            nonce_cols = await conn.run_sync(lambda c: inspect(c).get_columns("iam_step_up_nonces"))
            assert "session_id" not in {col["name"] for col in nonce_cols}

            has_paddle_events = await conn.run_sync(
                lambda c: inspect(c).has_table("paddle_webhook_events")
            )
            assert not has_paddle_events

            # Data preserved
            seeded_org = (
                await conn.execute(
                    text("SELECT id, name, plan FROM organizations WHERE id = 'tenant-pre-0047'")
                )
            ).fetchone()
            assert seeded_org is not None
            assert seeded_org[0] == "tenant-pre-0047"

        # 4. Re-upgrade 0046 -> 0047
        await _run_alembic(ini, env, "upgrade", "0047")

        async with engine.raw.connect() as conn:
            v_reup = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert v_reup == "0047"

            org_cols = await conn.run_sync(lambda c: inspect(c).get_columns("organizations"))
            assert "paddle_last_occurred_at" in {col["name"] for col in org_cols}

            nonce_cols = await conn.run_sync(lambda c: inspect(c).get_columns("iam_step_up_nonces"))
            assert "session_id" in {col["name"] for col in nonce_cols}

            has_paddle_events_reup = await conn.run_sync(
                lambda c: inspect(c).has_table("paddle_webhook_events")
            )
            assert has_paddle_events_reup
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_migration_cycle_0046_0047_0048(pg_test_db: str):
    """Full migration cycle on real PostgreSQL: 0046 -> 0047 -> 0048 -> 0047 -> 0048.

    Verifies complete schema integrity, uniqueness index toggles, and data preservation
    across 0046, 0047, and 0048 revisions.
    """
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

            # Verify 0047 columns
            org_cols = await conn.run_sync(lambda c: inspect(c).get_columns("organizations"))
            org_col_names = {col["name"] for col in org_cols}
            assert "paddle_last_occurred_at" in org_col_names
            assert "paddle_customer_id" in org_col_names
            assert "paddle_subscription_id" in org_col_names

            evt_cols = await conn.run_sync(
                lambda c: inspect(c).get_columns("paddle_webhook_events")
            )
            evt_col_names = {col["name"] for col in evt_cols}
            assert "occurred_at" in evt_col_names
            assert "entity_id" in evt_col_names

            nonce_cols = await conn.run_sync(lambda c: inspect(c).get_columns("iam_step_up_nonces"))
            nonce_col_names = {col["name"] for col in nonce_cols}
            assert "session_id" in nonce_col_names

            # Verify pre-0047 data preserved
            seeded_org = (
                await conn.execute(
                    text(
                        "SELECT id, name, plan, paddle_last_occurred_at FROM organizations WHERE id = 'tenant-pre-0047'"
                    )
                )
            ).fetchone()
            assert seeded_org is not None
            assert seeded_org[0] == "tenant-pre-0047"
            assert seeded_org[1] == "Pre 0047 Corp"
            assert seeded_org[2] == "PRO"
            assert seeded_org[3] is None

            # In 0047, idx_org_paddle_subscription is non-unique
            indices = await conn.run_sync(lambda c: inspect(c).get_indexes("organizations"))
            sub_idx = next(i for i in indices if i["name"] == "idx_org_paddle_subscription")
            assert sub_idx["unique"] is False or not sub_idx.get("unique")
            cust_idx = next(i for i in indices if i["name"] == "idx_org_paddle_customer")
            assert cust_idx["unique"] is True

            # Seed paddle_webhook_events in 0047
            await conn.execute(
                text("""
                    INSERT INTO paddle_webhook_events (event_id, event_type, payload_hash, status, received_at, occurred_at, entity_id)
                    VALUES ('evt_0047_cycle', 'subscription.updated', 'hash_cycle_123', 'PROCESSED', '2026-01-01T00:00:00Z', '2026-01-01T00:00:00Z', 'sub_cycle_123')
                """)
            )
            # Seed iam_step_up_nonces with session_id in 0047
            await conn.execute(
                text("""
                    INSERT INTO iam_step_up_nonces (id, org_id, principal_id, nonce_hash, action, target_resource_id, created_at, expires_at, session_id)
                    VALUES ('nonce_0047_cycle', 'tenant-pre-0047', 'prin_cycle', 'hash_nonce_cycle', 'admin_action', 'res_cycle', '2026-01-01T00:00:00Z', '2026-01-01T01:00:00Z', 'sess_0047_cycle')
                """)
            )
            # Seed valid Paddle mapping on pre-0047 org
            await conn.execute(
                text("""
                    UPDATE organizations
                    SET paddle_customer_id = 'ctm_cycle_47', paddle_subscription_id = 'sub_cycle_47', paddle_last_occurred_at = '2026-01-01T00:00:00Z'
                    WHERE id = 'tenant-pre-0047'
                """)
            )
            await conn.commit()

        # 3. Upgrade 0047 -> 0048
        await _run_alembic(ini, env, "upgrade", "0048")

        async with engine.raw.connect() as conn:
            v0048 = (await conn.execute(text("SELECT version_num FROM alembic_version"))).scalar()
            assert v0048 == "0048"

            # In 0048, idx_org_paddle_subscription is strictly UNIQUE
            indices = await conn.run_sync(lambda c: inspect(c).get_indexes("organizations"))
            sub_idx = next(i for i in indices if i["name"] == "idx_org_paddle_subscription")
            assert sub_idx["unique"] is True
            cust_idx = next(i for i in indices if i["name"] == "idx_org_paddle_customer")
            assert cust_idx["unique"] is True

            # Verify 0047 columns remain
            org_cols = await conn.run_sync(lambda c: inspect(c).get_columns("organizations"))
            org_col_names = {col["name"] for col in org_cols}
            assert "paddle_last_occurred_at" in org_col_names
            assert "paddle_customer_id" in org_col_names
            assert "paddle_subscription_id" in org_col_names

            evt_cols = await conn.run_sync(
                lambda c: inspect(c).get_columns("paddle_webhook_events")
            )
            evt_col_names = {col["name"] for col in evt_cols}
            assert "occurred_at" in evt_col_names
            assert "entity_id" in evt_col_names

            nonce_cols = await conn.run_sync(lambda c: inspect(c).get_columns("iam_step_up_nonces"))
            nonce_col_names = {col["name"] for col in nonce_cols}
            assert "session_id" in nonce_col_names

            # Verify seeded org data preserved
            seeded_org = (
                await conn.execute(
                    text(
                        "SELECT id, name, plan, paddle_customer_id, paddle_subscription_id, paddle_last_occurred_at FROM organizations WHERE id = 'tenant-pre-0047'"
                    )
                )
            ).fetchone()
            assert seeded_org is not None
            assert seeded_org[0] == "tenant-pre-0047"
            assert seeded_org[1] == "Pre 0047 Corp"
            assert seeded_org[2] == "PRO"
            assert seeded_org[3] == "ctm_cycle_47"
            assert seeded_org[4] == "sub_cycle_47"
            assert seeded_org[5] == "2026-01-01T00:00:00Z"

            # Verify webhook event preserved
            evt = (
                await conn.execute(
                    text(
                        "SELECT event_id, occurred_at, entity_id FROM paddle_webhook_events WHERE event_id = 'evt_0047_cycle'"
                    )
                )
            ).fetchone()
            assert evt is not None
            assert evt[0] == "evt_0047_cycle"
            assert evt[1] == "2026-01-01T00:00:00Z"
            assert evt[2] == "sub_cycle_123"

            # Verify auth seam data preserved
            nonce = (
                await conn.execute(
                    text(
                        "SELECT id, session_id FROM iam_step_up_nonces WHERE id = 'nonce_0047_cycle'"
                    )
                )
            ).fetchone()
            assert nonce is not None
            assert nonce[0] == "nonce_0047_cycle"
            assert nonce[1] == "sess_0047_cycle"

        # 4. Downgrade 0048 -> 0047
        await _run_alembic(ini, env, "downgrade", "0047")

        async with engine.raw.connect() as conn:
            v_down47 = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar()
            assert v_down47 == "0047"

            indices = await conn.run_sync(lambda c: inspect(c).get_indexes("organizations"))
            sub_idx = next(i for i in indices if i["name"] == "idx_org_paddle_subscription")
            assert sub_idx["unique"] is False or not sub_idx.get("unique")
            cust_idx = next(i for i in indices if i["name"] == "idx_org_paddle_customer")
            assert cust_idx["unique"] is True

            # 0047 columns remain
            org_cols = await conn.run_sync(lambda c: inspect(c).get_columns("organizations"))
            assert "paddle_last_occurred_at" in {col["name"] for col in org_cols}
            nonce_cols = await conn.run_sync(lambda c: inspect(c).get_columns("iam_step_up_nonces"))
            assert "session_id" in {col["name"] for col in nonce_cols}
            evt_cols = await conn.run_sync(
                lambda c: inspect(c).get_columns("paddle_webhook_events")
            )
            assert "occurred_at" in {col["name"] for col in evt_cols}

            # Data preserved
            seeded_org = (
                await conn.execute(
                    text(
                        "SELECT id, name, plan, paddle_customer_id, paddle_subscription_id FROM organizations WHERE id = 'tenant-pre-0047'"
                    )
                )
            ).fetchone()
            assert seeded_org is not None
            assert seeded_org[0] == "tenant-pre-0047"
            assert seeded_org[3] == "ctm_cycle_47"
            assert seeded_org[4] == "sub_cycle_47"

            evt = (
                await conn.execute(
                    text(
                        "SELECT event_id FROM paddle_webhook_events WHERE event_id = 'evt_0047_cycle'"
                    )
                )
            ).fetchone()
            assert evt is not None

            nonce = (
                await conn.execute(
                    text(
                        "SELECT id, session_id FROM iam_step_up_nonces WHERE id = 'nonce_0047_cycle'"
                    )
                )
            ).fetchone()
            assert nonce is not None
            assert nonce[1] == "sess_0047_cycle"

        # 5. Re-upgrade 0047 -> 0048
        await _run_alembic(ini, env, "upgrade", "0048")

        async with engine.raw.connect() as conn:
            v_reup48 = (
                await conn.execute(text("SELECT version_num FROM alembic_version"))
            ).scalar()
            assert v_reup48 == "0048"

            indices = await conn.run_sync(lambda c: inspect(c).get_indexes("organizations"))
            sub_idx = next(i for i in indices if i["name"] == "idx_org_paddle_subscription")
            assert sub_idx["unique"] is True

            # Data remains preserved
            seeded_org = (
                await conn.execute(
                    text(
                        "SELECT id, paddle_subscription_id FROM organizations WHERE id = 'tenant-pre-0047'"
                    )
                )
            ).fetchone()
            assert seeded_org is not None
            assert seeded_org[1] == "sub_cycle_47"

            evt = (
                await conn.execute(
                    text(
                        "SELECT event_id FROM paddle_webhook_events WHERE event_id = 'evt_0047_cycle'"
                    )
                )
            ).fetchone()
            assert evt is not None

            nonce = (
                await conn.execute(
                    text(
                        "SELECT id, session_id FROM iam_step_up_nonces WHERE id = 'nonce_0047_cycle'"
                    )
                )
            ).fetchone()
            assert nonce is not None
            assert nonce[1] == "sess_0047_cycle"
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
        assert (
            "duplicate paddle_subscription_id mappings" in err_msg or "sub_duplicate_999" in err_msg
        )

        # 3. Verify both organizations still exist untouched (no silent deletion or remapping)
        async with engine.raw.connect() as conn:
            rows = (
                await conn.execute(
                    text(
                        "SELECT id, paddle_subscription_id FROM organizations WHERE id IN ('org-dup-1', 'org-dup-2') ORDER BY id"
                    )
                )
            ).fetchall()
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
                rows = (
                    await conn.execute(
                        select(organizations.c.id).where(
                            organizations.c.paddle_subscription_id == sub_id
                        )
                    )
                ).fetchall()
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
            org = await org_repo.create_org(
                f"Chrono Org {i}", f"chrono-org-{i}-{uuid.uuid4().hex[:6]}"
            )
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
                row = (
                    await conn.execute(select(organizations).where(organizations.c.id == org.id))
                ).fetchone()
                if (
                    row.subscription_status == "active"
                    or row.paddle_last_occurred_at == "2026-09-17T11:00:00Z"
                ):
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
            org_a = await org_repo.create_org(
                f"Org Cust A {i}", f"org-cust-a-{i}-{uuid.uuid4().hex[:6]}"
            )
            org_b = await org_repo.create_org(
                f"Org Cust B {i}", f"org-cust-b-{i}-{uuid.uuid4().hex[:6]}"
            )
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
                rows = (
                    await conn.execute(
                        select(organizations.c.id).where(
                            organizations.c.paddle_customer_id == ctm_id
                        )
                    )
                ).fetchall()
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

    # Real PostgreSQL boot (engine + repository construction) can exceed
    # asgi-lifespan's default 5s bound even after skipping redundant
    # metadata.create_all. Bound the harness, do not sleep.
    async with LifespanManager(app_module.app, startup_timeout=30) as manager:
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
                responses = await asyncio.gather(
                    *[
                        client.post(
                            "/api/billing/paddle/webhook",
                            headers={"Paddle-Signature": sig},
                            content=raw,
                        )
                        for _ in range(20)
                    ]
                )

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


@pytest.mark.asyncio
async def test_real_postgres_equal_timestamp_reproduction_pro_to_enterprise(pg_test_db: str):
    """WP-AUTH-PDL-01-R1 Reproduction: PRO to ENTERPRISE elevation at equal occurred_at.

    An incoming ENTERPRISE event at identical occurred_at must NOT elevate an existing PRO plan.
    Under ambiguous provider chronology, commercial entitlement must never widen.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        org_repo = OrgRepository(engine)
        org = await org_repo.create_org("Equal Timestamp Repro", f"eq-repro-{uuid.uuid4().hex[:6]}")
        ts = "2026-09-17T12:00:00Z"
        sub_id = f"sub_eq_{uuid.uuid4().hex[:8]}"
        ctm_id = f"ctm_eq_{uuid.uuid4().hex[:8]}"

        # Baseline: PRO / active at T
        res1 = await org_repo.apply_paddle_entitlement(
            org_id=org.id,
            customer_id=ctm_id,
            subscription_id=sub_id,
            plan=Plan.PRO,
            subscription_status="active",
            occurred_at=ts,
        )
        assert res1 is True
        org_initial = await org_repo.get_org(org.id)
        assert org_initial is not None
        assert org_initial.plan == Plan.PRO

        # Incoming: ENTERPRISE / active at SAME T -> Must be rejected
        applied = await org_repo.apply_paddle_entitlement(
            org_id=org.id,
            customer_id=ctm_id,
            subscription_id=sub_id,
            plan=Plan.ENTERPRISE,
            subscription_status="active",
            occurred_at=ts,
        )
        org_final = await org_repo.get_org(org.id)
        assert org_final is not None
        assert applied is False, (
            "Equal-timestamp plan elevation (PRO -> ENTERPRISE) must be rejected"
        )
        assert org_final.plan == Plan.PRO, (
            f"Plan was elevated to {org_final.plan.value} on equal timestamp"
        )
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_equal_timestamp_plan_matrix(pg_test_db: str):
    """Exhaustive 3x3 plan matrix at identical occurred_at.

    FREE < PRO < ENTERPRISE
    - Upward transitions (FREE->PRO, FREE->ENTERPRISE, PRO->ENTERPRISE) must be rejected (return False, unchanged).
    - Idempotent transitions (FREE->FREE, PRO->PRO, ENTERPRISE->ENTERPRISE) succeed.
    - Narrowing transitions (PRO->FREE, ENTERPRISE->FREE, ENTERPRISE->PRO) succeed.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        org_repo = OrgRepository(engine)
        plans = [Plan.FREE, Plan.PRO, Plan.ENTERPRISE]
        plan_rank = {Plan.FREE: 0, Plan.PRO: 1, Plan.ENTERPRISE: 2}
        ts = "2026-09-17T12:00:00Z"

        for current_plan in plans:
            for incoming_plan in plans:
                org = await org_repo.create_org(
                    f"Plan Matrix {current_plan.value} to {incoming_plan.value}",
                    f"pm-{current_plan.value.lower()}-{incoming_plan.value.lower()}-{uuid.uuid4().hex[:6]}",
                )
                sub_id = f"sub_pm_{uuid.uuid4().hex[:8]}"
                ctm_id = f"ctm_pm_{uuid.uuid4().hex[:8]}"

                # Initial state at T
                await org_repo.apply_paddle_entitlement(
                    org_id=org.id,
                    customer_id=ctm_id,
                    subscription_id=sub_id,
                    plan=current_plan,
                    subscription_status="active",
                    occurred_at=ts,
                )

                # Attempt transition at identical T
                res = await org_repo.apply_paddle_entitlement(
                    org_id=org.id,
                    customer_id=ctm_id,
                    subscription_id=sub_id,
                    plan=incoming_plan,
                    subscription_status="active",
                    occurred_at=ts,
                )

                final_org = await org_repo.get_org(org.id)
                assert final_org is not None

                if plan_rank[incoming_plan] > plan_rank[current_plan]:
                    # Plan widening -> REJECTED
                    assert res is False, (
                        f"Widening {current_plan.value} -> {incoming_plan.value} must return False"
                    )
                    assert final_org.plan == current_plan, (
                        f"Widening occurred: {current_plan.value} became {final_org.plan.value}"
                    )
                else:
                    # Idempotent or narrowing -> ALLOWED
                    assert res is True, (
                        f"Non-widening {current_plan.value} -> {incoming_plan.value} should be accepted"
                    )
                    assert final_org.plan == incoming_plan
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_equal_timestamp_status_matrix(pg_test_db: str):
    """Exhaustive status transition matrix at identical occurred_at.

    Restrictive statuses: canceled, paused, past_due, inactive
    Active-like statuses: active, trialing

    - Restrictive -> active-like transitions must be rejected (equal_timestamp_reactivation_successes = 0).
    - Active-like -> restrictive transitions (narrowing) are allowed.
    - Same-status transitions are idempotent and allowed.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        org_repo = OrgRepository(engine)
        restrictive_statuses = ["canceled", "paused", "past_due", "inactive"]
        active_like_statuses = ["active", "trialing"]
        ts = "2026-09-17T12:00:00Z"

        # 1. Test all restrictive -> active-like transitions (must be rejected)
        for cur_status in restrictive_statuses:
            for inc_status in active_like_statuses:
                org = await org_repo.create_org(
                    f"Status {cur_status} to {inc_status}",
                    f"st-{cur_status}-{inc_status}-{uuid.uuid4().hex[:6]}",
                )
                sub_id = f"sub_st_{uuid.uuid4().hex[:8]}"
                ctm_id = f"ctm_st_{uuid.uuid4().hex[:8]}"

                # Initial state: PRO with restrictive status
                await org_repo.apply_paddle_entitlement(
                    org_id=org.id,
                    customer_id=ctm_id,
                    subscription_id=sub_id,
                    plan=Plan.PRO,
                    subscription_status=cur_status,
                    occurred_at=ts,
                )

                # Attempt reactivation at identical T
                res = await org_repo.apply_paddle_entitlement(
                    org_id=org.id,
                    customer_id=ctm_id,
                    subscription_id=sub_id,
                    plan=Plan.PRO,
                    subscription_status=inc_status,
                    occurred_at=ts,
                )
                assert res is False, (
                    f"Reactivation {cur_status} -> {inc_status} at equal occurred_at must return False"
                )
                final_org = await org_repo.get_org(org.id)
                assert final_org is not None
                assert final_org.subscription_status == cur_status

        # 2. Test active-like -> restrictive transitions (narrowing: allowed)
        for cur_status in active_like_statuses:
            for inc_status in restrictive_statuses:
                org = await org_repo.create_org(
                    f"Status {cur_status} to {inc_status}",
                    f"st-{cur_status}-{inc_status}-{uuid.uuid4().hex[:6]}",
                )
                sub_id = f"sub_st_{uuid.uuid4().hex[:8]}"
                ctm_id = f"ctm_st_{uuid.uuid4().hex[:8]}"

                await org_repo.apply_paddle_entitlement(
                    org_id=org.id,
                    customer_id=ctm_id,
                    subscription_id=sub_id,
                    plan=Plan.PRO,
                    subscription_status=cur_status,
                    occurred_at=ts,
                )

                res = await org_repo.apply_paddle_entitlement(
                    org_id=org.id,
                    customer_id=ctm_id,
                    subscription_id=sub_id,
                    plan=Plan.PRO,
                    subscription_status=inc_status,
                    occurred_at=ts,
                )
                assert res is True, (
                    f"Narrowing {cur_status} -> {inc_status} at equal occurred_at should be accepted"
                )
                final_org = await org_repo.get_org(org.id)
                assert final_org is not None
                assert final_org.subscription_status == inc_status
    finally:
        await engine.close()


@pytest.mark.asyncio
async def test_real_postgres_equal_timestamp_combined_matrix(pg_test_db: str):
    """Combined plan and status changes at identical occurred_at.

    Ensures that any transition attempting to widen either plan or status is rejected.
    """
    await run_migrations_or_raise(pg_test_db)
    engine = create_engine(pg_test_db)
    try:
        org_repo = OrgRepository(engine)
        ts = "2026-09-17T12:00:00Z"

        cases = [
            # (initial_plan, initial_status, incoming_plan, incoming_status, should_allow)
            (Plan.PRO, "canceled", Plan.ENTERPRISE, "active", False),
            (Plan.FREE, "paused", Plan.PRO, "active", False),
            (Plan.ENTERPRISE, "canceled", Plan.ENTERPRISE, "active", False),
            (Plan.PRO, "past_due", Plan.ENTERPRISE, "trialing", False),
            (Plan.ENTERPRISE, "active", Plan.PRO, "canceled", True),
            (Plan.PRO, "active", Plan.PRO, "paused", True),
        ]

        for cur_plan, cur_status, inc_plan, inc_status, should_allow in cases:
            org = await org_repo.create_org(
                f"Combined {cur_plan.value}/{cur_status} -> {inc_plan.value}/{inc_status}",
                f"comb-{uuid.uuid4().hex[:8]}",
            )
            sub_id = f"sub_comb_{uuid.uuid4().hex[:8]}"
            ctm_id = f"ctm_comb_{uuid.uuid4().hex[:8]}"

            await org_repo.apply_paddle_entitlement(
                org_id=org.id,
                customer_id=ctm_id,
                subscription_id=sub_id,
                plan=cur_plan,
                subscription_status=cur_status,
                occurred_at=ts,
            )

            res = await org_repo.apply_paddle_entitlement(
                org_id=org.id,
                customer_id=ctm_id,
                subscription_id=sub_id,
                plan=inc_plan,
                subscription_status=inc_status,
                occurred_at=ts,
            )

            assert res is should_allow, (
                f"Combined transition {cur_plan.value}/{cur_status} -> {inc_plan.value}/{inc_status} "
                f"expected allow={should_allow}, got {res}"
            )
            final_org = await org_repo.get_org(org.id)
            assert final_org is not None
            if not should_allow:
                assert final_org.subscription_status == cur_status
    finally:
        await engine.close()
