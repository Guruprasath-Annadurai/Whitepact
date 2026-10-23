# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Abrupt trusted-test-controller/pg_restore deaths, real independent stores."""

import asyncio
import multiprocessing
import os
import signal
import subprocess
from pathlib import Path

import httpx
import pytest
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import (
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from responsibleai.data_governance.operator_recovery_control import (
    OperatorProfile,
    _exclusive_operation,
)
from responsibleai.db.engine import create_engine
from tests.stage3_restore_transport import (
    fence_restore_incident,
    postgres_snapshot,
    restarted_dashboard,
)
from tests.test_operator_recovery_postgres import real_recovery as real_recovery


def _crash_controller(url, store_b_path, secret, profile, archive, point, events):
    async def run():
        engine = create_engine(url)
        provider = SqliteDurableLifecycleStateProvider(store_b_path, secret_key=secret)
        original_write = provider.set_readiness_state

        def write(state, updated_by=""):
            if point == "before_durable":
                os._exit(73)
            original_write(state, updated_by)
            if point == "after_durable":
                os._exit(73)

        provider.set_readiness_state = write
        if point == "during_restore":
            original_run = subprocess.run

            def observed_run(arguments, **kwargs):
                if Path(arguments[0]).name != "pg_restore":
                    return original_run(arguments, **kwargs)
                timeout = kwargs.pop("timeout")
                kwargs.pop("check")
                kwargs.pop("capture_output")
                process = subprocess.Popen(
                    arguments, stdout=subprocess.PIPE, stderr=subprocess.PIPE, **kwargs
                )
                events.send(process.pid)
                stdout, stderr = process.communicate(timeout=timeout)
                return subprocess.CompletedProcess(arguments, process.returncode, stdout, stderr)

            subprocess.run = observed_run
        await fence_restore_incident(engine, provider, profile)
        await engine.close()
        await postgres_snapshot(engine, archive, restore=True, provider=provider)
        os._exit(73)

    try:
        asyncio.run(run())
    except Exception:
        # Never print private environment/SQL data from a child failure.
        os._exit(74)


async def _probe_after_snapshot(engine, archive):
    async with engine.raw.begin() as connection:
        await connection.execute(text("CREATE TABLE restore_transport_probe(value text NOT NULL)"))
        await connection.execute(text("INSERT INTO restore_transport_probe VALUES('snapshot')"))
    await postgres_snapshot(engine, archive)
    async with engine.raw.begin() as connection:
        await connection.execute(text("UPDATE restore_transport_probe SET value='post-snapshot'"))


async def _verify_quarantine(engine, provider, url):
    reopened = SqliteDurableLifecycleStateProvider(provider.path, secret_key=provider._secret_key)
    assert reopened.get_readiness_state() == RestoreReadinessState.RESTORE_PENDING
    gate = RestoreReadinessGate(provider=reopened, db_engine=engine)
    with pytest.raises(RestoreQuarantineError):
        await gate.assert_current_traffic_admitted()
    async with restarted_dashboard(url) as (origin, _):
        async with httpx.AsyncClient(base_url=origin, timeout=10) as client:
            assert (await client.get("/api/v1/web/session")).status_code == 503
    async with engine.raw.connect() as connection:
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM governance_execution_authorizations")
            )
            == 0
        )
        assert (
            await connection.scalar(text("SELECT count(*) FROM test_consequential_counters")) == 0
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
@pytest.mark.parametrize("point", ["before_durable", "after_durable", "after_restore"])
async def test_restore_controller_crash_preserves_order_and_quarantine(
    real_recovery, tmp_path, point
):
    engine, provider, _, profile, _ = real_recovery
    archive = tmp_path / "crash-snapshot.dump"
    await _probe_after_snapshot(engine, archive)
    url = engine.raw.url.render_as_string(hide_password=False)
    process = multiprocessing.get_context("spawn").Process(
        target=_crash_controller,
        args=(url, provider.path, provider._secret_key, profile, archive, point, None),
    )
    process.start()
    try:
        await asyncio.to_thread(process.join, 50)
        assert not process.is_alive(), "Child did not reach the bounded crash point"
        assert process.exitcode == 73
    finally:
        if process.is_alive():
            process.kill()
            await asyncio.to_thread(process.join, 5)
    async with engine.raw.connect() as connection:
        value = await connection.scalar(text("SELECT value FROM restore_transport_probe"))
    assert value == ("snapshot" if point == "after_restore" else "post-snapshot")
    if point == "before_durable":
        assert provider.get_readiness_state() == RestoreReadinessState.READY
        # Even a surviving caller cannot invoke the real transport without fencing.
        with pytest.raises(AssertionError, match="durable RESTORE_PENDING"):
            await postgres_snapshot(engine, archive, restore=True, provider=provider)
    else:
        await _verify_quarantine(engine, provider, url)


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
async def test_killed_actual_pg_restore_remains_quarantined_and_rolls_back(real_recovery, tmp_path):
    engine, provider, _, profile, _ = real_recovery
    archive = tmp_path / "interrupted-restore.dump"
    await _probe_after_snapshot(engine, archive)
    url = engine.raw.url.render_as_string(hide_password=False)
    receiver, sender = multiprocessing.get_context("spawn").Pipe(duplex=False)
    process = multiprocessing.get_context("spawn").Process(
        target=_crash_controller,
        args=(url, provider.path, provider._secret_key, profile, archive, "during_restore", sender),
    )
    restore_pid = None
    restore_killed = False
    async with engine.raw.begin() as blocker:
        await blocker.execute(text("LOCK TABLE restore_transport_probe IN ACCESS EXCLUSIVE MODE"))
        process.start()
        try:
            assert await asyncio.to_thread(receiver.poll, 40), "pg_restore was never started"
            restore_pid = receiver.recv()
            async with asyncio.timeout(30):
                while True:
                    async with engine.raw.connect() as observer:
                        blocked = await observer.scalar(
                            text(
                                "SELECT count(*) FROM pg_stat_activity WHERE datname=current_database() "
                                "AND application_name='pg_restore' AND wait_event_type='Lock'"
                            )
                        )
                    if blocked:
                        break
                    await asyncio.sleep(0.1)
            os.kill(restore_pid, signal.SIGKILL)
            restore_killed = True
            await asyncio.to_thread(process.join, 10)
            assert process.exitcode == 74  # Actual restore failure, never a synthetic success.
        finally:
            if restore_pid is not None and not restore_killed:
                try:
                    os.kill(restore_pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
            if process.is_alive():
                process.kill()
                await asyncio.to_thread(process.join, 5)
            receiver.close()
            sender.close()
    async with engine.raw.connect() as connection:
        assert (
            await connection.scalar(text("SELECT value FROM restore_transport_probe"))
            == "post-snapshot"
        )
    await _verify_quarantine(engine, provider, url)


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
async def test_restore_transport_refuses_competing_operator_operation(real_recovery, tmp_path):
    engine, provider, _, profile_path, _ = real_recovery
    archive = tmp_path / "competing-operation.dump"
    await _probe_after_snapshot(engine, archive)
    await fence_restore_incident(engine, provider, profile_path)
    profile = OperatorProfile.load(profile_path)
    with _exclusive_operation(profile):
        with pytest.raises(RecoveryAuthorizationError):
            await postgres_snapshot(engine, archive, restore=True, provider=provider)
    async with engine.raw.connect() as connection:
        assert (
            await connection.scalar(text("SELECT value FROM restore_transport_probe"))
            == "post-snapshot"
        )
    await _verify_quarantine(engine, provider, engine.raw.url.render_as_string(hide_password=False))
