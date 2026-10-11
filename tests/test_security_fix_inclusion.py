# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The release candidate fails qualification when a mandatory control is absent."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_mandatory_security_controls_are_in_the_tree() -> None:
    script = Path(__file__).resolve().parents[1] / "scripts" / "check_security_fix_inclusion.py"
    completed = subprocess.run(
        [sys.executable, str(script)],
        check=False,
        capture_output=True,
        text=True,
    )
    report = json.loads(completed.stdout)
    assert completed.returncode == 0, report
    assert report["passed"] is True
