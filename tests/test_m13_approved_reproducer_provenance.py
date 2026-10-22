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
