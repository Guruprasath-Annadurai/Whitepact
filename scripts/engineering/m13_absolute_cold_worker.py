# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Disposable native qualification child. NOT a customer/root authority issuer."""

import asyncio
import os
from datetime import UTC, datetime, timedelta
from pathlib import Path

from responsibleai.db.engine import create_engine
from responsibleai.enterprise.runtime import configure_enterprise
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


if __name__ == "__main__":
    asyncio.run(main())
