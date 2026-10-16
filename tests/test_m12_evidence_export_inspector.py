# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Offline consumer cannot turn a bounded UI export into authorization proof."""

import json
import subprocess
import sys
from pathlib import Path

import pytest
from scripts.evidence.inspect_loaded_export import ExportError, inspect_export, load_export


def export(records):
    return {
        "format": "whitepact-bounded-evidence-v1",
        "scope": "untrusted descriptive text",
        "records": records,
    }


def test_unknown_and_matching_hash_references_never_establish_proof():
    out = inspect_export(
        export(
            [
                {
                    "evidence_id": "one",
                    "hash": "a" * 64,
                    "prev_hash": "b" * 64,
                    "decision": "ALLOW",
                    "outcome_status": "UNKNOWN",
                    "target": "secret-canary",
                },
                {
                    "evidence_id": "two",
                    "hash": "b" * 64,
                    "decision": "DENY",
                    "outcome_status": "NOT_ATTEMPTED",
                },
            ]
        )
    )
    assert out["unknown_outcomes"] == 1
    assert out["references_to_loaded_hashes"] == 1
    assert out["authority_proven"] is False
    assert out["external_effect_proven"] is False
    assert out["cryptographic_verification"] == "NOT_POSSIBLE_FROM_BOUNDED_EXPORT"
    assert "secret-canary" not in json.dumps(out)


@pytest.mark.parametrize(
    "records",
    [
        [{"evidence_id": "a", "raw_credentials": "secret"}],
        [{"evidence_id": "a", "decision": {"ALLOW": True}}],
        [{"evidence_id": "a"}, {"evidence_id": "a"}],
        [{"evidence_id": "a", "hash": "fabricated"}],
        [{"evidence_id": "a", "hash": "a" * 64}, {"evidence_id": "b", "hash": "a" * 64}],
        [{}],
        [{"evidence_id": "a", "risk_tier": float("inf")}],
        [{"evidence_id": "a"}] * 201,
    ],
)
def test_malformed_or_inappropriate_material_is_rejected(records):
    with pytest.raises(ExportError):
        inspect_export(export(records))


def test_partial_window_missing_status_and_unknown_decision_are_not_empty_success():
    out = inspect_export(
        export([{"evidence_id": "a", "decision": "secret-value", "prev_hash": "a" * 64}])
    )
    assert out["outcomes"] == {"UNRECOGNIZED_OR_MISSING": 1}
    assert out["decisions"] == {"UNRECOGNIZED_OR_MISSING": 1}
    assert out["references_to_loaded_hashes"] == 0
    assert "secret-value" not in str(out)


def test_duplicate_json_and_nonfinite_numbers_are_rejected(tmp_path):
    for raw in ('{"format":"a","format":"b"}', '{"number":NaN}'):
        file = tmp_path / "export.json"
        file.write_text(raw)
        with pytest.raises(ExportError):
            load_export(file)


def test_cli_outputs_only_safe_counts_and_fixed_failure(tmp_path):
    script = Path(__file__).parents[1] / "scripts/evidence/inspect_loaded_export.py"
    file = tmp_path / "private-export.json"
    file.write_text(
        json.dumps(
            export([{"evidence_id": "a", "decision": "QUARANTINE", "outcome_status": "UNKNOWN"}])
        )
    )
    result = subprocess.run(
        [sys.executable, str(script), str(file)], capture_output=True, text=True
    )
    assert result.returncode == 0
    assert json.loads(result.stdout)["unknown_outcomes"] == 1
    file.write_text("private-secret-canary invalid JSON")
    result = subprocess.run(
        [sys.executable, str(script), str(file)], capture_output=True, text=True
    )
    assert result.returncode == 2
    assert "private-secret-canary" not in result.stdout + result.stderr
    assert str(file) not in result.stdout + result.stderr
