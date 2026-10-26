# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exercise real pytest collection/runtime skip receipts in isolated subprocesses."""

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest


@pytest.mark.parametrize("phase", ["collection", "runtime"])
def test_qualification_receipt_records_every_skip(phase, tmp_path):
    probe = tmp_path / "test_probe.py"
    marker = "APEX deliberate skip receipt probe"
    source = (
        f"import pytest\npytest.skip({marker!r}, allow_module_level=True)\n"
        if phase == "collection"
        else f"import pytest\ndef test_skip():\n    pytest.skip({marker!r})\n"
    )
    probe.write_text(source)
    receipt = tmp_path / "skips.json"
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            "-p",
            "tests.conftest",
            "-o",
            "addopts=",
            "-q",
            str(probe),
        ],
        cwd=tmp_path,
        env={
            **os.environ,
            "PYTHONPATH": os.pathsep.join([str(root / "src"), str(root)]),
            "WHITEPACT_QUALIFICATION_SKIP_LOG": str(receipt),
        },
        capture_output=True,
        text=True,
        timeout=45,
        check=False,
    )
    assert result.returncode in {0, 5}, result.stdout + result.stderr
    payload = json.loads(receipt.read_text())
    assert payload["skip_count"] == 1
    assert len(payload["skips"]) == 1
    assert marker in payload["skips"][0]["reason"]
