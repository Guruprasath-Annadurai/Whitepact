# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual Linux late-ACK recovery; never a customer authority receipt."""

import asyncio
import json
import uuid

import pytest

from responsibleai.isolation import in_flight
from tests.test_m13_ironclad_native_contracts import (
    docker,
    running_receipt,
)
from tests.test_m13_ironclad_native_contracts import (
    native_backend as native_backend,
)
from tests.test_m13_ironclad_native_contracts import (
    request as probe_request,
)

pytestmark = pytest.mark.usefixtures("real_container_host")


@pytest.mark.asyncio
async def test_detached_late_ack_and_missing_tracking_require_real_owned_cid(native_backend):
    backend, observed = native_backend
    suffix = uuid.uuid4().hex[:8]
    org, action = f"late-{suffix}", f"probe-{suffix}"
    task = asyncio.create_task(backend.execute(probe_request(org, action, 20, "not-a-receipt")))
    try:
        owned = await running_receipt(observed, action)
        registry = in_flight.InFlightExecutionRegistry.get_instance()
        entry = next(e for e in registry._active.values() if e.organization_id == org)
        assert entry.container_receipt == str(owned["receipt"])
        # Discard the early cache and simulate lost in-process ownership. The
        # actual late Docker receipt and daemon creation labels must prove CID.
        entry.container_id = None
        entry.task = None
        entry.terminate_callback = None
        for path in in_flight._DISTRIBUTED_REGISTRY_DIR.glob("*.json"):
            record = json.loads(path.read_text())
            if record.get("registration_id") == entry.registration_id:
                path.unlink()  # Exact test-owned record only; absence is no proof.
        terminated = await registry.terminate_in_flight(organization_id=org)
        assert terminated == [entry.execution_id]
        absent = docker("inspect", owned["cid"])
        assert absent.returncode != 0 and "no such" in absent.stderr.lower()
        await asyncio.wait_for(asyncio.shield(task), 15)
        assert not registry.has_unresolved(org)
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
