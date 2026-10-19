# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Actual Docker containment probes, never customer authority/journey receipts."""

import asyncio
import json
import subprocess
import uuid
from pathlib import Path

import pytest

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)

pytestmark = pytest.mark.usefixtures("real_container_host")


def docker(*args):
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, check=False, timeout=10
    )


@pytest.fixture
def native_backend(monkeypatch, tmp_path):
    InFlightExecutionRegistry.reset_instance()
    monkeypatch.setattr(
        "responsibleai.isolation.in_flight._DISTRIBUTED_REGISTRY_DIR", tmp_path / "tracking"
    )
    backend = DockerContainerBackend()
    backend._containment_probe_enabled = True
    observed = []
    original = asyncio.create_subprocess_exec

    async def observe(*command, **kwargs):
        # Transparent observation: the real Docker process and its exact arguments
        # run unchanged. No inspection, removal or creation response is replaced.
        if command[0] == backend.docker_cmd and command[1] == "run":
            observed.append(
                {
                    "receipt": Path(
                        next(x.split("=", 1)[1] for x in command if x.startswith("--cidfile="))
                    ),
                    "name": next(x.split("=", 1)[1] for x in command if x.startswith("--name=")),
                }
            )
        return await original(*command, **kwargs)

    monkeypatch.setattr(asyncio, "create_subprocess_exec", observe)
    try:
        yield backend, observed
    finally:
        # Only exact test-owned acknowledged IDs are eligible for test cleanup.
        for row in observed:
            cid = row.get("cid")
            if cid:
                docker("rm", "-f", cid)
        InFlightExecutionRegistry.reset_instance()


async def running_receipt(observed, action_id):
    for _ in range(250):
        row = next((r for r in observed if action_id in r["name"]), None)
        if row is not None:
            try:
                value = row["receipt"].read_text(encoding="ascii")
            except FileNotFoundError:
                value = ""
            if len(value) == 64 and all(c in "0123456789abcdef" for c in value):
                info = docker("inspect", value)
                if info.returncode == 0 and json.loads(info.stdout)[0]["State"]["Running"]:
                    row["cid"] = value
                    return row
        await asyncio.sleep(0.02)
    raise AssertionError("Test container never reached actual acknowledged running state")


def request(org, action, delay, result):
    script = (
        "import json,time\n"
        f"time.sleep({delay!r})\n"
        f"print({json.dumps({'status': 'success', 'result': result})!r})\n"
    )
    return IsolatedExecutionRequest(
        action_id=action,
        organization_id=org,
        action_type="contract_probe",
        arguments={},
        profile=IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=8)),
        workspace_files={"runner.py": script},
    )


@pytest.mark.asyncio
async def test_acknowledged_cancellation_preserves_same_tenant_sibling(native_backend):
    backend, observed = native_backend
    suffix = uuid.uuid4().hex[:8]
    org = f"ack-{suffix}"
    action_a, action_b = f"a-{suffix}", f"b-{suffix}"
    task_a = asyncio.create_task(backend.execute(request(org, action_a, 20, "canceled")))
    task_b = asyncio.create_task(backend.execute(request(org, action_b, 2, "sibling")))
    try:
        own_a = await running_receipt(observed, action_a)
        await running_receipt(observed, action_b)
        task_a.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task_a), 15)
        outcome = await asyncio.wait_for(task_b, 15)
        assert outcome.is_success and outcome.result_payload == "sibling"
        absent = docker("inspect", own_a["cid"])
        assert absent.returncode != 0 and "no such" in absent.stderr.lower()
        registry = InFlightExecutionRegistry.get_instance()
        assert registry.count_active(org) == 0
        assert registry.count_unresolved(org) == 0
    finally:
        for task in (task_a, task_b):
            if not task.done():
                task.cancel()
        await asyncio.gather(task_a, task_b, return_exceptions=True)


@pytest.mark.asyncio
async def test_lost_receipt_keeps_org_denied_without_affecting_foreign_tenant(native_backend):
    backend, observed = native_backend
    suffix = uuid.uuid4().hex[:8]
    org, foreign = f"loss-{suffix}", f"foreign-{suffix}"
    action = f"loss-{suffix}"
    task = asyncio.create_task(backend.execute(request(org, action, 20, "canceled")))
    try:
        own = await running_receipt(observed, action)
        # Actual host-filesystem fault injection, after a real acknowledged
        # container exists. The backend cannot infer this missing proof from PID
        # death or an absence window. This grants no authority or recovery bypass.
        own["receipt"].unlink()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await asyncio.wait_for(asyncio.shield(task), 15)
        registry = InFlightExecutionRegistry.get_instance()
        assert registry.has_unresolved(org)
        denied = await backend.execute(request(org, f"denied-{suffix}", 0, "denied"))
        assert not denied.is_success
        assert registry.has_unresolved(org)
        allowed = await backend.execute(request(foreign, f"foreign-{suffix}", 0, "foreign"))
        assert allowed.is_success and allowed.result_payload == "foreign"
        assert not registry.has_unresolved(foreign)
        absent = docker("inspect", own["cid"])
        assert absent.returncode != 0 and "no such" in absent.stderr.lower()
    finally:
        if not task.done():
            task.cancel()
        await asyncio.gather(task, return_exceptions=True)
