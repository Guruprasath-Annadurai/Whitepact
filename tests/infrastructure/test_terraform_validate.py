# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "infrastructure" / "validate-terraform.sh"


@pytest.mark.skipif(shutil.which("terraform") is None, reason="terraform CLI not installed")
def test_terraform_examples_validate() -> None:
    result = subprocess.run([str(SCRIPT)], cwd=REPO, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr + result.stdout
