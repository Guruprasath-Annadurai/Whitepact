# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PG16 + SIGKILL + living Docker probe. NOT full customer authority proof."""

import asyncio
import json
import os
import signal
import subprocess
import sys
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import insert, select

from responsibleai.data_governance.backup_defense import (
    DurableLifecycleStateProvider,
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
)
from responsibleai.db.containment_repository import ContainmentAdmissionError
from responsibleai.db.engine import create_engine, organizations, runtime_containment_records
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from responsibleai.enterprise.runtime import configure_enterprise, get_enterprise_engine
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.models import IsolatedExecutionRequest
from tests.docker_runtime import require_container_isolation_host
from tests.pg_test_url import isolated_pg_url


def docker(*args):
    result = subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=15, check=True
    )
    return result.stdout.strip()


def safe_worker_failure(path):
    try:
        if path.is_symlink():
            category = "InvalidDiagnostic"
        elif path.exists():
            with path.open("rb") as source:
                category = source.read(81).decode("ascii")
        else:
            category = "NoDiagnostic"
    except (OSError, UnicodeError):
        category = "InvalidDiagnostic"
    if not category.isidentifier() or len(category) > 80:
        category = "InvalidDiagnostic"
    return f"Controlled worker exited before its boundary: {category}"


@pytest.mark.asyncio
@pytest.mark.parametrize("metadata", ["deleted", "corrupt"])
async def test_sigkill_and_lost_metadata_never_admit_normal_ready(metadata, tmp_path, monkeypatch):
    require_container_isolation_host()
    databases = isolated_pg_url("wp_absolute_cold")
    url = await anext(databases)
    await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "head")
    engine = create_engine(url)
    try:
        previous = get_enterprise_engine()
    except RuntimeError:
        previous = None
    child = None
    cid = None
    owned = None
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
        tracking = tmp_path / "child-tracking"
        tracking.mkdir()
        private = tmp_path / "child-private"
        private.mkdir()
        diagnostic = tmp_path / "child-failure"
        env = dict(
            os.environ,
            WHITEPACT_ALLOW_UNISOLATED_EXECUTION="0",
            WHITEPACT_ENV="staging",
            WP_ABSOLUTE_DISPOSABLE_DB=url,
            WP_ABSOLUTE_TRACKING=str(tracking),
            WP_ABSOLUTE_FAILURE_FILE=str(diagnostic),
            TMPDIR=str(private),
        )
        child = await asyncio.create_subprocess_exec(
            sys.executable,
            "scripts/engineering/m13_absolute_cold_worker.py",
            env=env,
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.DEVNULL,
        )
        deadline = asyncio.get_running_loop().time() + 45
        while asyncio.get_running_loop().time() < deadline:
            async with engine.raw.connect() as conn:
                owned = (
                    (
                        await conn.execute(
                            select(runtime_containment_records).where(
                                runtime_containment_records.c.state == "ACTIVE"
                            )
                        )
                    )
                    .mappings()
                    .first()
                )
            if owned:
                cid = owned["container_id"]
                inspected = json.loads(await asyncio.to_thread(docker, "inspect", cid))[0]
                if inspected["State"]["Running"]:
                    break
            if child.returncode is not None:
                pytest.fail(safe_worker_failure(diagnostic))
            await asyncio.sleep(0.05)
        else:
            pytest.fail("No acknowledged running controlled Docker workload within the bound")
        assert owned is not None and cid is not None
        os.kill(child.pid, signal.SIGKILL)
        assert await asyncio.wait_for(child.wait(), 10) == -signal.SIGKILL
        # Only THIS controlled child's private metadata is affected; Store A/B
        # and unrelated runtime files are not removed.
        files = list(tracking.glob("*.json"))
        assert files, "The actual backend must first have persisted local tracking"
        for path in files:
            if metadata == "deleted":
                path.unlink()
            else:
                path.write_text("{", encoding="utf-8")
        for path in private.glob("wp-container-receipt-*/container.cid"):
            path.unlink()
        assert json.loads(await asyncio.to_thread(docker, "inspect", cid))[0]["State"]["Running"]
        provider = DurableLifecycleStateProvider(tmp_path / "independent-store-b.sqlite")
        provider.set_readiness_state(
            RestoreReadinessState.READY, updated_by="controlled-native-fixture"
        )
        gate = RestoreReadinessGate(
            initial_state=RestoreReadinessState.READY, provider=provider, db_engine=engine
        )
        assert gate.state == RestoreReadinessState.READY
        with pytest.raises(RestoreQuarantineError):
            await gate.assert_current_traffic_admitted()
        assert gate.state == RestoreReadinessState.FAILED
        configure_enterprise(engine)
        monkeypatch.setenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", "0")
        request = IsolatedExecutionRequest(
            action_id="new",
            organization_id="native-owner",
            action_type="new",
            arguments={},
            authorization_id="new-component-grant",
            action_digest="b" * 64,
            authorization_expires_at=datetime.now(UTC) + timedelta(seconds=30),
        )
        with pytest.raises(ContainmentAdmissionError):
            await DockerContainerBackend().execute(request)
        assert json.loads(await asyncio.to_thread(docker, "inspect", cid))[0]["State"]["Running"], (
            "Admission fencing must not kill an unattributed prior-generation workload"
        )
    finally:
        if child is not None and child.returncode is None:
            child.kill()
            await child.wait()
        if cid and owned:
            obj = json.loads(await asyncio.to_thread(docker, "inspect", cid))[0]
            labels = obj["Config"]["Labels"]
            assert obj["Id"] == cid and labels["io.whitepact.execution"] == owned["execution_id"]
            # Test harness owns this exact immutable fixture; application
            # recovery never performs name-only cleanup or this manual action.
            await asyncio.to_thread(docker, "rm", "-f", cid)
        if previous is not None:
            configure_enterprise(previous)
        await engine.close()
        await databases.aclose()
