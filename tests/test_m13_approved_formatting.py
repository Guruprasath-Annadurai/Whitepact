# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Formatting approval preserves evidence; unknown edits never become authorized."""

from pathlib import Path

import pytest
from scripts.engineering import m13_approved_formatting as evidence


def test_all_fourteen_exact_relationships_have_recoverable_originals():
    records = evidence.verify_repository(Path(__file__).resolve().parents[1])
    assert len(records) == 14
    assert set(records) == set(evidence.APPROVED)


@pytest.mark.parametrize(
    "after",
    [
        b"# unchanged directive\nimport os\nassert False\n",
        b"# unchanged directive\nimport os\nassert 3 == 4\n",
        b"# changed directive\nimport os\nassert 3 == 3\n",
        b"# unchanged directive\nimport sys\nassert 3 == 3\n",
        b"# unchanged directive\nimport os\nassert 3 == 3\ntimeout = 100\n",
        b"# unchanged directive\nimport os\nassert 3 == 3  # type: ignore\n",
    ],
)
def test_semantic_or_directive_changes_fail_even_with_matching_supplied_hashes(after):
    before = b"# unchanged directive\nimport os\nassert 3 == 3\n"
    expected = (evidence.blob_hash(before), evidence.blob_hash(after))
    with pytest.raises(evidence.FormattingEvidenceError, match="Non-formatting"):
        evidence.verify_pair("negative-test", before, after, expected)


def test_unapproved_even_semantically_equal_content_fails_exact_hash_guard():
    before = b"assert True\n"
    expected = (evidence.blob_hash(before), evidence.blob_hash(before))
    with pytest.raises(evidence.FormattingEvidenceError, match="Unknown"):
        evidence.verify_pair("negative-test", before, before + b"\n", expected)


def test_missing_historical_evidence_is_not_waived(tmp_path):
    with pytest.raises(evidence.FormattingEvidenceError, match="Missing"):
        evidence.verify_repository(tmp_path)


def test_import_order_cannot_change_under_formatting_approval():
    before = b"import os\nimport sys\n"
    after = b"import sys\nimport os\n"
    with pytest.raises(evidence.FormattingEvidenceError, match="Non-formatting"):
        evidence.verify_pair(
            "negative-import-order",
            before,
            after,
            (evidence.blob_hash(before), evidence.blob_hash(after)),
        )
