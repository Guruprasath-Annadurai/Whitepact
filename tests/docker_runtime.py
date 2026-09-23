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


DOCKER_UNAVAILABLE_REASON = (
    "EXTERNAL VERIFICATION REQUIRED: Docker daemon is unavailable in this "
    "environment. Run scripts/ci-docker-isolation.sh on a privileged CI runner."
)
