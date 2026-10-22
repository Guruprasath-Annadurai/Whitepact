# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable native qualification child. NOT a customer/root authority issuer."""

import asyncio
import os
import sys
import time
from datetime import UTC, datetime, timedelta
from pathlib import Path

from responsibleai.db.engine import create_engine
from responsibleai.enterprise.runtime import configure_enterprise
from responsibleai.isolation import container_backend as backend_module
from responsibleai.isolation import in_flight
from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)


async def main() -> None:
    engine = create_engine(os.environ["WP_ABSOLUTE_DISPOSABLE_DB"])
    configure_enterprise(engine)
    in_flight._DISTRIBUTED_REGISTRY_DIR = Path(os.environ["WP_ABSOLUTE_TRACKING"])
    backend = DockerContainerBackend()
    backend._containment_probe_enabled = True
    # Disposable test-worker fault injection only; production has no such hook.
    phase = os.environ.get("WP_ABSOLUTE_PAUSE_PHASE")
    if phase:
        marker = Path(os.environ["WP_ABSOLUTE_PHASE_FILE"])

        def pause():
            marker.write_text(phase, encoding="utf-8")
            time.sleep(120)

        create = backend._create_stopped_container

        def paused_create(command, receipt):
            if phase == "before_create":
                pause()
            cid = create(command, receipt)
            if phase == "after_create":
                pause()
            return cid

        backend._create_stopped_container = paused_create
        start = backend_module.asyncio.create_subprocess_exec

        async def paused_start(*command, **kwargs):
            if phase == "before_start" and command[1] == "start":
                marker.write_text(phase, encoding="utf-8")
                await asyncio.sleep(120)
            return await start(*command, **kwargs)

        backend_module.asyncio.create_subprocess_exec = paused_start
    try:
        await backend.execute(
            IsolatedExecutionRequest(
                action_id="controlled-native-probe",
                organization_id="native-owner",
                action_type="controlled-native-probe",
                arguments={},
                authorization_id="component-test-grant",
                action_digest="a" * 64,
                authorization_expires_at=datetime.now(UTC) + timedelta(seconds=30),
                admission_epoch=0,
                workspace_files={"runner.py": "import time; time.sleep(120)"},
                profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=120)),
            )
        )
    finally:
        await engine.close()


def record_failure(error: Exception) -> None:
    """Test-only diagnostics: never retain exception text, traces or credentials."""
    destination = os.environ.get("WP_ABSOLUTE_FAILURE_FILE")
    if destination:
        category = type(error).__name__
        if not category.isascii() or not category.isidentifier() or len(category) > 80:
            category = "UnexpectedWorkerFailure"
        try:
            descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        except OSError:
            # Keep the original failing exit without printing a chained traceback.
            return
        with os.fdopen(descriptor, "w", encoding="ascii") as output:
            output.write(category)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as error:
        record_failure(error)
        sys.exit(1)
