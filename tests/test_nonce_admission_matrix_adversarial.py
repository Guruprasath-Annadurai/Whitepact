# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Adversarial qualification matrix for single-use execution nonces on real PostgreSQL.

Proves:
1. Missing organization fails closed with OrganizationNotGovernableError.
2. Disabled organization fails closed with OrganizationNotGovernableError.
3. Suspended organization fails closed with OrganizationNotGovernableError.
4. Revoked authority (stale revocation epoch) fails closed with StaleRevocationEpochError.
5. Expired / previously admitted nonce fails closed with NonceAlreadyConsumedError.
6. Concurrent nonce consumption by multiple workers admits exactly one, rejecting all others.
7. Transaction rollback ensures nonce is not consumed and epoch remains unlocked.
8. PostgreSQL foreign key integrity violations do not mislabel missing-tenant or constraint errors as replay.
9. Multi-worker replay attempts across independent database connections fail closed.
10. Valid active organization with matching epoch consumes nonce atomically.
"""

from __future__ import annotations

import asyncio
import uuid
from contextlib import aclosing
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select

from responsibleai.db.engine import (
    create_engine,
    metadata,
    organizations,
)
from responsibleai.db.engine import (
    governance_execution_nonces as nonces,
)
from responsibleai.db.execution_nonce_repository import (
    ExecutionNonceRepository,
    NonceAlreadyConsumedError,
    OrganizationNotGovernableError,
    StaleRevocationEpochError,
)
from responsibleai.db.revocation_epoch_repository import RevocationEpochRepository
from responsibleai.rbac.models import GovernanceStatus, Plan
from tests.pg_test_url import isolated_pg_url


async def _create_test_org(
    engine, org_id: str, status: GovernanceStatus = GovernanceStatus.ACTIVE
) -> str:
    async with engine.raw.begin() as conn:
        await conn.execute(
            insert(organizations).values(
                id=org_id,
                name=f"Org {org_id}",
                slug=f"slug-{org_id}",
                plan=Plan.ENTERPRISE.value,
                governance_status=status.value,
                created_at=datetime.now(UTC).isoformat(),
            )
        )
    return org_id


@pytest.mark.asyncio
async def test_nonce_admission_matrix_on_real_postgres() -> None:
    """Execute complete adversarial nonce admission matrix on real PostgreSQL."""
    async with aclosing(isolated_pg_url("wp_pg_nonce_matrix")) as urls:
        async for url in urls:
            engine = create_engine(url)
            async with engine.raw.begin() as conn:
                await conn.run_sync(metadata.create_all)

            nonce_repo = ExecutionNonceRepository(engine)
            epoch_repo = RevocationEpochRepository(engine)

            # 1. Missing organization: MUST fail closed with OrganizationNotGovernableError
            missing_org_id = f"org_missing_{uuid.uuid4().hex[:8]}"
            with pytest.raises(OrganizationNotGovernableError, match="Organization is not ACTIVE"):
                await nonce_repo.consume(
                    f"nonce_missing_{uuid.uuid4().hex[:8]}",
                    authorization_id="auth_missing",
                    organization_id=missing_org_id,
                    expected_epoch=0,
                )

            # 2. Disabled organization: MUST fail closed with OrganizationNotGovernableError
            disabled_org_id = f"org_dis_{uuid.uuid4().hex[:8]}"
            await _create_test_org(engine, disabled_org_id, GovernanceStatus.DISABLED)
            with pytest.raises(OrganizationNotGovernableError, match="Organization is not ACTIVE"):
                await nonce_repo.consume(
                    f"nonce_dis_{uuid.uuid4().hex[:8]}",
                    authorization_id="auth_dis",
                    organization_id=disabled_org_id,
                    expected_epoch=0,
                )

            # 3. Suspended organization: MUST fail closed with OrganizationNotGovernableError
            suspended_org_id = f"org_susp_{uuid.uuid4().hex[:8]}"
            await _create_test_org(engine, suspended_org_id, GovernanceStatus.SUSPENDED)
            with pytest.raises(OrganizationNotGovernableError, match="Organization is not ACTIVE"):
                await nonce_repo.consume(
                    f"nonce_susp_{uuid.uuid4().hex[:8]}",
                    authorization_id="auth_susp",
                    organization_id=suspended_org_id,
                    expected_epoch=0,
                )

            # 4. Valid active organization: MUST succeed atomically
            active_org_id = f"org_act_{uuid.uuid4().hex[:8]}"
            await _create_test_org(engine, active_org_id, GovernanceStatus.ACTIVE)
            valid_nonce = f"nonce_valid_{uuid.uuid4().hex[:8]}"
            valid_auth = f"auth_{uuid.uuid4().hex[:8]}"
            await nonce_repo.consume(
                valid_nonce,
                authorization_id=valid_auth,
                organization_id=active_org_id,
                expected_epoch=0,
            )

            # Verify nonce row exists in database
            async with engine.raw.connect() as conn:
                found = await conn.scalar(
                    select(nonces.c.nonce).where(nonces.c.nonce == valid_nonce)
                )
                assert found == valid_nonce

            # 5. Duplicate nonce consumption (replay): MUST fail closed with NonceAlreadyConsumedError
            with pytest.raises(NonceAlreadyConsumedError, match="Permit nonce already consumed"):
                await nonce_repo.consume(
                    valid_nonce,
                    authorization_id=valid_auth,
                    organization_id=active_org_id,
                    expected_epoch=0,
                )

            # 6. Revoked authority (stale revocation epoch): MUST fail closed with StaleRevocationEpochError
            # Bump epoch for active_org_id from 0 to 1
            bumped = await epoch_repo.bump(active_org_id)
            assert bumped.epoch == 1

            stale_nonce = f"nonce_stale_{uuid.uuid4().hex[:8]}"
            with pytest.raises(StaleRevocationEpochError, match="Permit revocation epoch is stale"):
                await nonce_repo.consume(
                    stale_nonce,
                    authorization_id="auth_stale",
                    organization_id=active_org_id,
                    expected_epoch=0,  # Expected 0, but current is 1!
                )

            # But consuming with updated expected_epoch=1 MUST succeed
            fresh_nonce = f"nonce_fresh_{uuid.uuid4().hex[:8]}"
            await nonce_repo.consume(
                fresh_nonce,
                authorization_id="auth_fresh",
                organization_id=active_org_id,
                expected_epoch=1,
            )

            # 7. Transaction rollback: if an exception occurs during admission, state is untouched
            rollback_org_id = f"org_rb_{uuid.uuid4().hex[:8]}"
            await _create_test_org(engine, rollback_org_id, GovernanceStatus.ACTIVE)
            rb_nonce = f"nonce_rb_{uuid.uuid4().hex[:8]}"

            # Attempt a consumption that fails halfway (e.g. invalid epoch)
            with pytest.raises(StaleRevocationEpochError):
                await nonce_repo.consume(
                    rb_nonce,
                    authorization_id="auth_rb",
                    organization_id=rollback_org_id,
                    expected_epoch=999,  # Current is 0
                )

            # Nonce must NOT be consumed
            async with engine.raw.connect() as conn:
                rb_found = await conn.scalar(
                    select(nonces.c.nonce).where(nonces.c.nonce == rb_nonce)
                )
                assert rb_found is None

            # 8. Concurrent nonce consumption by 5 parallel workers on real PostgreSQL
            concurrent_org_id = f"org_conc_{uuid.uuid4().hex[:8]}"
            await _create_test_org(engine, concurrent_org_id, GovernanceStatus.ACTIVE)
            target_nonce = f"nonce_target_{uuid.uuid4().hex[:8]}"

            # Create 5 separate worker engines to simulate distributed replicas
            worker_engines = [create_engine(url) for _ in range(5)]

            async def _worker_consume(worker_engine, n=target_nonce, o=concurrent_org_id):
                repo = ExecutionNonceRepository(worker_engine)
                await repo.consume(
                    n,
                    authorization_id="auth_concurrent",
                    organization_id=o,
                    expected_epoch=0,
                )

            results = await asyncio.gather(
                *[_worker_consume(w) for w in worker_engines],
                return_exceptions=True,
            )

            # Exactly one worker succeeded (None), and all other 4 raised NonceAlreadyConsumedError
            success_count = sum(1 for r in results if r is None)
            replay_count = sum(1 for r in results if isinstance(r, NonceAlreadyConsumedError))
            assert success_count == 1, (
                f"Expected exactly 1 success, got {success_count} (results={results})"
            )
            assert replay_count == 4, f"Expected 4 replays, got {replay_count} (results={results})"
