# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Release-debt: docker info must not use a shell, Store B must not use /tmp."""

from __future__ import annotations

import os
import stat
import subprocess
from pathlib import Path

import pytest

from responsibleai.data_governance.backup_defense import (
    MissingLifecycleProviderError,
    SqliteDurableLifecycleStateProvider,
)
from responsibleai.isolation.container_backend import DockerContainerBackend


def test_docker_availability_uses_argv_not_shell(monkeypatch: pytest.MonkeyPatch) -> None:
    seen: dict[str, object] = {}

    def fake_run(argv, **kwargs):
        seen["argv"] = list(argv)
        seen["shell"] = kwargs.get("shell")
        seen["timeout"] = kwargs.get("timeout")
        return subprocess.CompletedProcess(argv, 0)

    monkeypatch.setattr(
        "responsibleai.isolation.container_backend.shutil.which", lambda _cmd: "/usr/bin/docker"
    )
    monkeypatch.setattr("responsibleai.isolation.container_backend.subprocess.run", fake_run)
    backend = DockerContainerBackend(docker_cmd="docker")
    assert backend.is_available() is True
    assert seen["argv"] == ["docker", "info"]
    assert seen["shell"] is False
    assert seen["timeout"] == 8


def test_docker_availability_false_when_binary_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("responsibleai.isolation.container_backend.shutil.which", lambda _cmd: None)
    backend = DockerContainerBackend(docker_cmd="docker")
    assert backend.is_available() is False


def test_store_b_refuses_missing_path(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("WHITEPACT_STORE_B_PATH", raising=False)
    monkeypatch.delenv("WHITEPACT_LIFECYCLE_STORE_PATH", raising=False)
    with pytest.raises(MissingLifecycleProviderError, match="no shared /tmp fallback"):
        SqliteDurableLifecycleStateProvider()


def test_store_b_refuses_well_known_tmp_filename(tmp_path: Path) -> None:
    with pytest.raises(MissingLifecycleProviderError, match="well-known"):
        SqliteDurableLifecycleStateProvider(tmp_path / "whitepact_store_b_lifecycle.db")


def test_store_b_creates_0600_file_and_rejects_symlink(tmp_path: Path) -> None:
    db_path = tmp_path / "lifecycle.db"
    provider = SqliteDurableLifecycleStateProvider(db_path)
    mode = stat.S_IMODE(db_path.stat().st_mode)
    assert mode == 0o600
    assert provider.path == db_path

    link = tmp_path / "linked.db"
    os.symlink(db_path, link)
    with pytest.raises(MissingLifecycleProviderError, match="symlink"):
        SqliteDurableLifecycleStateProvider(link)
