# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression tests for DockerContainerBackend lifecycle cleanup invariants.

Proves that every container created by WhitePact isolation is removed on all
exit paths: success, failure, timeout (including TOCTOU race), asyncio
cancellation, and concurrent batch.  Tests verify docker ps -aq (ALL states:
Created, Exited, Running) — docker ps -q alone misses Created/Exited containers
that still occupy the name and cause collision on the next run.
"""

from __future__ import annotations

import asyncio
import subprocess
import uuid

import pytest

from tests.docker_runtime import DOCKER_UNAVAILABLE_REASON, docker_available

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.models import (
    DEFAULT_STRICT_PROFILE,
    IsolatedExecutionRequest,
    IsolationProfile,
    ResourceLimits,
)

pytestmark = pytest.mark.skipif(not docker_available(), reason=DOCKER_UNAVAILABLE_REASON)


def _container_name(org_id: str, action_id: str) -> str:
    return f"wp_iso_{org_id}_{action_id}"[:63]


def _container_exists(name: str) -> bool:
    """Return True if any Docker container starting with this prefix exists (any state)."""
    result = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"name=^{name}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    return result.stdout.strip() != ""


def _clear_container(name: str) -> None:
    """Best-effort pre-test cleanup to ensure a clean baseline."""
    res = subprocess.run(
        ["docker", "ps", "-aq", "--filter", f"name=^{name}"],
        capture_output=True,
        text=True,
        timeout=10,
    )
    for cid in res.stdout.strip().split():
        subprocess.run(
            ["docker", "rm", "-f", cid],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=10,
        )


def _make_req(
    action_id: str,
    org_id: str,
    script: str,
    profile: IsolationProfile | None = None,
) -> IsolatedExecutionRequest:
    return IsolatedExecutionRequest(
        action_id=action_id,
        organization_id=org_id,
        action_type="lifecycle_test",
        arguments={},
        profile=profile or DEFAULT_STRICT_PROFILE,
        workspace_files={"runner.py": script},
    )


SUCCESS_SCRIPT = """
import sys, json
sys.stdout.write(json.dumps({"status": "success", "result": "ok"}))
"""

ERROR_SCRIPT = """
import sys
sys.exit(42)
"""

LONG_SLEEP_SCRIPT = """
import time
time.sleep(30)
"""


@pytest.mark.asyncio
class TestSuccessPathCleanup:
    """Container must be removed after clean execution."""

    async def test_no_stale_container_after_success(self) -> None:
        backend = DockerContainerBackend()
        action_id = f"lc-success-{uuid.uuid4().hex[:8]}"
        org_id = "org-lifecycle"
        name = _container_name(org_id, action_id)
        _clear_container(name)

        outcome = await backend.execute(_make_req(action_id, org_id, SUCCESS_SCRIPT))
        assert outcome.is_success

        assert not _container_exists(name), (
            f"Container {name!r} left in docker registry after successful execution"
        )

    async def test_no_stale_container_after_error_exit(self) -> None:
        backend = DockerContainerBackend()
        action_id = f"lc-error-{uuid.uuid4().hex[:8]}"
        org_id = "org-lifecycle"
        name = _container_name(org_id, action_id)
        _clear_container(name)

        outcome = await backend.execute(_make_req(action_id, org_id, ERROR_SCRIPT))
        assert not outcome.is_success
        assert outcome.exit_code == 42

        assert not _container_exists(name), (
            f"Container {name!r} left in docker registry after error exit"
        )


@pytest.mark.asyncio
class TestTimeoutPathCleanup:
    """Container must be removed after wall-clock timeout, including the TOCTOU
    race where timeout fires before the daemon finishes registering the container
    (leaving it in Created state on the vulnerable base)."""

    async def test_no_stale_container_after_normal_timeout(self) -> None:
        backend = DockerContainerBackend()
        action_id = f"lc-timeout-{uuid.uuid4().hex[:8]}"
        org_id = "org-lifecycle"
        name = _container_name(org_id, action_id)
        _clear_container(name)

        profile = IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.5))
        outcome = await backend.execute(_make_req(action_id, org_id, LONG_SLEEP_SCRIPT, profile))
        assert outcome.timed_out

        await asyncio.sleep(0.3)
        assert not _container_exists(name), (
            f"Container {name!r} left in docker registry after timeout"
        )

    async def test_no_stale_container_after_aggressive_timeout(self) -> None:
        """Aggressive timeout fires before daemon can fully register the container.

        Vulnerable base: docker rm -f in except TimeoutError: gets 'No such
        container' (race), daemon then registers it as Created, --rm never fires.
        Fixed base: finally block re-runs docker rm -f synchronously after the
        daemon has had time to register the container and removes it cleanly.
        """
        backend = DockerContainerBackend()
        action_id = f"lc-aggtimeout-{uuid.uuid4().hex[:8]}"
        org_id = "org-lifecycle"
        name = _container_name(org_id, action_id)
        _clear_container(name)

        profile = IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.05))
        await backend.execute(_make_req(action_id, org_id, LONG_SLEEP_SCRIPT, profile))

        # Allow up to 1 s for daemon to register container, then assert cleanup
        await asyncio.sleep(1.0)
        assert not _container_exists(name), (
            f"Container {name!r} stranded in Created state after aggressive timeout. "
            "Root cause: docker rm -f called before daemon registered container; "
            "finally-block cleanup must cover this TOCTOU race."
        )

    async def test_sequential_same_name_no_collision_after_timeout(self) -> None:
        """Second execution with same action_id must succeed after first times out."""
        backend = DockerContainerBackend()
        action_id = f"lc-seqname-{uuid.uuid4().hex[:8]}"
        org_id = "org-lifecycle"
        name = _container_name(org_id, action_id)
        _clear_container(name)

        profile = IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.05))
        await backend.execute(_make_req(action_id, org_id, LONG_SLEEP_SCRIPT, profile))

        await asyncio.sleep(1.0)

        outcome2 = await backend.execute(_make_req(action_id, org_id, SUCCESS_SCRIPT))
        assert outcome2.is_success, (
            f"Second sequential run with action_id={action_id!r} failed — "
            f"likely name collision with stale container. "
            f"exit={outcome2.exit_code}, stderr={outcome2.stderr!r}"
        )


@pytest.mark.asyncio
class TestCancellationPathCleanup:
    """asyncio.CancelledError must not leave orphaned containers.

    The except TimeoutError: cleanup block is bypassed on CancelledError.
    Only a finally: block guarantees cleanup on this path.
    This is the primary regression path that goes RED on the vulnerable base.
    """

    async def test_no_stale_container_after_cancellation(self) -> None:
        backend = DockerContainerBackend()
        action_id = f"lc-cancel-{uuid.uuid4().hex[:8]}"
        org_id = "org-lifecycle"
        name = _container_name(org_id, action_id)
        _clear_container(name)

        task = asyncio.create_task(
            backend.execute(_make_req(action_id, org_id, LONG_SLEEP_SCRIPT))
        )
        await asyncio.sleep(0.5)  # Let container start

        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

        await asyncio.sleep(0.3)
        assert not _container_exists(name), (
            f"Container {name!r} left in docker registry after asyncio.CancelledError. "
            "Root cause: except TimeoutError: block is bypassed on cancellation; "
            "a finally: block is required to guarantee cleanup."
        )

    async def test_cancellation_does_not_affect_sibling_containers(self) -> None:
        """Cancelling execution A must not remove execution B's container."""
        backend = DockerContainerBackend()
        batch_id = uuid.uuid4().hex[:8]
        org_id = "org-lifecycle"
        action_a = f"lc-sib-a-{batch_id}"
        action_b = f"lc-sib-b-{batch_id}"
        name_a = _container_name(org_id, action_a)
        name_b = _container_name(org_id, action_b)
        _clear_container(name_a)
        _clear_container(name_b)

        task_a = asyncio.create_task(
            backend.execute(_make_req(action_a, org_id, LONG_SLEEP_SCRIPT))
        )
        task_b = asyncio.create_task(
            backend.execute(_make_req(action_b, org_id, SUCCESS_SCRIPT))
        )

        await asyncio.sleep(0.3)
        task_a.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task_a

        outcome_b = await task_b
        assert outcome_b.is_success, "Cancelling execution A must not affect execution B"
        assert not _container_exists(name_a), "Cancelled container A not cleaned up"
        assert not _container_exists(name_b), "Completed container B not cleaned up"


@pytest.mark.asyncio
class TestConcurrentBatchCleanup:
    """Concurrent mixed-outcome batch must leave zero stale containers.

    Exact reproduction of the original bug: 6 concurrent tasks with 2 aggressive
    timeouts.  docker ps -aq must be empty for all batch containers after gather.
    """

    async def test_concurrent_batch_no_stale_containers(self) -> None:
        backend = DockerContainerBackend()
        batch_id = uuid.uuid4().hex[:8]
        org_id = "org-lifecycle"

        spec = [
            ("s1", SUCCESS_SCRIPT, DEFAULT_STRICT_PROFILE),
            ("t1", LONG_SLEEP_SCRIPT, IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.5))),
            ("s2", SUCCESS_SCRIPT, DEFAULT_STRICT_PROFILE),
            ("e1", ERROR_SCRIPT, DEFAULT_STRICT_PROFILE),
            ("s3", SUCCESS_SCRIPT, DEFAULT_STRICT_PROFILE),
            ("t2", LONG_SLEEP_SCRIPT, IsolationProfile(resources=ResourceLimits(wall_timeout_seconds=0.5))),
        ]

        container_names = []
        tasks = []
        for label, script, profile in spec:
            action_id = f"lc-batch-{batch_id}-{label}"
            name = _container_name(org_id, action_id)
            _clear_container(name)
            container_names.append(name)
            tasks.append(backend.execute(_make_req(action_id, org_id, script, profile)))

        await asyncio.gather(*tasks)

        await asyncio.sleep(1.0)  # allow daemon to register any Created containers

        stale = [n for n in container_names if _container_exists(n)]
        assert stale == [], (
            f"Stale containers after concurrent batch: {stale}. "
            "Containers in Created/Exited state block same-name re-runs. "
            "docker ps -q alone would not catch these — always use docker ps -aq."
        )
