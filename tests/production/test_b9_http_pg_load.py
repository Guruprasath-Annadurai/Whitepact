# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""B9 — HTTP + PostgreSQL load qualification (integration)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "cell_b" / "http_load_qualification.py"
OUT = REPO / "artifacts" / "production" / "b9-http-pg-load.json"


def test_http_pg_load_qualification_generates_evidence() -> None:
    pytest.importorskip("asyncpg")
    # Shorter windows on CI keep real HTTP+PG load evidence without blowing the
    # shared pytest job budget (see .github/workflows/ci.yml).
    on_ci = bool(os.environ.get("GITHUB_ACTIONS"))
    burst_s = "4" if on_ci else "8"
    soak_s = "10" if on_ci else "20"
    result = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--duration",
            burst_s,
            "--soak",
            soak_s,
            "--workers",
            "3",
            "--output",
            str(OUT),
        ],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=280,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    data = json.loads(OUT.read_text(encoding="utf-8"))
    assert data["burst"]["errors"] == 0
    assert data["soak"]["errors"] == 0
    assert data["soak"]["measured_rps"] > 0
