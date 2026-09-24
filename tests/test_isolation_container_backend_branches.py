# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Branch coverage for Docker container backend availability and cleanup."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from responsibleai.isolation.container_backend import DockerContainerBackend
from responsibleai.isolation.errors import IsolationBackendUnavailableError
from responsibleai.isolation.models import IsolatedExecutionRequest


def test_is_available_false_for_missing_relative_executable(tmp_path: Path) -> None:
    missing = tmp_path / "no-docker-here"
    assert DockerContainerBackend(docker_cmd=str(missing)).is_available() is False


def test_is_available_false_when_which_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("shutil.which", lambda _name: None)
    assert DockerContainerBackend(docker_cmd="docker").is_available() is False


def test_is_available_false_on_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    def boom(*_a, **_k):
        raise subprocess.TimeoutExpired(cmd="docker", timeout=1)

    monkeypatch.setattr(subprocess, "run", boom)
    assert DockerContainerBackend(docker_cmd="docker").is_available() is False


def test_is_available_false_on_oserror(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=OSError("nope")))
    assert DockerContainerBackend(docker_cmd="docker").is_available() is False


def test_is_available_false_on_generic_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(subprocess, "run", MagicMock(side_effect=RuntimeError("boom")))
    assert DockerContainerBackend(docker_cmd="docker").is_available() is False


def test_is_available_true_when_docker_info_succeeds(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        MagicMock(return_value=subprocess.CompletedProcess(args=[], returncode=0)),
    )
    assert DockerContainerBackend(docker_cmd="docker").is_available() is True


def test_remove_containers_stable_zero_exits_immediately() -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    with patch.object(subprocess, "run") as run:
        run.return_value = subprocess.CompletedProcess(args=[], returncode=1)
        backend._remove_containers(["c1"], stable_seconds=0, wait_seconds=0.01)


def test_remove_containers_waits_until_gone(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    states = iter([0, 0, 1])  # inspect: exists, exists, gone
    clock = [0.0]

    def fake_run(cmd, **_k):
        if "inspect" in cmd:
            return subprocess.CompletedProcess(args=cmd, returncode=next(states, 1))
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.time.monotonic",
        lambda: clock[0],
    )
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.time.sleep",
        lambda _s: clock.__setitem__(0, clock[0] + 1.0),
    )
    backend._remove_containers(["c1"], stable_seconds=0.5, wait_seconds=5.0)


def test_remove_containers_inspect_exception_treats_as_gone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")

    def fake_run(cmd, **_k):
        if "inspect" in cmd:
            raise OSError("inspect failed")
        return subprocess.CompletedProcess(args=cmd, returncode=0)

    monkeypatch.setattr(subprocess, "run", fake_run)
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.time.monotonic",
        lambda: 100.0,
    )
    backend._remove_containers(["c1"], stable_seconds=0, wait_seconds=0.01)


@pytest.mark.asyncio
async def test_execute_raises_when_backend_unavailable() -> None:
    backend = DockerContainerBackend()
    with patch.object(backend, "is_available", return_value=False):
        req = IsolatedExecutionRequest(
            action_id="act-1",
            organization_id="org-1",
            action_type="python.exec",
            arguments={"code": "print(1)"},
        )
        with pytest.raises(IsolationBackendUnavailableError):
            await backend.execute(req)
