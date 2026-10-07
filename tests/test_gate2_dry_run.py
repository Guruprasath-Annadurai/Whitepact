# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Gate 2 dry-run tests. They do not call cloud APIs."""

from __future__ import annotations

import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_gate2_contract_verifier() -> None:
    script = ROOT / "scripts" / "cloud" / "gate2" / "verify_dry_run.py"
    result = subprocess.run(["python3", str(script)], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "GATE2_DRY_RUN=PASS" in result.stdout
    assert "CLOUDFLARE_MUTATION=NO" in result.stdout


def test_gate2_backup_restore_round_trip() -> None:
    script = ROOT / "scripts" / "cloud" / "gate2" / "backup_restore_dry_run.sh"
    result = subprocess.run(["bash", str(script)], check=False, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "GATE2_BACKUP=PASS" in result.stdout
    assert "R2_UPLOAD=NO" in result.stdout


def test_gate2_backup_refuses_upload_flag() -> None:
    script = ROOT / "scripts" / "cloud" / "gate2" / "backup_restore_dry_run.sh"
    result = subprocess.run(
        ["bash", str(script), "--upload"], check=False, capture_output=True, text=True
    )
    assert result.returncode != 0
