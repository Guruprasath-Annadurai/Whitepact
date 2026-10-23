# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Real PostgreSQL and restarted offline CLI transport, disposable databases only."""

import asyncio
import json
import os
import shutil
import socket
import subprocess
import sys
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

from responsibleai.data_governance.backup_defense import (
    RestoreQuarantineError,
    RestoreReadinessGate,
    RestoreReadinessState,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.data_governance.operator_recovery_control import (
    OperatorProfile,
    _exclusive_operation,
    collect_recovery_evidence,
)


async def fence_restore_incident(engine, provider, profile_path):
    """Trusted disposable test controller only; NOT production operator enrollment.

    No customer route calls this test helper. A caller label is audit metadata,
    not authentication. The protected fixture supplies the pinned host profile.
    """
    profile = OperatorProfile.load(profile_path)
    assert profile.environment != "production"
    # Verify the real journal, in-flight tracking and actual Docker inventory
    # before maintenance. Unknown or unresolved workloads are never assumed gone.
    await collect_recovery_evidence(engine, provider, profile)
    records = provider.list_all()
    with provider._get_connection() as connection:
        before = connection.execute(
            "SELECT state,epoch FROM durable_restore_readiness WHERE key='global'"
        ).fetchone()
    assert before is not None and before[0] == "READY"
    provider.set_readiness_state(
        RestoreReadinessState.RESTORE_PENDING,
        updated_by=f"trusted-nonproduction-restore-controller:{profile.incident_id}",
    )
    independently_opened = SqliteDurableLifecycleStateProvider(
        provider.path, secret_key=provider._secret_key
    )
    assert independently_opened.get_readiness_state() == RestoreReadinessState.RESTORE_PENDING
    assert independently_opened.list_all() == records
    assert independently_opened.verify_integrity()
    with independently_opened._get_connection() as connection:
        after = connection.execute(
            "SELECT state,epoch FROM durable_restore_readiness WHERE key='global'"
        ).fetchone()
    assert after[0] == "RESTORE_PENDING" and after[1] > before[1]
    gate = RestoreReadinessGate(provider=independently_opened, db_engine=engine)
    try:
        await gate.assert_current_traffic_admitted()
    except RestoreQuarantineError:
        pass
    else:
        raise AssertionError("Restore must not begin while admission is open")
    return {
        "incident_id": profile.incident_id,
        "before": before[0],
        "before_epoch": before[1],
        "after": after[0],
        "after_epoch": after[1],
    }


async def postgres_snapshot(engine, archive, *, restore=False, provider=None):
    url = engine.raw.url
    database = url.database
    if not database or not database.startswith("wp_r1_recovery_"):
        raise AssertionError("Only an explicitly owned disposable recovery database is permitted")
    if url.host not in {"localhost", "127.0.0.1", "::1"}:
        raise AssertionError("PostgreSQL snapshot transport is local only")
    command = "pg_restore" if restore else "pg_dump"
    executable = shutil.which(command)
    if executable is None:
        raise AssertionError("PostgreSQL backup/restore executable required; no simulated fallback")
    env = os.environ.copy()
    env.update(
        {
            "PGHOST": url.host,
            "PGPORT": str(url.port or 5432),
            "PGDATABASE": database,
            "PGUSER": url.username or "postgres",
            "PGPASSWORD": url.password or "",
            "PGCONNECT_TIMEOUT": "10",
        }
    )
    if restore:
        if type(provider) is not SqliteDurableLifecycleStateProvider:
            raise AssertionError("Verified durable restore fencing is required")
        if provider.get_readiness_state() != RestoreReadinessState.RESTORE_PENDING:
            raise AssertionError("PostgreSQL restore cannot start without durable RESTORE_PENDING")
        if not provider.verify_integrity():
            raise AssertionError("Unverified Store B cannot authorize restore transport")
        if not archive.is_file():
            raise AssertionError("Existing pre-deletion snapshot required")
        arguments = [
            executable,
            "--clean",
            "--if-exists",
            "--exit-on-error",
            "--single-transaction",
            "--no-owner",
            "--dbname",
            database,
            str(archive),
        ]
    else:
        if archive.exists():
            raise AssertionError("Do not overwrite an earlier snapshot")
        arguments = [executable, "--format=custom", "--no-owner", "--file", str(archive)]
    if restore:
        pinned = os.environ.get("WHITEPACT_OPERATOR_RECOVERY_TRUST_CONFIG")
        if not pinned:
            raise AssertionError("Trusted isolated restore-controller profile required")
        profile = OperatorProfile.load(Path(pinned))
        if profile.store_b_path != provider.path:
            raise AssertionError("Restore incident and Store B target differ")
        # Same lock as the genuine R1 controller, held across the real command.
        # An independently signed recovery cannot race the destructive restore.
        with _exclusive_operation(profile):
            if provider.get_readiness_state() != RestoreReadinessState.RESTORE_PENDING:
                raise AssertionError("Restore readiness changed before PostgreSQL restoration")
            result = await asyncio.to_thread(
                subprocess.run, arguments, env=env, capture_output=True, timeout=90, check=False
            )
            if provider.get_readiness_state() != RestoreReadinessState.RESTORE_PENDING:
                raise AssertionError("Restore readiness changed during PostgreSQL restoration")
    else:
        result = await asyncio.to_thread(
            subprocess.run, arguments, env=env, capture_output=True, timeout=90, check=False
        )
    # Never expose stderr, a URL or database credentials on failure.
    assert result.returncode == 0, f"{command} failed; return code {result.returncode}"
    if not restore:
        archive.chmod(0o600)
        assert archive.stat().st_size > 0


async def offline_cli(
    profile_path, *, operation, output=None, request=None, expect_rejection=False
):
    arguments = [
        sys.executable,
        "-m",
        "responsibleai.ops.operator_recovery",
        "--profile",
        str(profile_path),
        operation,
    ]
    if output is not None:
        arguments.extend(["--output", str(output)])
    if request is not None:
        arguments.extend(["--request", str(request)])
    result = await asyncio.to_thread(
        subprocess.run, arguments, capture_output=True, timeout=90, check=False
    )
    try:
        payload = json.loads(result.stdout)
    except (ValueError, UnicodeDecodeError):
        raise AssertionError("Offline recovery did not return a valid status receipt") from None
    if expect_rejection:
        assert result.returncode == 1 and payload == {"status": "RECOVERY_REJECTED_OR_FAILED"}
        return payload
    assert result.returncode == 0, {
        "operation": operation,
        "status": payload.get("status"),
        "returncode": result.returncode,
    }
    return payload


def write_signed_request(path: Path, envelope):
    descriptor = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(envelope, stream, sort_keys=True)
        stream.flush()
        os.fsync(stream.fileno())


@asynccontextmanager
async def restarted_dashboard(url):
    """A genuinely new application process, never an in-process gate reset."""
    listener = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    listener.bind(("127.0.0.1", 0))
    listener.listen(32)
    origin = f"http://127.0.0.1:{listener.getsockname()[1]}"
    env = os.environ.copy()
    env.update(
        {
            "WHITEPACT_DATABASE_URL": url,
            "WHITEPACT_AUTO_MIGRATE": "false",
            "WHITEPACT_AUTH_ENABLED": "true",
            "WHITEPACT_WEB_SESSION_SECURE": "false",
            "WHITEPACT_API_KEYS": "[]",
        }
    )
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "responsibleai.dashboard.app:app",
            "--fd",
            str(listener.fileno()),
            "--log-level",
            "critical",
            "--no-access-log",
        ],
        env=env,
        pass_fds=(listener.fileno(),),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    listener.close()
    try:
        async with asyncio.timeout(40):
            async with httpx.AsyncClient(timeout=1) as client:
                while True:
                    if process.poll() is not None:
                        raise AssertionError(
                            f"Isolated runtime startup failed: {process.returncode}"
                        )
                    try:
                        response = await client.get(origin + "/api/health")
                        if response.status_code in {200, 503}:
                            break
                    except httpx.TransportError:
                        pass
                    await asyncio.sleep(0.1)
        yield origin, process.pid
    finally:
        process.terminate()
        try:
            await asyncio.to_thread(process.wait, 10)
        except subprocess.TimeoutExpired:
            process.kill()
            await asyncio.to_thread(process.wait, 5)
