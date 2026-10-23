# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Immutable historical source, explicitly superseded by current-contract tests.

CTO test-evolution approval preserves the old missing-publication assumption as
evidence, not as an active assertion that correct onboarding must stay broken.
Replacement: test_stage3_sdk_recovery.py (real positive and six negative cases).
"""

import hashlib
import subprocess
from pathlib import Path

import pytest

ORIGINAL_COMMIT = "4293e930aa6d844f0f532cdf4e3ea8c9ae9d8ebd"
ORIGINAL_BLOB = "6c917ae76331ad12c143ffa26ad792d2dbd6cff8"
ORIGINAL_PATH = "tests/test_operator_recovery_sdk.py"
ARCHIVE = (
    Path(__file__).parent / "historical_evidence/operator_recovery_sdk_missing_publication.py.txt"
)


def _verify_original(content, expected=ORIGINAL_BLOB):
    digest = hashlib.sha1(b"blob " + str(len(content)).encode() + b"\0" + content).hexdigest()
    if digest != expected:
        raise ValueError("Historical SDK reproducer content changed")


def test_archived_original_matches_pinned_git_source_byte_for_byte():
    original = subprocess.run(
        ["git", "show", f"{ORIGINAL_COMMIT}:{ORIGINAL_PATH}"],
        cwd=Path(__file__).resolve().parents[1],
        check=True,
        capture_output=True,
    ).stdout
    _verify_original(original)
    archived = ARCHIVE.read_bytes()
    _verify_original(archived)
    assert archived == original


def test_original_positive_reproducer_archive_preserves_exact_blob():
    # This independently recorded reproducer was retained as a Git blob and
    # managed evidence artifact, not misrepresented as a committed test file.
    archive = ARCHIVE.with_name("operator_recovery_sdk_missing_lifecycle_positive.py.txt")
    expected = "727d78afceb6bbe4c34e17c9f99342db1e550177"
    _verify_original(archive.read_bytes(), expected)
    with pytest.raises(ValueError, match="content changed"):
        _verify_original(archive.read_bytes() + b"\nassert True\n", expected)


@pytest.mark.parametrize("tamper", [b"\nassert True\n", b"\n# timeout changed\n", b"\n# noqa\n"])
def test_original_provenance_rejects_any_unapproved_content(tamper):
    with pytest.raises(ValueError, match="content changed"):
        _verify_original(ARCHIVE.read_bytes() + tamper)
