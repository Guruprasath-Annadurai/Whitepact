# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Regression tests for the public launch demo and capability surface."""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def test_runtime_authority_demo_holds_execution() -> None:
    result = subprocess.run(
        [sys.executable, str(ROOT / "examples/09_runtime_authority_demo.py")],
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    assert "WhitePact decision: REQUIRE_APPROVAL" in result.stdout
    assert "Execution proceeded: NO" in result.stdout
    assert "APPROVAL_REQUIRED:action_type=payment.execute" in result.stdout
