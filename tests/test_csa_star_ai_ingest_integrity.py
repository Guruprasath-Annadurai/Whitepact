# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[1]
FIXTURE_SCRIPT = REPO / "tests/fixtures/csa_star_ai/generate_upstream_fixture.py"
FIXTURE_XLSX = REPO / "tests/fixtures/csa_star_ai/TEST_ONLY_AI-CAIQ_v1.1_320rows.xlsx"
SOURCE_UPSTREAM = REPO / "compliance/csa-star-ai/source/CSA_AI-CAIQ_v1.1_Official_upstream.xlsx"


@pytest.fixture(scope="module")
def synthetic_upstream() -> Path:
    subprocess.run([sys.executable, str(FIXTURE_SCRIPT)], cwd=REPO, check=True)
    assert FIXTURE_XLSX.is_file()
    return FIXTURE_XLSX


def test_ingest_parses_320_rows_all_unassessed(synthetic_upstream: Path, tmp_path: Path) -> None:
    from scripts.csa_star_ai.ingest_workbook import ingest
    from scripts.csa_star_ai.ledger import ControlAnswer

    ledger = ingest(synthetic_upstream)
    assert len(ledger.rows) == 320
    assert all(r.response == ControlAnswer.UNASSESSED for r in ledger.rows)


def test_official_upstream_missing_exits_nonzero() -> None:
    if SOURCE_UPSTREAM.is_file():
        pytest.skip("Official upstream present in environment")
    result = subprocess.run(
        [sys.executable, str(REPO / "scripts/csa_star_ai/ingest_workbook.py")],
        cwd=REPO,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 2


def test_source_integrity_documents_manual_acquisition() -> None:
    meta = json.loads(
        (REPO / "compliance/csa-star-ai/source/SOURCE_INTEGRITY.json").read_text(encoding="utf-8")
    )
    assert meta["acquisition_status"] in {"MANUAL_REQUIRED", "ACQUIRED"}
    assert meta["expected_question_count"] == 320
    assert meta["preliminary_external_audit_snapshot"]["authoritative"] is False
