# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exact CTO-approved identity constraint successor, never a hash waiver."""

from pathlib import Path

import pytest
from scripts.engineering import m13_approved_formatting as guard

ROOT = Path(__file__).resolve().parents[1]
INSERTION = (
    b"    UniqueConstraint(\n"
    b'        "provider",\n'
    b'        "provider_reference_id",\n'
    b'        name="uq_identity_verification_provider_session",\n'
    b"    ),\n"
)


def sources():
    before = guard.historical_blob(ROOT, guard.APPROVED[guard.ENGINE_PATH][0])
    stage3 = guard.historical_blob(ROOT, "22d2580db239dcca1fd60646b0cab7e9042fc130")
    final = guard.historical_blob(ROOT, "9cce74dbcd614facd309557fcc929bb69dcd2f10")
    return before, stage3, final


def test_both_exact_links_and_all_fourteen_original_relationships():
    before, stage3, final = sources()
    assert guard.ORIGINAL_COMMIT == "e4f3f12862712762f0d16d561afbd195067606e3"
    assert guard.APPROVED[guard.ENGINE_PATH] == (
        "be9a6a5d43126468435a924d8f6ea9564ce6676d",
        "35b7abf1ebdd04f57be4d45b6480e795a0b6cf11",
    )
    assert guard.STAGE3_ENGINE_BLOB == "22d2580db239dcca1fd60646b0cab7e9042fc130"
    guard.verify_stage3_schema(ROOT, before, stage3)
    guard.verify_identity_session_schema(ROOT, before, final)
    assert final.replace(INSERTION, b"", 1) == stage3
    verified = guard.verify_repository(ROOT)
    assert len(verified) == 14
    assert verified[guard.ENGINE_PATH]["stage3"] == guard.STAGE3_ENGINE_BLOB
    assert (
        verified[guard.ENGINE_PATH]["identity_session_successor"]
        == guard.IDENTITY_SESSION_ENGINE_BLOB
    )


@pytest.mark.parametrize(
    "fault", ["column", "name", "placement", "extra", "deletion", "comment", "format"]
)
def test_unknown_successor_bytes_are_rejected(fault):
    before, stage3, final = sources()
    candidates = {
        "column": final.replace(INSERTION, INSERTION.replace(b'"provider",', b'"user_id",')),
        "name": final.replace(
            INSERTION,
            INSERTION.replace(
                b"uq_identity_verification_provider_session", b"unapproved_constraint"
            ),
        ),
        "placement": final.replace(INSERTION, b"") + INSERTION,
        "extra": final + b"unapproved_statement = True\n",
        "deletion": final.replace(b'    Column("name", String(200), nullable=False),\n', b"", 1),
        "comment": final + b"# unapproved comment\n",
        "format": final + b"\n",
    }
    assert candidates[fault] != final
    with pytest.raises(guard.FormattingEvidenceError):
        guard.verify_identity_session_schema(ROOT, before, candidates[fault])
    # The old Stage 3 verifier must still reject the semantic successor.
    with pytest.raises(guard.FormattingEvidenceError):
        guard.verify_stage3_schema(ROOT, before, final)


def test_altered_historical_source_and_substituted_hash_fail_closed(monkeypatch):
    before, _, final = sources()
    with pytest.raises(guard.FormattingEvidenceError):
        guard.verify_identity_session_schema(ROOT, before + b"\n", final)
    monkeypatch.setattr(guard, "IDENTITY_SESSION_ENGINE_BLOB", guard.STAGE3_ENGINE_BLOB)
    with pytest.raises(guard.FormattingEvidenceError):
        guard.verify_identity_session_schema(ROOT, before, final)


def test_missing_historical_git_objects_are_not_optional(tmp_path):
    before, _, final = sources()
    with pytest.raises(guard.FormattingEvidenceError, match="Missing immutable"):
        guard.verify_identity_session_schema(tmp_path, before, final)
