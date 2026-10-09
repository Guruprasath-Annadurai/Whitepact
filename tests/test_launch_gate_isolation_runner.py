# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""The container runner must not report success when the runtime is missing."""

from __future__ import annotations

import json
import os
import subprocess
import sys

from responsibleai.isolation.container_backend import CONTAINER_RUNNER_SOURCE


def test_container_runner_fails_closed_when_runtime_is_missing(tmp_path) -> None:
    assert '"isolated": True' not in CONTAINER_RUNNER_SOURCE
    stub = tmp_path / "stub"
    package = stub / "responsibleai" / "mcp"
    package.mkdir(parents=True)
    (stub / "responsibleai" / "__init__.py").write_text("", encoding="utf-8")
    (package / "__init__.py").write_text("", encoding="utf-8")
    (package / "tools.py").write_text(
        "raise ImportError('responsibleai runtime is not installed in this image')\n",
        encoding="utf-8",
    )
    script = tmp_path / "runner.py"
    script.write_text(CONTAINER_RUNNER_SOURCE, encoding="utf-8")
    env = os.environ.copy()
    env["PYTHONPATH"] = str(stub)
    env["PYTHONSAFEPATH"] = "1"
    completed = subprocess.run(
        [sys.executable, str(script)],
        input=json.dumps({"action_type": "rai_health", "arguments": {}}),
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )
    assert completed.returncode != 0
    payload = json.loads(completed.stdout)
    assert payload["status"] == "error"
    assert "isolated runtime unavailable" in payload["error"]
