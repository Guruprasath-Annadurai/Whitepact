# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Two approved fixture seams cannot authorize changes to historical assertions."""

from pathlib import Path

import pytest
from scripts.engineering import m13_approved_formatting as evidence

ROOT = Path(__file__).resolve().parents[1]


def sources():
    path = evidence.STAGE3_ROOT_FIXTURE_PATH
    old = evidence.historical_blob(ROOT, evidence.APPROVED[path][0])
    formatted = evidence.historical_blob(ROOT, evidence.APPROVED[path][1])
    final = evidence.historical_blob(ROOT, evidence.STAGE3_ROOT_FIXTURE_BLOB)
    return path, old, formatted, final


def test_root_fixture_chain_preserves_independent_formatting_approval():
    path, old, formatted, final = sources()
    assert evidence.APPROVED[path] == (
        "81e838c9ce2f9f1510b0e8076a4b9d6764e44dba",
        "a2238c4269ab81b2d26c04384f34acde04a56ac2",
    )
    evidence.verify_pair(path, old, formatted, evidence.APPROVED[path])
    evidence.verify_stage3_root_fixtures(ROOT, old, final)
    with pytest.raises(evidence.FormattingEvidenceError):
        evidence.verify_pair(path, old, final, evidence.APPROVED[path])
    assert len(evidence.verify_repository(ROOT)) == 14


@pytest.mark.parametrize("suffix", [b"\n", b"\nassert False\n", b"\n# noqa\n", b"\ntimeout=100\n"])
def test_root_fixture_unknown_content_is_rejected(suffix):
    _, old, _, final = sources()
    with pytest.raises(evidence.FormattingEvidenceError, match="Unknown Stage 3"):
        evidence.verify_stage3_root_fixtures(ROOT, old, final + suffix)


def test_root_fixture_missing_or_wrong_original_evidence_is_rejected():
    _, old, _, final = sources()
    with pytest.raises(evidence.FormattingEvidenceError):
        evidence.verify_stage3_root_fixtures(ROOT, old + b"\n", final)
    with pytest.raises(evidence.FormattingEvidenceError, match="Missing"):
        evidence.verify_stage3_root_fixtures(ROOT / "absent", old, final)
