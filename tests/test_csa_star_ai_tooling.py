# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]


def test_baseline_snapshot_matches_external_audit_totals() -> None:
    snap = json.loads(
        (REPO / "compliance/csa-star-ai/ledger/BASELINE_AUDIT_SNAPSHOT.json").read_text()
    )
    assert snap["totals"]["questions"] == 320
    assert snap["totals"]["yes"] == 98
    assert snap["totals"]["no"] == 152
    assert snap["totals"]["na"] == 70


def test_ingest_exits_when_workbook_missing() -> None:
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts/csa_star_ai/ingest_workbook.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2
