# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Exact inventory preservation and fail-closed qualification metadata validation."""

from __future__ import annotations

import copy
import csv
import io
import json
from pathlib import Path

import pytest
from scripts.qualification.feature_registry import (
    RegistryError,
    generate,
    validate,
    write_generated,
)

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def registry():
    return json.loads((ROOT / "docs/m12/feature-registry.json").read_text())


def test_complete_original_inventory_and_deterministic_generation(registry):
    rows = validate(registry, ROOT)
    assert [row["id"] for row in rows] == list(range(1, 176))
    assert rows[82]["title"] == "Legitimate customer root/consent setup"
    assert rows[129]["title"] == "Production root authority provisioning"
    assert generate(registry, ROOT) == generate(copy.deepcopy(registry), ROOT)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing",
        "duplicate",
        "title",
        "both_titles",
        "status",
        "path",
        "absolute",
        "not_file",
        "qualification",
    ],
)
def test_rejects_invalid_or_fabricated_registry(registry, mutation):
    row = registry["entries"][0]
    if mutation == "missing":
        registry["entries"].pop()
    elif mutation == "duplicate":
        registry["entries"][-1]["id"] = 1
    elif mutation == "title":
        row["title"] = "Invented feature"
    elif mutation == "both_titles":
        row["title"] = registry["original_inventory"][0]["title"] = "Invented feature"
    elif mutation == "status":
        row["status"] = "PRODUCTION READY"
    elif mutation == "path":
        row["source_paths"] = ["../outside.py"]
    elif mutation == "absolute":
        row["source_paths"] = ["/etc/passwd"]
    elif mutation == "not_file":
        row["source_paths"] = ["missing-source.py"]
    else:
        row["status"] = "VERIFIED"
        row["qualification"] = {"kind": "SOURCE_INSPECTION", "passed": 175}
    with pytest.raises(RegistryError):
        validate(registry, ROOT)


def test_no_qualification_by_relabeling_prior_tests(registry):
    row = registry["entries"][0]
    row["status"] = "VERIFIED"
    row["qualification"] = {
        "kind": "FRESH_EXECUTED",
        "head": "a" * 40,
        "tree": "b" * 40,
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "executed_at": "2026-10-15T12:00:00+00:00",
        "command": "pytest",
        "scope": "old scope",
        "artifact": "pyproject.toml",
    }
    with pytest.raises(RegistryError, match="qualification target"):
        validate(registry, ROOT)


def test_known_overlaps_are_kept_not_deduplicated(registry):
    rows = {row["id"]: row for row in validate(registry, ROOT)}
    for first, second in ((83, 130), (129, 154), (120, 139)):
        assert second in rows[first]["overlap_ids"]
        assert first in rows[second]["overlap_ids"]


def test_generated_artifacts_match_registry(registry):
    csv_text, markdown = generate(registry, ROOT)
    assert (ROOT / "docs/m12/WHITEPACT_M12_175_FEATURE_LEDGER.csv").read_text() == csv_text
    assert (ROOT / "docs/m12/WHITEPACT_M12_FEATURE_ACCEPTANCE_MATRIX.md").read_text() == markdown


def test_source_symlink_cannot_escape_root(registry, tmp_path):
    (tmp_path / "outside-link").symlink_to(ROOT / "pyproject.toml")
    registry["original_inventory_source"] = "outside-link"
    with pytest.raises(RegistryError, match="escapes repository"):
        validate(registry, tmp_path)


def test_qualification_artifact_cannot_be_arbitrary_source_file(registry):
    registry["qualification_target_head"] = "a" * 40
    registry["qualification_target_tree"] = "b" * 40
    row = registry["entries"][0]
    row["status"] = "VERIFIED"
    row["latest_qualification_commit"] = "a" * 40
    row["test_evidence"]["kind"] = "FRESH_EXECUTED"
    row["qualification"] = {
        "kind": "FRESH_EXECUTED",
        "head": "a" * 40,
        "tree": "b" * 40,
        "passed": 1,
        "failed": 0,
        "skipped": 0,
        "executed_at": "2026-10-15T12:00:00+00:00",
        "command": "pytest",
        "scope": "source",
        "artifact": "pyproject.toml",
    }
    with pytest.raises(RegistryError, match="Machine-readable executed evidence"):
        validate(registry, ROOT)


def test_matching_head_never_hides_a_different_qualification_tree(registry):
    registry["qualification_target_head"] = "a" * 40
    registry["qualification_target_tree"] = "c" * 40
    row = registry["entries"][0]
    row["status"] = "VERIFIED"
    row["latest_qualification_commit"] = "a" * 40
    row["test_evidence"]["kind"] = "FRESH_EXECUTED"
    row["qualification"] = {"kind": "FRESH_EXECUTED", "head": "a" * 40, "tree": "b" * 40}
    with pytest.raises(RegistryError, match="qualification tree"):
        validate(registry, ROOT)


def test_merkle_is_not_invented_from_hash_linked_witnesses(registry):
    row = validate(registry, ROOT)[86]
    assert row["title"] == "Merkle evidence structures"
    assert row["status"] == "NOT FOUND"
    assert row["source_paths"] == row["symbol_mappings"] == row["test_paths"] == []
    assert row["latest_qualification_commit"] is None


@pytest.mark.parametrize(
    "field",
    [
        "implemented_behavior",
        "user_accessibility",
        "latest_qualification_commit",
        "test_evidence",
        "security_dependencies",
        "deployment_requirements",
        "symbol_mappings",
    ],
)
def test_complete_user_required_evidence_fields_are_mandatory(registry, field):
    del registry["entries"][0][field]
    with pytest.raises(RegistryError, match="missing required fields"):
        validate(registry, ROOT)


def test_csv_preserves_all_source_and_evidence_fields(registry):
    csv_text, _ = generate(registry, ROOT)
    rows = list(csv.DictReader(io.StringIO(csv_text)))
    assert len(rows) == 175
    assert set(rows[0]) == set(registry["entries"][0])
    assert json.loads(rows[0]["source_paths"]) == registry["entries"][0]["source_paths"]
    assert json.loads(rows[0]["test_evidence"])["kind"] != "FRESH_EXECUTED"


@pytest.mark.parametrize(
    "value", ["=1+1", "+1+1", "-1+1", "@SUM(A1)", "\t=1+1", "\r=1+1", "\x00=1+1", " \n=1+1"]
)
@pytest.mark.parametrize("field", ["owner", "limitations"])
def test_csv_neutralizes_spreadsheet_formulas_without_changing_original(registry, value, field):
    original_title = registry["entries"][0]["title"]
    registry["entries"][0][field] = value
    csv_text, _ = generate(registry, ROOT)
    row = next(csv.DictReader(io.StringIO(csv_text)))
    assert row[field] == "'" + value
    assert registry["entries"][0][field] == value
    assert row["title"] == registry["entries"][0]["title"] == original_title


def test_root_provisioning_is_blocked_not_absent(registry):
    rows = {row["id"]: row for row in validate(registry, ROOT)}
    for identifier in (83, 130):
        assert rows[identifier]["status"] == "BLOCKED"
        assert "src/responsibleai/trust_fabric/bootstrap.py" in rows[identifier]["source_paths"]


def test_generator_writes_only_fixed_artifacts(monkeypatch, tmp_path):
    # Pure presentation/write seam; registry validation is tested separately.
    monkeypatch.setattr(
        "scripts.qualification.feature_registry.generate", lambda *_args: ("csv\n", "md\n")
    )
    sentinel = tmp_path / "unrelated.txt"
    sentinel.write_text("preserve")
    write_generated({}, tmp_path)
    assert (tmp_path / "docs/m12/WHITEPACT_M12_175_FEATURE_LEDGER.csv").read_text() == "csv\n"
    assert (tmp_path / "docs/m12/WHITEPACT_M12_FEATURE_ACCEPTANCE_MATRIX.md").read_text() == "md\n"
    assert sentinel.read_text() == "preserve"


@pytest.mark.parametrize("kind", ["parent", "output"])
def test_generator_rejects_symlinks_before_any_write(monkeypatch, tmp_path, kind):
    monkeypatch.setattr(
        "scripts.qualification.feature_registry.generate", lambda *_args: ("csv\n", "md\n")
    )
    outside = tmp_path / "outside"
    outside.mkdir()
    victim = outside / "victim.txt"
    victim.write_text("preserve")
    root = tmp_path / "root"
    root.mkdir()
    if kind == "parent":
        (root / "docs").symlink_to(outside, target_is_directory=True)
    else:
        directory = root / "docs/m12"
        directory.mkdir(parents=True)
        (directory / "WHITEPACT_M12_175_FEATURE_LEDGER.csv").symlink_to(victim)
    with pytest.raises(RegistryError, match="unsafe"):
        write_generated({}, root)
    assert victim.read_text() == "preserve"
    assert not (root / "docs/m12/WHITEPACT_M12_FEATURE_ACCEPTANCE_MATRIX.md").exists()


def test_cli_write_and_check_are_mutually_exclusive(monkeypatch):
    from scripts.qualification.feature_registry import main

    monkeypatch.setattr(
        "sys.argv", ["feature_registry", "unused.json", "--write-generated", "--check-generated"]
    )
    with pytest.raises(SystemExit) as error:
        main()
    assert error.value.code == 2
