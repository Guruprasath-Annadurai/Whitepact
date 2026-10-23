# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exact approved helper chain, with immutable formatting approval unchanged."""

from pathlib import Path

import pytest
from scripts.engineering import m13_approved_formatting as evidence

ROOT = Path(__file__).resolve().parents[1]


def sources():
    path = evidence.STAGE3_SECURITY_FIXTURE_PATH
    old = evidence.historical_blob(ROOT, evidence.APPROVED[path][0])
    formatted = evidence.historical_blob(ROOT, evidence.APPROVED[path][1])
    final = evidence.historical_blob(ROOT, evidence.STAGE3_SECURITY_FIXTURE_BLOB)
    return path, old, formatted, final


def test_two_independent_chains_are_verified_without_broadening_formatting():
    path, old, formatted, final = sources()
    assert evidence.APPROVED[path] == (
        "ec36400f35e33df8e8790a8bcd9eca3590a0f166",
        "c7f88c32eb00c61c95e499b1e226bc5b526f8ab2",
    )
    evidence.verify_pair(path, old, formatted, evidence.APPROVED[path])
    evidence.verify_stage3_security_fixture(ROOT, old, final)
    with pytest.raises(evidence.FormattingEvidenceError):
        evidence.verify_pair(path, old, final, evidence.APPROVED[path])
    assert len(evidence.verify_repository(ROOT)) == 14


@pytest.mark.parametrize("suffix", [b"\n", b"\nassert False\n", b"\n# noqa\n", b"\ntimeout=100\n"])
def test_unknown_final_bytes_are_refused(suffix):
    _, old, _, final = sources()
    with pytest.raises(evidence.FormattingEvidenceError, match="Unknown Stage 3"):
        evidence.verify_stage3_security_fixture(ROOT, old, final + suffix)


@pytest.mark.parametrize(
    "old_value,new_value",
    [(b'"ACTIVE"', b'"DISABLED"'), (b"return engine, actor, user_id, org_id", b"return None")],
)
def test_modified_fixture_or_security_logic_cannot_be_blessed(old_value, new_value):
    _, old, _, final = sources()
    assert old_value in final
    with pytest.raises(evidence.FormattingEvidenceError):
        evidence.verify_stage3_security_fixture(ROOT, old, final.replace(old_value, new_value, 1))


def test_wrong_original_and_missing_history_are_refused():
    _, old, _, final = sources()
    with pytest.raises(evidence.FormattingEvidenceError):
        evidence.verify_stage3_security_fixture(ROOT, old + b"\n", final)
    with pytest.raises(evidence.FormattingEvidenceError, match="Missing"):
        evidence.verify_stage3_security_fixture(ROOT / "absent", old, final)
