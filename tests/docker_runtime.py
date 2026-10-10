# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Probe whether a real Docker daemon can run isolation tests."""

from __future__ import annotations

import os
import shutil
import sys

import pytest

from tests.linux_security import QUALIFICATION_SKIP_PREFIX, require_linux_tools

REQUIRE_DOCKER_ENV = "WHITEPACT_REQUIRE_DOCKER_ISOLATION"


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


def require_container_isolation_host() -> None:
    """Gate for tests that need a real, kernel-enforced container boundary.

    Non-Linux hosts record a QUALIFICATION_SKIP: Docker Desktop reaches the host
    through a VM file-sharing layer that does not enforce host owner/mode bits on
    bind mounts, and the host cannot grant UID 65534 via POSIX ACLs, so neither
    the workspace-mapping control nor the foreign-UID probe can be proven there.
    A skip is not a pass. Nothing here mocks the control.

    On Linux the container UID mapping tools must exist (fail, never skip). When
    ``WHITEPACT_REQUIRE_DOCKER_ISOLATION=1`` (designated Linux security CI) a
    missing Docker daemon also fails the job instead of skipping.
    """
    if sys.platform != "linux":
        pytest.skip(
            f"{QUALIFICATION_SKIP_PREFIX} platform={sys.platform} "
            "purpose=real container isolation (kernel DAC on bind mounts and "
            "container UID 65534 workspace mapping). This host cannot execute the "
            "Linux isolation control. The skip is not a pass and must appear in the "
            "qualification record."
        )
    if not docker_available():
        if os.environ.get(REQUIRE_DOCKER_ENV) == "1":
            pytest.fail(
                f"{REQUIRE_DOCKER_ENV}=1 but no Docker daemon is reachable. "
                "Real container isolation was not verified."
            )
        pytest.skip(DOCKER_UNAVAILABLE_REASON)
    if os.geteuid() != 0:
        require_linux_tools(
            "setfacl", purpose="POSIX ACL grant of the execution workspace to container UID 65534"
        )
