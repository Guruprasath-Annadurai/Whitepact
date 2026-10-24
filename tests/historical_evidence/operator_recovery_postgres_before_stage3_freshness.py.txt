# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real disposable PostgreSQL 16 and local Docker evidence, not production enrollment."""

import base64
import hashlib
import json
import os
import re
import sqlite3
import subprocess
import uuid
from dataclasses import replace
from datetime import UTC, datetime

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat
from sqlalchemy import text

from responsibleai.data_governance.backup_defense import (
    RestoreReadinessGate,
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.operator_recovery import RecoveryAuthorizationError
from responsibleai.data_governance.operator_recovery_control import (
    execute_offline_recovery,
    initialize_control_ledger,
    prepare_offline_recovery,
)
from responsibleai.db.engine import create_engine
from responsibleai.db.migrate import _find_alembic_ini, _migration_env, _run_alembic
from tests.pg_test_url import isolated_pg_url


@pytest.fixture
async def real_recovery(tmp_path, monkeypatch, request):
    monkeypatch.setenv("WHITEPACT_ENV", "staging")
    monkeypatch.delenv("WHITEPACT_ALLOW_UNISOLATED_EXECUTION", raising=False)
    async for url in isolated_pg_url("wp_r1_recovery"):
        await _run_alembic(_find_alembic_ini(), _migration_env(url), "upgrade", "head")
        engine = create_engine(url)
        try:
            async with engine.raw.connect() as connection:
                server = await connection.scalar(text("SHOW server_version_num"))
                assert 160000 <= int(server) < 170000
                identity = (
                    await connection.execute(
                        text(
                            "SELECT current_database(), oid::text, (SELECT system_identifier::text FROM pg_control_system()) "
                            "FROM pg_database WHERE datname=current_database()"
                        )
                    )
                ).one()
            provider = SqliteDurableLifecycleStateProvider(tmp_path / "store-b.sqlite3")
            provider.set_readiness_state(
                RestoreReadinessState.READY
                if getattr(request, "param", None) == "normal"
                else RestoreReadinessState.FAILED
            )
            gate = RestoreReadinessGate(provider=provider, db_engine=engine)
            ledger_path = tmp_path / "operator-receipts.sqlite3"
            initialize_control_ledger(ledger_path)
            private = {name: Ed25519PrivateKey.generate() for name in ("security", "operator")}
            daemon = subprocess.run(
                ["docker", "info", "--format", "{{.ID}}"],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            ).stdout.strip()
            inventory = subprocess.run(
                ["docker", "ps", "--all", "--no-trunc", "--format", "{{.ID}}"],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            ).stdout.splitlines()
            profile = {
                "purpose": "NONPRODUCTION_RECOVERY_QUALIFICATION",
                "deployment_id": "isolated-r1-test",
                "environment": "staging",
                "incident_id": "test-outage",
                "postgres_identity": hashlib.sha256(
                    json.dumps(
                        list(identity), sort_keys=True, separators=(",", ":"), ensure_ascii=True
                    ).encode()
                ).hexdigest(),
                "store_b_path": str(provider.path),
                "ledger_path": str(ledger_path),
                "docker_identity": daemon,
                "infrastructure_ids": inventory,
                "keys": [
                    {
                        "identity": name,
                        "role": role,
                        "revoked": False,
                        "public_key": private[name]
                        .public_key()
                        .public_bytes(Encoding.Raw, PublicFormat.Raw)
                        .hex(),
                    }
                    for name, role in (
                        ("security", "SECURITY_OWNER"),
                        ("operator", "RECOVERY_OPERATOR"),
                    )
                ],
            }
            profile_path = tmp_path / "nonproduction-trust.json"
            profile_path.write_text(json.dumps(profile))
            profile_path.chmod(0o600)
            monkeypatch.setenv("WHITEPACT_OPERATOR_RECOVERY_TRUST_CONFIG", str(profile_path))
            yield engine, provider, gate, profile_path, private
        finally:
            await engine.close()


def sign(manifest, private):
    return {
        name: base64.b64encode(key.sign(manifest.canonical_bytes())).decode("ascii")
        for name, key in private.items()
    }


@pytest.mark.asyncio
@pytest.mark.parametrize("real_recovery", ["normal"], indirect=True)
async def test_real_postgres_signed_recovery_and_restart_readback(real_recovery):
    import asyncpg

    from responsibleai.data_governance.backup_defense import RestoreQuarantineError
    from tests.pg_test_url import resolve_admin_url

    engine, provider, gate, profile_path, private = real_recovery
    await gate.assert_current_traffic_admitted()
    database = engine.raw.url.database
    assert database.startswith("wp_r1_recovery_")
    admin = await asyncpg.connect(await resolve_admin_url())
    try:
        await admin.execute(f'ALTER DATABASE "{database}" ALLOW_CONNECTIONS false')
        await admin.execute(
            "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE datname=$1", database
        )
        with pytest.raises(RestoreQuarantineError):
            await gate.assert_current_traffic_admitted()
    finally:
        await admin.execute(f'ALTER DATABASE "{database}" ALLOW_CONNECTIONS true')
        await admin.close()
    await engine.raw.dispose()
    with pytest.raises(RestoreQuarantineError):
        await gate.assert_current_traffic_admitted()
    assert gate.state == RestoreReadinessState.FAILED
    manifest = await prepare_offline_recovery(engine, provider, profile_path=profile_path)
    assert not gate.is_admitted()
    report = await execute_offline_recovery(
        engine,
        provider,
        gate,
        profile_path=profile_path,
        manifest=manifest,
        signatures=sign(manifest, private),
    )
    assert report.status == "RECONCILED"
    await gate.assert_current_traffic_admitted()
    assert gate.state == RestoreReadinessState.READY
    restarted = SqliteDurableLifecycleStateProvider(provider.path)
    restarted_gate = RestoreReadinessGate(provider=restarted, db_engine=engine)
    await restarted_gate.assert_current_traffic_admitted()
    assert restarted_gate.is_admitted()
    async with engine.raw.connect() as connection:
        row = (
            await connection.execute(
                text("SELECT status,reconciled_by FROM restore_reconciliation_records")
            )
        ).one()
    assert tuple(row) == ("RECONCILED", manifest.request_id)
    with pytest.raises(RecoveryAuthorizationError):
        await execute_offline_recovery(
            engine,
            restarted,
            restarted_gate,
            profile_path=profile_path,
            manifest=manifest,
            signatures=sign(manifest, private),
        )


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["forged", "missing", "expired", "stale", "wrong_incident"])
async def test_real_postgres_unsafe_authorization_stays_quarantined(real_recovery, case):
    engine, provider, gate, profile_path, private = real_recovery
    manifest = await prepare_offline_recovery(engine, provider, profile_path=profile_path)
    if case == "expired":
        manifest = replace(manifest, created_at=1, expires_at=2)
    elif case == "wrong_incident":
        manifest = replace(manifest, incident_id="different-incident")
    signatures = sign(manifest, private)
    if case == "forged":
        signatures["security"] = base64.b64encode(b"x" * 64).decode("ascii")
    elif case == "missing":
        signatures.pop("security")
    elif case == "stale":
        provider.set_readiness_state(RestoreReadinessState.FAILED)
    with pytest.raises(RecoveryAuthorizationError):
        await execute_offline_recovery(
            engine,
            provider,
            gate,
            profile_path=profile_path,
            manifest=manifest,
            signatures=signatures,
        )
    assert gate.state == RestoreReadinessState.FAILED
    async with engine.raw.connect() as connection:
        assert (
            await connection.scalar(text("SELECT count(*) FROM restore_reconciliation_records"))
            == 0
        )


@pytest.mark.asyncio
async def test_competing_operator_lock_cannot_consume_or_restore_authority(real_recovery):
    import fcntl

    from responsibleai.data_governance.operator_recovery_control import OperatorProfile

    engine, provider, gate, profile_path, private = real_recovery
    manifest = await prepare_offline_recovery(engine, provider, profile_path=profile_path)
    profile = OperatorProfile.load(profile_path)
    lock_path = profile.ledger_path.with_suffix(".recovery-lock")
    descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
    try:
        fcntl.flock(descriptor, fcntl.LOCK_EX | fcntl.LOCK_NB)
        with pytest.raises(BlockingIOError):
            await execute_offline_recovery(
                engine,
                provider,
                gate,
                profile_path=profile_path,
                manifest=manifest,
                signatures=sign(manifest, private),
            )
        assert gate.state == RestoreReadinessState.FAILED
        with sqlite3.connect(profile.ledger_path) as connection:
            assert connection.execute("SELECT count(*) FROM recovery_receipts").fetchone() == (0,)
        async with engine.raw.connect() as connection:
            assert (
                await connection.scalar(text("SELECT count(*) FROM restore_reconciliation_records"))
                == 0
            )
    finally:
        os.close(descriptor)
    # No automatic retry: a deliberate call after the competing operation ends
    # still has to validate the complete original evidence and both signatures.
    await execute_offline_recovery(
        engine,
        provider,
        gate,
        profile_path=profile_path,
        manifest=manifest,
        signatures=sign(manifest, private),
    )
    await gate.assert_current_traffic_admitted()


@pytest.mark.asyncio
async def test_actual_unknown_docker_workload_blocks_recovery_without_adoption(real_recovery):
    engine, provider, gate, profile_path, private = real_recovery
    image = subprocess.run(
        [
            "docker",
            "image",
            "inspect",
            os.environ.get("WHITEPACT_R1_TEST_IMAGE", "python:3.12-slim"),
            "--format",
            "{{.Id}}",
        ],
        capture_output=True,
        text=True,
        timeout=15,
        check=True,
    ).stdout.strip()
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", image)
    label = "r1-negative-" + uuid.uuid4().hex
    cid = subprocess.run(
        [
            "docker",
            "run",
            "--pull=never",
            "--detach",
            "--network=none",
            "--read-only",
            "--cap-drop=ALL",
            "--security-opt=no-new-privileges",
            "--pids-limit=16",
            "--memory=64m",
            "--cpus=0.1",
            "--user=65534:65534",
            "--label",
            "io.whitepact.execution=" + label,
            "--name",
            "wp_iso_" + label,
            image,
            "python3",
            "-c",
            "import time; time.sleep(120)",
        ],
        capture_output=True,
        text=True,
        timeout=20,
        check=True,
    ).stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{64}", cid)
    try:
        with pytest.raises(RecoveryAuthorizationError, match="Unknown or surviving"):
            await prepare_offline_recovery(engine, provider, profile_path=profile_path)
        assert gate.state == RestoreReadinessState.FAILED
        assert (
            subprocess.run(
                ["docker", "inspect", cid, "--format", "{{.State.Running}}"],
                capture_output=True,
                text=True,
                timeout=15,
                check=True,
            ).stdout.strip()
            == "true"
        )
    finally:
        # Only the exact disposable CID created above, after ownership readback;
        # never remove a production/unknown workload or clear a journal record.
        owned = subprocess.run(
            [
                "docker",
                "inspect",
                cid,
                "--format",
                '{{index .Config.Labels "io.whitepact.execution"}}',
            ],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout.strip()
        assert owned == label
        subprocess.run(
            ["docker", "stop", "--time=2", cid], capture_output=True, timeout=15, check=True
        )
        stopped = subprocess.run(
            ["docker", "inspect", cid, "--format", "{{.State.Running}}"],
            capture_output=True,
            text=True,
            timeout=15,
            check=True,
        ).stdout.strip()
        assert stopped == "false"
        subprocess.run(["docker", "rm", cid], capture_output=True, timeout=15, check=True)


@pytest.mark.asyncio
@pytest.mark.parametrize("case", ["postgres", "store_b"])
async def test_authority_change_between_approval_and_mutation_is_rejected(
    real_recovery, monkeypatch, case
):
    from responsibleai.data_governance.backup_defense import (
        LifecycleState,
        LifecycleStateRecord,
        RestoreReconciliationEngine,
        RestoreReconciliationError,
    )

    engine, provider, gate, profile_path, private = real_recovery
    manifest = await prepare_offline_recovery(engine, provider, profile_path=profile_path)
    original = RestoreReconciliationEngine.reconcile_post_restore
    incident = uuid.uuid4().hex

    async def concurrent_change(self, *args, **kwargs):
        if case == "postgres":
            async with engine.raw.begin() as connection:
                await connection.execute(
                    text(
                        "INSERT INTO restore_reconciliation_records "
                        "(id,restored_at,status,tombstones_detected,tenants_quarantined,reconciled_by,details_json) "
                        "VALUES(:id,:now,'FAILED',0,0,'separate-incident','{}')"
                    ),
                    {"id": incident, "now": datetime.now(UTC).isoformat()},
                )
        else:
            provider.record_state(
                LifecycleStateRecord(
                    tenant_id=incident,
                    generation_id="test-generation",
                    state=LifecycleState.ACTIVE,
                    effective_at=datetime.now(UTC).isoformat(),
                    security_epoch=2,
                    revocation_floor=2,
                )
            )
        return await original(self, *args, **kwargs)

    monkeypatch.setattr(RestoreReconciliationEngine, "reconcile_post_restore", concurrent_change)
    with pytest.raises(RestoreReconciliationError, match="Signed recovery inputs changed"):
        await execute_offline_recovery(
            engine,
            provider,
            gate,
            profile_path=profile_path,
            manifest=manifest,
            signatures=sign(manifest, private),
        )
    assert gate.state == RestoreReadinessState.FAILED
    async with engine.raw.connect() as connection:
        assert (
            await connection.scalar(
                text("SELECT count(*) FROM governance_execution_authorizations")
            )
            == 0
        )
        assert (
            await connection.scalar(text("SELECT count(*) FROM governance_root_authority_records"))
            == 0
        )
        if case == "postgres":
            assert (
                await connection.scalar(
                    text("SELECT status FROM restore_reconciliation_records WHERE id=:id"),
                    {"id": incident},
                )
                == "FAILED"
            )
    if case == "store_b":
        assert provider.get_state(incident).security_epoch == 2


@pytest.mark.asyncio
@pytest.mark.parametrize("store", ["postgres", "store_b"])
async def test_completed_recovery_cannot_be_reused_after_store_rollback(real_recovery, store):
    from responsibleai.data_governance.backup_defense import RestoreQuarantineError

    engine, provider, gate, profile_path, private = real_recovery
    manifest = await prepare_offline_recovery(engine, provider, profile_path=profile_path)
    await execute_offline_recovery(
        engine,
        provider,
        gate,
        profile_path=profile_path,
        manifest=manifest,
        signatures=sign(manifest, private),
    )
    await gate.assert_current_traffic_admitted()
    if store == "postgres":
        async with engine.raw.begin() as connection:
            await connection.execute(text("DELETE FROM restore_reconciliation_records"))
    else:
        # Controlled rollback-equivalent test corruption, never a production
        # maintenance path. The external consumption ledger is left intact.
        with sqlite3.connect(provider.path) as connection:
            connection.execute("DROP TABLE operator_recovery_binding")
            connection.execute(
                "UPDATE durable_restore_readiness SET state='READY',epoch=1 WHERE key='global'"
            )
    restarted = RestoreReadinessGate(
        provider=SqliteDurableLifecycleStateProvider(provider.path), db_engine=engine
    )
    with pytest.raises(RestoreQuarantineError):
        await restarted.assert_current_traffic_admitted()
    assert restarted.state == RestoreReadinessState.FAILED
