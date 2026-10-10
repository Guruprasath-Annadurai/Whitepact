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
from tests.linux_security import require_linux_tools


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


def _stub_acl_grant_for_runner_selection(monkeypatch: pytest.MonkeyPatch) -> None:
    """Let portable runner-selection tests proceed without a Linux ACL.

    Returning True from ``_try_setfacl`` does not verify POSIX ACL
    enforcement. ``test_linux_workspace_acl_grants_container_uid`` and
    ``tests/test_isolation_workspace_permissions.py`` exercise the real
    control and do not use this stub.
    """
    from responsibleai.isolation import filesystem as filesystem_module

    monkeypatch.setattr(filesystem_module, "_try_setfacl", lambda *_args, **_kwargs: True)
    # The trusted-runner grant is stubbed on the same terms: these tests select the runner,
    # they do not verify the grant. test_trusted_runner_is_readable_only_by_the_container_uid_
    # and_never_writable and the real-container tests exercise it.
    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.grant_container_read",
        lambda *_args, **_kwargs: None,
    )


@pytest.mark.asyncio
async def test_direct_backend_mounts_trusted_runner(monkeypatch: pytest.MonkeyPatch) -> None:
    _stub_acl_grant_for_runner_selection(monkeypatch)
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


def test_linux_workspace_acl_grants_container_uid() -> None:
    """Real setfacl grant. This test does not stub host ACL operations."""
    import os
    import stat
    import subprocess

    from responsibleai.isolation.filesystem import (
        EphemeralWorkspace,
        workspace_is_world_accessible,
    )

    require_linux_tools(
        "setfacl",
        "getfacl",
        purpose="POSIX ACL grant for container UID 65534",
    )
    with EphemeralWorkspace("act", "org") as workspace:
        workspace.populate({"notes.txt": "secret"})
        workspace.prepare_for_container(uid=65534, gid=65534)
        assert not workspace_is_world_accessible(workspace.path)
        assert stat.S_IMODE(os.stat(workspace.path).st_mode) & 0o007 == 0
        listed = subprocess.run(
            ["getfacl", "-n", "-p", str(workspace.path / "notes.txt")],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
        )
        assert listed.returncode == 0, listed.stderr
        assert "user:65534:r" in listed.stdout
        assert "other::---" in listed.stdout or "other::" in listed.stdout


def test_trusted_runner_is_readable_only_by_the_container_uid_and_never_writable() -> None:
    """Regression: a bare 0o400 runner was unreadable to the container UID on Linux.

    The container runs as UID 65534 and a bind-mounted file keeps its host owner and mode on
    Linux, so every isolated run died with EACCES (PR #179 CI). The fix must not make the
    file world-readable (CodeQL py/overly-permissive-file): it grants UID 65534 alone, by
    ACL or by chown as root, and fails closed where neither is possible. macOS Docker
    Desktop ignores host permissions, so only this mode-level check catches a regression on
    a laptop; the real-container tests prove it end to end on Linux.
    """
    import os
    import shutil
    import stat
    import subprocess

    from responsibleai.isolation.errors import IsolationFilesystemPermissionError
    from tests.docker_runtime import host_can_map_container_uid

    backend = DockerContainerBackend()
    if not host_can_map_container_uid():
        with pytest.raises(IsolationFilesystemPermissionError, match="world-readable"):
            backend._install_trusted_runner("print('trusted')\n")
        return

    runner = backend._install_trusted_runner("print('trusted')\n")
    try:
        info = os.stat(runner)
        mode = stat.S_IMODE(info.st_mode)
        assert not mode & stat.S_IROTH, f"runner must not be world-readable: {mode:o}"
        assert mode & 0o222 == 0, f"runner must not be writable by anyone: {mode:o}"
        assert stat.S_IMODE(os.stat(runner.parent).st_mode) == 0o700
        if info.st_uid != 65534:  # not chowned, so an ACL must name the container UID
            acl = subprocess.run(  # noqa: S603
                ["getfacl", "-p", str(runner)], capture_output=True, text=True, check=True
            ).stdout
            assert "user:65534:r" in acl, acl
    finally:
        shutil.rmtree(runner.parent, ignore_errors=True)
