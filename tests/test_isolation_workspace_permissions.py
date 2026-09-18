# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""WP-V1-AUD-001 / WP-V1-AUD-003: host execution workspaces must not be world-readable.

Universal DAC invariants run on every host. Linux/POSIX ACL and root-chown
behavior is exercised only when this host can actually grant UID 65534 access
without a world-readable fallback. Production still fails closed otherwise.
"""

from __future__ import annotations

import functools
import os
import stat
import subprocess
from pathlib import Path

import pytest

from responsibleai.isolation.errors import IsolationFilesystemPermissionError
from responsibleai.isolation.filesystem import (
    DEFAULT_CONTAINER_GID,
    DEFAULT_CONTAINER_UID,
    EphemeralWorkspace,
    workspace_is_world_accessible,
)


def _other_bits(mode: int) -> int:
    return mode & (stat.S_IROTH | stat.S_IWOTH | stat.S_IXOTH)


@functools.lru_cache(maxsize=1)
def _container_uid_mapping_supported() -> bool:
    """True when prepare_for_container can grant UID 65534 without world-readable modes.

    Capability probe — not a Darwin skip. Hosts with working setfacl or root
    chown return True; others hit the production fail-closed path.
    """
    if os.geteuid() == 0:
        return True
    try:
        with EphemeralWorkspace("probe", "aclcap") as ws:
            ws.populate({"f.txt": "x"})
            ws.prepare_for_container()
        return True
    except IsolationFilesystemPermissionError:
        return False


def _require_container_uid_mapping() -> None:
    if not _container_uid_mapping_supported():
        pytest.skip(
            "POSIX ACL (setfacl) and root chown are unavailable; production "
            "correctly refuses prepare_for_container rather than world-readable "
            "modes. Linux/Docker hosts with setfacl still run this check."
        )


def test_host_workspace_is_0700_and_files_0600() -> None:
    with EphemeralWorkspace("act", "org") as ws:
        ws.populate({"runner.py": "print('ok')\n", "nested/data.txt": "secret-payload\n"})
        assert _other_bits(os.stat(ws.path).st_mode) == 0
        assert stat.S_IMODE(os.stat(ws.path).st_mode) == 0o700
        runner = ws.path / "runner.py"
        nested = ws.path / "nested" / "data.txt"
        assert stat.S_IMODE(os.stat(runner).st_mode) == 0o600
        assert stat.S_IMODE(os.stat(nested).st_mode) == 0o600
        assert not workspace_is_world_accessible(ws.path)


def test_prepare_for_container_preserves_owner_only() -> None:
    _require_container_uid_mapping()
    with EphemeralWorkspace("act", "org") as ws:
        ws.populate({"runner.py": "print('ok')\n", "nested/data.txt": "secret-payload\n"})
        ws.prepare_for_container()
        assert not workspace_is_world_accessible(ws.path)
        assert _other_bits(os.stat(ws.path).st_mode) == 0
        assert _other_bits(os.stat(ws.path / "runner.py").st_mode) == 0
        assert stat.S_IMODE(os.stat(ws.path).st_mode) in {0o700, 0o770}
        assert "0o1777" not in oct(os.stat(ws.path).st_mode)


def test_world_sticky_modes_are_not_applied() -> None:
    source = Path(__file__).resolve().parents[1] / "src" / "responsibleai" / "isolation" / "filesystem.py"
    text = source.read_text()
    assert "0o1777" not in text
    assert "make_world_readable" not in text
    assert "os.chmod(root, 0o1777)" not in text


def test_unrelated_process_cannot_read_owner_only_workspace() -> None:
    """DAC: other-bits stay zero on every host. Foreign-UID probes need mapping."""
    with EphemeralWorkspace("act", "org") as ws:
        secret = "unrelated-must-not-read\n"
        ws.populate({"secret.txt": secret})
        secret_path = ws.path / "secret.txt"
        assert stat.S_IMODE(os.stat(ws.path).st_mode) == 0o700
        assert stat.S_IMODE(os.stat(secret_path).st_mode) == 0o600
        assert _other_bits(os.stat(ws.path).st_mode) == 0
        assert _other_bits(os.stat(secret_path).st_mode) == 0

        if os.geteuid() == 0:
            pid = os.fork()
            if pid == 0:
                try:
                    os.setuid(12345)
                    try:
                        secret_path.read_text()
                    except PermissionError:
                        os._exit(0)
                    os._exit(2)
                except Exception:
                    os._exit(3)
            _, status = os.waitpid(pid, 0)
            assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
            return

        docker = _docker_available()
        if not docker:
            return
        probe = subprocess.run(  # noqa: S603
            [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--user=12345:12345",
                f"-v={ws.path}:/probe:ro",
                "python:3.11-slim",
                "python3",
                "-c",
                "import pathlib; pathlib.Path('/probe/secret.txt').read_text()",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert probe.returncode != 0, probe.stdout + probe.stderr


def test_unrelated_uid_denied_after_container_prepare() -> None:
    _require_container_uid_mapping()
    docker = _docker_available()
    if not docker and os.geteuid() != 0:
        pytest.skip("Docker or root is required to probe an unrelated UID after ACL/chown")
    with EphemeralWorkspace("act", "org") as ws:
        ws.populate({"secret.txt": "unrelated-must-not-read\n"})
        ws.prepare_for_container()
        assert _other_bits(os.stat(ws.path).st_mode) == 0
        if os.geteuid() == 0:
            pid = os.fork()
            if pid == 0:
                try:
                    os.setuid(12345)
                    try:
                        (ws.path / "secret.txt").read_text()
                    except PermissionError:
                        os._exit(0)
                    os._exit(2)
                except Exception:
                    os._exit(3)
            _, status = os.waitpid(pid, 0)
            assert os.WIFEXITED(status) and os.WEXITSTATUS(status) == 0
            return
        probe = subprocess.run(  # noqa: S603
            [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--user=12345:12345",
                f"-v={ws.path}:/probe:ro",
                "python:3.11-slim",
                "python3",
                "-c",
                "import pathlib; pathlib.Path('/probe/secret.txt').read_text()",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert probe.returncode != 0, probe.stdout + probe.stderr


def test_container_uid_can_read_after_prepare() -> None:
    _require_container_uid_mapping()
    docker = _docker_available()
    if not docker:
        pytest.skip("Docker daemon required to prove container UID mapping")
    with EphemeralWorkspace("act", "org") as ws:
        ws.populate({"runner.py": "ok\n"})
        ws.prepare_for_container(uid=DEFAULT_CONTAINER_UID, gid=DEFAULT_CONTAINER_GID)
        probe = subprocess.run(  # noqa: S603
            [
                "docker",
                "run",
                "--rm",
                "--network=none",
                "--user=65534:65534",
                f"-v={ws.path}:/workspace:ro",
                "python:3.11-slim",
                "python3",
                "-c",
                "print(open('/workspace/runner.py').read())",
            ],
            capture_output=True,
            text=True,
            timeout=60,
        )
        assert probe.returncode == 0, probe.stdout + probe.stderr
        assert "ok" in probe.stdout


def _docker_available() -> bool:
    from tests.docker_runtime import docker_available

    return docker_available()


def test_prepare_fails_closed_when_acl_and_root_are_unavailable() -> None:
    if _container_uid_mapping_supported() and os.geteuid() != 0:
        pytest.skip(
            "This host can grant container UID access; fail-closed is covered "
            "by stubbing setfacl and a non-root euid."
        )
    if os.geteuid() == 0:
        pytest.skip("Root host uses chown rather than the fail-closed missing-capability path")
    with EphemeralWorkspace("act", "org") as ws:
        ws.populate({"f.txt": "x"})
        assert stat.S_IMODE(os.stat(ws.path).st_mode) == 0o700
        with pytest.raises(IsolationFilesystemPermissionError, match="without world-readable"):
            ws.prepare_for_container()
        assert not workspace_is_world_accessible(ws.path)
        assert stat.S_IMODE(os.stat(ws.path).st_mode) == 0o700
        assert stat.S_IMODE(os.stat(ws.path / "f.txt").st_mode) == 0o600


def test_prepare_does_not_chmod_world_readable_even_if_acl_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    from responsibleai.isolation import filesystem as fs

    monkeypatch.setattr(fs, "_try_setfacl", lambda *a, **k: False)
    if os.geteuid() == 0:
        with EphemeralWorkspace("act", "org") as ws:
            ws.populate({"f.txt": "x"})
            ws.prepare_for_container()
            assert not workspace_is_world_accessible(ws.path)
        return
    monkeypatch.setattr(os, "geteuid", lambda: 1000)
    with EphemeralWorkspace("act", "org") as ws:
        ws.populate({"f.txt": "x"})
        with pytest.raises(IsolationFilesystemPermissionError, match="without world-readable"):
            ws.prepare_for_container()
        assert not workspace_is_world_accessible(ws.path)
        assert _other_bits(os.stat(ws.path).st_mode) == 0
        assert stat.S_IMODE(os.stat(ws.path / "f.txt").st_mode) == 0o600
