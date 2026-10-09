# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""LG-04: caller workspace files cannot replace the trusted container runner."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

from responsibleai.isolation.broker import IsolationBroker
from responsibleai.isolation.container_backend import (
    CONTAINER_RUNNER_SOURCE,
    DockerContainerBackend,
    is_reserved_runner_path,
)
from responsibleai.isolation.errors import FilesystemEscapeError, IsolationPolicyViolationError
from responsibleai.isolation.filesystem import EphemeralWorkspace
from responsibleai.isolation.models import IsolatedExecutionRequest, IsolationProfile


def test_reserved_runner_paths_are_recognized() -> None:
    assert is_reserved_runner_path("runner.py")
    assert is_reserved_runner_path("./runner.py")
    assert is_reserved_runner_path("nested/../runner.py")
    assert is_reserved_runner_path("/workspace/runner.py")
    assert is_reserved_runner_path("subdir/runner.py")
    assert not is_reserved_runner_path("payload.txt")


def test_workspace_rejects_symlink_and_traversal(tmp_path) -> None:
    with EphemeralWorkspace("act", "org") as workspace:
        outside = tmp_path / "outside"
        outside.mkdir()
        link = workspace.path / "link"
        link.symlink_to(outside)
        with pytest.raises(FilesystemEscapeError):
            workspace.populate({"link/owned.txt": "nope"})
        with pytest.raises(FilesystemEscapeError):
            workspace.populate({"../../etc/passwd": "nope"})
        workspace.populate({"nested/data.txt": "ok"})
        assert (workspace.path / "nested" / "data.txt").read_text(encoding="utf-8") == "ok"


@pytest.mark.asyncio
async def test_direct_backend_rejects_caller_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    monkeypatch.setattr(backend, "is_available", lambda: True)
    launched = AsyncMock()
    monkeypatch.setattr("asyncio.create_subprocess_exec", launched)
    for name in ("runner.py", "./runner.py", "nested/../runner.py", "subdir/runner.py"):
        request = IsolatedExecutionRequest(
            action_id="act",
            organization_id="org",
            action_type="noop",
            arguments={},
            workspace_files={name: "print('pwned')\n"},
        )
        with pytest.raises(IsolationPolicyViolationError):
            await backend.execute(request)
    launched.assert_not_called()


@pytest.mark.asyncio
async def test_direct_backend_mounts_trusted_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    backend = DockerContainerBackend(docker_cmd="docker")
    monkeypatch.setattr(backend, "is_available", lambda: True)
    captured: dict[str, object] = {}

    async def _fake_exec(*cmd, **_kwargs):
        captured["cmd"] = cmd
        mount = next(part for part in cmd if part.startswith("-v=") and "runner.py" in part)
        host_path = mount.split(":", 1)[0][3:]
        captured["source"] = Path(host_path).read_text(encoding="utf-8")

        class _Proc:
            returncode = 0

            async def communicate(self, input=None):
                return (b'{"status":"success","result":{"ok":true}}', b"")

            async def wait(self):
                return 0

            def kill(self):
                pass

        return _Proc()

    monkeypatch.setattr("asyncio.create_subprocess_exec", _fake_exec)
    monkeypatch.setattr(backend, "_remove_containers_uninterruptible", AsyncMock())
    request = IsolatedExecutionRequest(
        action_id="act",
        organization_id="org",
        action_type="noop",
        arguments={},
        workspace_files={"notes.txt": "hello", "nested/other.py": "print(1)\n"},
    )
    outcome = await backend.execute(request)
    assert outcome.result_payload == {"ok": True}
    cmd = captured["cmd"]
    assert isinstance(cmd, tuple)
    assert "/opt/whitepact/runner.py" in cmd
    assert "runner.py" != cmd[-1]
    assert "--network=none" in cmd
    assert captured["source"] == CONTAINER_RUNNER_SOURCE


@pytest.mark.asyncio
async def test_unexpected_workspace_type_is_rejected() -> None:
    backend = DockerContainerBackend(docker_cmd="docker")

    class _BadRequest:
        profile = IsolationProfile()
        workspace_files: object = ["runner.py"]

    with patch.object(backend, "is_available", return_value=True):
        for bad in (["runner.py"], None, "runner.py"):
            request = _BadRequest()
            request.workspace_files = bad
            with pytest.raises(IsolationPolicyViolationError):
                await backend.execute(request)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_broker_does_not_forward_workspace_files() -> None:
    from unittest.mock import MagicMock

    from tests.test_isolation_egress_boundary import _make_action, _make_authorization

    action = _make_action("rai_health", {})
    auth = _make_authorization(action)
    mock_backend = AsyncMock()
    mock_backend.execute.return_value = MagicMock(
        is_success=True,
        exit_code=0,
        result_payload={"ok": True},
        violation=None,
        stderr="",
    )
    broker = IsolationBroker(backend=mock_backend)
    await broker.execute(auth, action)
    request = mock_backend.execute.await_args.args[0]
    assert request.workspace_files == {}
