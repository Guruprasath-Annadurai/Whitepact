# Copyright (c) 2026 Guruprasath Annadurai
# SPDX-License-Identifier: MIT
"""Authorized revisions require both immutable originals and unchanged semantics."""

import subprocess
from pathlib import Path

import pytest
from scripts.engineering import m13p4_security_acceptance as guard

ROOT = Path(__file__).resolve().parents[1]


def original(name):
    return subprocess.check_output(
        ["git", "show", f"{guard.SECURITY_REFERENCE}:{guard.REPRODUCER_DIRECTORY}/{name}"],
        cwd=ROOT,
        text=True,
    )


@pytest.mark.parametrize("name", guard.APPROVED_BLOBS)
def test_approved_source_has_only_authorized_changes(name):
    guard.verify_authorized_revision(
        name, original(name), (ROOT / guard.REPRODUCER_DIRECTORY / name).read_text()
    )


@pytest.mark.parametrize("tamper", ["assert False", "raise RuntimeError('tampered')", "import os"])
def test_revised_hash_cannot_waive_unauthorized_content(monkeypatch, tamper):
    name = "test_m13p_postgres_schema.py"
    source = (ROOT / guard.REPRODUCER_DIRECTORY / name).read_text() + "\n" + tamper + "\n"
    with pytest.raises(guard.PreflightError, match="Unauthorized"):
        guard.verify_authorized_revision(name, original(name), source)


def test_missing_original_or_changed_candidate_is_refused(monkeypatch):
    actual = {
        f"{guard.REPRODUCER_DIRECTORY}/{name}": blob for name, blob in guard.ORIGINAL_BLOBS.items()
    }
    monkeypatch.setattr(guard, "git_read", lambda *args: "missing")
    with pytest.raises(guard.PreflightError, match="historical"):
        guard.verify_reproducer_manifest(ROOT, actual)


def test_unknown_blob_is_refused_even_when_original_is_available(monkeypatch):
    actual = {
        f"{guard.REPRODUCER_DIRECTORY}/{name}": blob for name, blob in guard.ORIGINAL_BLOBS.items()
    }
    name = "test_m13p_postgres_schema.py"
    actual[f"{guard.REPRODUCER_DIRECTORY}/{name}"] = "a" * 40
    monkeypatch.setattr(
        guard, "git_read", lambda repo, command, ref: guard.ORIGINAL_BLOBS[Path(ref).name]
    )
    with pytest.raises(guard.PreflightError, match="pinned"):
        guard.verify_reproducer_manifest(ROOT, actual)


def runtime_original():
    return subprocess.check_output(
        ["git", "show", f"{guard.RUNTIME_REFERENCE}:{guard.RUNTIME_PATH}"], cwd=ROOT, text=True
    )


def test_cancellation_fixture_contains_only_approved_setup():
    guard.verify_cancellation_revision(runtime_original(), (ROOT / guard.RUNTIME_PATH).read_text())


@pytest.mark.parametrize(
    "before,after",
    [("== 2", "== 1"), ("started.wait, 3", "started.wait, 30"), ('"c" * 64', '"z" * 64')],
)
def test_cancellation_counts_bounds_and_acknowledgement_cannot_be_changed(before, after):
    source = (ROOT / guard.RUNTIME_PATH).read_text()
    modified = source.replace(before, after)
    assert modified != source
    with pytest.raises(guard.PreflightError, match="Unauthorized cancellation"):
        guard.verify_cancellation_revision(runtime_original(), modified)


def test_missing_original_cancellation_evidence_is_refused(monkeypatch):
    monkeypatch.setattr(guard, "git_read", lambda *args: "missing")
    with pytest.raises(guard.PreflightError, match="Original cancellation"):
        guard.verify_runtime_fixture(ROOT, "a" * 40)
