# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Platform gate for Linux-only security controls.

A non-Linux host records a qualification skip. A Linux host fails when a
required tool is missing. Skipping on Linux is not a pass.
"""

from __future__ import annotations

import shutil
import sys

import pytest

QUALIFICATION_SKIP_PREFIX = "QUALIFICATION_SKIP"


def require_linux_tools(*tools: str, purpose: str) -> None:
    """Run *purpose* on Linux, or skip it with an explicit qualification record.

    The skip is only for hosts whose platform cannot execute the control.
    Linux CI must have the named executables on ``PATH``.
    """
    if sys.platform != "linux":
        pytest.skip(
            f"{QUALIFICATION_SKIP_PREFIX} platform={sys.platform} "
            f"tools={','.join(tools)} purpose={purpose}. "
            "This host cannot execute the Linux security control. "
            "The skip is not a pass and must appear in the qualification record."
        )
    missing = [name for name in tools if shutil.which(name) is None]
    if missing:
        pytest.fail(
            "Linux security CI is missing required tools: " + ", ".join(missing) + f". {purpose}"
        )
