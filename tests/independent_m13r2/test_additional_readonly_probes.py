# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Verification-only additions; no implementation changes or authority root seed."""

import uuid

import asyncpg
import pytest
from tests.pg_test_url import isolated_pg_url

from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic


@pytest.mark.asyncio
async def test_real_postgres_generated_ids_vote_uniqueness_and_rollback():
    async for url in isolated_pg_url("wp_m13r2_rows"):
        ini = _find_alembic_ini()
        assert ini is not None
        await _run_alembic(ini, _migration_env(url), "upgrade", "head")
        conn = await asyncpg.connect(url)
        try:
            containment = f"wp_cnt_{uuid.uuid4().hex}"
            request_id = f"wp_recov_{uuid.uuid4().hex}"
            vote = f"wp_rvote_{uuid.uuid4().hex}"
            await conn.execute(
                "INSERT INTO authority_containment_records (id,org_id,responder_user_id,target_type,target_id,containment_action,reason,status,revocation_epoch,contained_at) VALUES ($1,'local-org','local-user','ORGANIZATION','local-org','LOCKDOWN','schema fixture','UNRESOLVED',1,'fixture-time')",
                containment,
            )
            await conn.execute(
                "INSERT INTO authority_recovery_requests (id,org_id,request_type,requester_user_id,proposed_parameters_json,action_digest,created_at,expires_at) VALUES ($1,'local-org','ROOT_RECOVERY','local-user','{}','digest','fixture-time','fixture-expiry')",
                request_id,
            )
            await conn.execute(
                "INSERT INTO authority_recovery_votes (id,request_id,voter_user_id,decision,action_digest,voted_at) VALUES ($1,$2,'voter','APPROVE','digest','fixture-time')",
                vote,
                request_id,
            )
            assert (
                await conn.fetchval(
                    "SELECT id FROM authority_containment_records WHERE id=$1", containment
                )
                == containment
            )
            assert (
                await conn.fetchval(
                    "SELECT id FROM authority_recovery_requests WHERE id=$1", request_id
                )
                == request_id
            )
            assert (
                await conn.fetchval("SELECT id FROM authority_recovery_votes WHERE id=$1", vote)
                == vote
            )
            with pytest.raises(asyncpg.UniqueViolationError):
                await conn.execute(
                    "INSERT INTO authority_recovery_votes (id,request_id,voter_user_id,decision,action_digest,voted_at) VALUES ('duplicate',$1,'voter','APPROVE','digest','fixture-time')",
                    request_id,
                )
            with pytest.raises(asyncpg.NotNullViolationError):
                async with conn.transaction():
                    await conn.execute(
                        "UPDATE authority_containment_records SET reason='must rollback' WHERE id=$1",
                        containment,
                    )
                    await conn.execute(
                        "UPDATE authority_containment_records SET status=NULL WHERE id=$1",
                        containment,
                    )
            assert (
                await conn.fetchval(
                    "SELECT reason FROM authority_containment_records WHERE id=$1", containment
                )
                == "schema fixture"
            )
        finally:
            await conn.close()
