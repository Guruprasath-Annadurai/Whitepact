# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual child process death with real PostgreSQL and durable recovery stores."""

import asyncio
import json
import os
import subprocess
import sys
from dataclasses import asdict

import pytest

from responsibleai.data_governance.backup_defense import (
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from responsibleai.data_governance.operator_recovery_control import (
    execute_offline_recovery,
    prepare_offline_recovery,
)
from tests.test_operator_recovery_postgres import real_recovery as real_recovery
from tests.test_operator_recovery_postgres import sign

_CRASH_CHILD = r"""
import asyncio, json, os, sys
from pathlib import Path
from responsibleai.data_governance.backup_defense import RestoreReadinessGate, SqliteDurableLifecycleStateProvider
from responsibleai.data_governance.operator_recovery import RecoveryManifest, RecoveryReceiptLedger
from responsibleai.data_governance import operator_recovery_control as control
from responsibleai.db.engine import create_engine

async def run():
    request = json.loads(Path(sys.argv[1]).read_text())
    point = sys.argv[2]
    profile = control.OperatorProfile.load(Path(request['profile_path']))
    provider = SqliteDurableLifecycleStateProvider(profile.store_b_path)
    engine = create_engine(os.environ['WHITEPACT_R1_TEST_DATABASE_URL'])
    gate = RestoreReadinessGate(provider=provider, db_engine=engine)
    original_phase = control._phase
    def phase(session, previous, following, **values):
        if point == 'before_complete' and following == 'COMPLETE':
            os._exit(71)
        original_phase(session, previous, following, **values)
        if ((point == 'after_pg_verified' and following == 'PG_VERIFIED') or
            (point == 'after_complete' and following == 'COMPLETE')):
            os._exit(71)
    control._phase = phase
    original_consume = RecoveryReceiptLedger.consume_approvals
    def consume(self, *args, **kwargs):
        value = original_consume(self, *args, **kwargs)
        if point == 'after_consumption':
            os._exit(71)
        return value
    RecoveryReceiptLedger.consume_approvals = consume
    original_ready = provider.set_readiness_state
    def ready(state, updated_by=''):
        original_ready(state, updated_by)
        if point == 'after_store_b_ready' and state == 'READY':
            os._exit(71)
    provider.set_readiness_state = ready
    try:
        await control.execute_offline_recovery(engine, provider, gate, profile_path=profile.path,
            manifest=RecoveryManifest(**request['manifest']), signatures=request['signatures'])
    finally:
        await engine.close()
try:
    asyncio.run(run())
except BaseException as exc:
    print(type(exc).__name__, file=sys.stderr)
    sys.exit(66)
"""


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "point",
    [
        "after_consumption",
        "after_pg_verified",
        "after_store_b_ready",
        "before_complete",
        "after_complete",
    ],
)
async def test_real_process_death_does_not_reopen_partial_recovery(real_recovery, point):
    engine, provider, gate, profile_path, private = real_recovery
    manifest = await prepare_offline_recovery(engine, provider, profile_path=profile_path)
    request_path = profile_path.with_name("signed-request.json")
    request_path.write_text(
        json.dumps(
            {
                "profile_path": str(profile_path),
                "manifest": asdict(manifest),
                "signatures": sign(manifest, private),
            }
        )
    )
    request_path.chmod(0o600)
    environment = dict(os.environ)
    # Credential is confined to the subprocess environment, not command/log data.
    environment["WHITEPACT_R1_TEST_DATABASE_URL"] = engine.raw.url.render_as_string(
        hide_password=False
    )
    result = await asyncio.to_thread(
        subprocess.run,
        [sys.executable, "-c", _CRASH_CHILD, str(request_path), point],
        env=environment,
        capture_output=True,
        text=True,
        timeout=90,
    )
    assert result.returncode == 71, result.stderr
    restarted = SqliteDurableLifecycleStateProvider(provider.path)
    restarted_gate = RestoreReadinessGate(provider=restarted, db_engine=engine)
    if point == "after_complete":
        await restarted_gate.assert_current_traffic_admitted()
        assert restarted_gate.state == RestoreReadinessState.READY
    else:
        assert restarted_gate.state != RestoreReadinessState.READY
        with pytest.raises(RestoreQuarantineError):
            await restarted_gate.assert_current_traffic_admitted()
        assert restarted_gate.state in (
            RestoreReadinessState.FAILED,
            RestoreReadinessState.RECONCILING,
        )
    with pytest.raises(RecoveryAuthorizationError):
        await execute_offline_recovery(
            engine,
            restarted,
            restarted_gate,
            profile_path=profile_path,
            manifest=manifest,
            signatures=sign(manifest, private),
        )
