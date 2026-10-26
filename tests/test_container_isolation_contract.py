# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline container contract. This does not start a live staging host."""

from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = (ROOT / "Dockerfile").read_text(encoding="utf-8")


def _runtime_stage() -> str:
    marker = "FROM python:3.12-slim@"
    first = DOCKERFILE.index(marker)
    start = DOCKERFILE.index(marker, first + len(marker))
    return DOCKERFILE[start:]


def test_runtime_image_is_digest_pinned_and_non_root() -> None:
    runtime = _runtime_stage()
    assert "python:3.12-slim@sha256:" in runtime
    assert "USER appuser" in runtime
    assert "USER root" not in runtime
    assert "--privileged" not in runtime
    assert "HEALTHCHECK" in runtime


def test_runtime_process_does_not_start_as_a_shell_login() -> None:
    runtime = _runtime_stage()
    user_at = runtime.index("USER appuser")
    cmd_at = runtime.index("CMD [")
    assert user_at < cmd_at
    assert "uvicorn responsibleai.dashboard.app:app" in runtime


def test_dockerfile_has_no_docker_socket_mount() -> None:
    assert "/var/run/docker.sock" not in DOCKERFILE
    assert "docker.sock" not in DOCKERFILE
