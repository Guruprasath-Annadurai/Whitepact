# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real pre-START crash boundaries; single daemon and disposable PostgreSQL16."""

import asyncio
import hashlib
import json
import os
import signal
import sys
from datetime import UTC, datetime

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.backup_defense import (
    DurableLifecycleStateProvider,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
)
from responsibleai.db.containment_repository import ContainmentAdmissionError, ContainmentRepository
from responsibleai.db.engine import create_engine, organizations, runtime_containment_records
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.docker_runtime import require_container_isolation_host
from tests.pg_test_url import isolated_pg_url
from tests.test_m13_absolute_cold_restart_native import docker


@pytest.mark.asyncio
@pytest.mark.parametrize("phase", ["before_create", "after_create", "before_start"])
async def test_prestart_sigkill_preserves_durable_fence(phase, tmp_path):
    require_container_isolation_host()
    databases = isolated_pg_url("wp_prestart_crash")
    url = await anext(databases)
    await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "0066")
    engine = create_engine(url)
    marker, tracking, private = (tmp_path / name for name in ("phase", "tracking", "private"))
    tracking.mkdir()
    private.mkdir()
    child = None
    owned = None
    cid = None
    try:
        async with engine.raw.begin() as conn:
            await conn.execute(
                insert(organizations).values(
                    id="native-owner",
                    name="Native owner",
                    slug="native-owner",
                    governance_status="ACTIVE",
                    created_at=datetime.now(UTC).isoformat(),
                )
            )
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "scripts/engineering/m13_absolute_cold_worker.py",
            env=dict(
                os.environ,
                WHITEPACT_ALLOW_UNISOLATED_EXECUTION="0",
                WHITEPACT_ENV="staging",
                WP_ABSOLUTE_DISPOSABLE_DB=url,
                WP_ABSOLUTE_TRACKING=str(tracking),
                WP_ABSOLUTE_PAUSE_PHASE=phase,
                WP_ABSOLUTE_PHASE_FILE=str(marker),
                TMPDIR=str(private),
            ),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        async with asyncio.timeout(45):
            while not marker.exists():
                assert child.returncode is None, "Fixture exited before its exact crash boundary"
                await asyncio.sleep(0.05)
        assert marker.read_text() == phase
        async with engine.raw.connect() as conn:
            owned = (await conn.execute(select(runtime_containment_records))).mappings().one()
        assert owned["organization_id"] == "native-owner"
        assert owned["state"] == ("ACTIVE" if phase == "before_start" else "PREPARING")
        candidates = (
            await asyncio.to_thread(
                docker,
                "ps",
                "-aq",
                "--no-trunc",
                "--filter",
                f"label=io.whitepact.execution={owned['execution_id']}",
            )
        ).splitlines()
        if phase == "before_create":
            assert candidates == []
        else:
            assert len(candidates) == 1
            cid = candidates[0]
            obj = json.loads(await asyncio.to_thread(docker, "inspect", cid))[0]
            assert obj["Id"] == cid and not obj["State"]["Running"]
            assert (
                obj["Config"]["Labels"]["io.whitepact.organization"]
                == hashlib.sha256(b"native-owner").hexdigest()
            )
        os.kill(child.pid, signal.SIGKILL)
        assert await child.wait() == -signal.SIGKILL
        for receipt in private.glob("wp-container-receipt-*/container.cid"):
            receipt.unlink()  # Only this fixture's private local metadata.
        restarted = ContainmentRepository(engine)
        with pytest.raises(ContainmentAdmissionError):
            await restarted.assert_admitted(owner_generation="fresh-process")
        provider = DurableLifecycleStateProvider(tmp_path / "store-b.sqlite")
        provider.set_readiness_state(RestoreReadinessState.READY, updated_by="fixture")
        gate = RestoreReadinessGate(
            initial_state=RestoreReadinessState.READY, provider=provider, db_engine=engine
        )
        with pytest.raises(RestoreQuarantineError):
            await gate.assert_current_traffic_admitted()
        assert gate.state == RestoreReadinessState.FAILED
        async with engine.raw.connect() as conn:
            assert await conn.scalar(select(runtime_containment_records.c.state)) == owned["state"]
    finally:
        if child is not None and child.returncode is None:
            child.kill()
            await child.wait()
        if cid is not None and owned is not None:
            obj = json.loads(await asyncio.to_thread(docker, "inspect", cid))[0]
            labels = obj["Config"]["Labels"]
            assert obj["Id"] == cid
            assert labels["io.whitepact.execution"] == owned["execution_id"]
            assert labels["io.whitepact.generation"] == owned["owner_generation"]
            assert (
                labels["io.whitepact.organization"] == hashlib.sha256(b"native-owner").hexdigest()
            )
            await asyncio.to_thread(docker, "rm", "-f", cid)
        await engine.close()
        await databases.aclose()
