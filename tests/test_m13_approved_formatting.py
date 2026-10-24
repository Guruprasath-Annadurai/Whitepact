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


def schema_sources():
    repo = Path(__file__).resolve().parents[1]
    original = evidence.historical_blob(repo, evidence.APPROVED[evidence.ENGINE_PATH][0])
    formatted = evidence.historical_blob(repo, evidence.APPROVED[evidence.ENGINE_PATH][1])
    final = evidence.historical_blob(repo, evidence.STAGE3_ENGINE_BLOB)
    return repo, original, formatted, final


def test_schema_chain_preserves_independent_formatting_approval():
    repo, original, formatted, final = schema_sources()
    evidence.verify_pair(
        evidence.ENGINE_PATH, original, formatted, evidence.APPROVED[evidence.ENGINE_PATH]
    )
    evidence.verify_stage3_schema(repo, original, final)
    with pytest.raises(evidence.FormattingEvidenceError, match="Unknown"):
        evidence.verify_pair(
            evidence.ENGINE_PATH, original, final, evidence.APPROVED[evidence.ENGINE_PATH]
        )


@pytest.mark.parametrize(
    "old,new",
    [
        (b'Column("deployment_id", String(256)', b'Column("deployment_id", String(255)'),
        (
            b"security_epoch>=1 AND revocation_floor>=1",
            b"security_epoch>=0 AND revocation_floor>=1",
        ),
        (b"tenant_provisioning_outbox = Table(", b"unapproved_outbox = Table("),
        (
            b"runtime_containment_records = Table(",
            b"unexpected = 1\nruntime_containment_records = Table(",
        ),
        (
            b"tenant_provisioning_records = Table(",
            b"# unexpected\ntenant_provisioning_records = Table(",
        ),
        (b"metadata,", b"metadata, "),
    ],
)
def test_schema_chain_rejects_every_unapproved_final_blob(old, new):
    repo, original, _, final = schema_sources()
    assert old in final
    with pytest.raises(evidence.FormattingEvidenceError, match="Unknown Stage 3"):
        evidence.verify_stage3_schema(repo, original, final.replace(old, new, 1))


def test_schema_chain_rejects_deleted_insertion_and_wrong_original():
    repo, original, formatted, final = schema_sources()
    with pytest.raises(evidence.FormattingEvidenceError):
        evidence.verify_stage3_schema(repo, original, formatted)
    with pytest.raises(evidence.FormattingEvidenceError):
        evidence.verify_stage3_schema(repo, original + b"\n", final)
    with pytest.raises(evidence.FormattingEvidenceError, match="Missing"):
        evidence.verify_stage3_schema(repo / "absent", original, final)
