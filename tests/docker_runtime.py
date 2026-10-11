# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Probe whether a real Docker daemon can run isolation tests."""

from __future__ import annotations

import os
import shutil


def docker_available() -> bool:
    if not shutil.which("docker"):
        return False
    return os.system("docker info >/dev/null 2>&1") == 0


def enable_containment_probe(monkeypatch: object) -> None:
    """Let isolation tests supply a probe entrypoint on the backend instance.

    Production ``execute`` ignores caller ``runner.py`` unless this instance
    flag is set. The flag is not read from the request.
    """
    from responsibleai.isolation.container_backend import DockerContainerBackend

    original = DockerContainerBackend.__init__

    def _init(self, *args, **kwargs):
        original(self, *args, **kwargs)
        self._containment_probe_enabled = True

    monkeypatch.setattr(DockerContainerBackend, "__init__", _init)  # type: ignore[attr-defined]


DOCKER_UNAVAILABLE_REASON = (
    "EXTERNAL VERIFICATION REQUIRED: Docker daemon is unavailable in this "
    "environment. Run scripts/ci-docker-isolation.sh on a privileged CI runner."
)
