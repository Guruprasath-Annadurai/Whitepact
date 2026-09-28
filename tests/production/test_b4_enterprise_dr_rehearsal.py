# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

"""B4 enterprise DR — optional heavyweight rehearsal (not in default CI budget)."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[2]
SCRIPT = REPO / "scripts" / "cell_b" / "b4_enterprise_dr_rehearsal.py"
OUT = REPO / "artifacts" / "production" / "b4-enterprise-dr-rehearsal.json"


@pytest.mark.skipif(
    os.environ.get("CELL_B_ENTERPRISE_DR") != "1",
    reason="Set CELL_B_ENTERPRISE_DR=1 to run 100k-row DR rehearsal",
)
def test_enterprise_dr_rehearsal_artifact() -> None:
    pytest.importorskip("asyncpg")
    result = subprocess.run(
        [sys.executable, str(SCRIPT), "--output", str(OUT)],
        cwd=REPO,
        capture_output=True,
        text=True,
        timeout=900,
    )
    assert result.returncode == 0, result.stderr + result.stdout
    data = json.loads(OUT.read_text(encoding="utf-8"))
    assert data["dataset_counts_after_seed"]["total_rows"] >= 100_000
    assert data["verification"]["audit_chain"]["intact"] is True
    assert data.get("security_state_passed") is True
    sec = REPO / "artifacts" / "production" / "b4-enterprise-dr-security-state.json"
    assert sec.is_file()
    sec_data = json.loads(sec.read_text(encoding="utf-8"))
    assert sec_data["post_restore_verification"]["passed"] is True
