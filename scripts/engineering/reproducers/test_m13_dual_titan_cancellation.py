# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Independent cancellation accounting and execute-path tests; Docker is mocked."""

import asyncio
import threading
import uuid
from unittest.mock import patch

import pytest
from tests.image_admission_fixture import approved_inert_image as approved_inert_image

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.in_flight import InFlightExecutionRegistry
from responsibleai.isolation.models import (
    IsolatedExecutionRequest,
    IsolationProfile,
    NetworkPolicy,
    ResourceLimits,
)


@pytest.mark.asyncio
async def test_cleanup_preserves_exact_cancellation_request_count() -> None:
    backend = DockerContainerBackend()
    started, release = threading.Event(), threading.Event()

    def cleanup(*args, **kwargs):
        started.set()
        assert release.wait(5)

    async def owner():
        await backend._remove_containers_uninterruptible(
            ["wp_exact_cancellation"], stable_seconds=0, wait_seconds=0.1
        )
        await asyncio.sleep(0)

    with patch.object(backend, "_remove_containers", side_effect=cleanup):
        task = asyncio.create_task(owner())
        try:
            assert await asyncio.to_thread(started.wait, 3)
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert task.cancelling() == 2, (
                "Cleanup must neither lose nor invent cancellation requests"
            )
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.asyncio
async def test_execute_cleanup_failure_retains_tracking_after_cancellation(approved_inert_image) -> None:
    """Exercise actual execute(), replacing Docker transport only; not native evidence."""
    from responsibleai.isolation.durable_intent import required_journal

    assert required_journal() is None
    InFlightExecutionRegistry.reset_instance()
    backend = DockerContainerBackend()
    registry = InFlightExecutionRegistry.get_instance()
    started, release = threading.Event(), threading.Event()
    org_id = f"dual-{uuid.uuid4().hex}"

    class Process:
        returncode = 0
        pid = 12345

        async def communicate(self, input=None):
            return b'{"status":"success","result":42}', b""

        def kill(self):
            pass

        async def wait(self):
            return 0

    def cleanup(*args, **kwargs):
        started.set()
        assert release.wait(5)
        raise RuntimeError("independent: containment unconfirmed")

    request = IsolatedExecutionRequest(
        action_id=f"action-{uuid.uuid4().hex}",
        organization_id=org_id,
        action_type="test.action",
        arguments={},
        profile=IsolationProfile(
            name="TEST",
            network_policy=NetworkPolicy.NONE,
            resources=ResourceLimits(wall_timeout_seconds=5),
        ),
    )
    def acknowledge_inert_create(command, receipt):
        cid = "c" * 64
        receipt.write_text(cid, encoding="utf-8")
        return cid

    with (
        patch.object(backend, "is_available", return_value=True),
        patch("responsibleai.isolation.container_backend.grant_container_read"),
        patch.object(EphemeralWorkspace, "prepare_for_container"),
        patch("asyncio.create_subprocess_exec", return_value=Process()),
        patch.object(backend, "_create_stopped_container", side_effect=acknowledge_inert_create),
        patch.object(backend, "_remove_containers", side_effect=cleanup),
    ):
        task = asyncio.create_task(backend.execute(request))
        try:
            assert await asyncio.to_thread(started.wait, 3)
            assert registry.count_active(org_id) == 1
            task.cancel()
            await asyncio.sleep(0)
            task.cancel()
            await asyncio.sleep(0)
            release.set()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert registry.has_unresolved(org_id)
            assert registry.count_active(org_id) == 0
            assert task.cancelling() == 2
        finally:
            release.set()
            await asyncio.gather(task, return_exceptions=True)
            InFlightExecutionRegistry.reset_instance()
